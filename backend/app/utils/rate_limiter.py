"""
速率限制中间件
基于滑动窗口算法的轻量级内存限流实现，无需外部依赖
"""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from typing import Dict, List, Tuple
from collections import defaultdict
from loguru import logger
import time
import threading


class SlidingWindowRateLimiter:
    """滑动窗口速率限流器"""

    def __init__(self):
        self._windows: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()
        self._last_cleanup = time.time()
        self._cleanup_interval = 60.0

    def _cleanup_old_entries(self, current_time: float, window_seconds: int):
        """清理过期的请求记录"""
        with self._lock:
            if current_time - self._last_cleanup < self._cleanup_interval:
                return
            self._last_cleanup = current_time
            cutoff = current_time - 600
            keys_to_remove = []
            for key, timestamps in self._windows.items():
                valid_times = [t for t in timestamps if t > cutoff]
                if valid_times:
                    self._windows[key] = valid_times
                else:
                    keys_to_remove.append(key)
            for key in keys_to_remove:
                del self._windows[key]

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> Tuple[bool, int]:
        """
        检查请求是否被允许
        
        Args:
            key: 限流键（通常是 IP 或 IP+路径）
            max_requests: 窗口内最大请求数
            window_seconds: 窗口时间（秒）
            
        Returns:
            (是否允许, 重试等待秒数)
        """
        current_time = time.time()
        self._cleanup_old_entries(current_time, window_seconds)
        
        window_start = current_time - window_seconds
        
        with self._lock:
            timestamps = self._windows[key]
            valid_timestamps = [t for t in timestamps if t > window_start]
            
            if len(valid_timestamps) >= max_requests:
                if valid_timestamps:
                    retry_after = int(window_seconds - (current_time - valid_timestamps[0])) + 1
                    retry_after = max(retry_after, 1)
                else:
                    retry_after = window_seconds
                self._windows[key] = valid_timestamps
                return False, retry_after
            
            valid_timestamps.append(current_time)
            self._windows[key] = valid_timestamps
            return True, 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    """速率限制中间件"""

    def __init__(self, app, settings):
        super().__init__(app)
        self.limiter = SlidingWindowRateLimiter()
        self.settings = settings
        
        self._rate_limits = {
            "/auth/login": self._parse_rate_limit(settings.RATE_LIMIT_LOGIN),
            "/auth/register": self._parse_rate_limit(settings.RATE_LIMIT_LOGIN),
            "/auth/refresh": (30, 60),
            "/knowledge/upload": self._parse_rate_limit(settings.RATE_LIMIT_UPLOAD),
            "/resources/generate": (10, 60),
            "/resources/generate/sync": (10, 60),
            "/tutoring/answer": (60, 60),
        }
        
        self._default_limit = self._parse_rate_limit(settings.RATE_LIMIT_API)
        
        self._health_paths = {
            "/health", "/health/live", "/health/ready", "/metrics",
            "/api/v1/health", "/api/v1/health/live", "/api/v1/health/ready",
            "/api/v1/metrics/prometheus",
            "/", "/docs", "/redoc", "/openapi.json", "/favicon.ico",
        }

    @staticmethod
    def _parse_rate_limit(rate_str: str) -> Tuple[int, int]:
        """解析速率限制字符串，如 '10/minute' -> (10, 60)"""
        try:
            parts = rate_str.strip().split("/")
            count = int(parts[0])
            unit = parts[1].lower() if len(parts) > 1 else "minute"
            
            unit_map = {
                "second": 1,
                "minute": 60,
                "hour": 3600,
                "day": 86400,
            }
            seconds = unit_map.get(unit, 60)
            return (count, seconds)
        except (ValueError, IndexError):
            return (100, 60)

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端真实 IP

        仅当直连客户端是可信代理时才信任 X-Forwarded-For / X-Real-IP，
        防止攻击者伪造这些头绕过限流。
        """
        direct_ip = request.client.host if request.client else "unknown"
        trusted_proxies = {
            ip.strip()
            for ip in (getattr(self.settings, "TRUSTED_PROXIES", "") or "").split(",")
            if ip.strip()
        }
        if direct_ip not in trusted_proxies:
            return direct_ip
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
        return direct_ip

    def _match_rate_limit(self, path: str) -> Tuple[int, int]:
        """匹配路径对应的限流规则"""
        api_prefix = self.settings.API_PREFIX
        if path.startswith(api_prefix):
            path = path[len(api_prefix):]
        
        for route_prefix, limit in self._rate_limits.items():
            if path.startswith(route_prefix):
                return limit
        
        return self._default_limit

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        
        if path in self._health_paths or request.method in ("OPTIONS", "HEAD"):
            return await call_next(request)
        
        client_ip = self._get_client_ip(request)
        max_requests, window_seconds = self._match_rate_limit(path)
        limit_key = f"{client_ip}:{path}"
        
        allowed, retry_after = self.limiter.is_allowed(limit_key, max_requests, window_seconds)
        
        if not allowed:
            logger.warning(
                f"[限流] 请求被拒绝: ip={client_ip}, path={path}, "
                f"limit={max_requests}/{window_seconds}s, retry_after={retry_after}s"
            )
            return JSONResponse(
                status_code=429,
                content={
                    "code": 429,
                    "message": f"请求过于频繁，请在 {retry_after} 秒后重试",
                    "retry_after": retry_after,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(max_requests),
                    "X-RateLimit-Window": str(window_seconds),
                },
            )
        
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(max_requests)
        response.headers["X-RateLimit-Window"] = str(window_seconds)
        return response
