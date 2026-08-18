"""
大模型通用调用封装
接入 DeepSeek 等 OpenAI 兼容 API（使用 httpx 直连）
使用单例 httpx 客户端复用连接，避免重复 TCP 握手开销

P3-3 增强：
- Prompt 哈希缓存（SHA256 of system_prompt + user_prompt，TTL 1 小时）
  仅对低温度（≤0.3）的确定性调用启用缓存，避免缓存创造性输出
- Token 用量统计（prompt_tokens / completion_tokens 累计计数）
- 已支持 SSE 流式输出（async_stream）
"""
from typing import Optional, List, Dict, Any, Tuple, AsyncGenerator
import asyncio
import json
import atexit
import hashlib
import time
import threading
from collections import OrderedDict

import httpx
from loguru import logger

from app.config import settings
from app.utils.circuit_breaker import CircuitBreaker


class LLMUnavailableError(RuntimeError):
    """Raised when a strict model call cannot reach a usable provider."""

    def __init__(self, reason: str = "provider_unavailable") -> None:
        self.reason = reason
        super().__init__(f"DeepSeek 当前不可用（{reason}）")


class LLMUtil:
    """
    大模型通用调用工具类
    接入统一的 OpenAI 兼容协议 API（默认 DeepSeek）
    使用 httpx 直连，避免 OpenAI SDK 在受限环境中的兼容问题
    复用 httpx 客户端连接池，提升并发性能
    """

    _available: Optional[bool] = None
    _sync_client: Optional[httpx.Client] = None
    _async_client: Optional[httpx.AsyncClient] = None

    # ===========================================
    # P3-3: Prompt 响应缓存（确定性调用专用）
    # ===========================================
    # 仅缓存 temperature ≤ 0.3 的调用结果，避免缓存创造性输出
    # 流式调用（async_stream）不参与缓存
    _response_cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
    _response_cache_ttl: int = 3600  # 默认 1 小时
    _response_cache_max_size: int = 1024  # LRU 最大条目数
    _response_cache_lock: threading.RLock = threading.RLock()
    _response_cache_redis = None
    _response_cache_redis_lock: threading.Lock = threading.Lock()
    _response_cache_redis_disabled_until: float = 0.0
    _response_cache_redis_retry_interval: float = 5.0
    _response_cache_redis_prefix: str = "llm:response:v1:"
    _cache_enabled_threshold: float = 0.3  # temperature ≤ 此值才启用缓存
    _cache_hits: int = 0
    _cache_misses: int = 0

    # ===========================================
    # P3-3: Token 用量统计
    # ===========================================
    _total_prompt_tokens: int = 0
    _total_completion_tokens: int = 0
    _total_calls: int = 0
    _total_errors: int = 0
    _usage_lock: threading.Lock = threading.Lock()

    # ===========================================
    # Phase 7: LLM 熔断器（防止 LLM 服务故障导致雪崩）
    # ===========================================
    _circuit_breaker: CircuitBreaker = CircuitBreaker(
        failure_threshold=settings.LLM_CIRCUIT_BREAKER_FAILURE_THRESHOLD,
        recovery_timeout=float(settings.LLM_CIRCUIT_BREAKER_RECOVERY_TIMEOUT),
        name="llm",
    )

    # ===========================================
    # 客户端生命周期管理（连接池复用）
    # ===========================================

    @classmethod
    def _get_sync_client(cls, timeout: float = 120.0) -> httpx.Client:
        """
        获取同步 httpx 客户端（单例，复用连接池）

        Args:
            timeout: 请求超时时间（仅在首次创建时生效）

        Returns:
            httpx.Client 实例
        """
        if cls._sync_client is None or cls._sync_client.is_closed:
            cls._sync_client = httpx.Client(
                timeout=timeout,
                limits=httpx.Limits(
                    max_connections=20,
                    max_keepalive_connections=10,
                    keepalive_expiry=30.0,
                ),
                headers=cls._default_headers(),
                # 不使用系统代理环境变量（HTTP_PROXY/HTTPS_PROXY）：
                # 本机配置了失效代理（127.0.0.1:7892 未运行），trust_env=True 会走代理导致
                # WinError 10061 连接被拒；LLM API（DeepSeek）实测可直连，故绕过系统代理。
                trust_env=False,
            )
            logger.debug("[LLM] 创建同步 httpx 客户端（连接池模式）")
        return cls._sync_client

    @classmethod
    def _get_async_client(cls, timeout: float = 120.0) -> httpx.AsyncClient:
        """
        获取异步 httpx 客户端（单例，复用连接池）

        Args:
            timeout: 请求超时时间（仅在首次创建时生效）

        Returns:
            httpx.AsyncClient 实例
        """
        if cls._async_client is None or cls._async_client.is_closed:
            cls._async_client = httpx.AsyncClient(
                timeout=timeout,
                limits=httpx.Limits(
                    max_connections=20,
                    max_keepalive_connections=10,
                    keepalive_expiry=30.0,
                ),
                headers=cls._default_headers(),
                trust_env=False,  # 同同步客户端：绕过失效的系统代理
            )
            logger.debug("[LLM] 创建异步 httpx 客户端（连接池模式）")
        return cls._async_client

    @classmethod
    def _default_headers(cls) -> Dict[str, str]:
        """默认请求头"""
        return {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }

    @classmethod
    def close_clients(cls) -> None:
        """关闭所有客户端连接（应用退出时调用）"""
        if cls._sync_client is not None and not cls._sync_client.is_closed:
            cls._sync_client.close()
            cls._sync_client = None
            logger.debug("[LLM] 同步 httpx 客户端已关闭")
        if cls._async_client is not None and not cls._async_client.is_closed:
            cls._async_client = None

    @classmethod
    async def aclose_clients(cls) -> None:
        """异步关闭所有客户端连接（ASGI shutdown 时调用）"""
        if cls._sync_client is not None and not cls._sync_client.is_closed:
            cls._sync_client.close()
            cls._sync_client = None
        if cls._async_client is not None and not cls._async_client.is_closed:
            await cls._async_client.aclose()
            cls._async_client = None
            logger.debug("[LLM] 异步 httpx 客户端已关闭")

    # ===========================================
    # 公共方法
    # ===========================================

    @classmethod
    def is_available(cls) -> bool:
        """检查大模型是否可用"""
        if cls._available is not None:
            return cls._available
        cls._available = bool((settings.OPENAI_API_KEY or "").strip())
        return cls._available

    @classmethod
    def health_check(cls) -> Dict[str, Any]:
        """Check provider reachability without exposing credentials or payloads."""
        started = time.perf_counter()
        if not cls.is_available():
            return {"available": False, "reason": "unauthorized"}
        try:
            response = cls._get_sync_client(timeout=10.0).get(
                f"{settings.OPENAI_API_BASE.rstrip('/')}/models"
            )
            latency_ms = round((time.perf_counter() - started) * 1000)
            if response.status_code in (401, 403):
                reason = "unauthorized"
            elif response.status_code == 404:
                reason = "invalid_model"
            elif response.status_code == 429:
                reason = "rate_limited"
            elif response.status_code >= 400:
                reason = "provider_error"
            else:
                return {"available": True, "provider": "deepseek", "model": settings.OPENAI_MODEL_NAME, "latency_ms": latency_ms}
            return {"available": False, "reason": reason, "latency_ms": latency_ms}
        except httpx.TimeoutException:
            return {"available": False, "reason": "timeout"}
        except (httpx.ConnectError, httpx.NetworkError, OSError):
            return {"available": False, "reason": "network_error"}
        except Exception:
            return {"available": False, "reason": "provider_error"}

    @classmethod
    def _build_messages(
        cls,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """构建 messages 列表"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    @classmethod
    def _chat_url(cls) -> str:
        """获取 Chat Completions API 地址"""
        return f"{settings.OPENAI_API_BASE.rstrip('/')}/chat/completions"

    @classmethod
    def _call_api(
        cls,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        model: Optional[str] = None,
        stream: bool = False,
    ) -> httpx.Response:
        """
        调用 Chat Completions API（使用复用的客户端）

        Args:
            messages: 对话消息列表
            temperature: 温度参数
            model: 模型名称
            stream: 是否流式

        Returns:
            httpx Response 对象
        """
        payload = {
            "model": model or settings.OPENAI_MODEL_NAME,
            "messages": messages,
            "temperature": temperature if temperature is not None else settings.OPENAI_TEMPERATURE,
            "max_tokens": settings.OPENAI_MAX_TOKENS,
            "thinking": {
                "type": "enabled" if settings.OPENAI_THINKING_ENABLED else "disabled"
            },
        }
        if stream:
            payload["stream"] = True

        client = cls._get_sync_client()
        return client.post(
            cls._chat_url(),
            json=payload,
        )

    @classmethod
    def _parse_response(cls, response: httpx.Response) -> Tuple[str, Dict[str, int]]:
        """
        解析 API 响应

        Args:
            response: httpx Response 对象

        Returns:
            (响应文本, Token用量字典)
        """
        if response.status_code != 200:
            logger.error(f"LLM API 返回错误: status={response.status_code}, body={response.text[:500]}")
            raise Exception(f"API error: {response.status_code}")

        data = response.json()
        content = data["choices"][0]["message"]["content"] or ""
        if not content.strip():
            raise ValueError("LLM response did not contain final content")
        usage_data = data.get("usage", {})
        usage = {
            "prompt_tokens": usage_data.get("prompt_tokens", 0),
            "completion_tokens": usage_data.get("completion_tokens", 0),
            "total_tokens": usage_data.get("total_tokens", 0),
        }
        logger.debug(f"LLM 调用成功: tokens={usage['total_tokens']}")
        cls._record_usage(usage)
        return content, usage

    # ===========================================
    # P3-3: Prompt 哈希缓存与用量统计
    # ===========================================

    @classmethod
    def _compute_prompt_hash(
        cls,
        prompt: str,
        system_prompt: Optional[str],
        model: Optional[str],
        temperature: Optional[float],
    ) -> str:
        """计算 prompt 哈希（含 system_prompt + model + temperature 量化）"""
        # temperature 量化到 0.1 粒度，避免微小浮点差异导致缓存失效
        temp_quantized = round(float(temperature if temperature is not None else settings.OPENAI_TEMPERATURE), 1)
        model_name = model or settings.OPENAI_MODEL_NAME
        key_str = f"{model_name}|{temp_quantized}|{system_prompt or ''}|{prompt}"
        return hashlib.sha256(key_str.encode("utf-8")).hexdigest()

    @classmethod
    def _is_cacheable(cls, temperature: Optional[float]) -> bool:
        """判断该调用是否可缓存（仅低温度确定性调用才缓存）"""
        temp = float(temperature if temperature is not None else settings.OPENAI_TEMPERATURE)
        return temp <= cls._cache_enabled_threshold

    @classmethod
    def _get_redis_cache_client(cls):
        if not settings.REDIS_URL or time.monotonic() < cls._response_cache_redis_disabled_until:
            return None
        with cls._response_cache_redis_lock:
            if cls._response_cache_redis is not None:
                return cls._response_cache_redis
            try:
                import redis

                cls._response_cache_redis = redis.Redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=0.2,
                    socket_timeout=0.2,
                )
                return cls._response_cache_redis
            except Exception as exc:
                cls._response_cache_redis_disabled_until = (
                    time.monotonic() + cls._response_cache_redis_retry_interval
                )
                logger.warning("Redis LLM 缓存客户端初始化失败，回退本地缓存: {}", exc)
                return None

    @classmethod
    def _disable_redis_cache(cls, exc: Exception) -> None:
        with cls._response_cache_redis_lock:
            cls._response_cache_redis_disabled_until = (
                time.monotonic() + cls._response_cache_redis_retry_interval
            )
            client = cls._response_cache_redis
            cls._response_cache_redis = None
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
        logger.warning("Redis LLM 缓存不可用，回退本地缓存: {}", exc)

    @classmethod
    def _get_redis_cached_response(cls, cache_key: str) -> Optional[Tuple[str, Dict[str, int]]]:
        client = cls._get_redis_cache_client()
        if client is None:
            return None
        try:
            raw = client.get(f"{cls._response_cache_redis_prefix}{cache_key}")
            if not raw:
                return None
            payload = json.loads(raw)
            return str(payload["value"]), dict(payload.get("usage") or {})
        except Exception as exc:
            cls._disable_redis_cache(exc)
            return None

    @classmethod
    def _set_redis_cached_response(
        cls,
        cache_key: str,
        value: Tuple[str, Dict[str, int]],
        ttl: int,
    ) -> None:
        client = cls._get_redis_cache_client()
        if client is None:
            return
        try:
            payload = json.dumps({"value": value[0], "usage": value[1]}, ensure_ascii=False)
            client.set(
                f"{cls._response_cache_redis_prefix}{cache_key}",
                payload,
                ex=ttl,
            )
        except Exception as exc:
            cls._disable_redis_cache(exc)

    @classmethod
    def _set_local_cached_response(
        cls,
        cache_key: str,
        value: Tuple[str, Dict[str, int]],
        ttl: int,
    ) -> None:
        with cls._response_cache_lock:
            cls._response_cache[cache_key] = {
                "value": value,
                "timestamp": time.time(),
                "ttl": ttl,
            }
            cls._response_cache.move_to_end(cache_key)
            if len(cls._response_cache) > cls._response_cache_max_size:
                oldest_key = next(iter(cls._response_cache))
                del cls._response_cache[oldest_key]

    @classmethod
    def _get_cached_response(cls, cache_key: str) -> Optional[Tuple[str, Dict[str, int]]]:
        """获取缓存的响应（线程安全，过期自动清理）"""
        remote = cls._get_redis_cached_response(cache_key)
        if remote is not None:
            with cls._response_cache_lock:
                cls._cache_hits += 1
            cls._set_local_cached_response(cache_key, remote, cls._response_cache_ttl)
            return remote

        with cls._response_cache_lock:
            entry = cls._response_cache.get(cache_key)
            if entry is None:
                cls._cache_misses += 1
                return None
            if time.time() - entry["timestamp"] > entry["ttl"]:
                # 已过期
                cls._response_cache.pop(cache_key, None)
                cls._cache_misses += 1
                return None
            cls._cache_hits += 1
            cls._response_cache.move_to_end(cache_key)
            return entry["value"]

    @classmethod
    def _set_cached_response(
        cls,
        cache_key: str,
        value: Tuple[str, Dict[str, int]],
        ttl: Optional[int] = None,
    ) -> None:
        """写入缓存响应（线程安全）"""
        effective_ttl = ttl or cls._response_cache_ttl
        cls._set_local_cached_response(cache_key, value, effective_ttl)
        cls._set_redis_cached_response(cache_key, value, effective_ttl)

    @classmethod
    def _record_usage(cls, usage: Dict[str, int]) -> None:
        """记录 token 用量（线程安全）"""
        with cls._usage_lock:
            cls._total_prompt_tokens += int(usage.get("prompt_tokens", 0))
            cls._total_completion_tokens += int(usage.get("completion_tokens", 0))
            cls._total_calls += 1

    @classmethod
    def _record_error(cls) -> None:
        """记录调用失败（线程安全）"""
        with cls._usage_lock:
            cls._total_errors += 1

    @classmethod
    def get_usage_stats(cls) -> Dict[str, Any]:
        """获取 LLM 用量统计"""
        with cls._usage_lock:
            total_tokens = cls._total_prompt_tokens + cls._total_completion_tokens
            cache_total = cls._cache_hits + cls._cache_misses
            return {
                "total_calls": cls._total_calls,
                "total_errors": cls._total_errors,
                "prompt_tokens": cls._total_prompt_tokens,
                "completion_tokens": cls._total_completion_tokens,
                "total_tokens": total_tokens,
                "cache_hits": cls._cache_hits,
                "cache_misses": cls._cache_misses,
                "cache_hit_rate": round(cls._cache_hits / cache_total, 4) if cache_total > 0 else 0.0,
                "circuit_breaker": cls._circuit_breaker.get_state_info() if settings.LLM_CIRCUIT_BREAKER_ENABLED else None,
            }

    @classmethod
    def reset_usage_stats(cls) -> None:
        """重置用量统计与缓存命中计数"""
        with cls._usage_lock:
            cls._total_prompt_tokens = 0
            cls._total_completion_tokens = 0
            cls._total_calls = 0
            cls._total_errors = 0
        with cls._response_cache_lock:
            cls._cache_hits = 0
            cls._cache_misses = 0

    @classmethod
    def clear_response_cache(cls) -> None:
        """清空 prompt 响应缓存"""
        with cls._response_cache_lock:
            cls._response_cache.clear()

    # ===========================================
    # 同步调用
    # ===========================================

    @classmethod
    def sync_call(
        cls,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        model: Optional[str] = None,
        use_cache: bool = True,
        allow_mock: bool = True,
    ) -> Tuple[str, Dict[str, int]]:
        """
        同步调用大模型

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词
            temperature: 温度参数
            model: 模型名称
            use_cache: 是否启用 prompt 哈希缓存（仅 temperature ≤ 0.3 时实际生效）

        Returns:
            (响应文本, Token用量字典)
        """
        if not cls.is_available():
            if not allow_mock:
                raise LLMUnavailableError("unauthorized")
            return cls._generate_mock_response(prompt, system_prompt), {
                "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0
            }

        # P3-3: 缓存命中检查（仅低温度确定性调用）
        cache_key: Optional[str] = None
        if use_cache and cls._is_cacheable(temperature):
            cache_key = cls._compute_prompt_hash(prompt, system_prompt, model, temperature)
            cached = cls._get_cached_response(cache_key)
            if cached is not None:
                logger.debug(f"[LLM] 缓存命中: key={cache_key[:12]}...")
                return cached

        messages = cls._build_messages(prompt, system_prompt)

        # Phase 7: 熔断器检查（开启时直接返回 mock，避免雪崩）
        if settings.LLM_CIRCUIT_BREAKER_ENABLED and not cls._circuit_breaker.allow_request():
            if not allow_mock:
                raise LLMUnavailableError("circuit_open")
            logger.warning("[LLM] 熔断器开启中，跳过 LLM 调用，返回 mock 响应")
            return cls._generate_mock_response(prompt, system_prompt), {
                "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0
            }

        try:
            response = cls._call_api(messages, temperature, model)
            result = cls._parse_response(response)
            if settings.LLM_CIRCUIT_BREAKER_ENABLED:
                cls._circuit_breaker._on_success()
            # 写入缓存（仅缓存非空响应）
            if cache_key and result[0]:
                cls._set_cached_response(cache_key, result)
            return result
        except Exception as e:
            if settings.LLM_CIRCUIT_BREAKER_ENABLED:
                cls._circuit_breaker._on_failure()
            logger.error(f"LLM sync_call 失败: {e}")
            cls._record_error()
            if not allow_mock:
                reason = "timeout" if isinstance(e, httpx.TimeoutException) else "provider_error"
                if isinstance(e, (httpx.ConnectError, httpx.NetworkError, OSError)):
                    reason = "network_error"
                error_text = str(e)
                if error_text.startswith("API error: 401"):
                    reason = "unauthorized"
                elif error_text.startswith("API error: 403"):
                    reason = "unauthorized"
                elif error_text.startswith("API error: 404"):
                    reason = "invalid_model"
                elif error_text.startswith("API error: 429"):
                    reason = "rate_limited"
                raise LLMUnavailableError(reason) from e
            return cls._generate_mock_response(prompt, system_prompt), {
                "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0
            }

    @classmethod
    def call_with_template(
        cls,
        template: str,
        params: Dict[str, Any],
        system_prompt: Optional[str] = None,
    ) -> Tuple[str, Dict[str, int]]:
        """
        使用模板调用大模型

        Args:
            template: 提示词模板
            params: 模板参数
            system_prompt: 系统提示词

        Returns:
            (响应文本, Token用量字典)
        """
        prompt = template.format(**params)
        return cls.sync_call(prompt, system_prompt)

    @classmethod
    def call_with_prompt_template(
        cls,
        template_name: str,
        variables: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
        model: Optional[str] = None,
        use_cache: bool = True,
        allow_mock: bool = True,
    ) -> Tuple[str, Dict[str, int]]:
        """
        使用 Prompt 工程化模板调用大模型（P3-4）

        从 backend/app/prompts/templates/<template_name>.txt 加载模板，
        渲染变量后调用 sync_call。模板可包含 `--- SYSTEM ---` 与 `--- USER ---`
        双段，分别作为 system_prompt 与 user_prompt。

        Args:
            template_name: 模板名（不含 .txt 扩展名）
            variables: 模板变量字典
            temperature: 温度参数（默认由模板语义决定，如幻觉检测用 0.1）
            model: 模型名称
            use_cache: 是否启用 prompt 哈希缓存

        Returns:
            (响应文本, Token用量字典)
        """
        from app.prompts import PromptManager

        rendered = PromptManager.render(template_name, **(variables or {}))
        logger.debug(
            f"[LLM] 调用 prompt 模板: name={template_name}, version={rendered.version}"
        )
        return cls.sync_call(
            prompt=rendered.user_prompt,
            system_prompt=rendered.system_prompt,
            temperature=temperature,
            model=model,
            use_cache=use_cache,
            allow_mock=allow_mock,
        )

    @classmethod
    def multi_turn_call(
        cls,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        model: Optional[str] = None,
    ) -> Tuple[str, Dict[str, int]]:
        """
        多轮对话调用

        Args:
            messages: 对话消息列表 [{"role": "user/assistant/system", "content": "..."}]
            temperature: 温度参数
            model: 模型名称

        Returns:
            (响应文本, Token用量字典)
        """
        if not cls.is_available():
            last_message = messages[-1]["content"] if messages else ""
            response = cls._generate_mock_response(last_message, None)
            return response, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        # Phase 7: 熔断器检查
        if settings.LLM_CIRCUIT_BREAKER_ENABLED and not cls._circuit_breaker.allow_request():
            logger.warning("[LLM] 熔断器开启中，跳过 multi_turn 调用，返回 mock 响应")
            last_message = messages[-1]["content"] if messages else ""
            response = cls._generate_mock_response(last_message, None)
            return response, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        try:
            response = cls._call_api(messages, temperature, model)
            result = cls._parse_response(response)
            if settings.LLM_CIRCUIT_BREAKER_ENABLED:
                cls._circuit_breaker._on_success()
            return result
        except Exception as e:
            if settings.LLM_CIRCUIT_BREAKER_ENABLED:
                cls._circuit_breaker._on_failure()
            logger.error(f"LLM multi_turn_call 失败: {e}")
            cls._record_error()
            last_message = messages[-1]["content"] if messages else ""
            response = cls._generate_mock_response(last_message, None)
            return response, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    # ===========================================
    # 异步调用
    # ===========================================

    @classmethod
    async def async_call(
        cls,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        model: Optional[str] = None,
        use_cache: bool = True,
    ) -> Tuple[str, Dict[str, int]]:
        """
        异步调用大模型

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词
            temperature: 温度参数
            model: 模型名称
            use_cache: 是否启用 prompt 哈希缓存（仅 temperature ≤ 0.3 时实际生效）

        Returns:
            (响应文本, Token用量字典)
        """
        if not cls.is_available():
            return cls._generate_mock_response(prompt, system_prompt), {
                "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0
            }

        # P3-3: 缓存命中检查（仅低温度确定性调用）
        cache_key: Optional[str] = None
        if use_cache and cls._is_cacheable(temperature):
            cache_key = cls._compute_prompt_hash(prompt, system_prompt, model, temperature)
            cached = await asyncio.to_thread(cls._get_cached_response, cache_key)
            if cached is not None:
                logger.debug(f"[LLM] 缓存命中: key={cache_key[:12]}...")
                return cached

        messages = cls._build_messages(prompt, system_prompt)
        payload = {
            "model": model or settings.OPENAI_MODEL_NAME,
            "messages": messages,
            "temperature": temperature if temperature is not None else settings.OPENAI_TEMPERATURE,
            "max_tokens": settings.OPENAI_MAX_TOKENS,
            "thinking": {
                "type": "enabled" if settings.OPENAI_THINKING_ENABLED else "disabled"
            },
        }

        # Phase 7: 熔断器检查
        if settings.LLM_CIRCUIT_BREAKER_ENABLED and not cls._circuit_breaker.allow_request():
            logger.warning("[LLM] 熔断器开启中，跳过 async 调用，返回 mock 响应")
            return cls._generate_mock_response(prompt, system_prompt), {
                "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0
            }

        try:
            client = cls._get_async_client()
            response = await client.post(
                cls._chat_url(),
                json=payload,
            )
            result = cls._parse_response(response)
            if settings.LLM_CIRCUIT_BREAKER_ENABLED:
                cls._circuit_breaker._on_success()
            if cache_key and result[0]:
                await asyncio.to_thread(cls._set_cached_response, cache_key, result)
            return result
        except Exception as e:
            if settings.LLM_CIRCUIT_BREAKER_ENABLED:
                cls._circuit_breaker._on_failure()
            logger.error(f"LLM async_call 失败: {e}")
            cls._record_error()
            return cls._generate_mock_response(prompt, system_prompt), {
                "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0
            }

    @classmethod
    async def async_stream(
        cls,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        model: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        异步流式调用大模型

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词
            temperature: 温度参数
            model: 模型名称

        Yields:
            流式响应的文本片段
        """
        if not cls.is_available():
            response = cls._generate_mock_response(prompt, system_prompt)
            for char in response:
                yield char
            return

        messages = cls._build_messages(prompt, system_prompt)
        payload = {
            "model": model or settings.OPENAI_MODEL_NAME,
            "messages": messages,
            "temperature": temperature if temperature is not None else settings.OPENAI_TEMPERATURE,
            "max_tokens": settings.OPENAI_MAX_TOKENS,
            "stream": True,
            "thinking": {
                "type": "enabled" if settings.OPENAI_THINKING_ENABLED else "disabled"
            },
        }

        try:
            client = cls._get_async_client()
            async with client.stream(
                "POST",
                cls._chat_url(),
                json=payload,
            ) as response:
                if response.status_code != 200:
                    body = await response.aread()
                    logger.error(f"LLM stream 错误: status={response.status_code}, body={body[:500]}")
                    response_text = cls._generate_mock_response(prompt, system_prompt)
                    for char in response_text:
                        yield char
                    return

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            if chunk.get("choices") and chunk["choices"][0].get("delta", {}).get("content"):
                                yield chunk["choices"][0]["delta"]["content"]
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error(f"LLM async_stream 失败: {e}")
            response = cls._generate_mock_response(prompt, system_prompt)
            for char in response:
                yield char

    # ===========================================
    # Mock 兜底（API 不可用时使用）
    # ===========================================

    @classmethod
    def _generate_mock_response(cls, prompt: str, system_prompt: Optional[str] = None) -> str:
        """生成模拟响应（兜底方案）"""
        if "诊断" in prompt or "诊断" in (system_prompt or ""):
            return json.dumps({
                "overall_score": 72,
                "overall_level": "中级学习者",
                "ability_scores": {
                    "theoretical_foundation": 75,
                    "programming_ability": 68,
                    "algorithm_design": 65,
                    "system_architecture": 70,
                    "data_analysis": 78,
                    "engineering_practice": 72
                },
                "knowledge_blind_areas": [
                    {"name": "系统架构", "severity": "medium", "description": "对大型系统设计模式理解不够深入"},
                    {"name": "算法设计", "severity": "high", "description": "高级算法如动态规划、贪心算法掌握不足"}
                ],
                "recommended_difficulty": {"recommended_difficulty": 3, "reason": "当前能力水平适合进阶难度"},
                "learning_suggestions": ["建议加强算法专项训练", "增加系统架构实战项目"],
                "_meta": {"model": "mock", "score": 82}
            }, ensure_ascii=False)

        elif "生成" in prompt or "资源" in prompt:
            # 提取 prompt 中的目标主题信息，使 mock 响应更有意义
            topic_hint = ""
            for line in prompt.split("\n"):
                if "知识" in line and "点" in line or "knowledge_topic" in line.lower() or "目标知识点" in line:
                    topic_hint = line.split("：")[-1].strip() if "：" in line else line.split(":")[-1].strip()
                    break
            if not topic_hint:
                for line in prompt.split("\n"):
                    stripped = line.strip()
                    if stripped and len(stripped) < 60 and not stripped.startswith("{") and "{" not in stripped:
                        topic_hint = stripped
                        break
            if not topic_hint:
                topic_hint = "指定领域"

            resource_type_hint = "学习资源"
            for line in prompt.split("\n"):
                if "resource_type" in line.lower() or "资源类型" in line:
                    rt = line.split("：")[-1].strip() if "：" in line else line.split(":")[-1].strip()
                    type_map = {"guide": "实操指南", "exercise": "分阶测试题", "lecture": "专属讲义"}
                    resource_type_hint = type_map.get(rt, resource_type_hint)
                    break

            return json.dumps({
                "resource_title": f"{topic_hint} - {resource_type_hint}",
                "content": (
                    f"# {topic_hint} {resource_type_hint}\n\n"
                    f"## 概述\n\n"
                    f"本资源聚焦于 **{topic_hint}** 领域的核心知识与实践。"
                    f"系统当前运行在确定性兜底模式（未配置 LLM API Key），"
                    f"以下内容基于知识库检索结果生成。\n\n"
                    f"## 学习指引\n\n"
                    f"1. 建议先了解 {topic_hint} 的基础概念和背景\n"
                    f"2. 通过实操练习加深理解\n"
                    f"3. 结合真实案例掌握应用场景\n\n"
                    f"> 💡 **提示**：配置 LLM API Key 后，系统将能够生成更丰富、"
                    f"更个性化的学习内容，包括详细的代码示例、案例分析、"
                    f"以及针对你学习风格定制的讲解方式。\n\n"
                    f"当前模式下，知识库中与「{topic_hint}」相关的内容"
                    f"将自动填充到资源中，请确保已在\"知识库管理\"中上传了相关文档。"
                ),
                "difficulty_level": 3,
                "topics": [topic_hint],
                "word_count": 300,
                "source_slice_ids": [],
                "source_doc_ids": [],
                "_meta": {"model": "mock", "score": 75, "note": "LLM unavailable, deterministic fallback will enrich with knowledge base content"}
            }, ensure_ascii=False)

        elif "校验" in prompt or "审核" in prompt or "修正" in prompt:
            return json.dumps({
                "passed": True,
                "score": 88,
                "issues": [],
                "suggestions": ["内容质量良好，可以发布"],
                "hallucination_detected": False,
                "hallucination_score": 0.05,
                "_meta": {"model": "mock"}
            }, ensure_ascii=False)

        else:
            return json.dumps({
                "result": "模拟响应成功",
                "message": "LLM API 不可用，返回模拟数据",
                "_meta": {"model": "mock"}
            }, ensure_ascii=False)


# 注册退出时关闭客户端
atexit.register(LLMUtil.close_clients)
