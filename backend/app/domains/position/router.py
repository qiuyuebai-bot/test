"""
岗位与胜任力域 API 路由
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.response import success, bad_request, not_found, BaseResponse
from app.domains.position.schemas import (
    PositionCreate, PositionUpdate,
    CompetencyCreate, CompetencyUpdate,
    PositionCompetencyCreate, PositionCompetencyUpdate,
)
from app.domains.position.service import PositionService
from app.utils.auth import get_current_user, CurrentUser, require_teacher

router = APIRouter(prefix="", tags=["岗位与胜任力"])


# ===========================================
# Competency 路由
# ===========================================

@router.get("/competencies", summary="胜任力项列表")
def get_competencies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    return PositionService.get_competency_list(db, page, page_size, keyword, category)


@router.post("/competencies", summary="创建胜任力项")
def create_competency(
    data: CompetencyCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return PositionService.create_competency(db, data)


@router.get("/competencies/{competency_id}", summary="胜任力项详情")
def get_competency_detail(
    competency_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    return PositionService.get_competency_by_id(db, competency_id)


@router.put("/competencies/{competency_id}", summary="更新胜任力项")
def update_competency(
    competency_id: int,
    data: CompetencyUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return PositionService.update_competency(db, competency_id, data)


@router.delete("/competencies/{competency_id}", summary="删除胜任力项")
def delete_competency(
    competency_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return PositionService.delete_competency(db, competency_id)


# ===========================================
# Position 路由
# ===========================================

@router.get("/positions", summary="岗位列表")
def get_positions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    return PositionService.get_position_list(db, page, page_size, keyword, category, industry, level)


@router.post("/positions", summary="创建岗位")
def create_position(
    data: PositionCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return PositionService.create_position(db, data)


@router.get("/positions/{position_id}", summary="岗位详情（含胜任力矩阵）")
def get_position_detail(
    position_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    return PositionService.get_position_by_id(db, position_id)


@router.put("/positions/{position_id}", summary="更新岗位")
def update_position(
    position_id: int,
    data: PositionUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return PositionService.update_position(db, position_id, data)


@router.delete("/positions/{position_id}", summary="删除岗位")
def delete_position(
    position_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return PositionService.delete_position(db, position_id)


# ===========================================
# Position-Competency 关联路由
# ===========================================

@router.post("/positions/{position_id}/competencies", summary="为岗位添加胜任力要求")
def add_competency_to_position(
    position_id: int,
    data: PositionCompetencyCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return PositionService.add_competency_to_position(db, position_id, data)


@router.put("/positions/{position_id}/competencies/{competency_id}", summary="更新岗位胜任力要求")
def update_position_competency(
    position_id: int,
    competency_id: int,
    data: PositionCompetencyUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return PositionService.update_position_competency(db, position_id, competency_id, data)


@router.delete("/positions/{position_id}/competencies/{competency_id}", summary="移除岗位胜任力要求")
def remove_competency_from_position(
    position_id: int,
    competency_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
) -> BaseResponse:
    return PositionService.remove_competency_from_position(db, position_id, competency_id)
