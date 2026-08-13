"""
评估域 API 路由
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.response import BaseResponse
from app.domains.assessment.schemas import (
    AssessmentTemplateCreate, AssessmentTemplateUpdate,
    AssessmentStartRequest, AssessmentSubmitRequest,
)
from app.domains.assessment.service import AssessmentService
from app.models.user import UserRoleEnum
from app.utils.auth import get_current_user, CurrentUser, require_teacher

router = APIRouter(prefix="/assessments", tags=["能力评估"])


# ===========================================
# 评估模板路由
# ===========================================

@router.get("/templates", summary="评估模板列表")
def get_templates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    position_id: Optional[int] = Query(None),
    keyword: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    return AssessmentService.get_template_list(db, page, page_size, position_id, keyword)


@router.post("/templates", summary="创建评估模板")
def create_template(
    data: AssessmentTemplateCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return AssessmentService.create_template(db, data)


@router.get("/templates/{template_id}", summary="评估模板详情")
def get_template_detail(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    return AssessmentService.get_template_by_id(db, template_id)


@router.put("/templates/{template_id}", summary="更新评估模板")
def update_template(
    template_id: int,
    data: AssessmentTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return AssessmentService.update_template(db, template_id, data)


@router.delete("/templates/{template_id}", summary="删除评估模板")
def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return AssessmentService.delete_template(db, template_id)


# ===========================================
# 评估记录路由
# ===========================================

@router.post("/start", summary="开始评估")
def start_assessment(
    data: AssessmentStartRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return AssessmentService.start_assessment(db, current_user.user_id, data.template_id, data.learner_id)


@router.get("/records", summary="评估记录列表")
def get_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: Optional[int] = Query(None),
    position_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    learner_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    is_staff = current_user.role in (UserRoleEnum.ADMIN.value, UserRoleEnum.TEACHER.value)
    if not is_staff:
        user_id = current_user.user_id
        learner_id = None
    return AssessmentService.get_record_list(
        db, page, page_size, user_id, position_id, status, learner_id, is_staff=is_staff,
    )


@router.get("/records/{record_id}", summary="评估记录详情（含评分明细）")
def get_record_detail(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    is_staff = current_user.role in (UserRoleEnum.ADMIN.value, UserRoleEnum.TEACHER.value)
    return AssessmentService.get_record_detail(db, record_id, current_user.user_id, is_staff=is_staff)


@router.post("/records/{record_id}/submit", summary="提交评估答案")
def submit_assessment(
    record_id: int,
    data: AssessmentSubmitRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return AssessmentService.submit_assessment(db, record_id, data)


@router.get("/records/{record_id}/gaps", summary="获取差距分析结果")
def get_gap_analysis(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    is_staff = current_user.role in (UserRoleEnum.ADMIN.value, UserRoleEnum.TEACHER.value)
    return AssessmentService.get_gap_analysis(db, record_id, current_user.user_id, is_staff=is_staff)
