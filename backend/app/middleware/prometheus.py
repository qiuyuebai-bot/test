"""
轻量级 Prometheus 指标采集
无外部依赖，手动实现 Counter / Gauge / Histogram
暴露 /metrics 端点供 Prometheus 抓取
"""
import time
import re
import threading
import bisect
from loguru import logger
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, PlainTextResponse


class Metric:
    """指标基类"""
    def __init__(self, name: str, description: str, labels: Tuple[str, ...] = ()):
        self.name = name
        self.description = description
        self.label_names = labels
        self._lock = threading.Lock()

    def _label_key(self, labels: dict) -> Tuple:
        """从 kwargs 提取与 label_names 对应的标签键"""
        return tuple(labels.get(k, "") for k in self.label_names)


class Counter(Metric):
    """Counter 计数器（只增不减）"""
    def __init__(self, name: str, description: str, labels: Tuple[str, ...] = ()):
        super().__init__(name, description, labels)
        self._values: Dict[Tuple, float] = defaultdict(float)

    def inc(self, amount: float = 1, **labels):
        label_key = self._label_key(labels)
        with self._lock:
            self._values[label_key] += amount

    def get(self, **labels) -> float:
        label_key = self._label_key(labels)
        return self._values.get(label_key, 0.0)


class Gauge(Metric):
    """Gauge 仪表盘（可增可减）"""
    def __init__(self, name: str, description: str, labels: Tuple[str, ...] = ()):
        super().__init__(name, description, labels)
        self._values: Dict[Tuple, float] = defaultdict(float)

    def set(self, value: float, **labels):
        label_key = self._label_key(labels)
        with self._lock:
            self._values[label_key] = value

    def inc(self, amount: float = 1, **labels):
        label_key = self._label_key(labels)
        with self._lock:
            self._values[label_key] += amount

    def dec(self, amount: float = 1, **labels):
        label_key = self._label_key(labels)
        with self._lock:
            self._values[label_key] -= amount

    def get(self, **labels) -> float:
        label_key = self._label_key(labels)
        return self._values.get(label_key, 0.0)


class Histogram(Metric):
    """Histogram 直方图（观测值分布）"""
    DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

    def __init__(self, name: str, description: str, labels: Tuple[str, ...] = (),
                 buckets: Tuple[float, ...] = None):
        super().__init__(name, description, labels)
        self.buckets = sorted(buckets or self.DEFAULT_BUCKETS)
        self._bucket_counts: Dict[Tuple, List[int]] = defaultdict(
            lambda: [0] * (len(self.buckets) + 1)
        )
        self._sums: Dict[Tuple, float] = defaultdict(float)
        self._counts: Dict[Tuple, int] = defaultdict(int)

    def observe(self, value: float, **labels):
        label_key = self._label_key(labels)
        with self._lock:
            # 累积桶：所有 upper >= value 的桶都 +1
            idx = bisect.bisect_left(self.buckets, value)
            for i in range(idx, len(self.buckets)):
                self._bucket_counts[label_key][i] += 1
            self._bucket_counts[label_key][-1] += 1
            self._sums[label_key] += value
            self._counts[label_key] += 1


# ===========================================
# 全局指标注册表
# ===========================================

