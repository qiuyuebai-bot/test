"""
OpenTelemetry 分布式追踪配置

自动注入 FastAPI 调用链，提供端到端可观测性。
SQLAlchemy 和 httpx instrumentation 需要额外安装：
  pip install opentelemetry-instrumentation-sqlalchemy opentelemetry-instrumentation-httpx

启用方式：
1. 设置环境变量 OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
2. 启动后端，自动注入追踪
3. 无 OTLP endpoint 时仍创建 TracerProvider（便于日志关联 trace_id）
"""
import os

from loguru import logger

try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False

try:
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

    _SQLALCHEMY_AVAILABLE = True
except ImportError:
    _SQLALCHEMY_AVAILABLE = False

try:
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

    _HTTPX_AVAILABLE = True
except ImportError:
    _HTTPX_AVAILABLE = False


def setup_otel(app) -> bool:
    """
    初始化 OpenTelemetry 追踪

    自动注入 FastAPI 请求链路，可选注入 SQLAlchemy/httpx 调用。
    无 OTLP endpoint 时仍创建 TracerProvider（便于日志关联 trace_id）。

    Args:
        app: FastAPI 应用实例

    Returns:
        True 如果核心 OTel 初始化成功
    """
    if not _OTEL_AVAILABLE:
        logger.debug("[OTel] OpenTelemetry 依赖未安装，跳过追踪初始化")
        return False

    service_name = os.environ.get(
        "OTEL_SERVICE_NAME", "knowledge-platform-backend"
    )
    otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    if otlp_endpoint:
        try:
            processor = BatchSpanProcessor(
                OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
            )
            provider.add_span_processor(processor)
            logger.info(f"[OTel] OTLP 导出器已配置: {otlp_endpoint}")
        except Exception as e:
            logger.warning(f"[OTel] OTLP 导出器配置失败: {e}")

    trace.set_tracer_provider(provider)

    try:
        FastAPIInstrumentor.instrument_app(app)
        logger.info("[OTel] FastAPI instrumentation 已启用")
    except Exception as e:
        logger.warning(f"[OTel] FastAPI instrumentation 失败: {e}")

    if _SQLALCHEMY_AVAILABLE:
        try:
            SQLAlchemyInstrumentor().instrument(enable_commenter=True)
            logger.info("[OTel] SQLAlchemy instrumentation 已启用")
        except Exception as e:
            logger.warning(f"[OTel] SQLAlchemy instrumentation 失败: {e}")
    else:
        logger.debug(
            "[OTel] SQLAlchemy instrumentation 未安装"
            "（pip install opentelemetry-instrumentation-sqlalchemy）"
        )

    if _HTTPX_AVAILABLE:
        try:
            HTTPXClientInstrumentor().instrument()
            logger.info("[OTel] httpx instrumentation 已启用")
        except Exception as e:
            logger.warning(f"[OTel] httpx instrumentation 失败: {e}")
    else:
        logger.debug(
            "[OTel] httpx instrumentation 未安装"
            "（pip install opentelemetry-instrumentation-httpx）"
        )

    return True
