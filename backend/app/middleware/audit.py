"""
审计日志中间件
拦截写操作和关键读操作，自动记录审计日志

记录范围:
  - 写操作: POST / PUT / PATCH / DELETE
  - 关键读: 导出、登录/登出
  - 跳过: 健康检查、指标采集、OPTIONS预检、静态资源
"""
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from loguru import logger

from app.models.audit_log import AuditLog
from app.middleware.tracing import get_request_id


_SKIP_PATHS = {"/", "/health", "/health/live", "/health/ready", "/metrics"}
_SKIP_PREFIXES = (
    "/health",
    "/metrics",
    "/api/v1/health",
    "/api/v1/metrics/prometheus",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
)

_PATH_PREFIX_TO_RESOURCE = {
    "/auth": "auth",
    "/learners": "learner",
    "/knowledge": "knowledge",
    "/agent": "agent",
    "/trainings": "training",
    "/resources": "resource",
    "/report": "report",
    "/privacy": "privacy",
    "/tutoring": "tutoring",
    "/tasks": "task",
    "/config": "config",
}


def _should_audit(method: str, path: str) -> bool:
    if method == "OPTIONS":
        return False
    if path in _SKIP_PATHS:
        return False
    for prefix in _SKIP_PREFIXES:
        if path.startswith(prefix):
            return False
    if method in ("POST", "PUT", "PATCH", "DELETE"):
        return True
    if "/export" in path or "/login" in path or "/logout" in path or "/register" in path:
        return True
    return False


def _classify_action(method: str, path: str) -> str:
    if "/login" in path and method == "POST":
        return "LOGIN"
    if "/logout" in path:
        return "LOGOUT"
    if "/register" in path and method == "POST":
        return "REGISTER"
    if "/export" in path:
        return "EXPORT"
    if "/search" in path and method == "POST":
        return "SEARCH"
    if method == "POST":
        return "CREATE"
    if method in ("PUT", "PATCH"):
        return "UPDATE"
    if method == "DELETE":
        return "DELETE"
    return "ACCESS"


def _extract_resource_type(path: str) -> str | None:
    api_path = path
    if api_path.startswith("/api/v1/"):
        api_path = "/" + api_path[len("/api/v1/"):]
    for prefix, resource in _PATH_PREFIX_TO_RESOURCE.items():
        if api_path.startswith(prefix):
            return resource
    return None


def _extract_resource_id(path: str) -> str | None:
    parts = path.rstrip("/").split("/")
    for part in reversed(parts):
        if part.isdigit():
            return part
    return None


def _extract_user(request: Request) -> tuple[int | None, str | None]:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None, None
    token = auth[7:]
    try:
        from app.utils.auth import decode_token
        payload = decode_token(token)
        if not payload:
            return None, None
        return payload.get("user_id"), payload.get("username")
    except Exception:
        return None, None


def _write_audit_log(entry: dict) -> None:
    try:
        from app.database import get_db_context
        with get_db_context() as db:
            log = AuditLog(**entry)
            db.add(log)
            db.commit()
    except Exception as e:
        logger.warning(f"审计日志写入失败: {e}")


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        method = request.method
        path = request.url.path

        if not _should_audit(method, path):
            return await call_next(request)

        start_time = time.time()
        user_id, username = _extract_user(request)
        action = _classify_action(method, path)
        resource_type = _extract_resource_type(path)
        resource_id = _extract_resource_id(path)
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("User-Agent", "")[:255] or None
        request_id = get_request_id()

        response = await call_next(request)

        duration_ms = int((time.time() - start_time) * 1000)

        _write_audit_log({
            "user_id": user_id,
            "username": username,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "method": method,
            "path": path[:255],
            "status_code": response.status_code,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "duration_ms": duration_ms,
            "request_id": request_id,
        })

        return response
