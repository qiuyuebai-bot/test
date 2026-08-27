"""Regression coverage for real generation after an account saves AI settings."""

import pytest

from app.agents.generation_agent import GenerationAgent
from app.agents.llm_generator import LLMGenerator
from app.services.ai_protocol_client import AIProtocolClient, RuntimeProtocolError
from app.utils.llm import LLMUnavailableError, LLMUtil
from app.utils.llm_response import LLMResponseError
from app.utils.llm_runtime import LLMRuntimeConfig, use_runtime_config


def _runtime(*, owner_user_id=None):
    return LLMRuntimeConfig(
        provider="custom",
        protocol="openai_chat",
        owner_user_id=owner_user_id,
        base_url="https://example.com/v1",
        api_key="test-key",
        model="test-model",
    )


def test_saved_account_runtime_never_returns_mock_when_provider_fails(monkeypatch):
    """Configured users must see a real failure instead of fabricated content."""

    monkeypatch.setattr(
        "app.services.ai_config_service.AIConfigService._is_permitted_endpoint",
        classmethod(lambda _cls, _runtime: True),
    )
    monkeypatch.setattr(
        AIProtocolClient,
        "complete",
        staticmethod(lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeProtocolError("network_error"))),
    )

    with pytest.raises(LLMUnavailableError, match="network_error"):
        LLMUtil.sync_call(
            "请生成内容",
            allow_mock=True,
            runtime_config=_runtime(owner_user_id=101),
        )


def test_demo_runtime_keeps_mock_fallback_when_no_account_config_exists(monkeypatch):
    """Offline demo mode remains available for users who did not configure AI."""

    monkeypatch.setattr(
        "app.services.ai_config_service.AIConfigService._is_permitted_endpoint",
        classmethod(lambda _cls, _runtime: True),
    )
    monkeypatch.setattr(
        AIProtocolClient,
        "complete",
        staticmethod(lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeProtocolError("network_error"))),
    )

    content, usage = LLMUtil.sync_call(
        "请生成内容",
        allow_mock=True,
        runtime_config=_runtime(),
    )

    assert content
    assert usage["total_tokens"] == 0


def test_resource_generation_does_not_silently_downgrade_a_configured_account(monkeypatch):
    """A bad provider response must fail the task so the UI can show the cause."""

    monkeypatch.setattr(LLMUtil, "is_available", classmethod(lambda _cls: True))
    monkeypatch.setattr(
        LLMGenerator,
        "generate_guide",
        classmethod(lambda _cls, *_args, **_kwargs: (_ for _ in ()).throw(LLMResponseError("bad JSON"))),
    )

    with use_runtime_config(_runtime(owner_user_id=101)):
        with pytest.raises(LLMUnavailableError, match="invalid_generation_response"):
            GenerationAgent()._generate_guide({}, [], {}, "测试主题")


def test_resource_generation_keeps_rule_fallback_without_account_config(monkeypatch):
    """The original no-key demo path is intentionally unchanged."""

    monkeypatch.setattr(LLMUtil, "is_available", classmethod(lambda _cls: True))
    monkeypatch.setattr(
        LLMGenerator,
        "generate_guide",
        classmethod(lambda _cls, *_args, **_kwargs: (_ for _ in ()).throw(LLMResponseError("bad JSON"))),
    )

    with use_runtime_config(_runtime()):
        result = GenerationAgent()._generate_guide({}, [], {}, "测试主题")

    assert result["content"]
    assert result.get("generation_method") is None
