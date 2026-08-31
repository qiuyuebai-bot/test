"""
FastAPI 主应用入口
领域知识个性化生成与多智能体协同决策系统
"""
import time
from contextlib import asynccontextmanager, nullcontext
from pathlib import Path
from loguru import logger

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.config import settings
from app.database import init_database, engine
from app.desktop_runtime import desktop_web_dir
from app.utils.logger import LoggerUtil
from app.utils.rate_limiter import RateLimitMiddleware
from app.middleware import (
    RequestTracingMiddleware,
    PrometheusMiddleware,
    SecurityHeadersMiddleware,
    AuditMiddleware,
)
from app.utils.otel import setup_otel
from app.exception_handlers import register_exception_handlers
from app.health import router as health_router
from app.seed_data import (
    init_default_admin,
    init_learner_seed_data,
    init_career_training_seed_data,
    init_knowledge_seed_data,
    normalize_demo_data_paths,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"应用启动: {settings.APP_NAME} v{settings.APP_VERSION}")
    LoggerUtil.init_logger()

    try:
        init_database()
        logger.info("数据库初始化完成")
        if settings.is_desktop:
            normalize_demo_data_paths()
            logger.info("桌面模式跳过默认管理员和演示数据，等待本机首次初始化")
        elif settings.SEED_ON_STARTUP:
            init_default_admin()
            init_learner_seed_data()
            init_career_training_seed_data()
            init_knowledge_seed_data()
            logger.info("种子数据初始化完成（SEED_ON_STARTUP=true）")
        else:
            init_default_admin()
            logger.info("跳过种子数据初始化（SEED_ON_STARTUP=false，可用 CLI: python -m app.seed_data）")

        # 桌面版首启不应因模型下载或 Chroma 初始化阻塞；首次使用知识库时再按需加载。
        if settings.is_desktop:
            app.state.knowledge_status = "lazy"
            logger.info("桌面模式跳过知识向量库预热，将在首次使用时按需初始化")
        else:
            # Warm the vector store and embedding provider before the service is
            # reported healthy, so the first learner request does not pay the
            # one-time Chroma initialization cost.
            from app.domains.knowledge.service import KnowledgeService

            try:
                KnowledgeService.warmup()
                app.state.knowledge_status = "ready"
            except Exception as exc:
                # Chroma 是可选增强能力；桌面离线场景仍可使用 SQLite 关键词检索。
                app.state.knowledge_status = "degraded"
                logger.warning("知识向量库预热失败，已降级为本地关键词检索: {}", exc)
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        if settings.APP_ENV == "production" or settings.is_desktop:
            raise  # 生产环境数据库初始化失败必须阻止启动

    yield

    from app.utils.llm import LLMUtil
    await LLMUtil.aclose_clients()

    try:
        engine.dispose()
    except Exception as e:
        logger.warning(f"释放数据库连接池失败: {e}")

    logger.info(f"应用关闭: uptime={time.time() - app.state.start_time:.1f}s")


