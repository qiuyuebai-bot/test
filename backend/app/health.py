"""
健康检查、系统信息、核心指标接口
"""
import time
import platform
import threading
from copy import deepcopy
from contextlib import contextmanager
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import case, func, text

from app.config import settings
from app.database import SessionLocal
from app.schemas.response import success
from app.middleware import prometheus_metrics_endpoint
from app.domains.knowledge.models import KnowledgeDoc, KnowledgeSlice
from app.utils.datetime import utcnow_naive


router = APIRouter(tags=["运维"])

# Readiness probes run every 15 seconds in the default Helm values. Keep a
# slightly longer cache window so repeated probes do not repeat full counts.
_READINESS_CACHE_TTL_SECONDS = 20.0
_readiness_cache_lock = threading.Lock()
_readiness_cache: tuple[float, int, str, dict] | None = None


@contextmanager
def _read_only_db_context():
    """Create and close a read-only session for health and metrics probes."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.get("/", tags=["基础"])
async def root(request: Request):
    """根路径 - 系统信息"""
    if settings.is_desktop:
        # 桌面端的根地址是 React 入口；运行状态仍可从 /health/live 获取。
        from app.desktop_runtime import desktop_web_dir

        web_dir = desktop_web_dir()
        index_path = web_dir / "index.html" if web_dir else None
        if index_path and index_path.is_file():
            return FileResponse(index_path)
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
def health_readiness(request: Request):
    """就绪检查（Readiness Probe）"""
    global _readiness_cache

    now = time.monotonic()
    with _readiness_cache_lock:
        if _readiness_cache and now - _readiness_cache[0] < _READINESS_CACHE_TTL_SECONDS:
            _, cached_status, cached_message, cached_checks = _readiness_cache
            return _readiness_response(request, cached_status, cached_message, deepcopy(cached_checks))

    checks = {}
    overall_status = "ready"
    http_status = 200

    # 1. 数据库检查
    db_latency_ms = 0
    knowledge_counts = {
        "enabled_docs": 0,
        "ready_docs": 0,
        "db_slices": 0,
        "db_indexed_slices": 0,
        "declared_slices": 0,
    }
    try:
        db_start = time.time()
        with _read_only_db_context() as db:
            db.execute(text("SELECT 1"))
            db_latency_ms = round((time.time() - db_start) * 1000, 1)
            doc_counts = db.query(
                func.count(KnowledgeDoc.id),
                func.coalesce(
                    func.sum(case((KnowledgeDoc.status == "ready", 1), else_=0)),
                    0,
                ),
                func.coalesce(func.sum(KnowledgeDoc.slice_count), 0),
            ).filter(KnowledgeDoc.is_enabled == True).one()
            slice_counts = db.query(
                func.count(KnowledgeSlice.id),
                func.coalesce(
                    func.sum(case((KnowledgeSlice.is_indexed == True, 1), else_=0)),
                    0,
                ),
            ).join(KnowledgeDoc).filter(KnowledgeDoc.is_enabled == True).one()
            knowledge_counts = {
                "enabled_docs": int(doc_counts[0] or 0),
                "ready_docs": int(doc_counts[1] or 0),
                "db_slices": int(slice_counts[0] or 0),
                "db_indexed_slices": int(slice_counts[1] or 0),
                "declared_slices": int(doc_counts[2] or 0),
            }
    except Exception as e:
        checks["database"] = {"status": "down", "error": str(e)[:200]}
        overall_status = "not_ready"
        http_status = 503
    else:
        checks["database"] = {
            "status": "up",
            "latency_ms": db_latency_ms,
            "knowledge": knowledge_counts,
        }

    # 2. Chroma 向量库检查
    try:
        from app.domains.knowledge.service import KnowledgeService, _get_chroma_collection
        collection = _get_chroma_collection()
        if collection is not None:
            vector_count = collection.count()
            expected_count = knowledge_counts["db_indexed_slices"]
            chroma_status = (
                "up"
                if vector_count == expected_count and (KnowledgeService.is_warmed() or vector_count == 0)
                else "degraded"
            )
            note = None
            if vector_count != expected_count:
                note = f"向量数量与数据库已索引切片不一致: vectors={vector_count}, db={expected_count}"
            elif vector_count > 0 and not KnowledgeService.is_warmed():
                note = "向量库已初始化但 embedding 尚未预热"
            elif (
                knowledge_counts["ready_docs"] > 0
                and (vector_count == 0 or knowledge_counts["declared_slices"] != knowledge_counts["db_slices"])
            ):
                # Default seed documents intentionally support database keyword
                # fallback so first startup does not download an embedding model.
                if knowledge_counts["db_slices"] > 0 and knowledge_counts["db_indexed_slices"] == 0:
                    chroma_status = "fallback"
                    note = "当前使用数据库关键词检索；管理员可在知识库页面重新索引以启用向量检索"
                else:
                    chroma_status = "degraded"
                    note = "存在已就绪文档但没有可检索切片，请执行重新索引"
            checks["chroma"] = {
                "status": chroma_status,
                "vector_count": vector_count,
                "db_indexed_slice_count": expected_count,
                "warmed": KnowledgeService.is_warmed(),
                **({"note": note} if note else {}),
            }
            if chroma_status == "degraded":
                overall_status = "not_ready"
                http_status = 503
        else:
            checks["chroma"] = {"status": "fallback", "note": "Chroma不可用，使用数据库关键词检索降级模式"}
    except Exception as e:
        checks["chroma"] = {"status": "degraded", "error": str(e)[:200], "note": "使用数据库关键词检索降级模式"}
        overall_status = "not_ready"
        http_status = 503

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

    if http_status == 200:
        with _readiness_cache_lock:
            _readiness_cache = (time.monotonic(), http_status, overall_status, deepcopy(checks))
    return _readiness_response(request, http_status, overall_status, checks)


def _readiness_response(request: Request, http_status: int, overall_status: str, checks: dict):
    """Build a probe response while keeping the expensive checks cacheable."""
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


@router.get("/health/llm")
@router.get("/api/v1/health/llm")
def health_llm():
    """Return a redacted AI connectivity check, scoped when authenticated."""
    from app.utils.llm import LLMUtil

    return success(LLMUtil.health_check())


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
def get_core_metrics():
    """获取核心量化指标（从数据库真实统计）"""
    from app.models import LearningResource, AgentTask, DebateRecord, KnowledgeSlice
    from app.utils.metrics import MetricsUtil
    from app.services.metric_service import MetricService
    from sqlalchemy import func, case

    with _read_only_db_context() as db:
        hallucination_metrics = MetricsUtil.calculate_hallucination_metrics(db)
        total_resources, active_learners, avg_match = db.query(
            func.count(LearningResource.id),
            func.count(func.distinct(LearningResource.learner_id)),
            func.avg(LearningResource.match_score),
        ).one()
        total_resources = total_resources or 0
        active_learners = active_learners or 0
        resource_match_accuracy = round(float(avg_match), 1) if avg_match is not None else None

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
        hallucination_rate = hallucination_metrics["hallucination_rate"]

        knowledge_coverage_rate = MetricsUtil.calculate_knowledge_index_coverage_rate(db)
        learning_blind_spot_coverage_rate = MetricsUtil.calculate_learning_blind_spot_coverage_rate(db)
        standard_metrics = MetricService.calculate_metrics(db, scope="global")
        standard_by_id = MetricService.by_id(standard_metrics)

        return success({
            "metrics": standard_metrics,
            "metric_registry": MetricService.registry(),
            "hallucination_rate": standard_by_id.get("hallucination_rate", {}).get("value"),
            "total_checks": hallucination_metrics["total_checks"],
            "evaluated_checks": hallucination_metrics["evaluated_checks"],
            "pending_checks": hallucination_metrics["pending_checks"],
            "confirmed_hallucinations": hallucination_metrics["confirmed_hallucinations"],
            "evidence_gaps": hallucination_metrics["evidence_gaps"],
            "has_sufficient_sample": hallucination_metrics["has_sufficient_sample"],
            "resource_match_accuracy": standard_by_id.get("resource_match_score", {}).get("value"),
            "resource_match_score": standard_by_id.get("resource_match_score", {}).get("value"),
            "resource_match_effectiveness": standard_by_id.get("resource_match_effectiveness", {}).get("value"),
            "answer_accuracy": standard_by_id.get("answer_accuracy", {}).get("value"),
            "knowledge_coverage_rate": standard_by_id.get("knowledge_index_coverage", {}).get("value"),
            "knowledge_index_coverage_rate": standard_by_id.get("knowledge_index_coverage", {}).get("value"),
            "generated_content_coverage_rate": standard_by_id.get("generated_content_coverage", {}).get("value"),
            "learning_blind_spot_coverage_rate": standard_by_id.get("blind_spot_resource_coverage", {}).get("value"),
            "metrics_status": "degraded" if any(
                metric.get("status") in {"collecting", "stale", "error"}
                for metric in standard_metrics
            ) else "ready" if standard_metrics else "no_data",
            "metrics_source": "realtime",
            "calculated_at": utcnow_naive().isoformat(),
            "agent_success_rate": agent_success_rate,
            "total_resources": total_resources,
            "active_learners": active_learners,
        })
