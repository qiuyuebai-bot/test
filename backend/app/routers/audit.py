"""
审计日志查询 API 路由
管理员可查询审计日志、查看统计、导出
"""
from datetime import datetime, date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, text
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.audit_log import AuditLog
from app.schemas.response import success, paged_success
from app.utils.auth import require_admin, CurrentUser

router = APIRouter(prefix="/audit", tags=["审计日志"])


@router.get("/logs", summary="查询审计日志（分页）")
def get_audit_logs(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    user_id: Optional[int] = Query(default=None, description="按用户ID筛选"),
    action: Optional[str] = Query(default=None, description="按操作类型筛选"),
    resource_type: Optional[str] = Query(default=None, description="按资源类型筛选"),
    start_date: Optional[date] = Query(default=None, description="开始日期(YYYY-MM-DD)"),
    end_date: Optional[date] = Query(default=None, description="结束日期(YYYY-MM-DD)"),
    keyword: Optional[str] = Query(default=None, description="路径关键词搜索"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
):
    """分页查询审计日志，支持多维度筛选"""
    query = db.query(AuditLog)

    if user_id is not None:
        query = query.filter(AuditLog.user_id == user_id)
    if action:
        query = query.filter(AuditLog.action == action)
    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)
    if start_date:
        query = query.filter(AuditLog.created_at >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        query = query.filter(AuditLog.created_at < datetime.combine(end_date, datetime.max.time()))
    if keyword:
        query = query.filter(AuditLog.path.contains(keyword))

    total = query.count()
    items = (
        query.order_by(desc(AuditLog.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    result = [
        {
            "id": log.id,
            "created_at": log.created_at.isoformat() if log.created_at else None,
            "user_id": log.user_id,
            "username": log.username,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "method": log.method,
            "path": log.path,
            "status_code": log.status_code,
            "ip_address": log.ip_address,
            "duration_ms": log.duration_ms,
            "request_id": log.request_id,
        }
        for log in items
    ]

    return paged_success(result, total, page, page_size)


@router.get("/stats", summary="审计日志统计")
def get_audit_stats(
    days: int = Query(default=7, ge=1, le=90, description="统计最近N天"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
):
    """审计日志统计概览：操作分布、活跃用户、趋势"""
    cutoff = func.datetime("now", f"-{days} days") if db.bind.dialect.name == "sqlite" else func.now() - text(f"interval '{days} days'")

    action_counts = (
        db.query(AuditLog.action, func.count(AuditLog.id).label("count"))
        .filter(AuditLog.created_at >= cutoff)
        .group_by(AuditLog.action)
        .order_by(desc("count"))
        .all()
    )

    top_users = (
        db.query(
            AuditLog.username,
            AuditLog.user_id,
            func.count(AuditLog.id).label("count"),
        )
        .filter(AuditLog.created_at >= cutoff)
        .filter(AuditLog.user_id.isnot(None))
        .group_by(AuditLog.user_id, AuditLog.username)
        .order_by(desc("count"))
        .limit(10)
        .all()
    )

    resource_counts = (
        db.query(AuditLog.resource_type, func.count(AuditLog.id).label("count"))
        .filter(AuditLog.created_at >= cutoff)
        .group_by(AuditLog.resource_type)
        .order_by(desc("count"))
        .all()
    )

    error_count = (
        db.query(func.count(AuditLog.id))
        .filter(AuditLog.created_at >= cutoff)
        .filter(AuditLog.status_code >= 400)
        .scalar()
    ) or 0

    total_count = (
        db.query(func.count(AuditLog.id))
        .filter(AuditLog.created_at >= cutoff)
        .scalar()
    ) or 0

    return success({
        "total": total_count,
        "errors": error_count,
        "error_rate": round(error_count / total_count * 100, 2) if total_count > 0 else 0,
        "actions": [
            {"action": a, "count": c} for a, c in action_counts
        ],
        "top_users": [
            {"username": u, "user_id": uid, "count": c} for u, uid, c in top_users
        ],
        "resources": [
            {"resource_type": r or "unknown", "count": c} for r, c in resource_counts
        ],
    }, "统计查询成功")


@router.get("/actions", summary="获取操作类型列表")
def get_audit_actions(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
):
    """获取所有已记录的操作类型，用于前端筛选下拉框"""
    actions = (
        db.query(AuditLog.action)
        .distinct()
        .order_by(AuditLog.action)
        .all()
    )
    return success([a[0] for a in actions])