TAGS_METADATA = [
    {"name": "认证", "description": "用户登录、注册、Token 刷新、个人信息与密码管理"},
    {"name": "学习者画像", "description": "学习者画像采集、查询、更新与自适应学习能力评估"},
    {"name": "知识库", "description": "知识文档上传、解析、切片、向量检索与溯源"},
    {"name": "Agent协同调度", "description": "多智能体任务编排、进度追踪与协同决策"},
    {"name": "核心业务", "description": "资源生成、学习报告、自适应导学等核心业务流程"},
    {"name": "企业培训", "description": "企业培训任务导入、管理与学员进度跟踪"},
    {"name": "数据隐私与合规", "description": "数据脱敏、合规检查与隐私保护接口"},
    {"name": "审计日志", "description": "审计日志查询、统计与操作追溯（管理员权限）"},
    {"name": "运维", "description": "健康检查、存活/就绪探针、Prometheus 指标采集"},
    {"name": "基础", "description": "系统根路径信息与应用元数据"},
    {"name": "指标", "description": "系统运行指标与核心业务指标查询"},
    {"name": "角色自适应 Dashboard", "description": "按角色聚合学习工作台、培训管理台和引导状态"},
]

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "领域知识个性化生成与多智能体协同决策系统后端API\n\n"
        "## 认证方式\n"
        "- 除 `/auth/login`、`/auth/register`、健康检查外，所有接口需在请求头携带 `Authorization: Bearer <access_token>`\n"
        "- Token 通过 `POST /api/v1/auth/login` 获取，有效期由 `JWT_EXPIRE_MINUTES` 控制\n"
        "- Token 过期后通过 `POST /api/v1/auth/refresh` 刷新\n\n"
        "## 统一响应格式\n"
        "所有接口返回 `{code, message, data, timestamp}` 结构，`code=200` 表示成功"
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=TAGS_METADATA,
    contact={"name": "知识系统团队", "url": "https://github.com/knowledge-system"},
    license_info={"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
    servers=[
        {"url": "/api/v1", "description": "当前环境（相对路径）"},
        {"url": "http://localhost:8000/api/v1", "description": "开发环境"},
        {"url": "https://staging.example.com/api/v1", "description": "预发布环境"},
        {"url": "https://api.example.com/api/v1", "description": "生产环境"},
    ],
    lifespan=lifespan,
)

if settings.is_desktop and not settings.DESKTOP_AUTH_TOKEN:
    raise RuntimeError("桌面模式必须提供 DESKTOP_AUTH_TOKEN")

app.state.start_time = time.time()


@app.middleware("http")
async def bind_ai_config_owner(request, call_next):
    """Bind the JWT owner before sync/async endpoints run.

    FastAPI may execute dependencies and sync routes in different worker
    contexts.  Binding at middleware scope lets ContextVar propagate through
    both paths, while ``get_current_user`` still performs the authoritative
    database active-user check for protected routes.
    """

    from app.utils.auth import ACCESS_TOKEN_COOKIE, verify_access_token
    from app.utils.llm_runtime import use_runtime_user_id

    token = None
    authorization = request.headers.get("Authorization", "")
    if authorization.startswith("Bearer "):
        token = authorization[7:].strip()
    if not token:
        token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    user_id = None
    if token:
        payload = verify_access_token(token)
        value = payload.get("user_id") if payload else None
        if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
            user_id = int(value)
    with use_runtime_user_id(user_id) if user_id is not None else nullcontext():
        return await call_next(request)

# CORS
cors_origins = settings.cors_origin_list
logger.info(f"CORS 允许来源: {cors_origins}")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Requested-With", "X-Zhiyu-Desktop-Token"],
)

# Prometheus 指标采集
app.add_middleware(PrometheusMiddleware)
logger.info("Prometheus 指标采集中间件已启用")

# 审计日志（先于链路追踪注册，使 Tracing 为外层，request_id 可用）
app.add_middleware(AuditMiddleware)
logger.info("审计日志中间件已启用")

# 请求链路追踪
app.add_middleware(RequestTracingMiddleware)
logger.info("请求链路追踪中间件已启用")

# 速率限制
app.add_middleware(RateLimitMiddleware, settings=settings)
logger.info("速率限制中间件已启用: 登录10次/分钟, 上传20次/分钟, 通用API 100次/分钟")

# 安全响应头
app.add_middleware(SecurityHeadersMiddleware)
logger.info("安全响应头中间件已启用: CSP, X-Frame-Options, nosniff, HSTS")

# OpenTelemetry
setup_otel(app)

if settings.is_desktop:
    from app.middleware.desktop_auth import DesktopAuthMiddleware

    app.add_middleware(DesktopAuthMiddleware, token=settings.DESKTOP_AUTH_TOKEN)

# 全局异常处理器
register_exception_handlers(app)

# ===========================================
# 路由注册
# ===========================================

