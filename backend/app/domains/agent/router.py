"""
Agent 协同调度 API 路由
"""
import asyncio
import json
import threading
from app.utils.datetime import utcnow_naive
from typing import Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from loguru import logger

from app.database import get_db
from app.schemas.response import (
    success,
    error,
    bad_request,
    not_found,
    unauthorized,
    paged_success,
    BaseResponse,
)
from app.domains.agent.schemas import (
    CreateAgentTaskRequest,
    DiagnosisRequest,
    GenerationRequest,
    AgentStatusResponse,
    TaskStatusResponse,
    TaskLogEntry,
    DiagnosisResultResponse,
    MetricsResponse,
)
from app.domains.learner.service import LearnerService
from app.agents.orchestrator import orchestrator
from app.models import (
    AgentTask,
    DebateRecord,
    KnowledgeDoc,
    KnowledgeSlice,
    LearnerProfile,
    LearningResource,
)
from app.domains.training.service import TrainingService
from app.utils.logger import LoggerUtil
from app.utils.auth import get_current_user, CurrentUser
from app.utils.metrics import MetricsUtil
from app.services.metric_service import MetricService
from app.services.common import ResourceServiceHelper
from app.utils.resource_content import normalize_resource_topic

router = APIRouter(prefix="/agent", tags=["Agent协同调度"])


def _validate_training_context(db: Session, learner_id: int, context: Optional[Dict]) -> Optional[str]:
    """Validate client-provided training context against persisted plan data."""
    return TrainingService.validate_training_context(db, learner_id, context)


def _check_task_permission(db: Session, current_user: CurrentUser, task: AgentTask) -> bool:
    if current_user.is_admin:
        return True
    if task.learner_id is None:
        return False
    return LearnerService.check_data_permission(db, current_user.user_id, task.learner_id)


def _parse_json_value(value, fallback):
    """Parse JSON columns that may contain either native values or strings."""
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


def _as_list(value):
    parsed = _parse_json_value(value, [])
    if isinstance(parsed, list):
        return parsed
    return [parsed] if parsed else []


_AGENT_STAGE_GROUPS = {
    "diagnosis": {"diagnosis"},
    "knowledge": {"knowledge_retrieval"},
    "generation": {"generation"},
    "judge": {"judge_first", "debate", "final_revision"},
}
_FLOW_STAGE_ORDER = {
    stage: index
    for index, stage in enumerate(
        ("diagnosis", "knowledge_retrieval", "generation", "judge_first", "debate", "final_revision")
    )
}


def _calculate_agent_statistics(tasks) -> Dict[str, Dict[str, float | int]]:
    """Aggregate durable per-agent counts and stage latency from task logs."""
    stats = {
        agent_type: {"total_tasks_handled": 0, "success_count": 0, "failure_count": 0, "duration_total": 0.0, "duration_count": 0}
        for agent_type in _AGENT_STAGE_GROUPS
    }

    for task in tasks:
        logs = [item for item in _as_list(task.execution_logs) if isinstance(item, dict)]
        seen_stages = {item.get("stage") for item in logs}
        stage_durations: Dict[str, float] = {}
        previous_stage = None
        for item in logs:
            stage = item.get("stage")
            duration = item.get("previous_stage_duration_ms")
            if previous_stage in _FLOW_STAGE_ORDER and isinstance(duration, (int, float)):
                stage_durations[previous_stage] = stage_durations.get(previous_stage, 0.0) + max(0.0, float(duration))
            if stage in _FLOW_STAGE_ORDER:
                previous_stage = stage

        handled_agents = {
            agent_type
            for agent_type, stages in _AGENT_STAGE_GROUPS.items()
            if seen_stages & stages
        }
        if task.task_type == "learner_diagnosis" and not handled_agents:
            handled_agents.add("diagnosis")
            if task.duration_ms is not None:
                stage_durations["diagnosis"] = max(0.0, float(task.duration_ms))

        last_stage = max(
            (stage for stage in seen_stages if stage in _FLOW_STAGE_ORDER),
            key=lambda stage: _FLOW_STAGE_ORDER[stage],
            default=None,
        )
        failed_agent = next(
            (agent_type for agent_type, stages in _AGENT_STAGE_GROUPS.items() if last_stage in stages),
            None,
        ) if task.status == "failed" else None

        for agent_type in handled_agents:
            agent_stats = stats[agent_type]
            agent_stats["total_tasks_handled"] += 1
            if task.status == "completed" or (task.status == "failed" and agent_type != failed_agent):
                agent_stats["success_count"] += 1
            elif task.status == "failed" and agent_type == failed_agent:
                agent_stats["failure_count"] += 1

            duration = sum(stage_durations.get(stage, 0.0) for stage in _AGENT_STAGE_GROUPS[agent_type])
            if duration > 0:
                agent_stats["duration_total"] += duration
                agent_stats["duration_count"] += 1

    return {
        agent_type: {
            "total_tasks_handled": int(values["total_tasks_handled"]),
            "success_count": int(values["success_count"]),
            "failure_count": int(values["failure_count"]),
            "avg_latency_ms": round(values["duration_total"] / values["duration_count"], 1)
            if values["duration_count"]
            else None,
        }
        for agent_type, values in stats.items()
    }


