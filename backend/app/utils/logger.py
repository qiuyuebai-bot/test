"""
日志统一封装
使用 loguru 实现统一日志管理，当 loguru 不可用时自动降级到标准库 logging
"""
import sys
import logging
from pathlib import Path
from typing import Any, Optional

try:
    from loguru import logger as _loguru_logger
    _LOGURU_AVAILABLE = True
except ImportError:
    _LOGURU_AVAILABLE = False

from app.config import settings


class _StdLoggerCompat:
    """标准库 logging 到 loguru 接口的兼容层"""

    def __init__(self):
        self._logger = logging.getLogger("app")
        self._extra = {"request_id": "-"}
        self._handlers_configured = False
        self._configure_std_logger()

    def _configure_std_logger(self):
        if self._handlers_configured:
            return
        self._logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        if not self._logger.handlers:
            self._logger.addHandler(handler)
        self._handlers_configured = True

    def _format_message(self, message: str) -> str:
        req_id = self._extra.get("request_id", "-")
        return f"{req_id:8} | {message}"

    def info(self, message: str, *args, **kwargs):
        self._logger.info(self._format_message(str(message)), *args, **kwargs)

    def debug(self, message: str, *args, **kwargs):
        self._logger.debug(self._format_message(str(message)), *args, **kwargs)

    def warning(self, message: str, *args, **kwargs):
        self._logger.warning(self._format_message(str(message)), *args, **kwargs)

    def error(self, message: str, *args, **kwargs):
        self._logger.error(self._format_message(str(message)), *args, **kwargs)

    def critical(self, message: str, *args, **kwargs):
        self._logger.critical(self._format_message(str(message)), *args, **kwargs)

    def exception(self, message: str, *args, **kwargs):
        self._logger.exception(self._format_message(str(message)), *args, **kwargs)

    def remove(self, handler_id: Optional[int] = None):
        pass

    def add(self, sink: Any, **kwargs: Any) -> int:
        return 0

    def configure(self, **kwargs: Any):
        if "extra" in kwargs:
            self._extra.update(kwargs["extra"])

    def bind(self, **kwargs: Any):
        new_compat = _StdLoggerCompat()
        new_compat._extra = {**self._extra, **kwargs}
        new_compat._logger = self._logger
        new_compat._handlers_configured = True
        return new_compat

    def opt(self, **kwargs: Any):
        return self


if _LOGURU_AVAILABLE:
    logger = _loguru_logger
else:
    logger = _StdLoggerCompat()


