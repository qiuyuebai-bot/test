"""
Agent 协同调度 API 路由
"""
import asyncio
import json
import threading
import secrets
import time
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
    paged_success,
    BaseResponse,
)
from app.schemas.agent import (
    CreateAgentTaskRequest,
    DiagnosisRequest,
    GenerationRequest,
)
from app.agents.orchestrator import orchestrator
from app.models import AgentTask, DebateRecord, LearnerProfile
from app.utils.logger import LoggerUtil
from app.utils.auth import get_current_user, CurrentUser

router = APIRouter(prefix="/agent", tags=["Agent协同调度"])

# SSE 短期票据存储（30 秒有效，一次性使用，避免 JWT Token 泄露到 URL/日志）
_SSE_TICKETS: Dict[str, Dict] = {}
_SSE_TICKET_TTL = 30


def _issue_sse_ticket(user_id: int, task_id: int) -> str:
    _cleanup_sse_tickets()
    ticket = secrets.token_urlsafe(32)
    _SSE_TICKETS[ticket] = {
        "user_id": user_id,
        "task_id": task_id,
        "expires_at": time.time() + _SSE_TICKET_TTL,
    }
    return ticket


def _consume_sse_ticket(ticket: str, task_id: int) -> Optional[int]:
    _cleanup_sse_tickets()
    info = _SSE_TICKETS.pop(ticket, None)
    if not info or info["expires_at"] < time.time():
        return None
    if info["task_id"] != task_id:
        return None
    return info["user_id"]


def _cleanup_sse_tickets() -> None:
    now = time.time()
    expired = [k for k, v in _SSE_TICKETS.items() if v["expires_at"] < now]
    for k in expired:
        _SSE_TICKETS.pop(k, None)


# ========== Agent 状态接口 ==========

@router.get("/status", summary="获取所有Agent状态")
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
        
        LoggerUtil.log_api_request("GET /api/v1/agent/status", {})
        
        return success(data={
            "agents": statuses,
            "total": len(statuses),
        })
    except Exception as e:
        LoggerUtil.log_error("获取Agent状态失败", e)
        return error(message=f"获取Agent状态失败: {str(e)}")


@router.get("/status/{agent_type}", summary="获取指定Agent状态")
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
        
        return success(data=status)
    except Exception as e:
        LoggerUtil.log_error(f"获取{agent_type}状态失败", e)
        return error(message=f"获取Agent状态失败: {str(e)}")


# ========== 任务管理接口 ==========

@router.post("/tasks", summary="创建Agent任务")
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
        
        task_info = orchestrator.create_task(
            learner_id=request.learner_id,
            task_name=request.task_name,
            task_type=request.task_type,
            input_data={
                "target_topic": request.target_topic,
                "resource_type": request.resource_type,
                "industry": request.industry,
                **(request.input_data or {}),
            },
        )
        
        LoggerUtil.log_api_request("POST /api/v1/agent/tasks", request.model_dump())
        logger.info(f"创建Agent任务成功: task_id={task_info.get('task_id')}")
        
        return success(data=task_info, message="任务创建成功")
    except Exception as e:
        LoggerUtil.log_error("创建Agent任务失败", e)
        return error(message=f"创建任务失败: {str(e)}")


@router.post("/tasks/{task_id}/start", summary="启动任务执行")
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
        
        if task.status == "running":
            return bad_request(message="任务正在执行中")
        
        # 解析输入数据
        input_data = {}
        if task.input_data:
            try:
                input_data = json.loads(task.input_data)
            except Exception as e:
                logger.warning(f"解析任务 input_data 失败，使用默认值: task_id={task.id}, error={e}")
        
        target_topic = input_data.get("target_topic", "未指定主题")
        resource_type = input_data.get("resource_type", "guide")
        industry = input_data.get("industry")
        
        # 使用后台线程立即启动（而非BackgroundTasks，后者在响应后才执行）
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
        
        logger.info(f"启动Agent任务: task_id={task_id}")
        
        return success(
            data={"task_id": task_id},
            message="任务已启动，可通过SSE端点实时接收进度",
        )
    except Exception as e:
        LoggerUtil.log_error("启动任务失败", e)
        return error(message=f"启动任务失败: {str(e)}")