class MetricsRegistry:
    """指标注册表"""
    def __init__(self):
        self._metrics: Dict[str, Metric] = {}
        self._lock = threading.Lock()
        self._start_time = time.time()

    def register(self, metric: Metric) -> Metric:
        with self._lock:
            if metric.name in self._metrics:
                return self._metrics[metric.name]
            self._metrics[metric.name] = metric
        return metric

    def generate_prometheus_text(self) -> str:
        """生成 Prometheus 文本格式"""
        lines: List[str] = []
        
        for metric in self._metrics.values():
            lines.append(f"# HELP {metric.name} {metric.description}")
            
            if isinstance(metric, Counter):
                lines.append(f"# TYPE {metric.name} counter")
                with metric._lock:
                    for label_key, value in metric._values.items():
                        label_str = self._format_labels(metric.label_names, label_key)
                        lines.append(f"{metric.name}{label_str} {value}")
                        
            elif isinstance(metric, Gauge):
                lines.append(f"# TYPE {metric.name} gauge")
                with metric._lock:
                    for label_key, value in metric._values.items():
                        label_str = self._format_labels(metric.label_names, label_key)
                        lines.append(f"{metric.name}{label_str} {value}")
                        
            elif isinstance(metric, Histogram):
                lines.append(f"# TYPE {metric.name} histogram")
                with metric._lock:
                    for label_key in metric._counts:
                        for i, upper in enumerate(metric.buckets):
                            le_str = self._format_labels(
                                tuple(list(metric.label_names) + ["le"]),
                                tuple(list(label_key) + [str(upper)])
                            )
                            count = metric._bucket_counts[label_key][i]
                            lines.append(f"{metric.name}_bucket{le_str} {count}")
                        inf_str = self._format_labels(
                            tuple(list(metric.label_names) + ["le"]),
                            tuple(list(label_key) + ["+Inf"])
                        )
                        lines.append(f"{metric.name}_bucket{inf_str} {metric._bucket_counts[label_key][-1]}")
                        
                        sum_str = self._format_labels(metric.label_names, label_key)
                        lines.append(f"{metric.name}_sum{sum_str} {metric._sums[label_key]}")
                        lines.append(f"{metric.name}_count{sum_str} {metric._counts[label_key]}")
            
            lines.append("")
        
        return "\n".join(lines)

    @staticmethod
    def _format_labels(names: Tuple[str, ...], values: Tuple) -> str:
        if not names:
            return ""
        pairs = []
        for n, v in zip(names, values):
            v_str = str(v).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
            pairs.append(f'{n}="{v_str}"')
        return "{" + ",".join(pairs) + "}"


registry = MetricsRegistry()

# ===========================================
# 预定义 RED 指标
# ===========================================

http_requests_total = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    labels=("method", "endpoint", "status_code"),
)
registry.register(http_requests_total)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    labels=("method", "endpoint"),
)
registry.register(http_request_duration_seconds)

http_requests_in_progress = Gauge(
    "http_requests_in_progress",
    "Number of HTTP requests currently being processed",
)
registry.register(http_requests_in_progress)

app_info = Gauge(
    "app_info",
    "Application information (always 1)",
    labels=("version",),
)
registry.register(app_info)

llm_calls_total = Counter(
    "llm_calls_total",
    "Total number of LLM API calls",
    labels=("model", "status"),
)
registry.register(llm_calls_total)

llm_call_duration_seconds = Histogram(
    "llm_call_duration_seconds",
    "LLM API call duration in seconds",
    labels=("model",),
)
registry.register(llm_call_duration_seconds)

llm_tokens_total = Counter(
    "llm_tokens_total",
    "Total tokens used by LLM calls",
    labels=("model", "type"),
)
registry.register(llm_tokens_total)

db_connections_active = Gauge(
    "db_connections_active",
    "Number of active database connections in the pool",
)
registry.register(db_connections_active)

agent_tasks_total = Counter(
    "agent_tasks_total",
    "Total number of agent tasks",
    labels=("agent_type", "status"),
)
registry.register(agent_tasks_total)

knowledge_docs_total = Gauge(
    "knowledge_docs_total",
    "Total number of knowledge documents",
    labels=("industry",),
)
registry.register(knowledge_docs_total)

knowledge_slices_total = Gauge(
    "knowledge_slices_total",
    "Total number of knowledge slices",
)
registry.register(knowledge_slices_total)

learning_resources_total = Gauge(
    "learning_resources_total",
    "Total number of generated learning resources",
)
registry.register(learning_resources_total)


# ===========================================
# Prometheus 中间件
# ===========================================

