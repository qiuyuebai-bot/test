"""
请求追踪中间件
为每个请求生成唯一 request_id，注入 loguru 上下文，实现链路追踪
"""
import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from loguru import logger
from contextvars import ContextVar


request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    """获取当前请求的 request_id（可在任意业务代码中调用）"""
    return request_id_var.get()


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """
    请求链路追踪中间件
    
    - 为每个请求生成/继承 X-Request-ID
    - 将 request_id 注入 loguru 上下文，所有日志自动携带
    - 在响应头中返回 X-Request-ID，便于前端/调用方排查问题
    - 在响应头中返回 X-Response-Time
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        raw_id = request.headers.get("X-Request-ID") or ""
        if raw_id and len(raw_id) <= 64 and all(c.isalnum() or c == "-" for c in raw_id):
            request_id = raw_id
        else:
            request_id = str(uuid.uuid4())

        token = request_id_var.set(request_id)

        start_time = time.time()
        client_ip = request.client.host if request.client else "-"
        method = request.method
        path = request.url.path

        with logger.contextualize(request_id=request_id):
            try:
                response = await call_next(request)

                duration_ms = (time.time() - start_time) * 1000

                response.headers["X-Request-ID"] = request_id
                response.headers["X-Response-Time"] = f"{duration_ms:.1f}ms"

                if 400 <= response.status_code < 500:
                    logger.warning(
                        f"{method} {path} -> {response.status_code} "
                        f"({duration_ms:.1f}ms) [client={client_ip}]"
                    )
                elif response.status_code >= 500:
                    logger.error(
                        f"{method} {path} -> {response.status_code} "
                        f"({duration_ms:.1f}ms) [client={client_ip}]"
                    )
                else:
                    logger.debug(
                        f"{method} {path} -> {response.status_code} "
                        f"({duration_ms:.1f}ms)"
                    )

                return response
            except Exception:
                duration_ms = (time.time() - start_time) * 1000
                logger.error(
                    f"{method} {path} -> EXCEPTION "
                    f"({duration_ms:.1f}ms) [client={client_ip}]"
                )
                raise
            finally:
                request_id_var.reset(token)
