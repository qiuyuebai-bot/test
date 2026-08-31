"""仅在 Windows 桌面模式下注册的本机初始化与关闭接口。"""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRoleEnum
from app.schemas.auth import DesktopBootstrapRequest
from app.schemas.response import BaseResponse, success
from app.seed_data import init_career_training_seed_data, init_knowledge_seed_data, init_learner_seed_data
from app.utils.auth import create_tokens_for_user, hash_password, set_auth_cookies
from app.utils.datetime import utcnow_naive


router = APIRouter(prefix="/desktop", tags=["桌面应用"])


def _has_admin(db: Session) -> bool:
    return db.query(User.id).filter(User.role == UserRoleEnum.ADMIN).first() is not None


@router.get("/bootstrap-status", response_model=BaseResponse[dict])
def bootstrap_status(db: Session = Depends(get_db)):
    """返回是否需要在本机创建首个管理员。"""
    return success({"required": not _has_admin(db)}, "桌面初始化状态已获取")


@router.post("/bootstrap", response_model=BaseResponse[dict], status_code=201)
def bootstrap_administrator(payload: DesktopBootstrapRequest, db: Session = Depends(get_db)):
    """只允许首次安装创建一个管理员，并立即返回登录状态。"""
    if _has_admin(db):
        raise HTTPException(status_code=409, detail="此设备已经完成管理员初始化")
    if db.query(User.id).filter(User.username == payload.username).first():
        raise HTTPException(status_code=409, detail="用户名已被占用")

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=UserRoleEnum.ADMIN,
        is_active=True,
        is_verified=True,
        last_login_at=utcnow_naive(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # 演示数据只在用户自主设置管理员后创建，避免分发固定管理员凭据。
    init_learner_seed_data()
    init_career_training_seed_data()
    init_knowledge_seed_data()
    tokens = create_tokens_for_user(user)
    response = success(
        {"user_id": user.id, "username": user.username, "role": user.role.value, **tokens},
        "管理员创建成功",
    )
    set_auth_cookies(response, tokens)
    response.status_code = 201
    return response


@router.post("/shutdown", response_model=BaseResponse[dict])
async def shutdown_desktop_backend(request: Request, background_tasks: BackgroundTasks):
    """由 Electron 触发优雅退出；令牌校验由桌面中间件统一完成。"""
    shutdown = getattr(request.app.state, "request_desktop_shutdown", None)
    if callable(shutdown):
        background_tasks.add_task(shutdown)
    return success({"accepted": True}, "正在关闭桌面服务")