class PrometheusMiddleware(BaseHTTPMiddleware):
    """Prometheus 指标收集中间件"""

    # 预编译的路径归一化规则（避免路径参数导致指标基数爆炸）
    _PATH_PATTERNS: List[Tuple["re.Pattern", str]] = [
        (re.compile(r"/api/v1/learners/\d+"), "/api/v1/learners/{id}"),
        (re.compile(r"/api/v1/knowledge/docs/\d+"), "/api/v1/knowledge/docs/{id}"),
        (re.compile(r"/api/v1/knowledge/slices/\d+"), "/api/v1/knowledge/slices/{id}"),
        (re.compile(r"/api/v1/resources/\d+"), "/api/v1/resources/{id}"),
        (re.compile(r"/api/v1/agent/tasks/\d+"), "/api/v1/agent/tasks/{id}"),
        (re.compile(r"/api/v1/reports/\w+"), "/api/v1/reports/{type}"),
    ]

    def __init__(self, app):
        super().__init__(app)

    def _normalize_path(self, path: str) -> str:
        """将含参数的路径归一化，避免指标基数爆炸"""
        for pattern, replacement in self._PATH_PATTERNS:
            if pattern.match(path):
                return replacement
        return path

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path == "/metrics" or request.url.path == "/api/v1/metrics/prometheus":
            return await call_next(request)

        endpoint = self._normalize_path(request.url.path)
        method = request.method

        http_requests_in_progress.inc()
        start = time.time()

        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            status_code = 500
            raise
        finally:
            duration = time.time() - start
            http_requests_in_progress.dec()
            http_requests_total.inc(
                method=method,
                endpoint=endpoint,
                status_code=str(status_code),
            )
            http_request_duration_seconds.observe(
                duration,
                method=method,
                endpoint=endpoint,
            )


# 模块级缓存的运行时指标 Gauge（避免每次请求重新创建）
_runtime_gauges: Optional[Dict[str, Gauge]] = None


def _get_runtime_gauges() -> Dict[str, Gauge]:
    """惰性创建并缓存运行时 Gauge（仅创建一次，后续复用）"""
    global _runtime_gauges
    if _runtime_gauges is None:
        _runtime_gauges = {
            "process_cpu": registry.register(Gauge(
                "process_cpu_usage_percent",
                "Process CPU usage percentage",
            )),
            "process_mem": registry.register(Gauge(
                "process_memory_rss_bytes",
                "Process RSS memory in bytes",
            )),
            "uptime": registry.register(Gauge(
                "app_uptime_seconds",
                "Application uptime in seconds",
            )),
        }
    return _runtime_gauges


_db_stats_cache = {"timestamp": 0.0, "slices": 0, "resources": 0}
_DB_STATS_CACHE_TTL = 30.0


async def prometheus_metrics_endpoint(request: Request) -> PlainTextResponse:
    """Prometheus /metrics 端点"""
    from app.config import settings

    app_info.set(1, version=settings.APP_VERSION)

    gauges = _get_runtime_gauges()

    try:
        import psutil
        process = psutil.Process()
        gauges["process_cpu"].set(process.cpu_percent(interval=0))
        gauges["process_mem"].set(process.memory_info().rss)
        gauges["uptime"].set(time.time() - registry._start_time)
    except ImportError:
        logger.warning("psutil 未安装，进程资源指标不可用")
    except Exception as e:
        logger.warning(f"采集进程资源指标失败: {e}")

    now = time.time()
    if now - _db_stats_cache["timestamp"] > _DB_STATS_CACHE_TTL:
        try:
            from app.database import SessionLocal
            from app.models import KnowledgeSlice, LearningResource
            from sqlalchemy import func
            from starlette.concurrency import run_in_threadpool

            def _query_counts():
                db = SessionLocal()
                try:
                    total_slices = db.query(func.count(KnowledgeSlice.id)).scalar() or 0
                    total_resources = db.query(func.count(LearningResource.id)).scalar() or 0
                    return total_slices, total_resources
                finally:
                    db.close()

            total_slices, total_resources = await run_in_threadpool(_query_counts)
            _db_stats_cache["slices"] = total_slices
            _db_stats_cache["resources"] = total_resources
            _db_stats_cache["timestamp"] = now
        except Exception as e:
            logger.warning(f"采集数据库统计指标失败: {e}")

    knowledge_slices_total.set(_db_stats_cache["slices"])
    learning_resources_total.set(_db_stats_cache["resources"])

    return PlainTextResponse(
        registry.generate_prometheus_text(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
