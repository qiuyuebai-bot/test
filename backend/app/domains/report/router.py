"""
学情可视化报告 API 路由
包含：完整学情报告、PDF导出、知识盲区热力图、难度匹配曲线、能力趋势、学习路径、能力雷达、系统指标
"""
import io
from datetime import datetime
from typing import Optional
from collections import defaultdict
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from loguru import logger

from app.database import get_db
from app.models import LearnerProfile, AnswerRecord
from app.schemas.response import (
    success,
    error,
    not_found,
    unauthorized,
    BaseResponse,
)
from app.services.report_service import ReportService
from app.domains.learner.service import LearnerService
from app.utils.logger import LoggerUtil
from app.utils.auth import get_current_user, CurrentUser, require_admin

router = APIRouter(prefix="", tags=["学情可视化报告"])


@router.get("/report/learner/{learner_id}", summary="生成完整学情报告")
def generate_learner_report(
    learner_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    """
    生成完整学情报告（前端可视化看板直接渲染）

    返回结构化数据：
    - 知识盲区热力图
    - 资源难度匹配曲线
    - 学习路径节点拓扑
    - 能力雷达图
    - 核心指标统计
    """
    if not current_user.is_admin:
        if not LearnerService.check_data_permission(db, current_user.user_id, learner_id):
            return unauthorized("无权限查看该学习者报告")
    try:
        result = ReportService.generate_learner_report(learner_id)

        if result.get("success"):
            return success(data=result, message="报告生成完成")
        else:
            return not_found(message=result.get("error", "报告生成失败"))
    except Exception as e:
        LoggerUtil.log_error("生成学情报告失败", e)
        return error(message=f"生成报告失败: {str(e)}")


@router.get("/report/learner/{learner_id}/pdf", summary="导出学情报告 PDF")
def export_learner_report_pdf(
    learner_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    一键导出学情报告为 PDF 文件

    - 包含学习者基本信息、核心指标、知识盲区分析、能力评估、学习路径规划
    - 返回 PDF 文件流，浏览器自动下载
    """
    if not current_user.is_admin:
        if not LearnerService.check_data_permission(db, current_user.user_id, learner_id):
            return unauthorized("无权限导出该学习者报告")
    try:
        pdf_bytes = ReportService.export_report_pdf(learner_id)

        if pdf_bytes is None:
            return not_found(message=f"无法生成报告: 学习者 {learner_id} 不存在或报告生成失败")

        learner = db.query(LearnerProfile).filter(LearnerProfile.id == learner_id).first()
        learner_name = (learner.real_name or f"learner_{learner_id}") if learner else f"learner_{learner_id}"

        filename = f"学情报告_{learner_name}_{datetime.now().strftime('%Y%m%d')}.pdf"

        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
            },
        )
    except Exception as e:
        LoggerUtil.log_error("导出 PDF 报告失败", e)
        return error(message=f"导出 PDF 报告失败: {str(e)}")


@router.get("/report/heatmap/{learner_id}", summary="获取知识盲区热力图数据")
def get_blind_area_heatmap(
    learner_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    """获取知识盲区热力图数据（对齐前端 Recharts HeatmapChart 需求）"""
    if not current_user.is_admin:
        if not LearnerService.check_data_permission(db, current_user.user_id, learner_id):
            return unauthorized("无权限查看该学习者数据")
    try:
        learner = db.query(LearnerProfile).filter(
            LearnerProfile.id == learner_id
        ).first()

        if not learner:
            return not_found(message=f"学习者不存在: {learner_id}")

        ability_scores = {
            "theoretical_foundation": learner.theoretical_foundation or 0,
            "programming_ability": learner.programming_ability or 0,
            "algorithm_design": learner.algorithm_design or 0,
            "system_architecture": learner.system_architecture or 0,
            "data_analysis": learner.data_analysis or 0,
            "engineering_practice": learner.engineering_practice or 0,
        }

        result = ReportService._generate_blind_area_heatmap(
            ability_scores,
            learner.knowledge_blind_areas or [],
        )
        return success(data=result)
    except Exception as e:
        LoggerUtil.log_error("获取热力图数据失败", e)
        return error(message=f"获取热力图数据失败: {str(e)}")


@router.get("/report/match-curve/{learner_id}", summary="获取难度匹配曲线数据")
def get_match_curve(
    learner_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    """获取资源难度匹配曲线数据（对齐前端 Recharts LineChart 需求）"""
    if not current_user.is_admin:
        if not LearnerService.check_data_permission(db, current_user.user_id, learner_id):
            return unauthorized("无权限查看该学习者数据")
    try:
        learner = db.query(LearnerProfile).filter(
            LearnerProfile.id == learner_id
        ).first()

        if not learner:
            return not_found(message=f"学习者不存在: {learner_id}")

        avg_ability = learner.average_ability

        result = ReportService._generate_match_curve(
            learner_id,
            avg_ability,
        )
        return success(data=result)
    except Exception as e:
        LoggerUtil.log_error("获取匹配曲线数据失败", e)
        return error(message=f"获取匹配曲线数据失败: {str(e)}")


@router.get("/report/ability-trend/{learner_id}", summary="获取能力发展趋势数据")
def get_ability_trend(
    learner_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    """获取学习者能力发展趋势数据（从答题记录按周聚合平均分，用于前端 AreaChart）"""
    if not current_user.is_admin:
        if not LearnerService.check_data_permission(db, current_user.user_id, learner_id):
            return unauthorized("无权限查看该学习者数据")
    try:
        learner = db.query(LearnerProfile).filter(
            LearnerProfile.id == learner_id
        ).first()

        if not learner:
            return not_found(message=f"学习者不存在: {learner_id}")

        records = db.query(AnswerRecord).filter(
            AnswerRecord.learner_id == learner_id
        ).order_by(AnswerRecord.created_at).all()

        weekly = defaultdict(list)
        for r in records:
            iso_year, iso_week, _ = r.created_at.isocalendar()
            weekly[(iso_year, iso_week)].append(r.score)

        sorted_weeks = sorted(weekly.keys())[-6:]
        trend = []
        for i, week_key in enumerate(sorted_weeks):
            scores = weekly[week_key]
            avg = sum(scores) / len(scores)
            trend.append({"week": f"W{i+1}", "score": round(avg, 1)})

        return success(data=trend)
    except Exception as e:
        LoggerUtil.log_error("获取能力发展趋势数据失败", e)
        return error(message=f"获取能力发展趋势数据失败: {str(e)}")


@router.get("/report/learning-path/{learner_id}", summary="获取学习路径拓扑数据")
def get_learning_path(
    learner_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    """获取学习路径节点拓扑数据（返回节点和边信息，用于前端绘制路径图）"""
    if not current_user.is_admin:
        if not LearnerService.check_data_permission(db, current_user.user_id, learner_id):
            return unauthorized("无权限查看该学习者数据")
    try:
        learner = db.query(LearnerProfile).filter(
            LearnerProfile.id == learner_id
        ).first()

        if not learner:
            return not_found(message=f"学习者不存在: {learner_id}")

        result = ReportService._generate_path_topology(learner, learner.knowledge_blind_areas or [])
        return success(data=result)
    except Exception as e:
        LoggerUtil.log_error("获取学习路径数据失败", e)
        return error(message=f"获取学习路径数据失败: {str(e)}")


@router.get("/report/ability-radar/{learner_id}", summary="获取能力雷达图数据")
def get_ability_radar(
    learner_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    """获取能力雷达图数据（对齐前端 Recharts RadarChart 需求）"""
    if not current_user.is_admin:
        if not LearnerService.check_data_permission(db, current_user.user_id, learner_id):
            return unauthorized("无权限查看该学习者数据")
    try:
        learner = db.query(LearnerProfile).filter(
            LearnerProfile.id == learner_id
        ).first()

        if not learner:
            return not_found(message=f"学习者不存在: {learner_id}")

        ability_scores = {
            "theoretical_foundation": learner.theoretical_foundation or 0,
            "programming_ability": learner.programming_ability or 0,
            "algorithm_design": learner.algorithm_design or 0,
            "system_architecture": learner.system_architecture or 0,
            "data_analysis": learner.data_analysis or 0,
            "engineering_practice": learner.engineering_practice or 0,
        }

        result = ReportService._generate_ability_radar(ability_scores)
        return success(data=result)
    except Exception as e:
        LoggerUtil.log_error("获取能力雷达数据失败", e)
        return error(message=f"获取能力雷达数据失败: {str(e)}")


@router.get("/report/metrics", summary="获取系统核心指标")
def get_system_metrics(db: Session = Depends(get_db)) -> BaseResponse:
    """
    获取系统级核心指标（对齐前端 SystemMetrics 类型）

    - 幻觉率、资源匹配准确率、知识点覆盖率
    - 趋势数据（最近7天）
    """
    try:
        result = ReportService.get_system_metrics()
        return success(data=result)
    except Exception as e:
        LoggerUtil.log_error("获取系统指标失败", e)
        return error(message=f"获取系统指标失败: {str(e)}")


@router.post("/report/metrics/update", summary="更新指标统计")
def update_metrics(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
) -> BaseResponse:
    """
    更新指标统计（定时任务调用）

    - 自动计算资源匹配准确率、知识点覆盖率
    - 更新到指标统计表
    """
    try:
        ReportService.update_metrics_periodically()
        return success(message="指标更新完成")
    except Exception as e:
        LoggerUtil.log_error("更新指标失败", e)
        return error(message=f"更新指标失败: {str(e)}")
