"""
熔断器（Circuit Breaker）
防止 LLM 服务故障导致雪崩：连续失败 N 次后快速失败（OPEN），
冷却时间后半开试探（HALF_OPEN），成功则恢复正常（CLOSED）。

三态状态机：
- CLOSED：正常处理请求，记录连续失败次数
- OPEN：连续失败达阈值后熔断，直接抛出 CircuitBreakerOpenError
- HALF_OPEN：冷却时间过后，允许一次试探请求
    - 试探成功 → CLOSED
    - 试探失败 → OPEN（重置冷却计时）
"""
import time
import threading
from enum import Enum
from typing import Optional, Callable, Any
from loguru import logger


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpenError(Exception):
    """熔断器开启时抛出，表示请求被快速拒绝"""
    pass


class CircuitBreaker:
    """线程安全的熔断器实现"""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        name: str = "default",
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            self._check_recovery()
            return self._state

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """同步调用：通过熔断器包装函数调用，熔断时抛出 CircuitBreakerOpenError"""
        with self._lock:
            self._check_recovery()
            if self._state == CircuitState.OPEN:
                logger.warning(f"[CircuitBreaker:{self.name}] 熔断中，请求被拒绝")
                raise CircuitBreakerOpenError(
                    f"熔断器 {self.name} 已开启，连续失败 {self._failure_count} 次"
                )

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except CircuitBreakerOpenError:
            raise
        except Exception:
            self._on_failure()
            raise

    async def call_async(self, func: Callable, *args, **kwargs) -> Any:
        """异步调用：通过熔断器包装 async 函数调用"""
        with self._lock:
            self._check_recovery()
            if self._state == CircuitState.OPEN:
                logger.warning(f"[CircuitBreaker:{self.name}] 熔断中，请求被拒绝")
                raise CircuitBreakerOpenError(
                    f"熔断器 {self.name} 已开启，连续失败 {self._failure_count} 次"
                )

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except CircuitBreakerOpenError:
            raise
        except Exception:
            self._on_failure()
            raise

    def allow_request(self) -> bool:
        """检查是否允许请求通过（不执行实际调用），用于在调用前快速判断"""
        with self._lock:
            self._check_recovery()
            return self._state != CircuitState.OPEN

    def _on_success(self) -> None:
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                logger.info(f"[CircuitBreaker:{self.name}] 半开试探成功，恢复为 CLOSED")
            self._state = CircuitState.CLOSED
            self._failure_count = 0

    def _on_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                logger.warning(f"[CircuitBreaker:{self.name}] 半开试探失败，重新熔断")
                self._state = CircuitState.OPEN
            elif self._failure_count >= self.failure_threshold:
                logger.error(
                    f"[CircuitBreaker:{self.name}] 连续失败 {self._failure_count} 次，"
                    f"达到阈值 {self.failure_threshold}，触发熔断"
                )
                self._state = CircuitState.OPEN

    def _check_recovery(self) -> None:
        """检查是否已过冷却时间，若是则从 OPEN 转 HALF_OPEN（调用方持锁）"""
        if self._state == CircuitState.OPEN and self._last_failure_time:
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                logger.info(f"[CircuitBreaker:{self.name}] 冷却完成，转为 HALF_OPEN 试探")
                self._state = CircuitState.HALF_OPEN

    def reset(self) -> None:
        """重置熔断器（手动恢复，用于测试或运维操作）"""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = None
            logger.info(f"[CircuitBreaker:{self.name}] 已手动重置为 CLOSED")

    def get_state_info(self) -> dict:
        """获取熔断器状态信息（用于监控/指标暴露）"""
        with self._lock:
            self._check_recovery()
            return {
                "name": self.name,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "failure_threshold": self.failure_threshold,
                "recovery_timeout": self.recovery_timeout,
            }
