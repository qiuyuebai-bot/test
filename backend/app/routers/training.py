"""
企业培训任务管理 API 路由
实现培训项目 CRUD、统计、转岗、批量导入等接口
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from loguru import logger

from app.database import get_db
from app.schemas.response import success, bad_request, not_found, paged_success
from app.schemas.training import (
    TrainingCreate,
    TrainingUpdate,
    TrainingBatchImportRequest,
)
from app.services.training_service import TrainingService
from app.services.common import BaseService
from app.utils.auth import get_current_user, CurrentUser, require_teacher

router = APIRouter(prefix="/trainings", tags=["企业培训"])


# ===========================================
# 固定路径路由（必须在 /{training_id} 之前定义，否则会被拦截）
# ===========================================

@router.get("", summary="获取培训任务列表")
def get_training_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    training_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
):
    """获取企业培训任务列表，支持分页、搜索、筛选"""
    items, total = TrainingService.get_training_list(
        db,
        page=page,
        page_size=page_size,
        keyword=keyword,
        status=status,
        training_type=training_type,
    )
    return paged_success(items=items, total=total, page=page, page_size=page_size)


@router.post("", summary="创建培训任务")
def create_training(
    data: TrainingCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
):
    """创建新的企业培训任务"""
    try:
        training = TrainingService.create_training(db, data)
        return success({"id": training.id}, "创建成功")
    except Exception as e:
        logger.error(f"创建培训任务失败: {e}")
        return bad_request(f"创建失败: {str(e)}")


@router.get("/stats/overview", summary="获取培训统计")
def get_training_stats(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """获取培训统计概览（缓存 30 秒）"""
    cache_key = "training_stats"
    cached = BaseService.get_cache(cache_key)
    if cached is not None:
        return success(cached)
    stats = TrainingService.get_stats(db)
    BaseService.set_cache(cache_key, stats)
    return success(stats)


@router.get("/transfers/list", summary="获取转岗培训列表")
def get_transfers(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """获取所有转岗培训记录"""
    transfers = TrainingService.get_transfers(db)
    return success(transfers)


@router.get("/skill-gaps/analysis", summary="获取技能差距分析")
def get_skill_gaps(
    training_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """获取技能差距分析数据"""
    gaps = TrainingService.get_skill_gaps(db, training_id)
    return success(gaps)


@router.post("/batch-import", summary="批量导入培训任务")
def batch_import(
    request: TrainingBatchImportRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
):
    """批量导入培训任务"""
    result = TrainingService.batch_import(db, request)
    return success(result, f"导入完成: 成功 {result['success_count']} 条, 失败 {result['failed_count']} 条")


# ===========================================
# 动态路径路由（/{training_id}）
# ===========================================

@router.get("/{training_id}", summary="获取培训任务详情")
def get_training_detail(
    training_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """根据ID获取培训任务详情"""
    training = TrainingService.get_training_by_id(db, training_id)
    if not training:
        return not_found("培训任务不存在")
    return success(training)


@router.put("/{training_id}", summary="更新培训任务")
def update_training(
    training_id: int,
    data: TrainingUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
):
    """更新培训任务信息"""
    training = TrainingService.update_training(db, training_id, data)
    if not training:
        return not_found("培训任务不存在")
    return success({"id": training.id}, "更新成功")


@router.delete("/{training_id}", summary="删除培训任务")
def delete_training(
    training_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_teacher),
):
    """删除培训任务"""
    result = TrainingService.delete_training(db, training_id)
    if not result:
        return not_found("培训任务不存在")
    return success(None, "删除成功")
