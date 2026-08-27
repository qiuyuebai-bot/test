"""Per-user AI configuration storage, encryption, and connectivity testing.

Every account owns one active provider/model configuration.  ``backend/.env``
remains a compatible fallback when that account has not saved a configuration.
"""

from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import math
import re
import socket
import time
from contextlib import contextmanager
from dataclasses import dataclass, replace
from typing import Any, Dict, Iterator, List, Optional
from urllib.parse import urlparse

import httpx
from cryptography.fernet import Fernet, InvalidToken
from loguru import logger
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.ai_config import UserAIConfig
from app.schemas.ai_config import AIConfigUpdate
from app.services.ai_providers import (
    PROTOCOL_ANTHROPIC,
    PROTOCOL_AZURE_OPENAI,
    PROTOCOL_GEMINI,
    PROTOCOL_OLLAMA,
    PROTOCOL_VERTEX_AI,
    ProviderDefinition,
    get_provider,
    infer_provider_from_base_url,
    is_protocol_implemented,
    provider_options,
)
from app.services.ai_protocol_client import AIProtocolClient, RuntimeProtocolError
from app.utils.datetime import utcnow_naive
from app.utils.llm_runtime import LLMRuntimeConfig, get_runtime_user_id, use_runtime_config, use_runtime_user_id


_ALLOWED_EXTRA_CONFIG_KEYS = {"apiVersion", "deploymentName", "projectId", "location", "region"}
_GENERATION_PROFILES_KEY = "_generationParamsProfiles"
_GENERATION_KEYS = ("temperature", "top_p", "frequency_penalty", "presence_penalty")
_GENERATION_PUBLIC_KEYS = {
    "temperature": "temperature",
    "top_p": "top_p",
    "frequency_penalty": "frequency_penalty",
    "presence_penalty": "presence_penalty",
}
_SAFE_CLOUD_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9-]{2,61}[a-z0-9]$")


@dataclass(frozen=True)
class ConnectionTestResult:
    success: bool
    models: List[str]
    latency_ms: Optional[int]
    message: str
    error_code: Optional[str] = None

    def to_public_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "models": self.models,
            "latencyMs": self.latency_ms,
            "message": self.message,
            "errorCode": self.error_code,
        }


