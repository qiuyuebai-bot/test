"""
健康检查、系统信息、核心指标接口
"""
import time
import platform
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from loguru import logger

from app.config import settings
from app.database import SessionLocal
from app.schemas.response import success
from app.middleware import prometheus_metrics_endpoint


router = APIRouter(tags=["运维"])


@router.get("/", tags=["基础"])
async def root(request: Request):
    """根路径 - 系统信息"""
    return success({
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "uptime_seconds": round(time.time() - request.app.state.start_time, 1),
    })


@router.get("/health", tags=["运维"])
@router.get("/health/live", tags=["运维"])
@router.get("/api/v1/health", tags=["运维"])
@router.get("/api/v1/health/live", tags=["运维"])
async def health_liveness(request: Request):
    """存活检查（Liveness Probe）"""
    return JSONResponse(
        status_code=200,
        content={
            "code": 200,
            "message": "alive",
            "data": {
                "status": "alive",
                "uptime_seconds": round(time.time() - request.app.state.start_time, 1),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            },
        },
    )


@router.get("/health/ready", tags=["运维"])
@router.get("/api/v1/health/ready", tags=["运维"])
async def health_readiness(request: Request):
    """就绪检查（Readiness Probe）"""
    checks = {}
    overall_status = "ready"
    http_status = 200

    # 1. 数据库检查
    db_latency_ms = 0
    try:
        db_start = time.time()
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            db_latency_ms = round((time.time() - db_start) * 1000, 1)
        finally:
            db.close()
    except Exception as e:
        checks["database"] = {"status": "down", "error": str(e)[:200]}
        overall_status = "not_ready"
        http_status = 503
    else:
        checks["database"] = {"status": "up", "latency_ms": db_latency_ms}

    # 2. Chroma 向量库检查
    try:
        from app.domains.knowledge.service import _get_chroma_collection
        collection = _get_chroma_collection()
        if collection is not None:
            collection.count()
            checks["chroma"] = {"status": "up"}
        else:
            checks["chroma"] = {"status": "fallback", "note": "Chroma不可用，使用数据库关键词检索降级模式"}
    except Exception as e:
        checks["chroma"] = {"status": "degraded", "error": str(e)[:200], "note": "使用数据库关键词检索降级模式"}

    # 3. 系统资源检查
    try:
        import psutil
        mem = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=0)
        checks["system"] = {
            "status": "up",
            "memory_percent": mem.percent,
            "cpu_percent": cpu,
            "disk_free_gb": round(psutil.disk_usage(".").free / (1024**3), 2),
        }
        if mem.percent > 95:
            checks["system"]["status"] = "warning"
            checks["system"]["note"] = "内存使用率过高"
    except ImportError:
        checks["system"] = {"status": "unknown", "note": "psutil 未安装，跳过系统资源检查"}
    except Exception as e:
        checks["system"] = {"status": "unknown", "error": str(e)[:100]}

    # 4. LLM 配置检查
    from app.utils.llm import LLMUtil
    checks["llm"] = {
        "status": "configured" if LLMUtil.is_available() else "mock_mode",
        "model": settings.OPENAI_MODEL_NAME,
        "note": "API可用" if LLMUtil.is_available() else "LLM未配置，使用Mock响应",
    }

    return JSONResponse(
        status_code=http_status,
        content={
            "code": http_status,
            "message": overall_status,
            "data": {
                "status": overall_status,
                "checks": checks,
                "uptime_seconds": round(time.time() - request.app.state.start_time, 1),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "version": settings.APP_VERSION,
                "python_version": platform.python_version(),
            },
        },
    )


@router.get("/metrics", tags=["运维"])
@router.get("/api/v1/metrics/prometheus", tags=["运维"])
async def get_prometheus_metrics(request: Request):
    """Prometheus /metrics 端点"""
    return await prometheus_metrics_endpoint(request)


@router.get("/api/v1/info", tags=["基础"])
async def system_info():
    """系统信息接口"""
    return success({
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "api_prefix": settings.API_PREFIX,
        "debug_mode": settings.DEBUG_MODE,
        "features": [
            "多智能体协同",
            "个性化资源生成",
            "幻觉检测与纠偏",
            "自适应导学",
        ],
    })


@router.get("/api/v1/metrics", tags=["指标"])
async def get_core_metrics():
    """获取核心量化指标（从数据库真实统计）"""
    from app.models import LearningResource, AgentTask, DebateRecord, KnowledgeSlice
    from sqlalchemy import func, case

    db = SessionLocal()
    try:
        total_resources, active_learners, avg_match = db.query(
            func.count(LearningResource.id),
            func.count(func.distinct(LearningResource.learner_id)),
            func.avg(LearningResource.match_score),
        ).one()
        total_resources = total_resources or 0
        active_learners = active_learners or 0
        resource_match_accuracy = round(float(avg_match or 0), 1)

        total_tasks, completed_tasks = db.query(
            func.count(AgentTask.id),
            func.coalesce(
                func.sum(case((AgentTask.status == "completed", 1), else_=0)), 0
            ),
        ).one()
        agent_success_rate = (
            round(completed_tasks / total_tasks * 100, 1) if total_tasks > 0 else 0
        )

        total_debates, hallucination_count = db.query(
            func.count(DebateRecord.id),
            func.coalesce(
                func.sum(case((DebateRecord.is_hallucination == True, 1), else_=0)), 0
            ),
        ).one()
        hallucination_rate = (
            round(hallucination_count / total_debates * 100, 1) if total_debates > 0 else 0
        )

        total_slices, indexed_slices = db.query(
            func.count(KnowledgeSlice.id),
            func.coalesce(
                func.sum(case((KnowledgeSlice.is_indexed == True, 1), else_=0)), 0
            ),
        ).one()
        knowledge_coverage_rate = (
            round(indexed_slices / total_slices * 100, 1) if total_slices > 0 else 0
        )

        return success({
            "hallucination_rate": hallucination_rate,
            "resource_match_accuracy": resource_match_accuracy,
            "knowledge_coverage_rate": knowledge_coverage_rate,
            "agent_success_rate": agent_success_rate,
            "total_resources": total_resources,
            "active_learners": active_learners,
        })
    except Exception as e:
        logger.warning(f"获取核心指标失败，返回默认值: {e}")
        return success({
            "hallucination_rate": 0,
            "resource_match_accuracy": 0,
            "knowledge_coverage_rate": 0,
            "agent_success_rate": 0,
            "total_resources": 0,
            "active_learners": 0,
        })
    finally:
        db.close()