def _score_percent(value):
    if value is None:
        return None
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if 0 <= score <= 1:
        score *= 100
    return round(max(0.0, min(100.0, score)), 1)


def _serialize_debate_record(record: DebateRecord) -> Dict:
    judge_view = _parse_json_value(record.agent_judge_view, {})
    generation_view = _parse_json_value(record.agent_generation_view, {})
    conflicts = _as_list(record.conflict_description)
    corrections = _as_list(record.judge_notes)
    return {
        "round": record.debate_round,
        "debate_type": record.debate_type,
        "has_conflict": record.has_conflict,
        "conflict_type": record.conflict_type,
        "conflict_severity": record.conflict_severity,
        "is_hallucination": record.is_hallucination,
        "hallucination_type": record.hallucination_type,
        "hallucination_score": record.hallucination_score,
        "judge_standpoint": judge_view,
        "generation_counterargument": generation_view,
        "conflict_points": conflicts,
        "corrections": corrections,
        "resolution_status": record.resolution_status,
        "judge_decision": record.judge_decision,
        "judge_confidence": record.judge_confidence,
        "original_content": record.original_content or "",
        "corrected_content": record.corrected_content or "",
        "correction_reason": record.correction_reason or "",
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "resolved_at": record.resolved_at.isoformat() if record.resolved_at else None,
    }


def _stage_timeline(task: AgentTask) -> list[Dict]:
    labels = {
        "diagnosis": "学情诊断",
        "knowledge_retrieval": "知识检索",
        "generation": "初稿生成",
        "judge_first": "初次审核",
        "debate": "辩论交叉验证",
        "final_revision": "最终修正",
        "complete": "放行",
    }
    ordered_stages = list(labels)
    logs = _as_list(task.execution_logs)
    by_stage = {}
    for log in logs:
        if isinstance(log, dict) and log.get("stage"):
            by_stage[log["stage"]] = log

    current_index = ordered_stages.index(task.flow_stage) if task.flow_stage in ordered_stages else -1
    timeline = []
    for index, stage in enumerate(ordered_stages):
        log = by_stage.get(stage, {})
        if stage in by_stage:
            status = "completed" if index < current_index or task.status == "completed" else "active"
        elif task.status == "completed" and index <= current_index:
            status = "completed"
        elif index < current_index:
            status = "completed"
        elif index == current_index and task.status in ("running", "pending"):
            status = "active"
        else:
            status = "pending"
        description = log.get("description", "")
        if stage == task.flow_stage and task.flow_description:
            description = task.flow_description
        timeline.append({
            "stage": stage,
            "label": labels[stage],
            "status": status,
            "progress": log.get("progress", 100 if status == "completed" else task.progress if stage == task.flow_stage else 0),
            "description": description,
            "timestamp": log.get("timestamp"),
        })
    return timeline

_AGENT_RESPONSES = {
    400: {"description": "请求参数错误（任务参数不合法、Agent类型无效等）"},
    401: {"description": "未授权（Token缺失或过期）"},
    403: {"description": "权限不足"},
    404: {"description": "任务不存在（task_id无效）"},
    409: {"description": "任务状态冲突（任务已在运行中）"},
    422: {"description": "请求体验证失败"},
    500: {"description": "服务器内部错误（Agent执行异常、LLM调用失败等）"},
}

# ========== Agent 状态接口 ==========

