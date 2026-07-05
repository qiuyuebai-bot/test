"""
FastAPI 主应用入口
领域知识个性化生成与多智能体协同决策系统
"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
from loguru import logger
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError
from sqlalchemy import text
import time
import traceback
import platform

from app.config import settings
from app.database import init_database, SessionLocal, engine
from app.schemas.response import success, ResponseCodeEnum
from app.utils.logger import LoggerUtil
from app.utils.auth import hash_password
from app.utils.rate_limiter import RateLimitMiddleware
from app.middleware import (
    RequestTracingMiddleware,
    PrometheusMiddleware,
    prometheus_metrics_endpoint,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    """
    # 启动时初始化
    logger.info(f"应用启动: {settings.APP_NAME} v{settings.APP_VERSION}")
    LoggerUtil.init_logger()
    
    # 初始化数据库
    try:
        init_database()
        logger.info("数据库初始化完成")
        # 初始化默认管理员账户
        _init_default_admin()
        # 初始化企业培训种子数据
        _init_training_seed_data()
        # 初始化学习者画像种子数据
        _init_learner_seed_data()
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
    
    yield
    
    # 关闭时清理资源
    from app.utils.llm import LLMUtil
    await LLMUtil.aclose_clients()
    
    # 释放数据库连接池
    try:
        engine.dispose()
    except Exception as e:
        logger.warning(f"释放数据库连接池失败: {e}")
    
    logger.info(f"应用关闭: uptime={time.time() - app.state.start_time:.1f}s")


# 创建FastAPI应用实例
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="领域知识个性化生成与多智能体协同决策系统后端API",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# 记录应用启动时间（用于 uptime 计算）
app.state.start_time = time.time()

# CORS中间件配置（从环境变量读取，生产环境应限制具体域名）
cors_origins = settings.cors_origin_list
logger.info(f"CORS 允许来源: {cors_origins}")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Requested-With"],
)

# Prometheus 指标收集中间件（最先注册，最先执行、最后返回，覆盖完整链路）
app.add_middleware(PrometheusMiddleware)
logger.info("Prometheus 指标采集中间件已启用")

# 请求追踪中间件（生成 request_id，注入 loguru 上下文）
app.add_middleware(RequestTracingMiddleware)
logger.info("请求链路追踪中间件已启用")

# 速率限制中间件（防暴力破解、防DDoS）
app.add_middleware(RateLimitMiddleware, settings=settings)
logger.info("速率限制中间件已启用: 登录10次/分钟, 上传20次/分钟, 通用API 100次/分钟")