# 健康检查、系统信息、核心指标（路径已含 /api/v1 前缀，无需重复）
app.include_router(health_router)

# 认证路由（无需API前缀，方便OAuth2 tokenUrl配置）
from app.routers.auth import router as auth_router
app.include_router(auth_router, prefix=settings.API_PREFIX)

# 学习者画像路由
from app.domains.learner.router import router as learner_router
app.include_router(learner_router, prefix=settings.API_PREFIX)

# 知识库路由
from app.domains.knowledge.router import router as knowledge_router
app.include_router(knowledge_router, prefix=settings.API_PREFIX)

# Agent协同调度路由
from app.domains.agent.router import router as agent_router
app.include_router(agent_router, prefix=settings.API_PREFIX)

# 个性化资源生成路由（从 core.py 拆分）
from app.domains.resource.router import router as resource_router
app.include_router(resource_router, prefix=settings.API_PREFIX)

# 学情可视化报告路由（从 core.py 拆分）
from app.domains.report.router import router as report_router
app.include_router(report_router, prefix=settings.API_PREFIX)

# 自适应导学路由（从 core.py 拆分）
from app.domains.tutoring.router import router as tutoring_router
app.include_router(tutoring_router, prefix=settings.API_PREFIX)
from app.domains.tutoring.batch_router import router as batch_tutoring_router
app.include_router(batch_tutoring_router, prefix=settings.API_PREFIX)

# 能力诊断路由
from app.domains.diagnostic.router import router as diagnostic_router
app.include_router(diagnostic_router, prefix=settings.API_PREFIX)

# 岗位与胜任力路由
from app.domains.position.router import router as position_router
app.include_router(position_router, prefix=settings.API_PREFIX)

# 评估域路由
from app.domains.assessment.router import router as assessment_router
app.include_router(assessment_router, prefix=settings.API_PREFIX)

# 认证发证域路由
from app.domains.certification.router import router as certification_router
app.include_router(certification_router, prefix=settings.API_PREFIX)

# 培训项目域路由
from app.domains.training.router import router as training_router
app.include_router(training_router, prefix=settings.API_PREFIX)

# 业务配置选项路由（从 core.py 拆分）
from app.routers.config import router as config_router
app.include_router(config_router, prefix=settings.API_PREFIX)

# 每个账号一套 AI 服务配置：所有已登录角色均可管理自己的生效模型。
from app.routers.ai_config import router as ai_config_router
app.include_router(ai_config_router, prefix=settings.API_PREFIX)

if settings.is_desktop:
    from app.routers.desktop import router as desktop_router

    app.include_router(desktop_router, prefix=settings.API_PREFIX)

# 角色自适应 Dashboard 路由
from app.domains.dashboard.router import router as dashboard_router
app.include_router(dashboard_router, prefix=settings.API_PREFIX)

# 数据隐私与合规路由
from app.routers.privacy import router as privacy_router
app.include_router(privacy_router, prefix=settings.API_PREFIX)

# 审计日志路由（管理员可查）
from app.routers.audit import router as audit_router
app.include_router(audit_router, prefix=settings.API_PREFIX)


def _register_desktop_spa() -> None:
    """最后注册 SPA 回退，确保任何 API 路由优先匹配。"""
    web_dir = desktop_web_dir()
    if not settings.is_desktop or web_dir is None:
        return
    index_path = web_dir / "index.html"
    if not index_path.is_file():
        raise RuntimeError(f"桌面前端资源不存在: {index_path}")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def desktop_spa(full_path: str):
        requested = Path(full_path.lstrip("/"))
        candidate = (web_dir / requested).resolve()
        try:
            candidate.relative_to(web_dir)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="资源不存在") from exc
        if requested.parts and candidate.is_file():
            return FileResponse(candidate)
        if requested.suffix:
            raise HTTPException(status_code=404, detail="资源不存在")
        return FileResponse(index_path)


_register_desktop_spa()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG_MODE,
    )