@router.get("/status", summary="获取所有Agent状态", response_model=BaseResponse[dict])
def get_all_agent_status(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    """
    获取三大Agent实时状态
    
    - 返回: 学情诊断Agent、领域知识生成Agent、审核裁判Agent的当前状态
    """
    try:
        statuses = orchestrator.get_all_agents_status()
        if current_user.is_admin:
            tasks = db.query(AgentTask).all()
        else:
            accessible_ids = LearnerService.get_accessible_learner_ids(
                db, current_user.user_id
            )
            tasks = (
                db.query(AgentTask)
                .filter(AgentTask.learner_id.in_(accessible_ids))
                .all()
            )
        statistics = _calculate_agent_statistics(tasks)
        for status_item in statuses:
            status_item.update(statistics.get(status_item["agent_type"], {}))
        
        LoggerUtil.log_api_request("GET /api/v1/agent/status", {})
        
        return success(data={
            "agents": statuses,
            "total": len(statuses),
        })
    except Exception as e:
        LoggerUtil.log_error("获取Agent状态失败", e)
        return error(message="获取Agent状态失败，请稍后重试")


@router.get("/status/{agent_type}", summary="获取指定Agent状态", response_model=BaseResponse[AgentStatusResponse])
def get_agent_status(
    agent_type: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    """
    获取指定Agent的状态
    
    - agent_type: diagnosis / generation / judge
    """
    try:
        status = orchestrator.get_agent_status(agent_type)
        if not status:
            return not_found(message=f"未找到Agent: {agent_type}")
        if current_user.is_admin:
            tasks = db.query(AgentTask).all()
        else:
            accessible_ids = LearnerService.get_accessible_learner_ids(
                db, current_user.user_id
            )
            tasks = (
                db.query(AgentTask)
                .filter(AgentTask.learner_id.in_(accessible_ids))
                .all()
            )
        status.update(_calculate_agent_statistics(tasks).get(agent_type, {}))
        
        return success(data=status)
    except Exception as e:
        LoggerUtil.log_error(f"获取{agent_type}状态失败", e)
        return error(message="获取Agent状态失败，请稍后重试")


# ========== 任务管理接口 ==========

@router.post("/tasks", summary="创建Agent任务", response_model=BaseResponse[dict], responses=_AGENT_RESPONSES)
def create_agent_task(
    request: CreateAgentTaskRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    """
    创建新的Agent协同任务
    
    - 支持任务类型:
      - learner_diagnosis: 学情诊断
      - resource_generation: 资源生成
      - full_pipeline: 完整流水线（诊断+生成+审核+辩论）
    """
    try:
        # 校验学习者是否存在
        learner = db.query(LearnerProfile).filter(
            LearnerProfile.id == request.learner_id
        ).first()
        if not learner:
            return bad_request(message=f"学习者不存在: {request.learner_id}")

        if not current_user.is_admin:
            if not LearnerService.check_data_permission(db, current_user.user_id, request.learner_id):
                return unauthorized("无权限为该学习者创建任务")

        task_input = {
            "target_topic": request.target_topic,
            "resource_type": request.resource_type,
            "industry": request.industry,
            **(request.input_data or {}),
        }
        if request.task_type in {"resource_generation", "full_pipeline"}:
            try:
                task_input["target_topic"] = normalize_resource_topic(task_input.get("target_topic"))
            except ValueError as exc:
                return bad_request(message=str(exc))

        task_info = orchestrator.create_task(
            learner_id=request.learner_id,
            task_name=request.task_name,
            task_type=request.task_type,
            input_data=task_input,
        )
        
        LoggerUtil.log_api_request("POST /api/v1/agent/tasks", request.model_dump())
        logger.info(f"创建Agent任务成功: task_id={task_info.get('task_id')}")
        
        return success(data=task_info, message="任务创建成功")
    except Exception as e:
        LoggerUtil.log_error("创建Agent任务失败", e)
        return error(message="创建任务失败，请稍后重试")


@router.post("/tasks/{task_id}/start", summary="启动任务执行", response_model=BaseResponse[dict], responses=_AGENT_RESPONSES)
def start_agent_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    """
    启动Agent任务执行
    
    - 使用后台线程立即执行，不阻塞HTTP响应
    - 可通过 /tasks/{task_id}/status 查询进度
    - 可通过 /tasks/{task_id}/events (SSE) 实时接收进度事件
    """
    try:
        task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
        if not task:
            return not_found(message="任务不存在")

        if not _check_task_permission(db, current_user, task):
            return unauthorized("无权限操作该任务")

        if task.status == "running":
            return bad_request(message="任务正在执行中")
        
        # 解析输入数据
        input_data = {}
        if task.input_data:
            try:
                input_data = json.loads(task.input_data)
            except Exception as e:
                logger.warning(f"解析任务 input_data 失败，使用默认值: task_id={task.id}, error={e}")
        
        if task.task_type in {"resource_generation", "full_pipeline"}:
            try:
                target_topic = normalize_resource_topic(input_data.get("target_topic"))
            except ValueError as exc:
                return bad_request(message=str(exc))
        else:
            target_topic = str(input_data.get("target_topic") or "未指定主题").strip()
        resource_type = input_data.get("resource_type", "guide")
        industry = input_data.get("industry")

        # 任务执行模式：USE_CELERY=true 走 Celery worker；否则走进程内 daemon 线程
        from app.config import settings

        if settings.USE_CELERY:
            from app.celery_app import full_pipeline_task

            full_pipeline_task.delay(
                task_id=task_id,
                learner_id=task.learner_id,
                target_topic=target_topic,
                resource_type=resource_type,
                industry=industry,
            )
            logger.info(f"启动Agent任务（Celery）: task_id={task_id}")
        else:
            def run_task():
                try:
                    orchestrator.run_full_pipeline(
                        task_id=task_id,
                        learner_id=task.learner_id,
                        target_topic=target_topic,
                        resource_type=resource_type,
                        industry=industry,
                    )
                except Exception as e:
                    logger.error(f"后台任务执行失败: task_id={task_id}, error={e}")

            thread = threading.Thread(target=run_task, daemon=True, name=f"agent-task-{task_id}")
            thread.start()
            logger.info(f"启动Agent任务（线程）: task_id={task_id}")
        
        return success(
            data={"task_id": task_id},
            message="任务已启动，可通过SSE端点实时接收进度",
        )
    except Exception as e:
        LoggerUtil.log_error("启动任务失败", e)
        return error(message="启动任务失败，请稍后重试")


@router.get("/tasks/{task_id}/events", summary="SSE实时任务进度流")
def task_events_stream(
    task_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Server-Sent Events 实时进度推送

    - 浏览器客户端使用 Authorization header 或 HttpOnly access cookie
    - 实时接收任务各阶段进度、辩论轮次、完成/失败事件
    - 连接关闭自动取消订阅
    """
    task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if not _check_task_permission(db, current_user, task):
        raise HTTPException(status_code=403, detail="无权限访问该任务")

    # 如果任务已完成或失败，先发送当前状态后关闭
    if task.status in ("completed", "failed"):
        async def completed_stream():
            data = json.dumps({
                "event": "task_completed" if task.status == "completed" else "task_failed",
                "data": {
                    "task_id": task_id,
                    "stage": task.flow_stage,
                    "progress": task.progress,
                    "description": task.flow_description,
                    "error": task.error_message,
                }
            }, ensure_ascii=False)
            yield f"data: {data}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(
            completed_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    
    # 订阅事件队列
    q = orchestrator.subscribe_task_events(task_id)
    
    async def event_generator():
        try:
            # 先发送当前状态作为初始事件
            initial = orchestrator.get_task_status(task_id)
            init_data = json.dumps({
                "event": "connected",
                "data": initial,
            }, ensure_ascii=False, default=str)
            yield f"data: {init_data}\n\n"
            
            # 持续读取事件队列
            while True:
                if await request.is_disconnected():
                    break
                
                try:
                    event = await asyncio.to_thread(q.get, timeout=1.0)
                except Exception:
                    # 超时检查连接状态
                    continue
                
                if event is None:
                    break
                
                event_data = json.dumps(event, ensure_ascii=False, default=str)
                yield f"data: {event_data}\n\n"
                
                # 任务结束后发送 DONE 并关闭
                if event.get("event") in ("task_completed", "task_failed"):
                    yield "data: [DONE]\n\n"
                    break
        finally:
            orchestrator.unsubscribe_task_events(task_id, q)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/tasks/{task_id}/status", summary="查询任务状态", response_model=BaseResponse[TaskStatusResponse])
def get_task_status(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    """
    查询任务实时状态和进度

    - 返回当前阶段、进度百分比、错误信息等
    """
    try:
        task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
        if not task:
            return not_found(message="任务不存在")
        if not _check_task_permission(db, current_user, task):
            return unauthorized("无权限查看该任务")

        status = orchestrator.get_task_status(task_id)
        if status.get("error") == "任务不存在":
            return not_found(message="任务不存在")
        
        return success(data=status)
    except Exception as e:
        LoggerUtil.log_error("查询任务状态失败", e)
        return error(message="查询状态失败，请稍后重试")


@router.get("/tasks/{task_id}/logs", summary="查询任务执行日志", response_model=BaseResponse[list[TaskLogEntry]])
def get_task_logs(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    """
    查询任务执行日志（供前端可视化）
    
    - 返回按时间排序的执行日志列表
    """
    try:
        task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
        if not task:
            return not_found(message="任务不存在")
        if not _check_task_permission(db, current_user, task):
            return unauthorized("无权限查看该任务日志")

        logs = orchestrator.get_task_logs(task_id)
        
        # 如果内存中没有，从数据库查辩论记录
        if not logs:
            debates = db.query(DebateRecord).filter(
                DebateRecord.task_id == task_id
            ).order_by(DebateRecord.debate_round).all()
            
            logs = [
                {
                    "stage": f"debate_round_{d.debate_round}",
                    "progress": 70 + d.debate_round * 10,
                    "description": f"第{d.debate_round}轮辩论",
                    "timestamp": d.created_at.isoformat() if d.created_at else "",
                }
                for d in debates
            ]
        
        return success(data={
            "task_id": task_id,
            "logs": logs,
            "total": len(logs),
        })
    except Exception as e:
        LoggerUtil.log_error("查询任务日志失败", e)
        return error(message="查询日志失败，请稍后重试")


@router.get("/tasks/{task_id}/evidence", summary="获取任务完整证据链")
def get_task_evidence(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    """返回任务摘要、时间线、辩论、知识来源、修正对比和决策依据。"""
    try:
        task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
        if not task:
            return not_found(message="任务不存在")
        if not _check_task_permission(db, current_user, task):
            return unauthorized("无权限查看该任务证据链")

        output_data = _parse_json_value(task.output_data, {})
        snapshot = output_data.get("evidence", {}) if isinstance(output_data, dict) else {}
        if not isinstance(snapshot, dict):
            snapshot = {}

        resource_id = output_data.get("resource_id") if isinstance(output_data, dict) else None
        resource = None
        if resource_id:
            resource = db.query(LearningResource).filter(LearningResource.id == resource_id).first()
        if resource is None:
            resource = db.query(LearningResource).filter(
                LearningResource.generation_task_id == task_id
            ).first()
        if resource is not None:
            resource_id = resource.id

        source_slice_ids = [
            int(value) for value in _as_list(resource.source_slice_ids if resource else snapshot.get("source_slice_ids"))
            if str(value).isdigit()
        ]
        snapshot_knowledge = [item for item in _as_list(snapshot.get("knowledge")) if isinstance(item, dict)]
        snapshot_by_slice = {
            int(item["slice_id"]): item
            for item in snapshot_knowledge
            if item.get("slice_id") is not None and str(item.get("slice_id")).isdigit()
        }
        if not source_slice_ids:
            source_slice_ids = list(snapshot_by_slice)

        source_slices = []
        if source_slice_ids:
            source_slices = db.query(KnowledgeSlice).filter(
                KnowledgeSlice.id.in_(source_slice_ids)
            ).order_by(KnowledgeSlice.doc_id, KnowledgeSlice.slice_index).all()

        source_doc_ids = [
            int(value) for value in _as_list(resource.source_doc_ids if resource else snapshot.get("source_doc_ids"))
            if str(value).isdigit()
        ]
        source_doc_ids.extend(slice_item.doc_id for slice_item in source_slices if slice_item.doc_id not in source_doc_ids)
        source_docs = []
        if source_doc_ids:
            source_docs = db.query(KnowledgeDoc).filter(KnowledgeDoc.id.in_(source_doc_ids)).all()
        source_doc_map = {doc.id: doc for doc in source_docs}

        knowledge_evidence = []
        for source_slice in source_slices:
            metadata = snapshot_by_slice.get(source_slice.id, {})
            doc = source_doc_map.get(source_slice.doc_id)
            knowledge_evidence.append({
                "slice_id": source_slice.id,
                "doc_id": source_slice.doc_id,
                "doc_title": doc.title if doc else "",
                "title": source_slice.title,
                "content": source_slice.content,
                "slice_index": source_slice.slice_index,
                "similarity": metadata.get("similarity"),
                "quality_score": source_slice.quality_score,
                "relation": "supports",
            })

        serialized_debates = [
            _serialize_debate_record(record)
            for record in db.query(DebateRecord).filter(
                DebateRecord.task_id == task_id
            ).order_by(DebateRecord.debate_round).all()
        ]

        initial_audit = snapshot.get("initial_audit") if isinstance(snapshot.get("initial_audit"), dict) else {}
        final_audit = snapshot.get("final_audit") if isinstance(snapshot.get("final_audit"), dict) else {}
        if not final_audit:
            final_audit = initial_audit

        all_conflicts = [
            point
            for debate in serialized_debates
            for point in debate.get("conflict_points", [])
        ]
        all_corrections = [
            correction
            for debate in serialized_debates
            for correction in debate.get("corrections", [])
        ]
        source_similarity = [
            float(item["similarity"])
            for item in knowledge_evidence
            if isinstance(item.get("similarity"), (int, float))
        ]
        source_quality = [
            float(item["quality_score"])
            for item in knowledge_evidence
            if isinstance(item.get("quality_score"), (int, float)) and item.get("quality_score") > 0
        ]
        evidence_coverage = _score_percent(final_audit.get("evidence_coverage"))
        if evidence_coverage is None:
            evidence_coverage = 100.0 if knowledge_evidence else 0.0
        source_relevance = _score_percent(
            sum(source_similarity) / len(source_similarity)
            if source_similarity
            else sum(source_quality) / len(source_quality)
            if source_quality
            else None
        )
        factual_consistency = _score_percent(final_audit.get("consistency_score"))
        if factual_consistency is None and resource is not None and resource.validation_score:
            factual_consistency = _score_percent(resource.validation_score)
        resolved_statuses = {"resolved", "accepted", "corrected"}
        if serialized_debates:
            resolved_count = sum(
                1 for debate in serialized_debates if debate.get("resolution_status") in resolved_statuses
            )
            issue_resolution = round(resolved_count / len(serialized_debates) * 100, 1)
        else:
            issue_resolution = 100.0 if task.validated else 0.0
        if source_docs:
            valid_sources = sum(1 for doc in source_docs if doc.is_enabled and doc.status == "ready")
            source_validity = round(valid_sources / len(source_docs) * 100, 1)
        else:
            source_validity = 0.0

        breakdown = [
            {"key": "evidence_coverage", "label": "证据覆盖度", "weight": 35, "score": evidence_coverage},
            {"key": "source_relevance", "label": "来源相关度", "weight": 25, "score": source_relevance or 0.0},
            {"key": "factual_consistency", "label": "事实一致性", "weight": 20, "score": factual_consistency or 0.0},
            {"key": "issue_resolution", "label": "审核问题解决率", "weight": 15, "score": issue_resolution},
            {"key": "source_validity", "label": "来源有效性", "weight": 5, "score": source_validity},
        ]
        has_sufficient_evidence = bool(knowledge_evidence and source_validity > 0)
        weighted_confidence = round(sum(item["score"] * item["weight"] for item in breakdown) / 100, 1)
        confidence = weighted_confidence if has_sufficient_evidence else None

        latest_decision = serialized_debates[-1].get("judge_decision") if serialized_debates else None
        passed = final_audit.get("passed")
        if passed is None and resource is not None:
            passed = resource.validation_passed
        if not has_sufficient_evidence:
            final_decision = "insufficient_evidence"
        elif latest_decision == "rejected" or (passed is False and task.status == "failed"):
            final_decision = "rejected"
        elif passed:
            final_decision = "revised_approved" if all_corrections else "approved"
        else:
            final_decision = "rejected"

        initial_content = snapshot.get("initial_content", "")
        if not initial_content and serialized_debates:
            initial_content = serialized_debates[0].get("original_content", "")
        final_content = resource.content if resource is not None else ""
        if not final_content and serialized_debates:
            final_content = serialized_debates[-1].get("corrected_content", "")

        key_correction = None
        if all_corrections:
            first_correction = all_corrections[0]
            if isinstance(first_correction, dict):
                correction_text = first_correction.get("description") or first_correction.get("suggested_fix") or ""
                correction_reason = first_correction.get("reason") or first_correction.get("suggested_fix") or correction_text
            else:
                correction_text = str(first_correction)
                correction_reason = correction_text
            key_correction = {
                "original": initial_content,
                "revised": final_content,
                "description": correction_text,
                "reason": correction_reason,
            }

        unresolved_risks = [
            point.get("description", str(point)) if isinstance(point, dict) else str(point)
            for point in all_conflicts
            if not serialized_debates or serialized_debates[-1].get("resolution_status") not in resolved_statuses
        ]
        decision_reason = {
            "release_reason": (
                "证据充分，审核问题已解决，允许放行。"
                if final_decision in ("approved", "revised_approved")
                else "当前证据不足，暂不允许将内容标记为可信。"
                if final_decision == "insufficient_evidence"
                else "审核未通过，内容仍存在未解决风险。"
            ),
            "unresolved_risks": unresolved_risks,
            "review_rules": [
                "证据覆盖度、来源相关度、事实一致性、问题解决率、来源有效性按固定权重计算。",
                "缺少有效知识来源时，可信度显示为证据不足。",
            ],
        }

        learner = db.query(LearnerProfile).filter(LearnerProfile.id == task.learner_id).first()
        diagnosis = snapshot.get("diagnosis") if isinstance(snapshot.get("diagnosis"), dict) else None
        task_payload = {
            "task_id": task.id,
            "task_name": task.task_name,
            "task_type": task.task_type,
            "status": task.status,
            "flow_stage": task.flow_stage,
            "progress": task.progress,
            "learner_id": task.learner_id,
            "resource_id": resource_id,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "updated_at": task.updated_at.isoformat() if task.updated_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        }
        summary = {
            "final_decision": final_decision,
            "confidence": confidence,
            "credibility": final_audit.get("credibility") if has_sufficient_evidence else "no_evidence",
            "has_sufficient_evidence": has_sufficient_evidence,
            "stats": {
                "debate_rounds": len(serialized_debates),
                "issues_found": len(all_conflicts),
                "corrections_applied": len(all_corrections),
                "source_count": len(knowledge_evidence),
            },
            "key_correction": key_correction,
            "confidence_breakdown": breakdown,
        }

        return success(data={
            "task": task_payload,
            "learner": {
                "id": learner.id if learner else task.learner_id,
                "name": learner.real_name if learner else None,
                "diagnosis": diagnosis,
            },
            "summary": summary,
            "timeline": _stage_timeline(task),
            "debate_records": serialized_debates,
            "knowledge_evidence": knowledge_evidence,
            "source_documents": [
                {
                    "id": doc.id,
                    "title": doc.title,
                    "industry": doc.industry,
                    "source": doc.source,
                    "version": doc.version,
                    "status": doc.status,
                    "is_enabled": doc.is_enabled,
                }
                for doc in source_docs
            ],
            "initial_generation": {"content": initial_content},
            "final_generation": {
                "content": final_content,
                "title": ResourceServiceHelper.safe_resource_title(resource) if resource else None,
                "resource_type": resource.resource_type if resource else None,
            },
            "revision_comparison": {
                "original_content": initial_content,
                "final_content": final_content,
                "corrections": all_corrections,
                "has_changes": bool(key_correction and initial_content != final_content),
            },
            "decision": decision_reason,
        })
    except Exception as e:
        LoggerUtil.log_error("获取任务证据链失败", e)
        return error(message="获取任务证据链失败，请稍后重试")


@router.get("/tasks", summary="获取任务列表")
def get_task_list(
    learner_id: Optional[int] = None,
    status: Optional[str] = None,
    task_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    """
    分页获取Agent任务列表
    
    - 支持按学习者、状态、类型筛选
    """
    try:
        query = db.query(AgentTask)

        if learner_id:
            if not current_user.is_admin:
                if not LearnerService.check_data_permission(db, current_user.user_id, learner_id):
                    return unauthorized("无权限查看该学习者任务")
            query = query.filter(AgentTask.learner_id == learner_id)
        elif not current_user.is_admin:
            # 非管理员默认仅可见有权访问的学习者的任务（不含无归属任务）
            accessible_ids = LearnerService.get_accessible_learner_ids(
                db, current_user.user_id
            )
            query = query.filter(AgentTask.learner_id.in_(accessible_ids))
        if status:
            query = query.filter(AgentTask.status == status)
        if task_type:
            query = query.filter(AgentTask.task_type == task_type)
        
        total = query.count()
        
        tasks = (
            query.order_by(AgentTask.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        
        task_list = []
        for task in tasks:
            task_list.append({
                "task_id": task.id,
                "task_name": task.task_name,
                "task_type": task.task_type,
                "agent_type": task.agent_type,
                "status": task.status,
                "progress": task.progress,
                "flow_stage": task.flow_stage,
                "flow_description": task.flow_description,
                "learner_id": task.learner_id,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "duration_ms": task.duration_ms,
                "error_message": task.error_message,
            })
        
        return paged_success(
            items=task_list,
            total=total,
            page=page,
            page_size=page_size,
        )
    except Exception as e:
        LoggerUtil.log_error("获取任务列表失败", e)
        return error(message="获取任务列表失败，请稍后重试")


# ========== 学情诊断接口 ==========

@router.post("/diagnose", summary="执行学情诊断", responses=_AGENT_RESPONSES)
def run_diagnosis(
    request: DiagnosisRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    """
    调用学情诊断Agent分析学习者画像
    
    - 输出: 能力评分、知识盲区、难度推荐、学习建议
    """
    try:
        # 获取学习者
        learner = db.query(LearnerProfile).filter(
            LearnerProfile.id == request.learner_id
        ).first()
        if not learner:
            return not_found(message=f"学习者不存在: {request.learner_id}")

        if not current_user.is_admin:
            if not LearnerService.check_data_permission(db, current_user.user_id, request.learner_id):
                return unauthorized("无权限为该学习者执行诊断")

        # 转换为字典
        learner_dict = {}
        for column in learner.__table__.columns:
            value = getattr(learner, column.name)
            learner_dict[column.name] = value
        
        # 创建任务记录
        task = AgentTask(
            learner_id=request.learner_id,
            task_name=f"学情诊断 - {learner.real_name or '未命名'}",
            task_type="learner_diagnosis",
            agent_type="diagnosis",
            flow_stage="diagnosis",
            flow_description="学情诊断执行中",
            input_data=json.dumps(learner_dict, ensure_ascii=False, default=str),
            status="running",
            progress=0,
        )
        db.add(task)
        db.flush()
        task_id = task.id
        db.commit()
        
        # 执行诊断
        from app.agents.diagnosis_agent import DiagnosisAgent
        agent = DiagnosisAgent()
        result = agent.run(
            task_id=task_id,
            input_data={
                "learner_id": request.learner_id,
                "learner_profile": learner_dict,
            },
        )
        
        # 更新任务
        task.status = "completed"
        task.progress = 100
        task.output_data = json.dumps(result, ensure_ascii=False, default=str)
        task.completed_at = utcnow_naive()
        if result.get("_meta", {}).get("duration_ms"):
            task.duration_ms = result["_meta"]["duration_ms"]
        db.commit()
        
        LoggerUtil.log_agent_task(
            task_id=task_id,
            agent_type="diagnosis",
            action="complete",
            status="completed",
            details=result,
        )
        
        return success(data=result, message="学情诊断完成")
    except Exception as e:
        LoggerUtil.log_error("学情诊断失败", e)
        try:
            task.status = "failed"
            task.error_message = str(e)
            task.completed_at = utcnow_naive()
            db.commit()
        except Exception:
            db.rollback()
        return error(message="学情诊断失败，请稍后重试")


# ========== 辩论记录接口 ==========

@router.get("/debate/{task_id}", summary="获取辩论记录")
def get_debate_records(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    """
    获取指定任务的辩论交叉验证记录
    
    - 返回所有辩论轮次的完整记录
    - 包含: 裁判观点、生成Agent回应、冲突点、修正方案
    """
    try:
        task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
        if not task:
            return not_found(message="任务不存在")
        if not _check_task_permission(db, current_user, task):
            return unauthorized("无权限查看该任务辩论记录")

        records = db.query(DebateRecord).filter(
            DebateRecord.task_id == task_id
        ).order_by(DebateRecord.debate_round).all()
        
        debate_list = [_serialize_debate_record(record) for record in records]
        
        return success(data={
            "task_id": task_id,
            "debate_records": debate_list,
            "total_rounds": len(debate_list),
            "has_hallucination": any(d["is_hallucination"] for d in debate_list),
            "all_resolved": all(
                d["resolution_status"] == "resolved" for d in debate_list
            ) if debate_list else True,
        })
    except Exception as e:
        LoggerUtil.log_error("获取辩论记录失败", e)
        return error(message="获取辩论记录失败，请稍后重试")


# ========== 指标统计接口 ==========

@router.get("/metrics/hallucination", summary="幻觉率统计", response_model=BaseResponse[MetricsResponse])
def get_hallucination_metrics(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    """
    统计幻觉率等核心指标
    
    - 幻觉率 = 检出幻觉的内容数 / 总内容数
    - 返回: 总数量、幻觉数量、幻觉率、平均得分、通过率
    """
    try:
        metrics = MetricsUtil.calculate_hallucination_metrics(db)
        standard = MetricService.calculate_metrics(
            db,
            scope="global",
            metric_ids=["hallucination_rate"],
        )
        return success(data={**metrics, "metric": standard[0] if standard else None})

    except Exception as e:
        LoggerUtil.log_error("获取幻觉率统计失败", e)
        return error(message="获取统计失败，请稍后重试")


@router.get("/metrics/performance", summary="Agent性能统计")
def get_agent_performance(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    """
    Agent执行性能统计
    
    - 总任务数、成功数、失败数
    - 平均执行时长
    """
    try:
        from sqlalchemy import func, case
        
        total, success_count, failed_count, running_count, avg_duration = db.query(
            func.count(AgentTask.id),
            func.coalesce(func.sum(case((AgentTask.status == "completed", 1), else_=0)), 0),
            func.coalesce(func.sum(case((AgentTask.status == "failed", 1), else_=0)), 0),
            func.coalesce(func.sum(case((AgentTask.status == "running", 1), else_=0)), 0),
            func.coalesce(func.avg(
                case(
                    (AgentTask.status == "completed", AgentTask.duration_ms),
                    else_=None,
                )
            ), 0),
        ).one()
        
        return success(data={
            "total_tasks": total,
            "success_count": success_count,
            "failed_count": failed_count,
            "running_count": running_count,
            "success_rate": round(success_count / total * 100, 2) if total > 0 else None,
            "avg_duration_ms": round(float(avg_duration or 0), 2),
        })
    except Exception as e:
        LoggerUtil.log_error("获取性能统计失败", e)
        return error(message="获取性能统计失败，请稍后重试")


# ========== 快速执行接口 ==========

@router.post("/run/full-pipeline", summary="一键执行完整流水线", responses=_AGENT_RESPONSES)
def run_full_pipeline(
    request: GenerationRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    """
    一键执行完整Agent协同流水线
    
    流程: 学情诊断 → 知识库检索 → 内容生成 → 初次审核 → 辩论交叉验证 → 最终输出
    
    - 后台线程立即异步执行
    - 返回任务ID，用于查询进度或订阅SSE事件流
    """
    try:
        # 校验学习者
        learner = db.query(LearnerProfile).filter(
            LearnerProfile.id == request.learner_id
        ).first()
        if not learner:
            return not_found(message=f"学习者不存在: {request.learner_id}")

        if not current_user.is_admin:
            if not LearnerService.check_data_permission(db, current_user.user_id, request.learner_id):
                return unauthorized("无权限为该学习者启动流水线")
        context_error = _validate_training_context(db, request.learner_id, request.training_context)
        if context_error:
            return bad_request(context_error)

        # 创建任务
        task = AgentTask(
            learner_id=request.learner_id,
            task_name=f"生成{request.target_topic}学习资源",
            task_type="full_pipeline",
            agent_type="system",
            flow_stage="init",
            flow_description="任务初始化",
            input_data=json.dumps({
                "target_topic": request.target_topic,
                "resource_type": request.resource_type,
                "industry": request.industry,
                "training_context": request.training_context,
            }, ensure_ascii=False),
            status="pending",
            progress=0,
        )
        db.add(task)
        db.flush()
        task_id = task.id
        db.commit()
        
        # 后台线程立即启动（支持SSE实时进度）
        def run_task():
            try:
                orchestrator.run_full_pipeline(
                    task_id=task_id,
                    learner_id=request.learner_id,
                    target_topic=request.target_topic,
                    resource_type=request.resource_type,
                    industry=request.industry,
                    training_context=request.training_context,
                )
            except Exception as e:
                logger.error(f"完整流水线执行失败: task_id={task_id}, error={e}")
        
        t = threading.Thread(target=run_task, daemon=True, name=f"full-pipeline-{task_id}")
        t.start()
        
        logger.info(
            f"启动完整流水线: task_id={task_id}, "
            f"topic={request.target_topic}, type={request.resource_type}"
        )
        
        return success(
            data={"task_id": task_id},
            message="完整流水线已启动，可通过 /agent/tasks/{task_id}/events 订阅实时进度",
        )
    except Exception as e:
        LoggerUtil.log_error("启动完整流水线失败", e)
        return error(message="启动失败，请稍后重试")