@router.post("/tasks/{task_id}/stream-ticket", summary="获取SSE短期票据")
def create_sse_ticket(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    """签发一次性短期票据用于 SSE 连接鉴权（30 秒有效），避免 JWT Token 泄露到 URL/日志"""
    task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
    if not task:
        return not_found("任务不存在")
    ticket = _issue_sse_ticket(current_user.id, task_id)
    return success(data={"ticket": ticket, "expires_in": _SSE_TICKET_TTL})


@router.get("/tasks/{task_id}/events", summary="SSE实时任务进度流")
async def task_events_stream(
    task_id: int,
    request: Request,
    ticket: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Server-Sent Events 实时进度推送

    - 前端先调用 POST /tasks/{task_id}/stream-ticket 获取短期票据
    - 再用 ?ticket= 参数连接此端点（票据 30 秒有效，一次性消费）
    - 实时接收任务各阶段进度、辩论轮次、完成/失败事件
    - 连接关闭自动取消订阅
    """
    from app.models import User

    if not ticket:
        raise HTTPException(status_code=401, detail="未提供SSE票据")

    user_id = _consume_sse_ticket(ticket, task_id)
    if user_id is None:
        raise HTTPException(status_code=401, detail="票据无效或已过期")

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="用户不存在或已被禁用")

    task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
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


@router.get("/tasks/{task_id}/status", summary="查询任务状态")
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
        status = orchestrator.get_task_status(task_id)
        if status.get("error") == "任务不存在":
            return not_found(message="任务不存在")
        
        return success(data=status)
    except Exception as e:
        LoggerUtil.log_error("查询任务状态失败", e)
        return error(message=f"查询状态失败: {str(e)}")


@router.get("/tasks/{task_id}/logs", summary="查询任务执行日志")
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
        return error(message=f"查询日志失败: {str(e)}")


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
            query = query.filter(AgentTask.learner_id == learner_id)
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
        return error(message=f"获取任务列表失败: {str(e)}")


# ========== 学情诊断接口 ==========

@router.post("/diagnose", summary="执行学情诊断")
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
        return error(message=f"学情诊断失败: {str(e)}")


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
        records = db.query(DebateRecord).filter(
            DebateRecord.task_id == task_id
        ).order_by(DebateRecord.debate_round).all()
        
        debate_list = []
        for record in records:
            try:
                judge_view = json.loads(record.agent_judge_view) if record.agent_judge_view else {}
                gen_view = json.loads(record.agent_generation_view) if record.agent_generation_view else {}
                conflicts = json.loads(record.conflict_description) if record.conflict_description else []
                corrections = json.loads(record.judge_notes) if record.judge_notes else []
            except (json.JSONDecodeError, TypeError, ValueError):
                judge_view = {}
                gen_view = {}
                conflicts = []
                corrections = []
            
            debate_list.append({
                "round": record.debate_round,
                "debate_type": record.debate_type,
                "has_conflict": record.has_conflict,
                "conflict_type": record.conflict_type,
                "conflict_severity": record.conflict_severity,
                "is_hallucination": record.is_hallucination,
                "hallucination_type": record.hallucination_type,
                "hallucination_score": record.hallucination_score,
                "judge_standpoint": judge_view,
                "generation_counterargument": gen_view,
                "conflict_points": conflicts,
                "corrections": corrections,
                "resolution_status": record.resolution_status,
                "judge_decision": record.judge_decision,
                "judge_confidence": record.judge_confidence,
                "created_at": record.created_at.isoformat() if record.created_at else None,
                "resolved_at": record.resolved_at.isoformat() if record.resolved_at else None,
            })
        
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
        return error(message=f"获取辩论记录失败: {str(e)}")


# ========== 指标统计接口 ==========

@router.get("/metrics/hallucination", summary="幻觉率统计")
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
        from sqlalchemy import func, case
        
        total, hallucination_count, passed_count = db.query(
            func.count(DebateRecord.id),
            func.coalesce(func.sum(case((DebateRecord.is_hallucination == True, 1), else_=0)), 0),
            func.coalesce(func.sum(case((DebateRecord.resolution_status == "resolved", 1), else_=0)), 0),
        ).one()
        
        hallucination_rate = (hallucination_count / total * 100) if total > 0 else 0
        pass_rate = (passed_count / total * 100) if total > 0 else 100
        
        return success(data={
            "total_checks": total,
            "hallucination_count": hallucination_count,
            "hallucination_rate": round(hallucination_rate, 2),
            "pass_rate": round(pass_rate, 2),
            "unit": "%",
        })
    except Exception as e:
        LoggerUtil.log_error("获取幻觉率统计失败", e)
        return error(message=f"获取统计失败: {str(e)}")


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
            "success_rate": round(success_count / total * 100, 2) if total > 0 else 0,
            "avg_duration_ms": round(float(avg_duration or 0), 2),
        })
    except Exception as e:
        LoggerUtil.log_error("获取性能统计失败", e)
        return error(message=f"获取性能统计失败: {str(e)}")


# ========== 快速执行接口 ==========

@router.post("/run/full-pipeline", summary="一键执行完整流水线")
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
        return error(message=f"启动失败: {str(e)}")
