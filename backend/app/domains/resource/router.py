"""
个性化知识资源生成 API 路由
包含：资源生成（异步/同步/批量）、Celery 任务进度查询、资源列表/详情/导出
"""
from typing import Optional
from fastapi import APIRouter, Depends, BackgroundTasks, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from loguru import logger

from app.database import get_db
from app.schemas.response import (
    success,
    error,
    bad_request,
    not_found,
    paged_success,
    unauthorized,
    BaseResponse,
)
from app.schemas.core import GenerateResourcesRequest
from app.domains.resource.service import ResourceGenerationService
from app.domains.learner.service import LearnerService
from app.models import LearningResource
from app.utils.logger import LoggerUtil
from app.utils.auth import get_current_user, CurrentUser, require_admin

# Celery 可选依赖
try:
    from app.celery_app import (
        generate_resources_task,
        batch_generate_resources_task,
        celery_app,
    )
    from celery.result import AsyncResult
    _CELERY_AVAILABLE = True
except ImportError:
    _CELERY_AVAILABLE = False
    logger.warning("Celery 未安装，异步任务功能不可用，将使用同步模式")

router = APIRouter(prefix="", tags=["个性化资源生成"])


@router.post("/resources/generate", summary="生成三类个性化学习资源（Celery异步）")
def generate_resources(
    request: GenerateResourcesRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    """
    一次性生成三类学习资源：定制实操指南、分阶训练测试题、专属知识讲义

    - 传入学情画像ID，自动调度多Agent协同
    - 复用诊断+检索阶段，避免重复执行
    - 自动计算资源匹配度
    - 优先使用 Celery 异步队列，不可用时降级为 BackgroundTasks
    """
    try:
        if _CELERY_AVAILABLE:
            task = generate_resources_task.delay(
                learner_id=request.learner_id,
                target_topic=request.target_topic,
                industry=request.industry,
            )

            logger.info(f"Celery 任务已提交: task_id={task.id}, learner_id={request.learner_id}")

            return success(
                data={
                    "task_id": task.id,
                    "learner_id": request.learner_id,
                    "target_topic": request.target_topic,
                },
                message="资源生成任务已推入异步队列，可通过 /api/v1/tasks/{task_id}/status 查询进度",
            )
        else:
            def run_generation():
                try:
                    ResourceGenerationService.generate_all_resources(
                        learner_id=request.learner_id,
                        target_topic=request.target_topic,
                        industry=request.industry,
                    )
                except Exception as e:
                    logger.error(f"资源生成失败: {e}")

            background_tasks.add_task(run_generation)

            return success(
                data={"learner_id": request.learner_id, "target_topic": request.target_topic},
                message="资源生成任务已启动（BackgroundTasks模式），可通过资源列表查询结果",
            )
    except Exception as e:
        LoggerUtil.log_error("生成资源失败", e)
        return error(message=f"生成资源失败: {str(e)}")


@router.post("/resources/generate/batch", summary="批量生成资源（Celery异步）")
def batch_generate_resources(
    request: dict,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
) -> BaseResponse:
    """
    批量生成资源（多个学习者）

    请求体:
    {
        "learner_ids": [1, 2, 3],
        "target_topic": "Python机器学习",
        "industry": "人工智能训练"
    }
    """
    try:
        if not _CELERY_AVAILABLE:
            return error(message="Celery 未安装，批量生成功能不可用。请使用 /resources/generate/sync 同步生成")

        learner_ids = request.get("learner_ids", [])
        target_topic = request.get("target_topic", "")
        industry = request.get("industry")

        if not learner_ids or not target_topic:
            return bad_request(message="learner_ids 和 target_topic 不能为空")

        task = batch_generate_resources_task.delay(
            learner_ids=learner_ids,
            target_topic=target_topic,
            industry=industry,
        )

        logger.info(f"Celery 批量任务已提交: task_id={task.id}, learners={len(learner_ids)}")

        return success(
            data={
                "task_id": task.id,
                "learner_count": len(learner_ids),
                "target_topic": target_topic,
            },
            message=f"批量生成任务已推入异步队列，共 {len(learner_ids)} 个学习者",
        )
    except Exception as e:
        LoggerUtil.log_error("批量生成资源失败", e)
        return error(message=f"批量生成资源失败: {str(e)}")


@router.get("/tasks/{task_id}/status", summary="查询 Celery 任务进度")
def get_task_status(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    """
    查询异步任务进度

    - 返回当前阶段、进度百分比、状态信息
    - 支持 resource_generation / batch_generation 等任务类型
    """
    if not _CELERY_AVAILABLE:
        return error(message="Celery 未安装，任务进度查询不可用")

    try:
        task_result = AsyncResult(task_id, app=celery_app)

        response_data = {
            "task_id": task_id,
            "status": task_result.state,
            "ready": task_result.ready(),
        }

        if task_result.state == "PENDING":
            response_data.update({
                "progress": 0,
                "stage": "pending",
                "message": "任务等待执行中...",
            })
        elif task_result.state == "PROGRESS":
            meta = task_result.info or {}
            response_data.update({
                "progress": meta.get("progress", 0),
                "stage": meta.get("stage", "unknown"),
                "message": meta.get("message", ""),
                "current": meta.get("current"),
                "total": meta.get("total"),
            })
        elif task_result.state == "SUCCESS":
            result = task_result.result
            response_data.update({
                "progress": 100,
                "stage": "completed",
                "message": "任务执行完成",
                "result": result,
            })
        elif task_result.state == "FAILURE":
            response_data.update({
                "progress": 0,
                "stage": "failed",
                "message": str(task_result.info),
            })
        else:
            response_data.update({
                "progress": 0,
                "stage": task_result.state,
                "message": str(task_result.info) if task_result.info else "",
            })

        return success(data=response_data)
    except Exception as e:
        LoggerUtil.log_error("查询任务状态失败", e)
        return error(message=f"查询任务状态失败: {str(e)}")


@router.post("/resources/generate/sync", summary="同步生成三类资源")
def generate_resources_sync(
    request: GenerateResourcesRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    """
    同步生成三类学习资源（演示用）

    - 传入学情画像ID，自动调度多Agent协同
    - 返回完整生成结果
    """
    try:
        result = ResourceGenerationService.generate_all_resources(
            learner_id=request.learner_id,
            target_topic=request.target_topic,
            industry=request.industry,
        )

        if result.get("success"):
            return success(data=result, message="资源生成完成")
        else:
            return error(message=result.get("error", "生成失败"))
    except Exception as e:
        LoggerUtil.log_error("同步生成资源失败", e)
        return error(message=f"生成资源失败: {str(e)}")


@router.get("/resources", summary="获取资源列表")
def get_resource_list(
    learner_id: Optional[int] = Query(None, description="学习者ID"),
    resource_type: Optional[str] = Query(None, description="资源类型"),
    difficulty_level: Optional[int] = Query(None, description="难度等级"),
    status: Optional[str] = Query(None, description="状态"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    """
    获取资源列表（支持分页、筛选）

    - 支持按学习者、类型、难度、状态筛选
    - 返回资源匹配度等关键指标
    """
    try:
        result = ResourceGenerationService.get_resource_list(
            learner_id=learner_id,
            resource_type=resource_type,
            difficulty_level=difficulty_level,
            status=status,
            page=page,
            page_size=page_size,
        )

        return paged_success(
            items=result["resources"],
            total=result["total"],
            page=page,
            page_size=page_size,
        )
    except Exception as e:
        LoggerUtil.log_error("获取资源列表失败", e)
        return error(message=f"获取资源列表失败: {str(e)}")


@router.get("/resources/{resource_id}", summary="获取资源详情")
def get_resource_detail(
    resource_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    """
    获取资源详情（含完整内容）

    - 返回资源完整信息，包括内容、匹配度、来源切片等
    """
    try:
        result = ResourceGenerationService.get_resource_detail(resource_id)
        if not result:
            return not_found(message=f"资源不存在: {resource_id}")

        # IDOR 防护：校验资源归属（资源关联的 learner_id 必须属于当前用户）
        resource_learner_id = result.get("learner_id")
        if resource_learner_id is None:
            # 无关联学习者的资源仅管理员可访问
            if not current_user.is_admin:
                return unauthorized("无权限查看该资源")
        else:
            if not current_user.is_admin:
                if not LearnerService.check_data_permission(
                    db, current_user.user_id, resource_learner_id
                ):
                    return unauthorized("无权限查看该资源")

        return success(data=result)
    except Exception as e:
        LoggerUtil.log_error("获取资源详情失败", e)
        return error(message=f"获取资源详情失败: {str(e)}")


@router.get("/resources/{resource_id}/export", summary="导出资源")
def export_resource(
    resource_id: int,
    format: str = Query("txt", description="导出格式: txt/md"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    导出资源文件

    - 支持txt和md两种格式
    - 返回纯文本内容，可直接下载
    """
    try:
        # IDOR 防护：先校验资源归属再导出（直接查询模型，避免触发 view_count 副作用）
        resource = db.query(LearningResource).filter(
            LearningResource.id == resource_id
        ).first()
        if not resource:
            return not_found(message=f"资源不存在或无法导出: {resource_id}")

        resource_learner_id = resource.learner_id
        if resource_learner_id is None:
            # 无关联学习者的资源仅管理员可访问
            if not current_user.is_admin:
                return unauthorized("无权限导出该资源")
        else:
            if not current_user.is_admin:
                if not LearnerService.check_data_permission(
                    db, current_user.user_id, resource_learner_id
                ):
                    return unauthorized("无权限导出该资源")

        content = ResourceGenerationService.export_resource(resource_id, format)
        if not content:
            return not_found(message=f"资源不存在或无法导出: {resource_id}")

        filename = f"resource_{resource_id}.{format}"
        headers = {
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Type": "text/plain; charset=utf-8",
        }

        return PlainTextResponse(content=content, headers=headers)
    except Exception as e:
        LoggerUtil.log_error("导出资源失败", e)
        return error(message=f"导出资源失败: {str(e)}")
