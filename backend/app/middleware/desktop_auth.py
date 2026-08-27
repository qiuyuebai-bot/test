"""为桌面发行包的回环 HTTP 服务增加进程级访问令牌。"""
from __future__ import annotations

import hmac

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class DesktopAuthMiddleware(BaseHTTPMiddleware):
    """仅允许 Electron 主进程为本次运行注入令牌的请求进入应用。"""

    def __init__(self, app, token: str):
        super().__init__(app)
        self._token = token

    async def dispatch(self, request: Request, call_next):
        candidate = request.headers.get("X-Zhiyu-Desktop-Token", "")
        if not self._token or not hmac.compare_digest(candidate, self._token):
            return JSONResponse(
                status_code=403,
                content={"code": 403, "message": "桌面会话验证失败", "data": None},
            )
        return await call_next(request)