class LoggerUtil:
    """日志统一封装工具类"""

    _initialized = False

    @staticmethod
    def init_logger() -> None:
        """
        初始化日志配置
        """
        if LoggerUtil._initialized:
            return

        if not _LOGURU_AVAILABLE:
            log_dir = Path(settings.LOG_DIR)
            log_dir.mkdir(parents=True, exist_ok=True)
            LoggerUtil._initialized = True
            logger.info(f"[降级模式] 使用标准库 logging, log_dir={log_dir}, debug_mode={settings.DEBUG_MODE}")
            return

        log_dir = Path(settings.LOG_DIR)
        log_dir.mkdir(parents=True, exist_ok=True)

        logger.remove()

        logger.configure(extra={"request_id": "-"})

        if settings.DEBUG_MODE:
            logger.add(
                sys.stdout,
                format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                       "<level>{level: <8}</level> | "
                       "<yellow>{extra[request_id]: <8}</yellow> | "
                       "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                       "<level>{message}</level>",
                level="DEBUG",
                colorize=True,
            )

        logger.add(
            log_dir / "app_{time:YYYY-MM-DD}.log",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {extra[request_id]: <8} | {name}:{function}:{line} - {message}",
            level="DEBUG" if settings.DEBUG_MODE else "INFO",
            rotation="00:00",
            retention="30 days",
            compression="zip",
            encoding="utf-8",
        )

        logger.add(
            log_dir / "app_json_{time:YYYY-MM-DD}.log",
            format="{message}",
            level="INFO",
            rotation="00:00",
            retention="30 days",
            compression="zip",
            encoding="utf-8",
            serialize=True,
        )

        logger.add(
            log_dir / "error_{time:YYYY-MM-DD}.log",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {extra[request_id]: <8} | {name}:{function}:{line} - {message}",
            level="ERROR",
            rotation="00:00",
            retention="30 days",
            compression="zip",
            encoding="utf-8",
        )

        LoggerUtil._initialized = True

        logger.info(f"日志系统初始化完成: log_dir={log_dir}, debug_mode={settings.DEBUG_MODE}")

    @staticmethod
    def get_logger(name: str = None):
        """
        获取日志实例

        Args:
            name: 日志名称（可选）

        Returns:
            logger实例
        """
        if not LoggerUtil._initialized:
            LoggerUtil.init_logger()

        if name:
            return logger.bind(name=name)

        return logger

    @staticmethod
    def log_api_request(
        method: str,
        path: str,
        params: dict = None,
        body: dict = None,
    ):
        """
        记录API请求日志

        Args:
            method: 请求方法
            path: 请求路径
            params: 查询参数
            body: 请求体
        """
        log_msg = f"API请求: {method} {path}"
        if params:
            log_msg += f" | params={params}"
        if body:
            log_msg += f" | body={body}"

        logger.debug(log_msg)

    @staticmethod
    def log_api_response(
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
    ):
        """
        记录API响应日志

        Args:
            method: 请求方法
            path: 请求路径
            status_code: 状态码
            duration_ms: 响应耗时（毫秒）
        """
        log_msg = f"API响应: {method} {path} | status={status_code} | duration={duration_ms}ms"

        if status_code >= 400:
            logger.warning(log_msg)
        else:
            logger.debug(log_msg)

    @staticmethod
    def log_agent_task(
        task_id: int,
        agent_type: str,
        action: str,
        status: str,
        details: dict = None,
    ):
        """
        记录Agent任务日志

        Args:
            task_id: 任务ID
            agent_type: Agent类型
            action: 执行动作
            status: 任务状态
            details: 详细信息
        """
        log_msg = f"Agent任务: id={task_id} | agent={agent_type} | action={action} | status={status}"
        if details:
            log_msg += f" | details={details}"

        if status == "failed":
            logger.error(log_msg)
        elif status == "running":
            logger.debug(log_msg)
        else:
            logger.info(log_msg)

    @staticmethod
    def log_llm_call(
        prompt_length: int,
        response_length: int,
        tokens: dict,
        duration_ms: float,
    ):
        """
        记录大模型调用日志

        Args:
            prompt_length: 提示长度
            response_length: 响应长度
            tokens: Token统计
            duration_ms: 调用耗时
        """
        log_msg = f"LLM调用: prompt={prompt_length} | response={response_length} | "
        log_msg += f"tokens={tokens} | duration={duration_ms}ms"

        logger.debug(log_msg)

    @staticmethod
    def log_hallucination_detection(
        content_id: int,
        is_hallucination: bool,
        score: float,
        keywords: list,
    ):
        """
        记录幻觉检测日志

        Args:
            content_id: 内容ID
            is_hallucination: 是否幻觉
            score: 幻觉评分
            keywords: 检测到的关键词
        """
        if is_hallucination:
            logger.warning(f"幻觉检测: id={content_id} | score={score} | keywords={keywords}")
        else:
            logger.debug(f"幻觉检测通过: id={content_id} | score={score}")

    @staticmethod
    def log_error(
        error_type: str,
        error_msg: Any,
        stack_trace: str = None,
    ):
        """
        记录错误日志

        Args:
            error_type: 错误类型
            error_msg: 错误消息
            stack_trace: 堆栈跟踪（可选）
        """
        log_msg = f"错误: type={error_type} | msg={error_msg}"
        if stack_trace:
            log_msg += f"\n{stack_trace}"

        logger.error(log_msg)
