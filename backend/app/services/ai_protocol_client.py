"""Protocol-specific text generation adapters for runtime AI configurations."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Tuple

import httpx

from app.services.ai_providers import (
    PROTOCOL_ANTHROPIC,
    PROTOCOL_AZURE_OPENAI,
    PROTOCOL_BEDROCK,
    PROTOCOL_GEMINI,
    PROTOCOL_OLLAMA,
    PROTOCOL_OPENAI_CHAT,
    PROTOCOL_OPENAI_RESPONSES,
    PROTOCOL_VERTEX_AI,
    is_protocol_implemented,
)
from app.utils.llm_runtime import LLMRuntimeConfig


class RuntimeProtocolError(RuntimeError):
    """A safe, normalized provider error for runtime-configured requests."""

    def __init__(
        self,
        reason: str,
        status_code: int | None = None,
        public_message: str | None = None,
    ) -> None:
        self.reason = reason
        self.status_code = status_code
        self.public_message = public_message
        super().__init__(reason)


class AIProtocolClient:
    """Translate the internal message contract to each supported wire protocol."""

    # Service-account credentials are allowed to refresh only against Google's
    # documented OAuth token endpoint. Accepting a caller-supplied token URI
    # would give the credential parser a second SSRF-capable destination.
    VERTEX_TOKEN_URI = "https://oauth2.googleapis.com/token"

    _GENERATION_DEFAULTS: Dict[str, float] = {
        # OpenAI-compatible APIs use these values when a control is omitted.
        "temperature": 1.0,
        "top_p": 1.0,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0,
    }
    _PROVIDER_GENERATION_DEFAULTS: Dict[str, Dict[str, float]] = {
        # Anthropic documents a slightly-below-one nucleus default and does
        # not expose the OpenAI penalty controls.
        "anthropic": {"top_p": 0.999},
        # Gemini's documented baseline is topP=0.95; model-specific values
        # can still be supplied by the metadata endpoint in a later phase.
        "gemini": {"top_p": 0.95},
        "vertex_ai": {"top_p": 0.95},
        # DashScope's common Qwen text models default to temperature 0.7 and
        # top_p 0.8.  More specific reasoning/vision families are handled
        # below by model prefix.
        "qwen": {"temperature": 0.7, "top_p": 0.8},
        # The official Kimi model families exposed by Moonshot use top_p 0.95
        # as their sampling baseline.
        "moonshot": {"top_p": 0.95},
        "moonshot_global": {"top_p": 0.95},
        # MiniMax's current official text models use temperature 1.0 and
        # top_p 0.95 (Text-01 is the documented low-temperature exception).
        "minimax": {"top_p": 0.95},
        "minimax_global": {"top_p": 0.95},
    }
    _GENERATION_PUBLIC_KEYS: Dict[str, str] = {
        "temperature": "temperature",
        "top_p": "top_p",
        "frequency_penalty": "frequency_penalty",
        "presence_penalty": "presence_penalty",
    }
    _GENERATION_KEYS = ("temperature", "top_p", "frequency_penalty", "presence_penalty")
    _GENERATION_LABELS: Dict[str, str] = {
        "temperature": "温度",
        "top_p": "Top P",
        "frequency_penalty": "频率惩罚",
        "presence_penalty": "存在惩罚",
    }
    _GENERATION_DESCRIPTIONS: Dict[str, str] = {
        "temperature": "控制输出的随机程度。数值越高，结果越有变化。",
        "top_p": "限制采样候选词范围，通常与温度二选一调整。",
        "frequency_penalty": "降低重复出现相同词语的概率。",
        "presence_penalty": "鼓励或抑制引入新主题。",
    }

    @classmethod
    def generation_defaults(cls, runtime: LLMRuntimeConfig) -> Dict[str, float]:
        """Return the documented initial sampling values for a model."""

        defaults = dict(cls._GENERATION_DEFAULTS)
        defaults.update(cls._PROVIDER_GENERATION_DEFAULTS.get(runtime.provider, {}))
        model = runtime.model.strip().lower()
        if runtime.provider == "qwen":
            if "qwen-vl" in model and "thinking" not in model:
                defaults.update({"temperature": 0.01, "top_p": 0.001})
            elif "qwen-math" in model:
                defaults.update({"temperature": 0.0, "top_p": 1.0})
            elif any(token in model for token in ("qwq", "thinking", "qwen3")):
                defaults.update({"temperature": 0.6, "top_p": 0.95})
        elif runtime.provider in {"minimax", "minimax_global"} and "text-01" in model:
            defaults["temperature"] = 0.1
        return defaults

    @classmethod
    def default_generation_params(cls) -> Dict[str, float]:
        """Return a fresh copy of the provider-neutral compatibility defaults."""

        return dict(cls._GENERATION_DEFAULTS)

    @classmethod
    def _sampling_is_disabled(cls, runtime: LLMRuntimeConfig) -> bool:
        model = runtime.model.strip().lower()
        if cls._is_openai_reasoning_model(runtime):
            return True
        if runtime.provider in {"moonshot", "moonshot_global"} and model.startswith(("kimi-k2.5", "kimi-k2.6")):
            return True
        normalized_model = model.removeprefix("models/").removeprefix("google/")
        if runtime.provider in {"gemini", "vertex_ai"} and normalized_model.startswith("gemini-3"):
            return True
        if runtime.provider == "anthropic" and model.startswith("claude-opus-4-7"):
            return True
        if runtime.provider == "deepseek" and runtime.thinking_param and runtime.thinking_enabled:
            return True
        return False

    @classmethod
    def _generation_parameter_specs(cls, runtime: LLMRuntimeConfig) -> Dict[str, Dict[str, Any]]:
        """Describe sampling controls that are safe for this provider/model.

        Unknown custom endpoints intentionally get no managed controls. Their
        capabilities cannot be inferred safely, so sending a generic OpenAI
        payload could turn a valid endpoint into a failed connection test.
        """

        if cls._sampling_is_disabled(runtime):
            return {}

        common = {
            "temperature": {"min": 0.0, "max": 2.0, "step": 0.01},
            "top_p": {"min": 0.0, "max": 1.0, "step": 0.01},
            "frequency_penalty": {"min": -2.0, "max": 2.0, "step": 0.01},
            "presence_penalty": {"min": -2.0, "max": 2.0, "step": 0.01},
        }
        # Custom endpoints use the OpenAI-compatible request shape. Their
        # actual model limits are unknown, so expose broad common limits and
        # let the user choose whether to send any control at all.
        if runtime.provider == "custom":
            return common
        if runtime.protocol == PROTOCOL_ANTHROPIC:
            return {
                "temperature": {"min": 0.0, "max": 1.0, "step": 0.01},
                "top_p": {"min": 0.0, "max": 1.0, "step": 0.01},
            }
        if runtime.protocol in {PROTOCOL_GEMINI, PROTOCOL_VERTEX_AI}:
            return {
                "temperature": common["temperature"],
                "top_p": common["top_p"],
            }
        if runtime.provider in {"minimax", "minimax_global"}:
            return {
                "temperature": {"min": 0.000001, "max": 1.0, "step": 0.01},
                "top_p": common["top_p"],
            }
        if runtime.protocol == PROTOCOL_OPENAI_RESPONSES:
            # Responses models have a narrower stable surface than Chat
            # Completions. Do not advertise penalties they may reject.
            return {
                "temperature": common["temperature"],
                "top_p": common["top_p"],
            }
        if runtime.protocol in {
            PROTOCOL_OPENAI_CHAT,
            PROTOCOL_AZURE_OPENAI,
            PROTOCOL_BEDROCK,
            PROTOCOL_OLLAMA,
        }:
            return common
        return {}

    @classmethod
    def generation_params_meta(cls, runtime: LLMRuntimeConfig) -> List[Dict[str, Any]]:
        """Return browser-facing metadata for the current provider/model."""

        supported = cls._generation_parameter_specs(runtime)
        defaults = cls.generation_defaults(runtime)
        defaults_by_key = {
            "temperature": {"min": 0.0, "max": 2.0, "step": 0.01},
            "top_p": {"min": 0.0, "max": 1.0, "step": 0.01},
            "frequency_penalty": {"min": -2.0, "max": 2.0, "step": 0.01},
            "presence_penalty": {"min": -2.0, "max": 2.0, "step": 0.01},
        }
        return [
            {
                "key": cls._GENERATION_PUBLIC_KEYS[key],
                "label": cls._GENERATION_LABELS[key],
                "type": "number",
                "min": (spec or defaults_by_key[key])["min"],
                "max": (spec or defaults_by_key[key])["max"],
                "step": (spec or defaults_by_key[key])["step"],
                "defaultValue": defaults[key],
                "description": cls._GENERATION_DESCRIPTIONS[key],
                "supported": key in supported,
            }
            for key in cls._GENERATION_KEYS
            for spec in [supported.get(key)]
        ]

    @classmethod
    def generation_param_specs(cls, runtime: LLMRuntimeConfig) -> Dict[str, Dict[str, Any]]:
        """Expose internal numeric limits to the configuration service."""

        return cls._generation_parameter_specs(runtime)

    @classmethod
    def _managed_generation_params(
        cls, runtime: LLMRuntimeConfig, temperature: float
    ) -> Dict[str, float]:
        """Return the validated controls that may be sent for this request.

        A runtime without `generation_params` is a legacy/internal caller;
        retain its historical temperature-only behavior. Saved UI configs use
        a mapping (which may be empty) and are filtered strictly by provider
        metadata.
        """

        if runtime.generation_params is None:
            return {"temperature": float(temperature)} if cls._supports_temperature(runtime) else {}

        # Saved profiles are sparse.  Do not turn an omitted control into an
        # explicit wire field: an empty mapping intentionally uses provider
        # defaults, even when a legacy business call carries a temperature.
        # The latter still applies to callers that have no account runtime
        # mapping (the branch above).
        values: Dict[str, float] = {}
        defaults = cls.generation_defaults(runtime)
        for key, value in runtime.generation_params.items():
            if key in cls._GENERATION_DEFAULTS:
                values[key] = float(value)

        specs = cls._generation_parameter_specs(runtime)
        result = {key: values[key] for key in specs if key in values}
        if runtime.protocol == PROTOCOL_ANTHROPIC and "top_p" in result:
            # Anthropic accepts either sampling control. Its initial Top P is
            # provider-specific, so send it only after a deliberate adjustment.
            if result["top_p"] != defaults["top_p"]:
                result.pop("temperature", None)
            else:
                result.pop("top_p", None)
        return result

    @staticmethod
    def _is_openai_reasoning_model(runtime: LLMRuntimeConfig) -> bool:
        """Whether an official OpenAI model rejects Chat sampling controls."""

        if runtime.provider not in {"openai", "openai_responses"}:
            return False
        model = runtime.model.strip().lower()
        return model.startswith(("gpt-5", "o1", "o3", "o4"))

    @classmethod
    def _supports_temperature(cls, runtime: LLMRuntimeConfig) -> bool:
        """Avoid sending sampling controls to models that explicitly reject them."""

        return not cls._sampling_is_disabled(runtime)

    @classmethod
    def _temperature_for_provider(cls, runtime: LLMRuntimeConfig, temperature: float) -> float:
        """Return a sampling value accepted by the provider's native API."""

        value = float(temperature)
        if runtime.provider in {"minimax", "minimax_global"}:
            # MiniMax rejects zero and values above 1.0.
            return min(1.0, max(1e-6, value))
        if runtime.protocol == PROTOCOL_ANTHROPIC:
            return min(1.0, max(0.0, value))
        return value

    @classmethod
    def _uses_completion_token_limit(cls, runtime: LLMRuntimeConfig) -> bool:
        """Whether an OpenAI-compatible endpoint expects the new token field."""

        return cls._is_openai_reasoning_model(runtime) or runtime.provider in {
            "minimax",
            "minimax_global",
        }

    @staticmethod
    def _base_url(runtime: LLMRuntimeConfig) -> str:
        return (runtime.proxy_url or runtime.normalized_base_url).rstrip("/")

    @staticmethod
    def _headers(runtime: LLMRuntimeConfig) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        credential = runtime.credential
        if runtime.protocol == PROTOCOL_ANTHROPIC:
            if credential:
                headers["x-api-key"] = credential
            headers["anthropic-version"] = "2023-06-01"
        elif runtime.protocol == PROTOCOL_AZURE_OPENAI and credential:
            headers["api-key"] = credential
        elif runtime.protocol == PROTOCOL_GEMINI and credential:
            headers["x-goog-api-key"] = credential
        elif runtime.protocol == PROTOCOL_VERTEX_AI and credential:
            headers["Authorization"] = f"Bearer {AIProtocolClient._vertex_access_token(runtime)}"
        elif credential:
            headers["Authorization"] = f"Bearer {credential}"
        return headers

    @staticmethod
    def _vertex_access_token(runtime: LLMRuntimeConfig) -> str:
        """Exchange the encrypted service-account JSON for a short-lived token.

        Vertex's OpenAI-compatible endpoint only accepts Google Cloud
        authentication.  The service account is stored in the existing encrypted
        credential column; this method deliberately returns only its temporary
        access token and never logs either secret.
        """

        try:
            from google.auth.exceptions import GoogleAuthError, TransportError
            from google.auth.transport.requests import Request
            from google.oauth2.service_account import Credentials
        except ImportError as exc:
            raise RuntimeProtocolError("provider_error") from exc

        try:
            service_account = json.loads(runtime.api_key)
            if not isinstance(service_account, dict):
                raise ValueError("service account must be an object")
            if service_account.get("token_uri") != AIProtocolClient.VERTEX_TOKEN_URI:
                raise ValueError("unsupported token URI")
            credentials = Credentials.from_service_account_info(
                service_account,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
            credentials.refresh(Request())
            if not credentials.token:
                raise ValueError("missing access token")
            return credentials.token
        except TransportError as exc:
            raise RuntimeProtocolError("network_error") from exc
        except (GoogleAuthError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeProtocolError("invalid_credential") from exc

    @classmethod
    def complete(
        cls,
        runtime: LLMRuntimeConfig,
        messages: List[Dict[str, str]],
        *,
        temperature: float,
        max_tokens: int,
        timeout: float = 120.0,
    ) -> Tuple[str, Dict[str, int]]:
        if not runtime.normalized_base_url:
            raise RuntimeProtocolError("invalid_url")
        if runtime.requires_api_key and not runtime.credential:
            raise RuntimeProtocolError("unauthorized")
        if not is_protocol_implemented(runtime.protocol):
            raise RuntimeProtocolError("unsupported_protocol")

        base_url = cls._base_url(runtime)
        headers = cls._headers(runtime)
        try:
            with httpx.Client(
                timeout=timeout,
                headers=headers,
                trust_env=False,
                follow_redirects=False,
            ) as client:
                if runtime.protocol in {
                    PROTOCOL_OPENAI_CHAT,
                    PROTOCOL_AZURE_OPENAI,
                    PROTOCOL_VERTEX_AI,
                    PROTOCOL_BEDROCK,
                }:
                    return cls._openai_chat(client, base_url, runtime, messages, temperature, max_tokens)
                if runtime.protocol == PROTOCOL_OPENAI_RESPONSES:
                    return cls._openai_responses(client, base_url, runtime, messages, temperature, max_tokens)
                if runtime.protocol == PROTOCOL_ANTHROPIC:
                    return cls._anthropic(client, base_url, runtime, messages, temperature, max_tokens)
                if runtime.protocol == PROTOCOL_GEMINI:
                    return cls._gemini(client, base_url, runtime, messages, temperature, max_tokens)
                if runtime.protocol == PROTOCOL_OLLAMA:
                    return cls._ollama(client, base_url, runtime, messages, temperature, max_tokens)
        except httpx.TimeoutException as exc:
            raise RuntimeProtocolError("timeout") from exc
        except (httpx.ConnectError, httpx.NetworkError, OSError) as exc:
            raise RuntimeProtocolError("network_error") from exc
        except httpx.HTTPError as exc:
            raise RuntimeProtocolError("provider_error") from exc
        raise RuntimeProtocolError("unsupported_protocol")

    @classmethod
    def _openai_chat(
        cls, client: httpx.Client, base_url: str, runtime: LLMRuntimeConfig,
        messages: List[Dict[str, str]], temperature: float, max_tokens: int,
    ) -> Tuple[str, Dict[str, int]]:
        payload: Dict[str, Any] = {
            "model": runtime.model,
            "messages": messages,
        }
        generation_params = cls._managed_generation_params(runtime, temperature)
        if "temperature" in generation_params:
            payload["temperature"] = cls._temperature_for_provider(runtime, generation_params["temperature"])
        for key in ("top_p", "frequency_penalty", "presence_penalty"):
            if key in generation_params:
                payload[key] = generation_params[key]
        if cls._uses_completion_token_limit(runtime):
            # OpenAI reasoning families and MiniMax reject the legacy
            # ``max_tokens`` field in favor of this replacement.
            payload["max_completion_tokens"] = max_tokens
        else:
            payload["max_tokens"] = max_tokens
        # DeepSeek understands this extension; generic OpenAI-compatible
        # providers frequently reject it, so never send it universally.
        if runtime.provider == "deepseek" and runtime.thinking_param:
            payload["thinking"] = {"type": "enabled" if runtime.thinking_enabled else "disabled"}
        response = client.post(f"{base_url}/chat/completions", json=payload)
        cls._raise_for_status(response)
        data = cls._json(response)
        try:
            content = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeProtocolError("provider_error") from exc
        if not str(content).strip():
            raise RuntimeProtocolError("empty_response")
        return str(content), cls._openai_usage(data.get("usage"))

    @classmethod
    def _openai_responses(
        cls, client: httpx.Client, base_url: str, runtime: LLMRuntimeConfig,
        messages: List[Dict[str, str]], temperature: float, max_tokens: int,
    ) -> Tuple[str, Dict[str, int]]:
        payload = {
            "model": runtime.model,
            "input": messages,
            "max_output_tokens": max_tokens,
        }
        generation_params = cls._managed_generation_params(runtime, temperature)
        if "temperature" in generation_params:
            payload["temperature"] = cls._temperature_for_provider(runtime, generation_params["temperature"])
        if "top_p" in generation_params:
            payload["top_p"] = generation_params["top_p"]
        response = client.post(f"{base_url}/responses", json=payload)
        cls._raise_for_status(response)
        data = cls._json(response)
        content = str(data.get("output_text") or "")
        if not content:
            chunks: List[str] = []
            for output in data.get("output", []) or []:
                for item in output.get("content", []) or []:
                    if item.get("type") in {"output_text", "text"}:
                        chunks.append(str(item.get("text") or ""))
            content = "".join(chunks)
        if not content.strip():
            raise RuntimeProtocolError("empty_response")
        return content, cls._openai_usage(data.get("usage"))

    @classmethod
    def _anthropic(
        cls, client: httpx.Client, base_url: str, runtime: LLMRuntimeConfig,
        messages: List[Dict[str, str]], temperature: float, max_tokens: int,
    ) -> Tuple[str, Dict[str, int]]:
        system = "\n\n".join(str(item.get("content") or "") for item in messages if item.get("role") == "system")
        chat_messages = [
            {"role": item.get("role"), "content": item.get("content")}
            for item in messages if item.get("role") in {"user", "assistant"}
        ]
        payload: Dict[str, Any] = {
            "model": runtime.model,
            "max_tokens": max_tokens,
            "messages": chat_messages,
        }
        generation_params = cls._managed_generation_params(runtime, temperature)
        if "temperature" in generation_params:
            payload["temperature"] = cls._temperature_for_provider(runtime, generation_params["temperature"])
        if "top_p" in generation_params:
            payload["top_p"] = generation_params["top_p"]
        if system:
            payload["system"] = system
        response = client.post(f"{base_url}/messages", json=payload)
        cls._raise_for_status(response)
        data = cls._json(response)
        content = "".join(
            str(item.get("text") or "")
            for item in data.get("content", []) or []
            if isinstance(item, dict) and item.get("type") == "text"
        )
        if not content.strip():
            raise RuntimeProtocolError("empty_response")
        usage = data.get("usage") or {}
        return content, {
            "prompt_tokens": int(usage.get("input_tokens") or 0),
            "completion_tokens": int(usage.get("output_tokens") or 0),
            "total_tokens": int(usage.get("input_tokens") or 0) + int(usage.get("output_tokens") or 0),
        }

    @classmethod
    def _gemini(
        cls, client: httpx.Client, base_url: str, runtime: LLMRuntimeConfig,
        messages: List[Dict[str, str]], temperature: float, max_tokens: int,
    ) -> Tuple[str, Dict[str, int]]:
        system_parts = [str(item.get("content") or "") for item in messages if item.get("role") == "system"]
        contents = []
        for item in messages:
            role = item.get("role")
            if role not in {"user", "assistant"}:
                continue
            contents.append({
                "role": "model" if role == "assistant" else "user",
                "parts": [{"text": str(item.get("content") or "")}],
            })
        generation_config: Dict[str, Any] = {"maxOutputTokens": max_tokens}
        generation_params = cls._managed_generation_params(runtime, temperature)
        if "temperature" in generation_params:
            generation_config["temperature"] = generation_params["temperature"]
        if "top_p" in generation_params:
            generation_config["topP"] = generation_params["top_p"]
        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": generation_config,
        }
        if system_parts:
            payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}
        model = runtime.model.removeprefix("models/")
        response = client.post(
            f"{base_url}/models/{model}:generateContent",
            json=payload,
        )
        cls._raise_for_status(response)
        data = cls._json(response)
        parts = ((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
        content = "".join(str(item.get("text") or "") for item in parts if isinstance(item, dict))
        if not content.strip():
            raise RuntimeProtocolError("empty_response")
        usage = data.get("usageMetadata") or {}
        prompt_tokens = int(usage.get("promptTokenCount") or 0)
        completion_tokens = int(usage.get("candidatesTokenCount") or 0)
        return content, {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": int(usage.get("totalTokenCount") or prompt_tokens + completion_tokens),
        }

    @classmethod
    def _ollama(
        cls, client: httpx.Client, base_url: str, runtime: LLMRuntimeConfig,
        messages: List[Dict[str, str]], temperature: float, max_tokens: int,
    ) -> Tuple[str, Dict[str, int]]:
        generation_params = cls._managed_generation_params(runtime, temperature)
        options: Dict[str, Any] = {"num_predict": max_tokens}
        if "temperature" in generation_params:
            options["temperature"] = generation_params["temperature"]
        for key in ("top_p", "frequency_penalty", "presence_penalty"):
            if key in generation_params:
                options[key] = generation_params[key]
        payload = {
            "model": runtime.model,
            "messages": messages,
            "stream": False,
            "options": options,
        }
        response = client.post(f"{base_url}/api/chat", json=payload)
        cls._raise_for_status(response)
        data = cls._json(response)
        content = str((data.get("message") or {}).get("content") or "")
        if not content.strip():
            raise RuntimeProtocolError("empty_response")
        prompt_tokens = int(data.get("prompt_eval_count") or 0)
        completion_tokens = int(data.get("eval_count") or 0)
        return content, {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }

    @staticmethod
    def _json(response: httpx.Response) -> Dict[str, Any]:
        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeProtocolError("provider_error") from exc
        if not isinstance(data, dict):
            raise RuntimeProtocolError("provider_error")
        return data

    @staticmethod
    def _openai_usage(usage: Any) -> Dict[str, int]:
        usage = usage or {}
        prompt_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": int(usage.get("total_tokens") or prompt_tokens + completion_tokens),
        }

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        if response.status_code in (401, 403):
            reason = "unauthorized"
        elif response.status_code == 404:
            reason = "invalid_model"
        elif response.status_code == 429:
            reason = "rate_limited"
        else:
            reason = "provider_error"
        public_message = AIProtocolClient._provider_error_message(response)
        if (
            public_message
            and response.status_code in {400, 422}
            and re.search(
                r"(?i)\b(temperature|top[_ ]?p|frequency[_ ]?penalty|presence[_ ]?penalty)\b",
                public_message,
            )
        ):
            reason = "invalid_parameter"
        raise RuntimeProtocolError(reason, response.status_code, public_message)

    @staticmethod
    def _provider_error_message(response: httpx.Response) -> str | None:
        """Extract a bounded, credential-safe provider validation message."""

        try:
            payload = response.json()
        except ValueError:
            return None
        message: Any = None
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                message = error.get("message") or error.get("detail")
            elif isinstance(error, str):
                message = error
            message = message or payload.get("message") or payload.get("detail")
        if isinstance(message, list):
            message = "; ".join(str(item) for item in message)
        if not isinstance(message, str):
            return None
        # Provider diagnostics occasionally echo credentials. Redact both
        # ``Authorization: Bearer <token>`` and ``api_key=<token>`` forms
        # before returning the bounded message to the browser.
        message = re.sub(
            r"(?i)\b(api[_ -]?key|authorization|bearer)\b"
            r"(?:\s*[:=]\s*|\s+)(?:bearer\s+)?[^\s,;\"'}]+",
            r"\1=***",
            message,
        )
        message = " ".join(message.split())[:240]
        return message or None
