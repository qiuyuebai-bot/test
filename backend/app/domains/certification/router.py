"""
认证发证域 API 路由
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.response import BaseResponse
from app.domains.certification.schemas import (
    CertificationCreate, CertificationUpdate,
    CertificationRuleCreate, CertificationApplyRequest,
    CertificationReviewRequest,
)
from app.domains.certification.service import CertificationService
from app.models.user import UserRoleEnum
from app.utils.auth import get_current_user, CurrentUser, require_teacher

router = APIRouter(prefix="/certifications", tags=["认证发证"])


# ===========================================
# 认证定义路由
# ===========================================

@router.get("", summary="认证列表")
def get_certifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    position_id: Optional[int] = Query(None),
    keyword: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    return CertificationService.get_certification_list(db, page, page_size, position_id, keyword)


@router.post("", summary="创建认证")
def create_certification(
    data: CertificationCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return CertificationService.create_certification(db, data)


@router.get("/{cert_id}", summary="认证详情（含规则）")
def get_certification_detail(
    cert_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    return CertificationService.get_certification_by_id(db, cert_id)


@router.put("/{cert_id}", summary="更新认证")
def update_certification(
    cert_id: int,
    data: CertificationUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return CertificationService.update_certification(db, cert_id, data)


@router.delete("/{cert_id}", summary="删除认证")
def delete_certification(
    cert_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return CertificationService.delete_certification(db, cert_id)


# ===========================================
# 发证规则路由
# ===========================================

@router.get("/{cert_id}/rules", summary="认证规则列表")
def get_rules(
    cert_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    return CertificationService.get_rules(db, cert_id)


@router.post("/rules", summary="添加发证规则")
def add_rule(
    data: CertificationRuleCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return CertificationService.add_rule(db, data)


@router.delete("/rules/{rule_id}", summary="删除发证规则")
def delete_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return CertificationService.delete_rule(db, rule_id)


# ===========================================
# 认证记录路由
# ===========================================

@router.post("/apply", summary="申请认证")
def apply_for_certification(
    data: CertificationApplyRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    is_staff = current_user.role in (UserRoleEnum.ADMIN.value, UserRoleEnum.TEACHER.value)
    return CertificationService.apply_for_certification(
        db, current_user.user_id, data, is_staff=is_staff,
    )


@router.get("/records/list", summary="认证记录列表")
def get_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    learner_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    is_staff = current_user.role in (UserRoleEnum.ADMIN.value, UserRoleEnum.TEACHER.value)
    if not is_staff:
        user_id = current_user.user_id
        learner_id = None
    return CertificationService.get_record_list(
        db, page, page_size, user_id, status, learner_id, is_staff=is_staff,
    )


@router.get("/records/{record_id}", summary="认证记录详情")
def get_record_detail(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    is_staff = current_user.role in (UserRoleEnum.ADMIN.value, UserRoleEnum.TEACHER.value)
    return CertificationService.get_record_detail(
        db, record_id, current_user.user_id, is_staff=is_staff,
    )


@router.post("/records/{record_id}/approve", summary="批准认证")
def approve_record(
    record_id: int,
    data: CertificationReviewRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return CertificationService.approve_record(db, record_id, current_user.user_id, data.comment)


@router.post("/records/{record_id}/reject", summary="拒绝认证")
def reject_record(
    record_id: int,
    data: CertificationReviewRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return CertificationService.reject_record(db, record_id, current_user.user_id, data.comment)


@router.post("/records/{record_id}/revoke", summary="撤销已发证书")
def revoke_record(
    record_id: int,
    data: CertificationReviewRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return CertificationService.revoke_record(db, record_id, current_user.user_id, data.comment)


@router.get("/verify/{certificate_number}", summary="公开验真证书")
def verify_certificate(
    certificate_number: str,
    db: Session = Depends(get_db),
) -> BaseResponse:
    return CertificationService.verify_certificate(db, certificate_number)
