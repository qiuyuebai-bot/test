"""角色自适应 Dashboard API。"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.response import BaseResponse, bad_request, forbidden, success
from app.utils.auth import CurrentUser, get_current_user, require_teacher

from .service import (
    get_learner_dashboard,
    get_teacher_dashboard,
    update_guidance_state,
)

router = APIRouter(prefix="/dashboard", tags=["角色自适应 Dashboard"])


class GuidanceStateUpdate(BaseModel):
    action: str = Field(..., pattern="^(complete|snooze|resume)$")


@router.get("/learner", summary="获取学习者 Dashboard 数据")
def learner_dashboard(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    if not current_user.is_learner:
        return forbidden("当前角色不能访问学习者 Dashboard")
    return success(get_learner_dashboard(db, current_user.user_id))


@router.patch("/learner/guidance", summary="更新学习者 Dashboard 引导状态")
def learner_guidance_state(
    request: GuidanceStateUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    if not current_user.is_learner:
        return forbidden("当前角色不能更新学习者引导状态")
    try:
        state = update_guidance_state(db, current_user.user_id, request.action)
    except ValueError as exc:
        return bad_request(str(exc))
    return success(state)


@router.get("/teacher", summary="获取教师 Dashboard 数据")
def teacher_dashboard(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = Query(None, max_length=100),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return success(get_teacher_dashboard(db, page, page_size, keyword))
