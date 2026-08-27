"""Authenticated per-user AI configuration endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.ai_config import AIConfigTestRequest, AIConfigUpdate
from app.schemas.response import bad_request, error, success
from app.services.ai_config_service import AIConfigService
from app.utils.auth import CurrentUser, get_current_user
from app.utils.datetime import utcnow_naive


router = APIRouter(prefix="/ai-config", tags=["AI 服务"])


@router.get("", summary="获取当前 AI 服务配置")
def get_ai_config(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return this account's redacted configuration for every authenticated role."""

    return success(AIConfigService.public_config(db, current_user.user_id), "查询 AI 服务配置成功")


@router.post("/dismiss-onboarding", summary="跳过当前账户的 AI 首次配置引导")
def dismiss_ai_config_onboarding(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """仅记录当前登录账户，避免客户端指定 user_id 造成越权。"""
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if user is None:
        return bad_request("当前用户不存在")
    user.ai_config_onboarding_dismissed_at = utcnow_naive()
    db.commit()
    return success({"onboardingDismissed": True}, "已跳过 AI 首次配置")


@router.get("/generation-params", summary="获取指定模型的高级生成参数")
def get_generation_params(
    provider: str,
    model: str = "",
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return static controls for a provider/model without contacting it."""

    try:
        data = AIConfigService.public_generation_params_for_model(
            db,
            current_user.user_id,
            provider,
            model,
        )
        return success(data, "查询模型高级生成参数成功")
    except ValueError as exc:
        return bad_request(str(exc))


@router.put("", summary="保存当前 AI 服务配置")
def update_ai_config(
    payload: AIConfigUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save this account's one active provider/model; blank secrets preserve values."""

    try:
        record = AIConfigService.save(
            db,
            payload,
            current_user.user_id,
            require_generation_test=True,
        )
        db.commit()
        db.refresh(record)
        return success(AIConfigService.public_config(db, current_user.user_id), "AI 服务配置已保存")
    except ValueError as exc:
        db.rollback()
        return bad_request(str(exc))
    except SQLAlchemyError:
        db.rollback()
        return error(message="保存 AI 服务配置失败，请稍后重试")


@router.post("/test", summary="测试 AI 服务连接并获取模型")
def test_ai_config(
    payload: AIConfigTestRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Test either the saved config or the unsaved form values.

    A successful test containing form values saves the verified credentials
    and one selected model for the current account. Failed tests never replace
    the active configuration.
    """

    try:
        record = AIConfigService.get_record(db, current_user.user_id)
        provider, runtime, _ = AIConfigService.prepare_runtime_config(payload, record)
        result = AIConfigService.test_connection(runtime)

        configuration_fields = {
            "provider", "protocol", "base_url", "api_key", "selected_model",
            "proxy_url", "proxy_password", "extra_config", "clear_api_key",
            "clear_proxy_password", "generation_params",
        }
        has_form_values = bool(payload.model_fields_set & configuration_fields)
        response_data = {
            **result.to_public_dict(),
            **AIConfigService.public_generation_state(runtime),
        }
        if result.success and has_form_values:
            requested_model = (payload.selected_model or "").strip()
            saved_model = ""
            if record and (payload.provider is None or payload.provider == record.provider):
                saved_model = (record.selected_model or "").strip()
            selected_model = requested_model or saved_model
            if not selected_model and result.models:
                selected_model = (
                    provider.default_model
                    if provider.default_model in result.models
                    else result.models[0]
                )
            if not selected_model:
                selected_model = runtime.model.strip()
            if selected_model:
                values = payload.model_dump()
                values["selected_model"] = selected_model
                values["available_models"] = result.models
                saved_payload = AIConfigUpdate.model_validate(values)
                AIConfigService.save(db, saved_payload, current_user.user_id)
                AIConfigService.record_test_result(
                    db,
                    current_user.user_id,
                    result,
                    selected_model=selected_model,
                )
                db.commit()
                response_data["selectedModel"] = selected_model
                response_data["message"] = f"{result.message}，配置已保存"
                saved_runtime = AIConfigService.runtime_from_record(
                    AIConfigService.get_record(db, current_user.user_id)
                )
                if saved_runtime is not None:
                    response_data.update(AIConfigService.public_generation_state(saved_runtime))
        elif record and not has_form_values:
            AIConfigService.record_test_result(db, current_user.user_id, result)
            db.commit()
        return success(response_data, response_data.get("message", result.message))
    except ValueError as exc:
        db.rollback()
        return bad_request(str(exc))
    except SQLAlchemyError:
        db.rollback()
        return error(message="保存连接测试结果失败，请稍后重试")


@router.delete("", summary="清除 AI 服务配置")
def delete_ai_config(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove this account's config and return it to the legacy .env fallback."""

    try:
        deleted = AIConfigService.delete(db, current_user.user_id)
        db.commit()
        return success(
            {"deleted": deleted, "source": "environment"},
            "AI 服务配置已清除，已回退到环境变量配置",
        )
    except SQLAlchemyError:
        db.rollback()
        return error(message="清除 AI 服务配置失败，请稍后重试")