class AIConfigService:
    """Own the one active provider/model configuration for each account."""

    @staticmethod
    def _fernet() -> Fernet:
        """Create a stable encryption cipher without exposing its source.

        A separately configured key is preferred.  Falling back to a key
        derived from the existing persistent ``SECRET_KEY`` keeps upgrades
        usable while avoiding plaintext credentials in SQLite/PostgreSQL.
        """

        configured_key = (settings.AI_CONFIG_ENCRYPTION_KEY or "").strip()
        if configured_key:
            try:
                return Fernet(configured_key.encode("utf-8"))
            except (ValueError, TypeError) as exc:
                raise RuntimeError("AI_CONFIG_ENCRYPTION_KEY 不是有效的 Fernet 密钥") from exc

        material = f"{settings.SECRET_KEY}:ai-config-encryption:v1".encode("utf-8")
        derived_key = base64.urlsafe_b64encode(hashlib.sha256(material).digest())
        return Fernet(derived_key)

    @classmethod
    def encrypt_secret(cls, value: str) -> str:
        return cls._fernet().encrypt(value.encode("utf-8")).decode("utf-8")

    @classmethod
    def decrypt_secret(cls, value: Optional[str]) -> str:
        if not value:
            return ""
        try:
            return cls._fernet().decrypt(value.encode("utf-8")).decode("utf-8")
        except (InvalidToken, ValueError, TypeError):
            # Do not expose the encrypted payload or cipher details to clients.
            logger.error("AI 配置中的加密凭据无法解密，请重新保存 AI 配置")
            return ""

    @staticmethod
    def mask_secret(value: str) -> Optional[str]:
        value = (value or "").strip()
        if not value:
            return None
        if len(value) <= 8:
            return "*" * len(value)
        return f"{value[:3]}...{value[-4:]}"

    @classmethod
    def get_record(
        cls, db: Session, user_id: int, *, for_update: bool = False
    ) -> Optional[UserAIConfig]:
        query = db.query(UserAIConfig).filter(UserAIConfig.user_id == user_id)
        if for_update:
            query = query.with_for_update()
        return query.first()

    @classmethod
    def get_active_runtime_config(cls, user_id: Optional[int] = None) -> Optional[LLMRuntimeConfig]:
        """Load the current request/task owner's config, returning ``None`` on fallback.

        No configuration is selected when there is no owner context.  This is
        deliberate: a worker must bind an explicit user ID and can never pick
        another account's key merely because it is the most recently updated.
        """

        user_id = user_id if user_id is not None else get_runtime_user_id()
        if user_id is None:
            return None

        try:
            from app.database import SessionLocal

            db = SessionLocal()
            try:
                record = cls.get_record(db, user_id)
                return cls.runtime_from_record(record) if record and record.is_active else None
            finally:
                db.close()
        except (OperationalError, SQLAlchemyError):
            # A migration may not have run yet.  Preserve historical .env
            # behavior instead of blocking startup/login.
            return None
        except Exception:
            logger.warning("读取用户 AI 配置失败，回退至环境变量配置")
            return None

    @classmethod
    def runtime_from_record(cls, record: Optional[UserAIConfig]) -> Optional[LLMRuntimeConfig]:
        if record is None:
            return None
        try:
            provider = get_provider(record.provider)
        except ValueError:
            logger.error("AI 配置包含未知提供商，已忽略并回退环境变量")
            return None
        model = record.selected_model or provider.default_model
        runtime = LLMRuntimeConfig(
            provider=provider.id,
            protocol=record.protocol or provider.protocol,
            owner_user_id=record.user_id,
            base_url=record.base_url or provider.default_base_url,
            api_key=cls.decrypt_secret(record.api_key_encrypted),
            model=model,
            proxy_url=record.proxy_url or "",
            proxy_password=cls.decrypt_secret(record.proxy_password_encrypted),
            requires_api_key=provider.requires_api_key,
            temperature=settings.OPENAI_TEMPERATURE,
            max_tokens=settings.OPENAI_MAX_TOKENS,
            thinking_enabled=settings.OPENAI_THINKING_ENABLED,
            thinking_param=settings.OPENAI_THINKING_PARAM,
            extra_config=dict(record.extra_config or {}),
        )
        has_generation_profile = cls._has_generation_profile(record, runtime)
        generation_params = cls._generation_params_for_record(record, runtime)
        effective_generation_params = generation_params or {}
        provider_defaults = cls._default_generation_params_for_runtime(runtime)
        return replace(
            runtime,
            # Keep the historical process-level temperature as the effective
            # baseline while the persisted mapping remains sparse.
            temperature=effective_generation_params.get(
                "temperature",
                provider_defaults.get("temperature", cls._default_generation_params()["temperature"]),
            ),
            # ``None`` means no account-level profile exists.  The protocol
            # client uses that distinction to preserve legacy task-specific
            # temperatures.  An explicit empty mapping means the user
            # deliberately removed every override and must remain empty.
            generation_params=generation_params if has_generation_profile else None,
        )

    @classmethod
    def effective_runtime_config(
        cls, db: Optional[Session] = None, user_id: Optional[int] = None
    ) -> LLMRuntimeConfig:
        user_id = user_id if user_id is not None else get_runtime_user_id()
        if db is not None and user_id is not None:
            record = cls.get_record(db, user_id)
            runtime = cls.runtime_from_record(record) if record and record.is_active else None
        else:
            runtime = cls.get_active_runtime_config(user_id)
        return runtime or LLMRuntimeConfig.from_settings()

    @classmethod
    @contextmanager
    def use_user_runtime_config(cls, user_id: int) -> Iterator[LLMRuntimeConfig]:
        """Bind an owner's configuration around detached worker/task code.

        Queue payloads should contain only ``user_id``.  The encrypted secret
        is read here at execution time and stays inside this process context.
        """

        with use_runtime_user_id(user_id):
            runtime = cls.get_active_runtime_config(user_id) or LLMRuntimeConfig.from_settings()
            with use_runtime_config(runtime):
                yield runtime

    @classmethod
    def public_config(
        cls, db: Session, user_id: int, *, include_provider_options: bool = True
    ) -> Dict[str, Any]:
        record = cls.get_record(db, user_id)
        from app.models.user import User

        user = db.query(User).filter(User.id == user_id).first()
        onboarding_dismissed = bool(
            user and user.ai_config_onboarding_dismissed_at is not None
        )
        if record and record.is_active:
            runtime = cls.runtime_from_record(record)
            assert runtime is not None
            api_key = runtime.api_key
            proxy_password = runtime.proxy_password
            has_generation_profile = runtime.generation_params is not None
            generation_params = cls._generation_params_for_runtime(runtime)
            if not has_generation_profile:
                generation_params = cls._default_generation_params_for_runtime(runtime)
            data: Dict[str, Any] = {
                "configured": True,
                "source": "database",
                "provider": runtime.provider,
                "protocol": runtime.protocol,
                "baseUrl": runtime.normalized_base_url,
                "selectedModel": runtime.model or None,
                "availableModels": cls._normalize_models(record.available_models),
                "apiKeyConfigured": bool(api_key),
                # A Vertex credential is a complete service-account JSON
                # document.  Do not return even a masked fragment of it.
                "apiKeyHint": None if runtime.provider == "vertex_ai" else cls.mask_secret(api_key),
                "proxyUrl": record.proxy_url or "",
                "proxyPasswordConfigured": bool(proxy_password),
                "extraConfig": cls._public_extra_config(record.extra_config),
                "generationParams": cls._public_generation_params(generation_params),
                "generationParamsMeta": AIProtocolClient.generation_params_meta(runtime),
                "generationParamsConfigured": has_generation_profile,
                "lastTestStatus": record.last_test_status or "never",
                "lastTestMessage": record.last_test_message,
                "lastTestedAt": record.last_tested_at.isoformat() if record.last_tested_at else None,
                "updatedAt": record.updated_at.isoformat() if record.updated_at else None,
                "onboardingDismissed": onboarding_dismissed,
            }
        else:
            runtime = LLMRuntimeConfig.from_settings()
            inferred = infer_provider_from_base_url(runtime.base_url)
            data = {
                "configured": False,
                "source": "environment",
                "provider": inferred.id,
                "protocol": inferred.protocol,
                "baseUrl": runtime.normalized_base_url,
                "selectedModel": runtime.model or None,
                "availableModels": [],
                "apiKeyConfigured": bool(runtime.api_key.strip()),
                # The fallback belongs to the server process, not to this
                # account.  Do not reveal even a partial environment secret.
                "apiKeyHint": None,
                "proxyUrl": "",
                "proxyPasswordConfigured": False,
                "extraConfig": {},
                "generationParams": cls._public_generation_params(
                    cls._default_generation_params_for_runtime(runtime)
                ),
                "generationParamsMeta": AIProtocolClient.generation_params_meta(runtime),
                "generationParamsConfigured": False,
                "lastTestStatus": "never",
                "lastTestMessage": None,
                "lastTestedAt": None,
                "updatedAt": None,
                "onboardingDismissed": onboarding_dismissed,
            }
        if include_provider_options:
            data["providerOptions"] = provider_options()
        return data

    @staticmethod
    def _normalize_models(models: Any) -> List[str]:
        if not isinstance(models, list):
            return []
        result: List[str] = []
        for model in models:
            value = str(model or "").strip()
            if value and value not in result:
                result.append(value)
        return result[:500]

    @staticmethod
    def _default_generation_params() -> Dict[str, float]:
        """Return canonical defaults without coupling storage to provider code."""

        return AIProtocolClient.default_generation_params()

    @classmethod
    def _default_generation_params_for_runtime(
        cls, runtime: LLMRuntimeConfig
    ) -> Dict[str, float]:
        """Return the provider/model's initial controls that are supported."""

        specs = AIProtocolClient.generation_param_specs(runtime)
        defaults = AIProtocolClient.generation_defaults(runtime)
        return {key: defaults[key] for key in specs if key in defaults}

    @staticmethod
    def _public_extra_config(value: Any) -> Dict[str, Any]:
        """Hide the internal per-provider/model parameter profiles."""

        if not isinstance(value, dict):
            return {}
        return {key: item for key, item in value.items() if key != _GENERATION_PROFILES_KEY}

    @classmethod
    def _profile_key(cls, provider: str, model: str) -> str:
        # JSON object keys may contain any model punctuation. A compact JSON
        # tuple avoids collisions without storing a NUL character, which some
        # PostgreSQL JSON implementations reject even when it is escaped.
        return json.dumps([provider, model], ensure_ascii=True, separators=(",", ":"))

    @staticmethod
    def _legacy_profile_key(provider: str, model: str) -> str:
        """Read the pre-release separator format during an in-place upgrade."""

        return f"{provider}\x00{model}"

    @classmethod
    def _profile_values(
        cls, profiles: Dict[str, Dict[str, float]], provider: str, model: str
    ) -> Optional[Dict[str, float]]:
        profile_key = cls._profile_key(provider, model)
        if profile_key in profiles:
            return profiles[profile_key]
        legacy_profile_key = cls._legacy_profile_key(provider, model)
        if legacy_profile_key in profiles:
            return profiles[legacy_profile_key]
        return None

    @classmethod
    def _generation_profiles(cls, value: Any) -> Dict[str, Dict[str, float]]:
        if not isinstance(value, dict):
            return {}
        raw = value.get(_GENERATION_PROFILES_KEY)
        if not isinstance(raw, dict):
            return {}
        profiles: Dict[str, Dict[str, float]] = {}
        for profile_key, profile in raw.items():
            if not isinstance(profile_key, str) or not isinstance(profile, dict):
                continue
            normalized: Dict[str, float] = {}
            for key in _GENERATION_KEYS:
                item = profile.get(key)
                if (
                    isinstance(item, (int, float))
                    and not isinstance(item, bool)
                    and math.isfinite(float(item))
                ):
                    normalized[key] = float(item)
            # Preserve an explicit empty mapping. It is different from an
            # absent profile: the former records that the user removed all
            # controls for this provider/model.
            if normalized or profile == {}:
                profiles[profile_key] = normalized
        return profiles

    @classmethod
    def _has_generation_profile(
        cls, record: UserAIConfig, runtime: LLMRuntimeConfig
    ) -> bool:
        profiles = cls._generation_profiles(record.extra_config)
        return cls._profile_values(profiles, runtime.provider, runtime.model) is not None

    @classmethod
    def _generation_params_for_record(
        cls, record: UserAIConfig, runtime: LLMRuntimeConfig
    ) -> Dict[str, float]:
        profiles = cls._generation_profiles(record.extra_config)
        stored = cls._profile_values(profiles, runtime.provider, runtime.model)
        if stored is None:
            return {}
        # Profiles are written through the validator, but filter old/corrupt
        # rows before they can reach a protocol adapter.
        specs = AIProtocolClient.generation_param_specs(runtime)
        return {
            key: float(value)
            for key, value in stored.items()
            if key in specs
            and math.isfinite(float(value))
            and specs[key]["min"] <= float(value) <= specs[key]["max"]
        }

    @classmethod
    def _generation_params_for_runtime(cls, runtime: LLMRuntimeConfig) -> Dict[str, float]:
        params = dict(runtime.generation_params or {})
        return {
            key: round(float(value), 6)
            for key, value in params.items()
            if key in _GENERATION_KEYS
            and isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
        }

    @classmethod
    def _public_generation_params(cls, params: Dict[str, float]) -> Dict[str, float]:
        return {
            _GENERATION_PUBLIC_KEYS[key]: round(float(value), 6)
            for key, value in params.items()
            if key in _GENERATION_PUBLIC_KEYS
            and isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
        }

    @classmethod
    def public_generation_state(cls, runtime: LLMRuntimeConfig) -> Dict[str, Any]:
        """Return the non-secret sampling state used by GET and connection tests."""
        configured = runtime.generation_params is not None
        params = cls._generation_params_for_runtime(runtime)
        if not configured:
            params = cls._default_generation_params_for_runtime(runtime)
        return {
            "generationParams": cls._public_generation_params(params),
            "generationParamsMeta": AIProtocolClient.generation_params_meta(runtime),
            "generationParamsConfigured": configured,
        }

    @classmethod
    def public_generation_params_for_model(
        cls,
        db: Session,
        user_id: int,
        provider_id: str,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return static generation metadata for one provider/model pair.

        This endpoint is intentionally independent of the active runtime:
        switching a form to an untested model must not require credentials or
        an upstream request just to render the advanced controls.  Only the
        requested account's encrypted-config row is consulted for its sparse
        profile; credentials are never decrypted here.
        """

        normalized_provider_id = (provider_id or "").strip()
        if not normalized_provider_id:
            raise ValueError("请提供 AI 服务来源")
        provider = get_provider(normalized_provider_id)
        normalized_model = (model or "").strip()
        if len(normalized_model) > 255:
            raise ValueError("模型名称长度不能超过 255")
        if not normalized_model:
            normalized_model = provider.default_model

        runtime = LLMRuntimeConfig(
            provider=provider.id,
            protocol=provider.protocol,
            model=normalized_model,
            requires_api_key=provider.requires_api_key,
            thinking_enabled=settings.OPENAI_THINKING_ENABLED,
            thinking_param=settings.OPENAI_THINKING_PARAM,
        )
        record = cls.get_record(db, user_id)
        configured = False
        params: Dict[str, float] = {}
        if record is not None:
            configured = cls._has_generation_profile(record, runtime)
            if configured:
                params = cls._generation_params_for_record(record, runtime)
        if not configured:
            params = cls._default_generation_params_for_runtime(runtime)

        return {
            "provider": provider.id,
            "protocol": provider.protocol,
            "model": normalized_model or None,
            "generationParams": cls._public_generation_params(params),
            "generationParamsMeta": AIProtocolClient.generation_params_meta(runtime),
            "generationParamsConfigured": configured,
        }

    @classmethod
    def _generation_params_for_payload(
        cls,
        value: Optional[Dict[str, Any]],
        *,
        provider: ProviderDefinition,
        model: str,
        existing: Optional[UserAIConfig],
        provider_changed: bool,
        model_changed: bool,
    ) -> Optional[Dict[str, float]]:
        """Validate and resolve the current provider/model sampling values."""

        runtime_for_specs = LLMRuntimeConfig(
            provider=provider.id,
            protocol=provider.protocol,
            model=model,
            thinking_enabled=settings.OPENAI_THINKING_ENABLED,
            thinking_param=settings.OPENAI_THINKING_PARAM,
        )
        defaults = AIProtocolClient.generation_defaults(runtime_for_specs)
        if value is None and existing:
            profiles = cls._generation_profiles(existing.extra_config)
            stored = cls._profile_values(profiles, provider.id, model)
            if stored is None:
                return None
            specs = AIProtocolClient.generation_param_specs(runtime_for_specs)
            return {
                key: float(item)
                for key, item in stored.items()
                if key in specs
                and math.isfinite(float(item))
                and specs[key]["min"] <= float(item) <= specs[key]["max"]
            }
        if value is None:
            return None

        aliases = {
            "temperature": "temperature",
            "top_p": "top_p",
            "topP": "top_p",
            "frequency_penalty": "frequency_penalty",
            "frequencyPenalty": "frequency_penalty",
            "presence_penalty": "presence_penalty",
            "presencePenalty": "presence_penalty",
        }
        normalized: Dict[str, float] = {}
        for raw_key, raw_value in value.items():
            key = aliases.get(raw_key)
            if key is None:
                raise ValueError(f"不支持的生成参数: {raw_key}")
            if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
                raise ValueError(f"生成参数 {raw_key} 必须是数字")
            numeric = float(raw_value)
            if numeric != numeric or numeric in (float("inf"), float("-inf")):
                raise ValueError(f"生成参数 {raw_key} 必须是有限数字")
            normalized[key] = numeric

        # Validate against the provider/model limits before any network call.
        specs = AIProtocolClient.generation_param_specs(runtime_for_specs)
        for key, numeric in list(normalized.items()):
            spec = specs.get(key)
            if spec is None:
                # Unsupported controls are harmless only at the provider's
                # documented initial default. Drop those defaults from the
                # sparse profile so a provider that rejects sampling never
                # receives them.
                if numeric == defaults[key]:
                    normalized.pop(key, None)
                    continue
                label = AIProtocolClient._GENERATION_LABELS.get(key, key)
                raise ValueError(f"{provider.label} 当前模型不支持修改生成参数 {label}")
            if numeric < spec["min"] or numeric > spec["max"]:
                label = AIProtocolClient._GENERATION_LABELS.get(key, key)
                raise ValueError(
                    f"生成参数 {label} 超出 {provider.label} 当前模型允许范围 "
                    f"[{spec['min']}, {spec['max']}]"
                )
        if provider.protocol == PROTOCOL_ANTHROPIC:
            if (
                normalized.get("temperature", defaults["temperature"]) != defaults["temperature"]
                and normalized.get("top_p", defaults["top_p"]) != defaults["top_p"]
            ):
                raise ValueError("Claude 官方的温度和 Top P 不能同时调整，请只修改其中一个")
        if (
            provider.id in {"minimax", "minimax_global"}
            and "temperature" in normalized
            and normalized["temperature"] <= 0
        ):
            raise ValueError("MiniMax 温度必须大于 0 且不超过 1")
        return normalized

    @classmethod
    def _validate_extra_config(cls, value: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if value is None:
            return {}
        result: Dict[str, Any] = {}
        for key, item in value.items():
            if key == _GENERATION_PROFILES_KEY:
                # This key is written only by this service; the public API
                # must use `generationParams` so callers cannot inject a
                # profile belonging to another model/provider.
                raise ValueError("生成参数必须通过 generationParams 提交")
            if key not in _ALLOWED_EXTRA_CONFIG_KEYS:
                raise ValueError(f"不支持的高级配置字段: {key}")
            if not isinstance(item, (str, int, float, bool)):
                raise ValueError(f"高级配置字段 {key} 的值无效")
            result[key] = str(item).strip()[:255]
        return result

    @staticmethod
    def _require_safe_cloud_identifier(value: Any, label: str) -> str:
        normalized = str(value or "").strip().lower()
        if not _SAFE_CLOUD_IDENTIFIER.fullmatch(normalized):
            raise ValueError(f"请填写有效的 {label}")
        return normalized

    @classmethod
    def _normalize_azure_endpoint(cls, value: str) -> str:
        endpoint = (value or "").strip().rstrip("/")
        if not endpoint:
            return ""
        try:
            parsed = urlparse(endpoint)
            port = parsed.port
        except ValueError as exc:
            raise ValueError("Azure OpenAI 资源 Endpoint 格式不正确") from exc
        host = (parsed.hostname or "").lower()
        path = parsed.path.rstrip("/")
        if (
            parsed.scheme != "https"
            or not host.endswith(".openai.azure.com")
            or port is not None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.params
            or parsed.query
            or parsed.fragment
            or path not in {"", "/openai/v1"}
        ):
            raise ValueError(
                "Azure OpenAI 资源 Endpoint 仅支持 https://<资源名>.openai.azure.com（可省略 /openai/v1）"
            )
        return f"https://{host}/openai/v1"

    @classmethod
    def _vertex_base_url(cls, extra_config: Dict[str, Any]) -> str:
        project_id = cls._require_safe_cloud_identifier(extra_config.get("projectId"), "Google Cloud 项目 ID")
        location = cls._require_safe_cloud_identifier(extra_config.get("location"), "Google Cloud 区域")
        if location == "global":
            host = "aiplatform.googleapis.com"
        else:
            host = f"{location}-aiplatform.googleapis.com"
        return (
            f"https://{host}/v1/projects/{project_id}/locations/{location}/endpoints/openapi"
        )

    @classmethod
    def _bedrock_base_url(cls, extra_config: Dict[str, Any]) -> str:
        region = cls._require_safe_cloud_identifier(extra_config.get("region"), "AWS 区域")
        return f"https://bedrock-mantle.{region}.api.aws/v1"

    @staticmethod
    def _validate_vertex_service_account(value: str) -> None:
        """Reject malformed credentials before they can be persisted.

        The JSON itself stays in the encrypted credential column and is never
        copied into ``extra_config`` or a response body.
        """

        try:
            service_account = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError("Google Cloud 服务账号 JSON 格式不正确") from exc
        if not isinstance(service_account, dict) or service_account.get("type") != "service_account":
            raise ValueError("Google Cloud 服务账号 JSON 格式不正确")
        required = ("client_email", "private_key", "token_uri")
        if any(not isinstance(service_account.get(key), str) or not service_account[key].strip() for key in required):
            raise ValueError("Google Cloud 服务账号 JSON 格式不正确")
        if service_account.get("token_uri") != AIProtocolClient.VERTEX_TOKEN_URI:
            raise ValueError("Google Cloud 服务账号 token_uri 必须是官方 OAuth 地址")

    @classmethod
    def prepare_runtime_config(
        cls,
        payload: AIConfigUpdate,
        existing: Optional[UserAIConfig],
    ) -> tuple[ProviderDefinition, LLMRuntimeConfig, Dict[str, Any]]:
        """Merge a partial payload with the active config without persisting it."""

        existing_provider_id = existing.provider if existing else infer_provider_from_base_url(settings.OPENAI_API_BASE).id
        provider = get_provider(payload.provider if payload.provider is not None else existing_provider_id)
        if payload.protocol and payload.protocol != provider.protocol:
            raise ValueError("所选服务来源的协议类型不可修改")
        if not provider.implemented or not is_protocol_implemented(provider.protocol):
            # It remains saveable so future adapters can use it, but test/call
            # reports unsupported rather than sending an incorrect request.
            pass

        provider_changed = existing is not None and provider.id != existing.provider
        extra_config = (
            cls._validate_extra_config(payload.extra_config)
            if payload.extra_config is not None
            else dict(existing.extra_config or {}) if existing and not provider_changed else {}
        )

        if provider.id == "azure_openai":
            if payload.base_url is not None:
                base_url = cls._normalize_azure_endpoint(payload.base_url)
            elif provider_changed or not existing:
                base_url = ""
            else:
                base_url = cls._normalize_azure_endpoint(existing.base_url or "")
        elif provider.id == "vertex_ai":
            base_url = cls._vertex_base_url(extra_config)
        elif provider.id == "bedrock":
            base_url = cls._bedrock_base_url(extra_config)
        elif provider.group not in {"custom", "local"}:
            # Official and gateway endpoints are maintained in the registry.
            # Only custom/local providers accept a caller-controlled base URL.
            base_url = provider.default_base_url
        elif payload.base_url is not None:
            base_url = payload.base_url
        elif provider_changed or not existing:
            base_url = provider.default_base_url
        else:
            base_url = existing.base_url or provider.default_base_url

        if payload.proxy_url is not None:
            proxy_url = payload.proxy_url
        elif provider_changed or not existing:
            proxy_url = ""
        else:
            proxy_url = existing.proxy_url or ""
        if proxy_url and not provider.supports_reverse_proxy:
            raise ValueError(f"{provider.label} 暂不支持反向代理配置")

        existing_api_key = cls.decrypt_secret(existing.api_key_encrypted) if existing else ""
        if payload.clear_api_key:
            api_key = ""
        elif payload.api_key:
            api_key = payload.api_key.strip()
        elif provider_changed:
            # A key issued for one provider must never be sent to a different
            # provider just because the replacement form left it blank.
            api_key = ""
        else:
            api_key = existing_api_key

        existing_proxy_password = cls.decrypt_secret(existing.proxy_password_encrypted) if existing else ""
        if payload.clear_proxy_password:
            proxy_password = ""
        elif payload.proxy_password:
            proxy_password = payload.proxy_password.strip()
        elif provider_changed:
            proxy_password = ""
        else:
            proxy_password = existing_proxy_password

        if payload.selected_model is not None:
            model = payload.selected_model.strip()
        elif provider_changed:
            model = ""
        elif existing:
            model = existing.selected_model or ""
        else:
            model = provider.default_model

        if provider.id == "vertex_ai" and api_key:
            cls._validate_vertex_service_account(api_key)

        existing_model = (
            (existing.selected_model or "").strip() if existing and existing.provider == provider.id else ""
        )
        model_changed = bool(existing and (provider_changed or model != existing_model))
        generation_params = cls._generation_params_for_payload(
            payload.generation_params,
            provider=provider,
            model=model,
            existing=existing,
            provider_changed=provider_changed,
            model_changed=model_changed,
        )

        effective_generation_params = generation_params or {}
        provider_defaults = AIProtocolClient.generation_defaults(
            LLMRuntimeConfig(provider=provider.id, protocol=provider.protocol, model=model)
        )
        runtime = LLMRuntimeConfig(
            provider=provider.id,
            protocol=provider.protocol,
            base_url=base_url or "",
            api_key=api_key,
            model=model,
            proxy_url=proxy_url or "",
            proxy_password=proxy_password,
            requires_api_key=provider.requires_api_key,
            temperature=effective_generation_params.get(
                "temperature",
                provider_defaults.get("temperature", cls._default_generation_params()["temperature"]),
            ),
            max_tokens=settings.OPENAI_MAX_TOKENS,
            thinking_enabled=settings.OPENAI_THINKING_ENABLED,
            thinking_param=settings.OPENAI_THINKING_PARAM,
            extra_config=extra_config,
            generation_params=generation_params,
        )
        # Retain the change flags for save() without exposing secrets.
        metadata = {
            "provider_changed": provider_changed,
            "model_changed": model_changed,
            "extra_config": extra_config,
            "api_key": api_key,
            "proxy_password": proxy_password,
            "generation_params": generation_params,
        }
        metadata["generation_params_changed"] = cls._generation_change_requires_test(
            existing, runtime, metadata, payload
        )
        return provider, runtime, metadata

    @classmethod
    def save(
        cls,
        db: Session,
        payload: AIConfigUpdate,
        user_id: int,
        *,
        require_generation_test: bool = False,
    ) -> UserAIConfig:
        record = cls.get_record(db, user_id, for_update=True)
        provider, runtime, metadata = cls.prepare_runtime_config(payload, record)
        if not provider.implemented or not is_protocol_implemented(provider.protocol):
            raise ValueError("该服务协议尚未完成适配，暂不能保存")
        if not runtime.normalized_base_url:
            raise ValueError("请填写 API Base URL")
        if not runtime.is_configured:
            raise ValueError("请填写 API Key；使用反向代理时也可填写代理密码")
        if not runtime.model.strip():
            raise ValueError("请先连接服务并选择一个可用模型")
        if not cls._is_permitted_endpoint(runtime):
            raise ValueError("该地址指向受保护的内网服务")
        if require_generation_test and cls._generation_change_requires_test(
            record, runtime, metadata, payload
        ):
            raise ValueError("高级生成参数或模型已变化，请先点击连接测试并确认成功")
        if record is None:
            record = UserAIConfig(user_id=user_id)
            db.add(record)

        provider_changed = metadata["provider_changed"]
        record.provider = provider.id
        record.protocol = provider.protocol
        record.base_url = runtime.normalized_base_url
        record.selected_model = runtime.model or None
        record.proxy_url = runtime.proxy_url.rstrip("/")
        extra_config = dict(metadata["extra_config"])
        # Keep the legacy JSON shape unchanged until a user actually edits
            # advanced controls. Existing profiles remain available for model
        # switching; defaults need no persistence because they are derived.
        profiles = cls._generation_profiles(record.extra_config)
        if payload.generation_params is not None:
            profile_key = cls._profile_key(provider.id, runtime.model)
            legacy_profile_key = cls._legacy_profile_key(provider.id, runtime.model)
            explicit_params = {
                key: float(value)
                for key, value in metadata["generation_params"].items()
                if key in _GENERATION_KEYS
            }
            # Keep an explicit empty object as a durable profile. It records
            # that the user removed every override for this provider/model,
            # rather than allowing a later refresh to restore old values.
            profiles[profile_key] = explicit_params
            profiles.pop(legacy_profile_key, None)
        if profiles:
            extra_config[_GENERATION_PROFILES_KEY] = profiles
        else:
            extra_config.pop(_GENERATION_PROFILES_KEY, None)
        record.extra_config = extra_config
        record.is_active = True
        if payload.clear_api_key or (provider_changed and not payload.api_key):
            record.api_key_encrypted = None
        elif payload.api_key:
            record.api_key_encrypted = cls.encrypt_secret(metadata["api_key"])
        if payload.clear_proxy_password or (provider_changed and not payload.proxy_password):
            record.proxy_password_encrypted = None
        elif payload.proxy_password:
            record.proxy_password_encrypted = cls.encrypt_secret(metadata["proxy_password"])
        if provider_changed:
            record.available_models = []
            record.last_test_status = "never"
            record.last_test_message = None
            record.last_tested_at = None
        elif metadata.get("model_changed") or metadata.get("generation_params_changed"):
            # A parameter/model edit must be verified by a fresh connection
            # test before the UI treats it as healthy.
            record.last_test_status = "never"
            record.last_test_message = None
            record.last_tested_at = None
        if payload.available_models is not None:
            # Model discovery is not secret.  The browser supplies this only
            # after a successful transient test so a saved selected model has
            # a stable list after refresh; it never changes credentials.
            record.available_models = cls._normalize_models(payload.available_models)
        db.flush()
        return record

    @classmethod
    def _generation_change_requires_test(
        cls,
        record: Optional[UserAIConfig],
        runtime: LLMRuntimeConfig,
        metadata: Dict[str, Any],
        payload: AIConfigUpdate,
    ) -> bool:
        if record is None:
            return payload.generation_params is not None
        if metadata.get("provider_changed") or metadata.get("model_changed"):
            return True
        if payload.generation_params is None:
            return False
        profiles = cls._generation_profiles(record.extra_config)
        stored = cls._profile_values(profiles, runtime.provider, runtime.model)
        # Adding or removing a control is a configuration change even when the
        # value happens to equal the provider's initial default. Require a
        # fresh connection test for that shape change as well as value edits.
        if stored is None:
            return True
        current = cls._generation_params_for_record(record, runtime)
        proposed = metadata["generation_params"]
        if set(current) != set(proposed):
            return True
        return any(
            abs(
                float(current[key])
                - float(proposed[key])
            )
            > 1e-9
            for key in current
        )

    @classmethod
    def delete(cls, db: Session, user_id: int) -> bool:
        record = cls.get_record(db, user_id, for_update=True)
        if not record:
            return False
        db.delete(record)
        db.flush()
        return True

    @classmethod
    def _effective_base_url(cls, runtime: LLMRuntimeConfig) -> str:
        # Reverse proxy mode treats proxy_url as the compatible upstream base.
        return (runtime.proxy_url or runtime.normalized_base_url).rstrip("/")

    @classmethod
    def _is_permitted_endpoint(cls, runtime: LLMRuntimeConfig) -> bool:
        """Block private endpoint targets, including DNS aliases, by default.

        Checking only a literal IP is insufficient: a user-controlled hostname
        can resolve to loopback, link-local, or RFC1918 space. Resolve every
        address returned by the OS and require all answers to be public (or
        loopback for explicitly local providers). The check is repeated before
        each runtime request by ``LLMUtil``.
        """

        if settings.AI_CONFIG_ALLOW_PRIVATE_ENDPOINTS:
            return True
        try:
            host = (urlparse(cls._effective_base_url(runtime)).hostname or "").strip().lower()
        except ValueError:
            return False
        host = host.rstrip(".")
        if not host:
            return False
        local_provider = runtime.provider in {"ollama", "lmstudio"}

        addresses: set[ipaddress.IPv4Address | ipaddress.IPv6Address] = set()
        try:
            addresses.add(ipaddress.ip_address(host))
        except ValueError:
            try:
                resolved = socket.getaddrinfo(
                    host,
                    None,
                    socket.AF_UNSPEC,
                    socket.SOCK_STREAM,
                    socket.IPPROTO_TCP,
                )
            except (OSError, UnicodeError):
                return False
            for item in resolved:
                if len(item) < 5 or not item[4]:
                    continue
                raw_address = item[4][0]
                if not isinstance(raw_address, str):
                    continue
                # IPv6 link-local answers may include a scope ID.
                raw_address = raw_address.split("%", 1)[0]
                try:
                    addresses.add(ipaddress.ip_address(raw_address))
                except ValueError:
                    continue

        if not addresses:
            return False
        if local_provider:
            return all(address.is_loopback for address in addresses)
        return all(address.is_global for address in addresses)

    @classmethod
    def _headers(cls, runtime: LLMRuntimeConfig) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        credential = runtime.credential
        if runtime.protocol == PROTOCOL_ANTHROPIC:
            if credential:
                headers["x-api-key"] = credential
            headers["anthropic-version"] = "2023-06-01"
        elif runtime.protocol == PROTOCOL_AZURE_OPENAI and credential:
            headers["api-key"] = credential
        elif runtime.protocol == PROTOCOL_GEMINI and credential:
            headers["x-goog-api-key"] = credential
        elif runtime.protocol == PROTOCOL_VERTEX_AI:
            return AIProtocolClient._headers(runtime)
        elif credential:
            headers["Authorization"] = f"Bearer {credential}"
        return headers

    @classmethod
    def test_connection(cls, runtime: LLMRuntimeConfig) -> ConnectionTestResult:
        """Discover models and verify that the selected model can generate text."""

        if not runtime.normalized_base_url:
            return ConnectionTestResult(False, [], None, "请填写 API Base URL", "invalid_url")
        if runtime.requires_api_key and not runtime.credential:
            return ConnectionTestResult(
                False,
                [],
                None,
                "请填写 API Key；使用反向代理时也可填写代理密码",
                "missing_api_key",
            )
        if not cls._is_permitted_endpoint(runtime):
            return ConnectionTestResult(False, [], None, "该地址指向受保护的内网服务", "unsafe_endpoint")
        if not is_protocol_implemented(runtime.protocol):
            return ConnectionTestResult(False, [], None, "该服务协议正在适配，暂不可连接", "unsupported_protocol")

        started = time.perf_counter()
        base_url = cls._effective_base_url(runtime)
        models: List[str] = []
        # Some otherwise valid official APIs do not expose an OpenAI-style
        # ``/models`` endpoint.  Treat model discovery as optional: a real text
        # completion is the authoritative connection check in that case.
        model_listing_unavailable = not get_provider(runtime.provider).supports_models_endpoint
        headers = cls._headers(runtime) if not model_listing_unavailable else {}
        try:
            with httpx.Client(
                timeout=float(settings.AI_CONFIG_TEST_TIMEOUT_SECONDS),
                headers=headers,
                trust_env=False,
                follow_redirects=False,
            ) as client:
                if not model_listing_unavailable:
                    if runtime.protocol == PROTOCOL_OLLAMA:
                        response = client.get(f"{base_url}/api/tags")
                    else:
                        response = client.get(f"{base_url}/models")

                    if response.status_code >= 400:
                        if response.status_code in {404, 405, 501}:
                            model_listing_unavailable = True
                        else:
                            latency_ms = round((time.perf_counter() - started) * 1000)
                            return ConnectionTestResult(
                                False,
                                [],
                                latency_ms,
                                cls._status_message(response.status_code),
                                cls._status_code(response.status_code),
                            )
                    else:
                        try:
                            payload = response.json()
                        except ValueError:
                            # A non-JSON discovery response is no more useful
                            # than an unavailable endpoint.  Continue with the
                            # requested/default model and verify generation.
                            model_listing_unavailable = True
                        else:
                            if not isinstance(payload, dict):
                                model_listing_unavailable = True
                            elif runtime.protocol == PROTOCOL_OLLAMA:
                                models = cls._normalize_models(
                                    [
                                        item.get("name")
                                        for item in payload.get("models", [])
                                        if isinstance(item, dict)
                                    ]
                                )
                            elif runtime.protocol == PROTOCOL_GEMINI:
                                models = cls._normalize_models(
                                    [
                                        str(item.get("name", "")).removeprefix("models/")
                                        for item in payload.get("models", [])
                                        if isinstance(item, dict)
                                    ]
                                )
                            else:
                                models = cls._normalize_models(
                                    [
                                        item.get("id")
                                        for item in payload.get("data", [])
                                        if isinstance(item, dict)
                                    ]
                                )
            latency_ms = round((time.perf_counter() - started) * 1000)
            test_model = runtime.model.strip() or (models[0] if models else "")
            if not test_model:
                return ConnectionTestResult(
                    False,
                    models,
                    latency_ms,
                    "服务可访问，但没有可用于生成测试的模型，请手动填写模型 ID",
                    "missing_model",
                )

            AIProtocolClient.complete(
                replace(runtime, model=test_model),
                [{"role": "user", "content": "请只回复 OK"}],
                temperature=float(runtime.temperature or settings.OPENAI_TEMPERATURE),
                max_tokens=min(64, int(runtime.max_tokens or settings.OPENAI_MAX_TOKENS)),
                timeout=float(settings.AI_CONFIG_TEST_TIMEOUT_SECONDS),
            )
            latency_ms = round((time.perf_counter() - started) * 1000)
            return ConnectionTestResult(
                True,
                models,
                latency_ms,
                (
                    "连接及文本生成测试成功；该服务未提供模型列表，已验证当前模型"
                    if model_listing_unavailable
                    else f"连接及文本生成测试成功，发现 {len(models)} 个可用模型"
                ),
            )
        except RuntimeProtocolError as exc:
            messages = {
                "unauthorized": "API Key 无效或没有模型调用权限",
                "invalid_model": "所选模型不可用，请重新选择模型",
                "invalid_parameter": "模型拒绝当前高级生成参数",
                "rate_limited": "模型调用过于频繁或余额不足，请稍后重试",
                "timeout": "模型生成测试超时，请稍后重试",
                "network_error": "模型生成接口无法连接，请检查服务地址或网络",
                "invalid_credential": "Google Cloud 服务账号凭据无效或没有 Vertex AI 调用权限",
                "empty_response": "模型接口已响应，但没有返回可用文本",
            }
            return ConnectionTestResult(
                False,
                models,
                round((time.perf_counter() - started) * 1000),
                (
                    exc.public_message
                    if exc.reason == "invalid_parameter" and exc.public_message
                    else messages.get(exc.reason, "服务可访问，但所选模型无法完成文本生成")
                ),
                exc.reason,
            )
        except httpx.TimeoutException:
            return ConnectionTestResult(False, [], None, "连接超时，请检查地址或网络", "timeout")
        except (httpx.ConnectError, httpx.NetworkError, OSError):
            return ConnectionTestResult(False, [], None, "无法连接服务，请检查地址或网络", "network_error")
        except (ValueError, TypeError):
            return ConnectionTestResult(False, [], None, "服务返回的模型列表格式无效", "provider_error")
        except httpx.HTTPError:
            return ConnectionTestResult(False, [], None, "连接服务时发生错误", "provider_error")

    @staticmethod
    def _status_code(status_code: int) -> str:
        if status_code in (401, 403):
            return "unauthorized"
        if status_code == 404:
            return "not_found"
        if status_code == 429:
            return "rate_limited"
        return "provider_error"

    @staticmethod
    def _status_message(status_code: int) -> str:
        messages = {
            401: "API Key 无效或未授权",
            403: "当前 API Key 没有访问权限",
            404: "服务地址或模型列表接口不存在",
            429: "请求过于频繁，请稍后重试",
        }
        return messages.get(status_code, f"服务返回错误（HTTP {status_code}）")

    @classmethod
    def record_test_result(
        cls,
        db: Session,
        user_id: int,
        result: ConnectionTestResult,
        *,
        selected_model: Optional[str] = None,
    ) -> Optional[UserAIConfig]:
        record = cls.get_record(db, user_id, for_update=True)
        if not record:
            return None
        record.last_test_status = "success" if result.success else "failed"
        record.last_test_message = result.message[:500]
        record.last_tested_at = utcnow_naive()
        if result.success:
            record.available_models = result.models
            if selected_model and selected_model in result.models:
                record.selected_model = selected_model
        db.flush()
        return record