# ===========================================
# 全局异常处理器（按异常类型细分，统一响应格式）
# ===========================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    处理 FastAPI HTTPException（如401、403、404等）
    """
    detail = exc.detail
    if isinstance(detail, dict):
        message = detail.get("message", str(detail))
    else:
        message = str(detail) if detail else "请求错误"
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "message": message,
            "data": None,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    处理请求参数校验错误（Pydantic validation）
    将详细的字段错误信息整理后返回
    """
    errors = []
    for err in exc.errors():
        loc = " -> ".join(str(l) for l in err.get("loc", []))
        msg = err.get("msg", "")
        errors.append({"field": loc, "message": msg})
    
    logger.warning(f"[参数校验失败] {request.method} {request.url.path}: {errors}")
    
    return JSONResponse(
        status_code=400,
        content={
            "code": ResponseCodeEnum.BAD_REQUEST.value,
            "message": "请求参数校验失败",
            "data": {"errors": errors} if settings.DEBUG_MODE else None,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
    )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    """
    处理数据库唯一约束/外键约束冲突（如重复创建、引用不存在等）
    """
    error_msg = str(exc.orig) if hasattr(exc, "orig") else str(exc)
    logger.warning(f"[数据库约束冲突] {request.method} {request.url.path}: {error_msg}")
    
    return JSONResponse(
        status_code=400,
        content={
            "code": ResponseCodeEnum.BAD_REQUEST.value,
            "message": "数据已存在或引用无效",
            "data": {"detail": error_msg} if settings.DEBUG_MODE else None,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
    )


@app.exception_handler(OperationalError)
async def db_operational_error_handler(request: Request, exc: OperationalError):
    """
    处理数据库连接错误（如数据库不可用、连接超时等）
    """
    logger.error(f"[数据库连接错误] {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=503,
        content={
            "code": ResponseCodeEnum.SERVICE_UNAVAILABLE.value,
            "message": "数据库服务暂时不可用，请稍后重试",
            "data": None,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
    """
    处理其他SQLAlchemy数据库错误
    """
    logger.error(f"[数据库错误] {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "code": ResponseCodeEnum.INTERNAL_ERROR.value,
            "message": "数据库操作失败",
            "data": {"detail": str(exc)} if settings.DEBUG_MODE else None,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """
    处理值错误（如非法参数值、业务逻辑校验失败等）
    """
    logger.warning(f"[值错误] {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=400,
        content={
            "code": ResponseCodeEnum.BAD_REQUEST.value,
            "message": str(exc) or "参数值不合法",
            "data": None,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
    )


@app.exception_handler(FileNotFoundError)
async def file_not_found_handler(request: Request, exc: FileNotFoundError):
    """
    处理文件不存在错误
    """
    logger.warning(f"[文件不存在] {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=404,
        content={
            "code": ResponseCodeEnum.NOT_FOUND.value,
            "message": "请求的资源文件不存在",
            "data": None,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
    )


@app.exception_handler(PermissionError)
async def permission_error_handler(request: Request, exc: PermissionError):
    """
    处理权限错误
    """
    logger.error(f"[权限错误] {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=403,
        content={
            "code": ResponseCodeEnum.FORBIDDEN.value,
            "message": "无权访问该资源",
            "data": None,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    全局兜底异常处理器（未被前面处理器捕获的所有异常）
    """
    tb_str = traceback.format_exc()
    logger.error(
        f"[未捕获异常] {request.method} {request.url.path}\n"
        f"异常类型: {type(exc).__name__}\n"
        f"异常信息: {exc}\n"
        f"堆栈:\n{tb_str}"
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "code": ResponseCodeEnum.INTERNAL_ERROR.value,
            "message": "服务器内部错误" if not settings.DEBUG_MODE else f"服务器错误: {type(exc).__name__}: {exc}",
            "data": {
                "exception_type": type(exc).__name__,
                "traceback": tb_str,
            } if settings.DEBUG_MODE else None,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
    )


# ===========================================
# 基础路由
# ===========================================

@app.get("/", tags=["基础"])
async def root():
    """
    根路径 - 系统信息
    """
    return success({
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "uptime_seconds": round(time.time() - app.state.start_time, 1),
    })


# ===========================================
# 健康检查（K8s 风格：liveness + readiness）
# ===========================================

@app.get("/health", tags=["运维"])
@app.get("/health/live", tags=["运维"])
@app.get("/api/v1/health", tags=["运维"])
@app.get("/api/v1/health/live", tags=["运维"])
async def health_liveness():
    """
    存活检查（Liveness Probe）
    
    轻量级检查：仅确认进程存活，不检查依赖
    Kubernetes/容器编排用此判断容器是否需要重启
    """
    return JSONResponse(
        status_code=200,
        content={
            "code": 200,
            "message": "alive",
            "data": {
                "status": "alive",
                "uptime_seconds": round(time.time() - app.state.start_time, 1),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            },
        },
    )


@app.get("/health/ready", tags=["运维"])
@app.get("/api/v1/health/ready", tags=["运维"])
async def health_readiness():
    """
    就绪检查（Readiness Probe）
    
    深度检查：验证所有核心依赖是否可用
    - 数据库连接
    - Chroma 向量库（如果可用）
    - httpx LLM 客户端（仅验证配置存在）
    Kubernetes 用此判断是否将流量路由到实例
    """
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
    
    # 2. Chroma 向量库检查（降级模式不阻塞就绪）
    try:
        from app.services.knowledge_service import _get_chroma_collection
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
                "uptime_seconds": round(time.time() - app.state.start_time, 1),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "version": settings.APP_VERSION,
                "python_version": platform.python_version(),
            },
        },
    )


# ===========================================
# Prometheus 指标端点
# ===========================================

@app.get("/metrics", tags=["运维"])
@app.get("/api/v1/metrics/prometheus", tags=["运维"])
async def get_prometheus_metrics(request: Request):
    """Prometheus /metrics 端点，供 Prometheus Server 抓取"""
    return await prometheus_metrics_endpoint(request)


@app.get("/api/v1/info", tags=["基础"])
async def system_info():
    """
    系统信息接口
    """
    return success({
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "api_prefix": settings.API_PREFIX,
        "debug_mode": settings.DEBUG_MODE,
        "features": [
            "多智能体协同",
            "学情画像分析",
            "知识库管理",
            "个性化资源生成",
            "幻觉检测与纠偏",
            "自适应导学",
        ],
    })


# ===========================================
# 核心指标接口
# ===========================================

@app.get("/api/v1/metrics", tags=["指标"])
async def get_core_metrics():
    """
    获取核心量化指标（从数据库真实统计）
    """
    from app.database import SessionLocal
    from app.models import LearningResource, AgentTask, DebateRecord
    from sqlalchemy import func, case
    
    db = SessionLocal()
    try:
        # 资源总数
        total_resources = db.query(func.count(LearningResource.id)).scalar() or 0
        
        # 活跃学习者数（有生成资源的学习者）
        active_learners = db.query(
            func.count(func.distinct(LearningResource.learner_id))
        ).scalar() or 0
        
        # Agent任务成功率
        total_tasks = db.query(func.count(AgentTask.id)).scalar() or 0
        completed_tasks = db.query(func.count(AgentTask.id)).filter(
            AgentTask.status == "completed"
        ).scalar() or 0
        agent_success_rate = round(completed_tasks / total_tasks * 100, 1) if total_tasks > 0 else 0
        
        # 幻觉率（合并查询避免多次COUNT）
        total_debates, hallucination_count = db.query(
            func.count(DebateRecord.id),
            func.coalesce(func.sum(case((DebateRecord.is_hallucination == True, 1), else_=0)), 0),
        ).one()
        hallucination_rate = round(hallucination_count / total_debates * 100, 1) if total_debates > 0 else 0
        
        # 平均匹配度（从最新TestMetrics取，或从资源计算）
        avg_match_result = db.query(func.avg(LearningResource.match_score)).scalar()
        resource_match_accuracy = round(float(avg_match_result or 0), 1)
        
        # 知识覆盖率（有切片索引的文档比例）
        from app.models import KnowledgeSlice
        indexed_slices = db.query(func.count(KnowledgeSlice.id)).filter(
            KnowledgeSlice.is_indexed == True
        ).scalar() or 0
        total_slices = db.query(func.count(KnowledgeSlice.id)).scalar() or 0
        knowledge_coverage_rate = round(indexed_slices / total_slices * 100, 1) if total_slices > 0 else 0
        
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


# ===========================================
# 默认管理员初始化
# ===========================================

def _init_default_admin():
    """初始化默认管理员账户"""
    from app.models.user import User, UserRoleEnum
    
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                password_hash=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
                email="admin@knowledge-system.com",
                role=UserRoleEnum.ADMIN,
                is_active=True,
                is_verified=True,
            )
            db.add(admin)
            db.commit()
            logger.info("默认管理员账户已创建（密码来自 DEFAULT_ADMIN_PASSWORD 配置）")
        else:
            logger.debug("默认管理员账户已存在")
    except Exception as e:
        logger.warning(f"初始化默认管理员失败: {e}")
        db.rollback()
    finally:
        db.close()


def _init_training_seed_data():
    """初始化企业培训种子数据"""
    from app.services.training_service import TrainingService
    db = SessionLocal()
    try:
        TrainingService.init_seed_data(db)
    except Exception as e:
        logger.warning(f"初始化培训种子数据失败: {e}")
        db.rollback()
    finally:
        db.close()


def _init_learner_seed_data():
    """初始化学习者画像种子数据（从 JSON 配置文件读取，避免硬编码）"""
    from app.models.user import User, UserRoleEnum
    from app.models.learner_profile import LearnerProfile
    from app.utils.seed_loader import load_seed_data, load_seed_meta

    db = SessionLocal()
    try:
        existing = db.query(LearnerProfile).count()
        if existing > 0:
            logger.debug("学习者种子数据已存在，跳过初始化")
            return

        meta = load_seed_meta("learners.json")
        default_password = meta.get("default_password", "learner123")
        default_role = meta.get("default_role", "learner")
        try:
            role_enum = UserRoleEnum(default_role)
        except ValueError:
            logger.warning(f"未知角色 {default_role}，回退为 LEARNER")
            role_enum = UserRoleEnum.LEARNER

        records = load_seed_data("learners.json")
        for record in records:
            username = record.pop("username", None)
            if not username:
                logger.warning(f"跳过缺少 username 的学习者记录: {record}")
                continue
            user = User(
                username=username,
                password_hash=hash_password(default_password),
                role=role_enum,
                is_active=True,
                is_verified=True,
            )
            db.add(user)
            db.flush()
            profile = LearnerProfile(user_id=user.id, **record)
            db.add(profile)
        db.commit()
        logger.info(f"学习者种子数据已初始化: {len(records)} 条 (默认密码已配置)")
    except Exception as e:
        logger.warning(f"初始化学习者种子数据失败: {e}")
        db.rollback()
    finally:
        db.close()


# ===========================================
# 路由注册
# ===========================================

# 认证路由（无需API前缀，方便OAuth2 tokenUrl配置）
from app.routers.auth import router as auth_router
app.include_router(auth_router, prefix=settings.API_PREFIX)

# 学习者画像路由
from app.routers.learner import router as learner_router
app.include_router(learner_router, prefix=settings.API_PREFIX)

# 知识库路由
from app.routers.knowledge import router as knowledge_router
app.include_router(knowledge_router, prefix=settings.API_PREFIX)

# Agent协同调度路由
from app.routers.agent import router as agent_router
app.include_router(agent_router, prefix=settings.API_PREFIX)

# 核心业务路由（资源生成、报告、自适应导学）
from app.routers.core import router as core_router
app.include_router(core_router, prefix=settings.API_PREFIX)

# 企业培训任务路由
from app.routers.training import router as training_router
app.include_router(training_router, prefix=settings.API_PREFIX)

# 数据隐私与合规路由
from app.routers.privacy import router as privacy_router
app.include_router(privacy_router, prefix=settings.API_PREFIX)


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG_MODE,
    )