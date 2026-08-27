"""Runtime configuration passed to a single LLM request.

The existing application keeps a process-level ``.env`` configuration.  This
module adds an immutable request-level value without changing that fallback.
It deliberately contains no database imports, so it can be used by workers and
tests without introducing persistence cycles.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, Mapping, Optional

from app.config import settings


@dataclass(frozen=True)
class LLMRuntimeConfig:
    """All values needed to make one model request.

    ``requires_api_key`` is provider metadata rather than a validation result;
    local providers such as Ollama can therefore be used with an empty key.
    """

    provider: str = "custom"
    protocol: str = "openai_chat"
    # The account ID is an in-process cache partition only.  It is never sent
    # to a provider, stored in a task payload, or returned by the API.
    owner_user_id: Optional[int] = None
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    proxy_url: str = ""
    proxy_password: str = ""
    requires_api_key: bool = True
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    thinking_enabled: Optional[bool] = None
    thinking_param: Optional[bool] = None
    extra_config: Mapping[str, Any] = field(default_factory=dict)
    # Provider-specific sampling controls selected in the AI configuration
    # page. Values are validated before a runtime is built and are never
    # secrets.
    # ``None`` is reserved for legacy environment callers.  A saved account
    # always carries a mapping (possibly empty), where only explicitly enabled
    # sampling overrides are present.
    generation_params: Optional[Mapping[str, float]] = None

    @classmethod
    def from_settings(cls) -> "LLMRuntimeConfig":
        """Build the backwards-compatible process-level configuration."""

        # The provider registry is imported lazily to keep this lightweight
        # value object free of module-import cycles during application startup.
        from app.services.ai_providers import infer_provider_from_base_url

        provider = infer_provider_from_base_url(settings.OPENAI_API_BASE)

        return cls(
            provider=provider.id,
            protocol=provider.protocol,
            base_url=settings.OPENAI_API_BASE,
            api_key=settings.OPENAI_API_KEY,
            model=settings.OPENAI_MODEL_NAME,
            requires_api_key=provider.requires_api_key,
            temperature=settings.OPENAI_TEMPERATURE,
            max_tokens=settings.OPENAI_MAX_TOKENS,
            thinking_enabled=settings.OPENAI_THINKING_ENABLED,
            thinking_param=settings.OPENAI_THINKING_PARAM,
        )

    @property
    def credential(self) -> str:
        """Return the credential used by the effective upstream endpoint.

        A configured reverse proxy is the request destination, so its password
        takes precedence over a vendor key. This matches the common
        OpenAI-compatible reverse-proxy convention while retaining API-key
        fallback when a proxy does not require a separate password.
        """

        if self.proxy_url.strip() and self.proxy_password.strip():
            return self.proxy_password.strip()
        return self.api_key.strip()

    @property
    def is_configured(self) -> bool:
        """Whether this provider has enough credentials for a request."""

        return bool(self.credential) or not self.requires_api_key

    @property
    def normalized_base_url(self) -> str:
        return (self.base_url or "").strip().rstrip("/")

    def redacted(self) -> Dict[str, Any]:
        """Return a safe diagnostic representation with no secret values."""

        return {
            "provider": self.provider,
            "protocol": self.protocol,
            "base_url": self.normalized_base_url,
            "model": self.model,
            "api_key_configured": bool(self.api_key.strip()),
            "proxy_url": self.proxy_url,
            "proxy_password_configured": bool(self.proxy_password.strip()),
        }


_runtime_config: ContextVar[Optional[LLMRuntimeConfig]] = ContextVar(
    "llm_runtime_config", default=None
)
_runtime_user_id: ContextVar[Optional[int]] = ContextVar("llm_runtime_user_id", default=None)


def get_runtime_config() -> Optional[LLMRuntimeConfig]:
    """Return the config bound to the current request/task, if any."""

    return _runtime_config.get()


def get_runtime_user_id() -> Optional[int]:
    """Return the authenticated owner whose config may be loaded lazily."""

    return _runtime_user_id.get()


def set_runtime_user_id(user_id: Optional[int]) -> Token[Optional[int]]:
    """Bind an owner to this request/task context without storing secrets."""

    return _runtime_user_id.set(user_id)


@contextmanager
def use_runtime_user_id(user_id: int) -> Iterator[int]:
    """Bind a user ID around worker code; configuration is loaded on demand."""

    token = _runtime_user_id.set(user_id)
    try:
        yield user_id
    finally:
        _runtime_user_id.reset(token)


@contextmanager
def use_runtime_config(config: LLMRuntimeConfig) -> Iterator[LLMRuntimeConfig]:
    """Temporarily bind a runtime config to the current execution context."""

    token: Token[Optional[LLMRuntimeConfig]] = _runtime_config.set(config)
    try:
        yield config
    finally:
        _runtime_config.reset(token)
