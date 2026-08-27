"""Regression tests for isolated AI configuration storage and protocol metadata."""

import json
import socket

import httpx
import pytest

from app.config import settings
from app.models import User, UserAIConfig, UserRoleEnum
from app.services.ai_protocol_client import AIProtocolClient
from app.services.ai_providers import (
    PROTOCOL_ANTHROPIC,
    PROTOCOL_AZURE_OPENAI,
    PROTOCOL_BEDROCK,
    PROTOCOL_GEMINI,
    PROTOCOL_OLLAMA,
    PROTOCOL_OPENAI_RESPONSES,
    PROTOCOL_VERTEX_AI,
    get_provider,
)
from app.schemas.ai_config import AIConfigUpdate
from app.utils.auth import create_access_token, hash_password
from app.utils.logger import _sanitize_dict
from app.utils.llm_runtime import (
    LLMRuntimeConfig,
    get_runtime_config,
    get_runtime_user_id,
    use_runtime_user_id,
)
from app.utils.llm import LLMUnavailableError, LLMUtil
from app.services.ai_config_service import AIConfigService, ConnectionTestResult


def test_ai_config_is_encrypted_and_isolated_per_account(client, db_session, sample_user, auth_headers):
    response = client.put(
        "/api/v1/ai-config",
        headers=auth_headers,
        json={
            "provider": "custom",
            "baseUrl": "https://example.com/v1",
            "apiKey": "secret-key-for-user-a",
            "selectedModel": "model-a",
            "availableModels": ["model-a", "model-b"],
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["selectedModel"] == "model-a"
    assert data["availableModels"] == ["model-a", "model-b"]
    assert data["apiKeyConfigured"] is True
    assert "secret-key-for-user-a" not in response.text

    stored = db_session.query(UserAIConfig).filter(UserAIConfig.user_id == sample_user.id).one()
    assert stored.api_key_encrypted
    assert stored.api_key_encrypted != "secret-key-for-user-a"
    assert AIConfigService.decrypt_secret(stored.api_key_encrypted) == "secret-key-for-user-a"

    other_user = User(
        username="ai_config_other_user",
        password_hash=hash_password("test_password"),
        email="ai_config_other@example.com",
        role=UserRoleEnum.LEARNER,
        is_active=True,
        is_verified=True,
    )
    db_session.add(other_user)
    db_session.commit()
    other_token = create_access_token({
        "user_id": other_user.id,
        "username": other_user.username,
        "role": other_user.role.value,
    })
    other_response = client.get(
        "/api/v1/ai-config",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert other_response.status_code == 200
    other_data = other_response.json()["data"]
    assert other_data["configured"] is False
    assert other_data["source"] == "environment"
    assert "secret-key-for-user-a" not in other_response.text


def test_ai_config_requires_key_for_cloud_provider(client, auth_headers):
    response = client.put(
        "/api/v1/ai-config",
        headers=auth_headers,
        json={
            "provider": "custom",
            "baseUrl": "https://example.com/v1",
            "selectedModel": "model-a",
        },
    )

    assert response.status_code == 400
    assert "API Key" in response.json()["message"]


def test_generation_params_endpoint_returns_defaults_without_contacting_upstream(
    client, auth_headers, monkeypatch
):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("generation metadata endpoint must not contact an upstream")

    monkeypatch.setattr(AIProtocolClient, "complete", fail_if_called)
    response = client.get(
        "/api/v1/ai-config/generation-params",
        headers=auth_headers,
        params={"provider": "anthropic", "model": "claude-sonnet-4-5"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["provider"] == "anthropic"
    assert data["model"] == "claude-sonnet-4-5"
    assert data["generationParamsConfigured"] is False
    assert data["generationParams"] == {"temperature": 1.0, "top_p": 0.999}
    assert {item["key"] for item in data["generationParamsMeta"]} == {
        "temperature",
        "top_p",
        "frequency_penalty",
        "presence_penalty",
    }
    assert all(item["supported"] is False for item in data["generationParamsMeta"] if item["key"] in {"frequency_penalty", "presence_penalty"})
    assert "apiKey" not in response.text


@pytest.mark.parametrize(
    ("provider", "protocol", "model", "expected"),
    [
        (
            "gemini",
            PROTOCOL_GEMINI,
            "gemini-2.0-flash",
            {"temperature": 1.0, "top_p": 0.95},
        ),
        (
            "qwen",
            "openai_chat",
            "qwen-plus",
            {"temperature": 0.7, "top_p": 0.8},
        ),
        (
            "qwen",
            "openai_chat",
            "qwen3-max-thinking",
            {"temperature": 0.6, "top_p": 0.95},
        ),
        (
            "moonshot",
            "openai_chat",
            "kimi-k3",
            {"temperature": 1.0, "top_p": 0.95},
        ),
        (
            "minimax",
            "openai_chat",
            "MiniMax-M2.7",
            {"temperature": 1.0, "top_p": 0.95},
        ),
    ],
)
def test_generation_metadata_uses_provider_model_initial_defaults(
    provider, protocol, model, expected
):
    runtime = LLMRuntimeConfig(provider=provider, protocol=protocol, model=model)
    meta = {item["key"]: item for item in AIProtocolClient.generation_params_meta(runtime)}
    assert {key: meta[key]["defaultValue"] for key in expected} == expected


def test_generation_params_endpoint_reads_only_the_requested_model_profile(
    client, db_session, sample_user, auth_headers
):
    profile_key = AIConfigService._profile_key("openai", "gpt-4o")
    record = UserAIConfig(
        user_id=sample_user.id,
        provider="openai",
        protocol="openai_chat",
        base_url="https://api.openai.com/v1",
        api_key_encrypted=AIConfigService.encrypt_secret("profile-secret"),
        selected_model="gpt-4o",
        extra_config={
            "_generationParamsProfiles": {
                profile_key: {"temperature": 0.35, "top_p": 0.8},
            }
        },
    )
    db_session.add(record)
    db_session.commit()

    current = client.get(
        "/api/v1/ai-config/generation-params",
        headers=auth_headers,
        params={"provider": "openai", "model": "gpt-4o"},
    )
    unseen = client.get(
        "/api/v1/ai-config/generation-params",
        headers=auth_headers,
        params={"provider": "openai", "model": "gpt-4.1"},
    )

    assert current.status_code == 200
    current_data = current.json()["data"]
    assert current_data["generationParamsConfigured"] is True
    assert current_data["generationParams"] == {"temperature": 0.35, "top_p": 0.8}
    assert "profile-secret" not in current.text

    assert unseen.status_code == 200
    unseen_data = unseen.json()["data"]
    assert unseen_data["generationParamsConfigured"] is False
    assert unseen_data["generationParams"] == {
        "temperature": 1.0,
        "top_p": 1.0,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0,
    }


def test_generation_params_endpoint_rejects_unknown_provider(client, auth_headers):
    response = client.get(
        "/api/v1/ai-config/generation-params",
        headers=auth_headers,
        params={"provider": "not-a-real-provider", "model": "model"},
    )

    assert response.status_code == 400
    assert response.json()["code"] == 400
    assert "unsupported_provider" in response.json()["message"]


def test_successful_connection_persists_key_and_default_model(
    client, db_session, sample_user, auth_headers, monkeypatch
):
    monkeypatch.setattr(
        AIConfigService,
        "test_connection",
        lambda runtime: ConnectionTestResult(
            True,
            ["deepseek-chat", "deepseek-reasoner"],
            12,
            "连接成功，发现 2 个可用模型",
        ),
    )

    response = client.post(
        "/api/v1/ai-config/test",
        headers=auth_headers,
        json={
            "provider": "deepseek",
            "apiKey": "verified-deepseek-key",
            "selectedModel": None,
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["selectedModel"] == "deepseek-chat"
    stored = db_session.query(UserAIConfig).filter(UserAIConfig.user_id == sample_user.id).one()
    assert stored.provider == "deepseek"
    assert stored.selected_model == "deepseek-chat"
    assert stored.available_models == ["deepseek-chat", "deepseek-reasoner"]
    assert stored.last_test_status == "success"
    assert AIConfigService.decrypt_secret(stored.api_key_encrypted) == "verified-deepseek-key"
    runtime = AIConfigService.effective_runtime_config(db_session, sample_user.id)
    assert runtime.provider == "deepseek"
    assert runtime.model == "deepseek-chat"
    assert runtime.api_key == "verified-deepseek-key"

    reloaded = client.get("/api/v1/ai-config", headers=auth_headers).json()["data"]
    assert reloaded["provider"] == "deepseek"
    assert reloaded["selectedModel"] == "deepseek-chat"
    assert reloaded["apiKeyConfigured"] is True
    assert "verified-deepseek-key" not in str(reloaded)


def test_failed_connection_does_not_replace_saved_configuration(
    client, db_session, sample_user, auth_headers, monkeypatch
):
    existing = UserAIConfig(
        user_id=sample_user.id,
        provider="deepseek",
        protocol="openai_chat",
        base_url="https://api.deepseek.com",
        api_key_encrypted=AIConfigService.encrypt_secret("working-key"),
        selected_model="deepseek-chat",
        available_models=["deepseek-chat"],
        is_active=True,
    )
    db_session.add(existing)
    db_session.commit()
    monkeypatch.setattr(
        AIConfigService,
        "test_connection",
        lambda runtime: ConnectionTestResult(False, [], 10, "API Key 无效", "unauthorized"),
    )

    response = client.post(
        "/api/v1/ai-config/test",
        headers=auth_headers,
        json={
            "provider": "openai",
            "apiKey": "invalid-replacement-key",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["success"] is False
    db_session.refresh(existing)
    assert existing.provider == "deepseek"
    assert existing.selected_model == "deepseek-chat"
    assert AIConfigService.decrypt_secret(existing.api_key_encrypted) == "working-key"


def test_reconnecting_does_not_replace_the_explicitly_selected_model(
    client, db_session, sample_user, auth_headers, monkeypatch
):
    existing = UserAIConfig(
        user_id=sample_user.id,
        provider="custom",
        protocol="openai_chat",
        base_url="https://example.com/v1",
        api_key_encrypted=AIConfigService.encrypt_secret("placeholder-key"),
        selected_model="model-kept-by-user",
        available_models=["model-kept-by-user", "model-a"],
        is_active=True,
    )
    db_session.add(existing)
    db_session.commit()
    monkeypatch.setattr(
        AIConfigService,
        "test_connection",
        lambda runtime: ConnectionTestResult(
            True,
            ["model-a", "model-b"],
            10,
            "连接成功",
        ),
    )

    response = client.post(
        "/api/v1/ai-config/test",
        headers=auth_headers,
        json={
            "provider": "custom",
            "baseUrl": "https://example.com/v1",
            "selectedModel": "model-kept-by-user",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["selectedModel"] == "model-kept-by-user"
    db_session.refresh(existing)
    assert existing.selected_model == "model-kept-by-user"


def test_reverse_proxy_password_can_be_saved_without_vendor_key(
    client, db_session, sample_user, auth_headers
):
    response = client.put(
        "/api/v1/ai-config",
        headers=auth_headers,
        json={
            "provider": "openai",
            "selectedModel": "gpt-4o",
            "proxyUrl": "https://example.com/v1",
            "proxyPassword": "proxy-secret",
        },
    )

    assert response.status_code == 200
    stored = db_session.query(UserAIConfig).filter(UserAIConfig.user_id == sample_user.id).one()
    assert stored.api_key_encrypted is None
    assert AIConfigService.decrypt_secret(stored.proxy_password_encrypted) == "proxy-secret"


def test_provider_change_does_not_reuse_old_credentials():
    existing = UserAIConfig(
        user_id=1,
        provider="deepseek",
        protocol="openai_chat",
        base_url="https://api.deepseek.com",
        api_key_encrypted=AIConfigService.encrypt_secret("deepseek-secret"),
        proxy_url="https://example.com/v1",
        proxy_password_encrypted=AIConfigService.encrypt_secret("old-proxy-secret"),
        selected_model="deepseek-chat",
    )

    _, runtime, _ = AIConfigService.prepare_runtime_config(
        AIConfigUpdate(provider="anthropic", selectedModel="claude-3-5-sonnet-latest"),
        existing,
    )

    assert runtime.api_key == ""
    assert runtime.proxy_password == ""
    assert runtime.proxy_url == ""


def test_official_provider_uses_registered_base_url(client, auth_headers):
    response = client.put(
        "/api/v1/ai-config",
        headers=auth_headers,
        json={
            "provider": "openai",
            "baseUrl": "https://untrusted.example/v1",
            "apiKey": "key-for-openai",
            "selectedModel": "gpt-4o",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["baseUrl"] == "https://api.openai.com/v1"


def test_user_runtime_context_never_selects_another_account(db_session, sample_user, monkeypatch):
    import app.database as database_module

    monkeypatch.setattr(database_module, "SessionLocal", lambda: db_session)
    config = UserAIConfig(
        user_id=sample_user.id,
        provider="custom",
        protocol="openai_chat",
        base_url="https://example.com/v1",
        api_key_encrypted=AIConfigService.encrypt_secret("key-for-a"),
        selected_model="model-a",
        available_models=["model-a"],
    )
    db_session.add(config)
    db_session.commit()

    with use_runtime_user_id(sample_user.id):
        runtime = AIConfigService.get_active_runtime_config()
        assert runtime is not None
        assert runtime.model == "model-a"
        assert runtime.api_key == "key-for-a"

    with use_runtime_user_id(sample_user.id + 10000):
        assert AIConfigService.get_active_runtime_config() is None


def test_gemini_key_is_sent_only_in_header():
    runtime = LLMRuntimeConfig(
        provider="gemini",
        protocol=PROTOCOL_GEMINI,
        base_url="https://generativelanguage.googleapis.com/v1beta",
        api_key="gemini-secret",
        model="gemini-2.0-flash",
    )
    headers = AIProtocolClient._headers(runtime)
    assert headers["x-goog-api-key"] == "gemini-secret"
    assert "Authorization" not in headers


def test_special_provider_config_is_derived_and_safe_to_return(client, db_session, sample_user, auth_headers):
    service_account_json = json.dumps(
        {
            "type": "service_account",
            "client_email": "vertex-test@example.iam.gserviceaccount.com",
            "private_key": "-----BEGIN PRIVATE KEY-----\\nplaceholder\\n-----END PRIVATE KEY-----\\n",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    )

    response = client.put(
        "/api/v1/ai-config",
        headers=auth_headers,
        json={
            "provider": "vertex_ai",
            "apiKey": service_account_json,
            "selectedModel": "google/gemini-2.5-flash",
            "extraConfig": {"projectId": "vertex-demo-project", "location": "global"},
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["baseUrl"] == (
        "https://aiplatform.googleapis.com/v1/projects/vertex-demo-project/locations/global/endpoints/openapi"
    )
    assert data["extraConfig"] == {"projectId": "vertex-demo-project", "location": "global"}
    assert data["apiKeyConfigured"] is True
    assert data["apiKeyHint"] is None
    assert service_account_json not in response.text

    stored = db_session.query(UserAIConfig).filter(UserAIConfig.user_id == sample_user.id).one()
    assert stored.base_url == data["baseUrl"]
    assert stored.extra_config == data["extraConfig"]
    assert service_account_json not in (stored.extra_config or {}).values()


def test_special_provider_url_validation_and_metadata():
    azure = AIConfigService.prepare_runtime_config(
        AIConfigUpdate(
            provider="azure_openai",
            baseUrl="https://example-resource.openai.azure.com",
            apiKey="azure-placeholder-key",
            selectedModel="learning-deployment",
        ),
        None,
    )[1]
    bedrock = AIConfigService.prepare_runtime_config(
        AIConfigUpdate(
            provider="bedrock",
            apiKey="bedrock-placeholder-key",
            selectedModel="openai.gpt-oss-120b",
            extraConfig={"region": "us-east-1"},
        ),
        None,
    )[1]

    assert azure.base_url == "https://example-resource.openai.azure.com/openai/v1"
    assert bedrock.base_url == "https://bedrock-mantle.us-east-1.api.aws/v1"
    assert get_provider("azure_openai").implemented is True
    assert get_provider("azure_openai").supports_models_endpoint is False
    assert get_provider("vertex_ai").implemented is True
    assert get_provider("vertex_ai").supports_models_endpoint is False
    assert get_provider("bedrock").implemented is True
    assert get_provider("bedrock").supports_models_endpoint is True

    with pytest.raises(ValueError, match="Azure OpenAI"):
        AIConfigService.prepare_runtime_config(
            AIConfigUpdate(
                provider="azure_openai",
                baseUrl="https://untrusted.example/v1",
                apiKey="azure-placeholder-key",
                selectedModel="learning-deployment",
            ),
            None,
        )


def test_vertex_service_account_rejects_untrusted_token_uri():
    credential = json.dumps(
        {
            "type": "service_account",
            "client_email": "vertex-test@example.iam.gserviceaccount.com",
            "private_key": "-----BEGIN PRIVATE KEY-----\\nplaceholder\\n-----END PRIVATE KEY-----\\n",
            "token_uri": "http://127.0.0.1/token",
        }
    )

    with pytest.raises(ValueError, match="token_uri"):
        AIConfigService.prepare_runtime_config(
            AIConfigUpdate(
                provider="vertex_ai",
                apiKey=credential,
                selectedModel="google/gemini-2.5-flash",
                extraConfig={"projectId": "vertex-demo-project", "location": "global"},
            ),
            None,
        )


def test_azure_openai_uses_its_v1_header_and_deployment_name(monkeypatch):
    original_client = httpx.Client
    captured = {}

    def handle_request(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        captured["path"] = request.url.path
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original_client(transport=httpx.MockTransport(handle_request), **kwargs),
    )
    runtime = LLMRuntimeConfig(
        provider="azure_openai",
        protocol=PROTOCOL_AZURE_OPENAI,
        base_url="https://example-resource.openai.azure.com/openai/v1",
        api_key="azure-placeholder-key",
        model="learning-deployment",
    )

    content, _ = AIProtocolClient.complete(
        runtime,
        [{"role": "user", "content": "reply OK"}],
        temperature=0.2,
        max_tokens=64,
    )

    assert content == "OK"
    assert captured["path"] == "/openai/v1/chat/completions"
    assert captured["headers"]["api-key"] == "azure-placeholder-key"
    assert "authorization" not in captured["headers"]
    assert captured["payload"]["model"] == "learning-deployment"


def test_vertex_uses_service_account_token_and_openai_compatible_endpoint(monkeypatch):
    original_client = httpx.Client
    captured = {}

    def handle_request(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        captured["path"] = request.url.path
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})

    monkeypatch.setattr(
        AIProtocolClient,
        "_vertex_access_token",
        staticmethod(lambda runtime: "short-lived-google-token"),
    )
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original_client(transport=httpx.MockTransport(handle_request), **kwargs),
    )
    runtime = LLMRuntimeConfig(
        provider="vertex_ai",
        protocol=PROTOCOL_VERTEX_AI,
        base_url="https://aiplatform.googleapis.com/v1/projects/vertex-demo-project/locations/global/endpoints/openapi",
        api_key="encrypted-service-account-json-at-runtime",
        model="google/gemini-3-flash-preview",
        extra_config={"projectId": "vertex-demo-project", "location": "global"},
    )

    content, _ = AIProtocolClient.complete(
        runtime,
        [{"role": "user", "content": "reply OK"}],
        temperature=0.2,
        max_tokens=64,
    )

    assert content == "OK"
    assert captured["path"] == "/v1/projects/vertex-demo-project/locations/global/endpoints/openapi/chat/completions"
    assert captured["headers"]["authorization"] == "Bearer short-lived-google-token"
    assert "temperature" not in captured["payload"]
    assert captured["payload"]["model"] == "google/gemini-3-flash-preview"


def test_bedrock_discovers_models_then_calls_openai_compatible_endpoint(monkeypatch):
    original_client = httpx.Client
    requests = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["authorization"] == "Bearer bedrock-placeholder-key"
        if request.method == "GET":
            assert request.url.path == "/v1/models"
            return httpx.Response(200, json={"data": [{"id": "openai.gpt-oss-120b"}]})
        assert request.url.path == "/v1/chat/completions"
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original_client(transport=httpx.MockTransport(handle_request), **kwargs),
    )
    runtime = LLMRuntimeConfig(
        provider="bedrock",
        protocol=PROTOCOL_BEDROCK,
        base_url="https://bedrock-mantle.us-east-1.api.aws/v1",
        api_key="bedrock-placeholder-key",
        model="",
        extra_config={"region": "us-east-1"},
    )

    result = AIConfigService.test_connection(runtime)

    assert result.success is True
    assert result.models == ["openai.gpt-oss-120b"]
    assert [request.method for request in requests] == ["GET", "POST"]


def test_reverse_proxy_password_is_the_effective_upstream_credential():
    runtime = LLMRuntimeConfig(
        provider="openai",
        protocol="openai_chat",
        base_url="https://api.openai.com/v1",
        api_key="vendor-secret",
        proxy_url="https://example.com/v1",
        proxy_password="proxy-secret",
        model="gpt-4o",
    )

    headers = AIProtocolClient._headers(runtime)
    assert runtime.credential == "proxy-secret"
    assert headers["Authorization"] == "Bearer proxy-secret"
    assert "vendor-secret" not in str(headers)


def test_reverse_proxy_handles_model_discovery_and_text_generation(monkeypatch):
    requests = []
    original_client = httpx.Client

    def handle_request(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["Authorization"] == "Bearer placeholder-proxy-password"
        if request.method == "GET" and request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "proxy-model"}]})
        if request.method == "POST" and request.url.path == "/v1/chat/completions":
            payload = json.loads(request.content)
            assert payload["model"] == "proxy-model"
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "proxy-generated-content"}}],
                    "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handle_request)
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original_client(transport=transport, **kwargs),
    )
    runtime = LLMRuntimeConfig(
        provider="openai",
        protocol="openai_chat",
        base_url="https://api.openai.com/v1",
        api_key="placeholder-vendor-key",
        proxy_url="https://example.com/v1",
        proxy_password="placeholder-proxy-password",
        model="proxy-model",
    )

    connection = AIConfigService.test_connection(runtime)
    content, usage = LLMUtil.sync_call(
        "generate",
        temperature=0.2,
        use_cache=False,
        allow_mock=False,
        runtime_config=runtime,
    )

    assert connection.success is True
    assert connection.models == ["proxy-model"]
    assert content == "proxy-generated-content"
    assert usage["total_tokens"] == 5
    assert [str(request.url) for request in requests] == [
        "https://example.com/v1/models",
        "https://example.com/v1/chat/completions",
        "https://example.com/v1/chat/completions",
    ]


@pytest.mark.parametrize("model", ["kimi-k2.5", "kimi-k2.6"])
def test_kimi_k2_omits_incompatible_sampling_parameters(monkeypatch, model):
    captured = {}
    original_client = httpx.Client

    def handle_request(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        captured.update(payload)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "OK"}}],
                "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
            },
        )

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original_client(
            transport=httpx.MockTransport(handle_request), **kwargs
        ),
    )
    runtime = LLMRuntimeConfig(
        provider="moonshot",
        protocol="openai_chat",
        base_url="https://api.moonshot.cn/v1",
        api_key="placeholder-kimi-key",
        model=model,
    )

    content, _ = AIProtocolClient.complete(
        runtime,
        [{"role": "user", "content": "reply OK"}],
        temperature=0.7,
        max_tokens=64,
    )

    assert content == "OK"
    assert captured["max_tokens"] == 64
    assert "temperature" not in captured
    assert "thinking" not in captured


def test_connection_test_rejects_model_listing_without_text_generation(monkeypatch):
    original_client = httpx.Client

    def handle_request(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"data": [{"id": "listed-model"}]})
        return httpx.Response(
            400,
            json={"error": {"message": "unsupported generation parameters"}},
        )

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original_client(
            transport=httpx.MockTransport(handle_request), **kwargs
        ),
    )
    runtime = LLMRuntimeConfig(
        provider="custom",
        protocol="openai_chat",
        base_url="https://example.com/v1",
        api_key="placeholder-key",
        model="listed-model",
    )

    result = AIConfigService.test_connection(runtime)

    assert result.success is False
    assert result.models == ["listed-model"]
    assert result.error_code == "provider_error"
    assert "无法完成文本生成" in result.message


@pytest.mark.parametrize(
    ("runtime", "model_response", "generation_path", "generation_response"),
    [
        (
            LLMRuntimeConfig(
                provider="openai_responses",
                protocol=PROTOCOL_OPENAI_RESPONSES,
                base_url="https://api.openai.com/v1",
                api_key="placeholder-key",
                model="gpt-test",
            ),
            {"data": [{"id": "gpt-test"}]},
            "/v1/responses",
            {"output_text": "OK", "usage": {"input_tokens": 2, "output_tokens": 1}},
        ),
        (
            LLMRuntimeConfig(
                provider="anthropic",
                protocol=PROTOCOL_ANTHROPIC,
                base_url="https://api.anthropic.com/v1",
                api_key="placeholder-key",
                model="claude-test",
            ),
            {"data": [{"id": "claude-test"}]},
            "/v1/messages",
            {"content": [{"type": "text", "text": "OK"}], "usage": {}},
        ),
        (
            LLMRuntimeConfig(
                provider="gemini",
                protocol=PROTOCOL_GEMINI,
                base_url="https://generativelanguage.googleapis.com/v1beta",
                api_key="placeholder-key",
                model="gemini-test",
            ),
            {"models": [{"name": "models/gemini-test"}]},
            "/v1beta/models/gemini-test:generateContent",
            {"candidates": [{"content": {"parts": [{"text": "OK"}]}}]},
        ),
        (
            LLMRuntimeConfig(
                provider="ollama",
                protocol=PROTOCOL_OLLAMA,
                base_url="http://127.0.0.1:11434",
                model="local-test",
                requires_api_key=False,
            ),
            {"models": [{"name": "local-test"}]},
            "/api/chat",
            {"message": {"content": "OK"}},
        ),
    ],
)
def test_connection_generates_text_for_each_supported_protocol(
    runtime, model_response, generation_path, generation_response, monkeypatch
):
    original_client = httpx.Client
    requests = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json=model_response)
        assert request.url.path == generation_path
        return httpx.Response(200, json=generation_response)

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original_client(
            transport=httpx.MockTransport(handle_request), **kwargs
        ),
    )

    result = AIConfigService.test_connection(runtime)

    assert result.success is True
    if runtime.provider == "anthropic":
        assert result.models == []
        assert [request.method for request in requests] == ["POST"]
    else:
        assert result.models == [runtime.model]
        assert [request.method for request in requests] == ["GET", "POST"]


def test_ai_config_survives_logout_and_relogin(client, sample_user, auth_headers):
    saved = client.put(
        "/api/v1/ai-config",
        headers=auth_headers,
        json={
            "provider": "custom",
            "baseUrl": "https://example.com/v1",
            "apiKey": "placeholder-persistent-key",
            "selectedModel": "persistent-model",
            "availableModels": ["persistent-model", "other-model"],
        },
    )
    assert saved.status_code == 200
    assert client.post("/api/v1/auth/logout", headers=auth_headers).status_code == 200

    fresh_token = create_access_token({
        "user_id": sample_user.id,
        "username": sample_user.username,
        "role": sample_user.role.value,
    })
    reloaded = client.get(
        "/api/v1/ai-config",
        headers={"Authorization": f"Bearer {fresh_token}"},
    )

    assert reloaded.status_code == 200
    config = reloaded.json()["data"]
    assert config["selectedModel"] == "persistent-model"
    assert config["availableModels"] == ["persistent-model", "other-model"]
    assert config["apiKeyConfigured"] is True
    assert "placeholder-persistent-key" not in reloaded.text


def test_resource_page_pipeline_thread_binds_requesting_account_runtime(
    client,
    sample_user,
    sample_learner_profile,
    auth_headers,
    monkeypatch,
):
    import app.domains.agent.router as agent_router

    captured = {}
    observed = {}

    class DeferredThread:
        def __init__(self, *, target, **_kwargs):
            captured["target"] = target

        def start(self):
            return None

    class ThreadingStub:
        Thread = DeferredThread

    runtime = LLMRuntimeConfig(
        owner_user_id=sample_user.id,
        provider="custom",
        protocol="openai_chat",
        base_url="https://example.com/v1",
        api_key="placeholder-account-key",
        model="account-selected-model",
    )
    monkeypatch.setattr(agent_router, "threading", ThreadingStub)
    monkeypatch.setattr(
        AIConfigService,
        "get_active_runtime_config",
        classmethod(lambda _cls, user_id=None: runtime if user_id == sample_user.id else None),
    )

    def record_runtime(**_kwargs):
        observed["user_id"] = get_runtime_user_id()
        observed["runtime"] = get_runtime_config()

    monkeypatch.setattr(agent_router.orchestrator, "run_full_pipeline", record_runtime)
    response = client.post(
        "/api/v1/agent/run/full-pipeline",
        headers=auth_headers,
        json={
            "learner_id": sample_learner_profile.id,
            "target_topic": "runtime binding test",
            "resource_type": "guide",
        },
    )
    assert response.status_code == 200

    # Execute after the HTTP middleware has released its request ContextVar,
    # matching the detached thread used by the resource-generation page.
    captured["target"]()

    assert observed["user_id"] == sample_user.id
    assert observed["runtime"].owner_user_id == sample_user.id
    assert observed["runtime"].model == "account-selected-model"


def test_local_provider_endpoints_are_limited_to_loopback_by_default(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "AI_CONFIG_ALLOW_PRIVATE_ENDPOINTS", False)
    local_runtime = LLMRuntimeConfig(
        provider="ollama",
        protocol="ollama",
        base_url="http://127.0.0.1:11434",
        requires_api_key=False,
        model="qwen2.5",
    )
    remote_runtime = LLMRuntimeConfig(
        provider="ollama",
        protocol="ollama",
        base_url="https://example.com",
        requires_api_key=False,
        model="qwen2.5",
    )
    custom_private_runtime = LLMRuntimeConfig(
        provider="custom",
        protocol="openai_chat",
        base_url="http://127.0.0.1:8000/v1",
        api_key="test-key",
        model="test-model",
    )

    assert AIConfigService._is_permitted_endpoint(local_runtime) is True
    assert AIConfigService._is_permitted_endpoint(remote_runtime) is False
    assert AIConfigService._is_permitted_endpoint(custom_private_runtime) is False


def test_hostname_resolution_blocks_private_addresses(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("10.20.30.40", 443)),
        ],
    )
    runtime = LLMRuntimeConfig(
        provider="custom",
        protocol="openai_chat",
        base_url="https://alias.example.com/v1",
        api_key="test-key",
        model="test-model",
    )

    assert AIConfigService._is_permitted_endpoint(runtime) is False


def test_hostname_resolution_requires_all_answers_to_be_public(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 443)),
        ],
    )
    runtime = LLMRuntimeConfig(
        provider="custom",
        protocol="openai_chat",
        base_url="https://mixed.example.com/v1",
        api_key="test-key",
        model="test-model",
    )

    assert AIConfigService._is_permitted_endpoint(runtime) is False


def test_runtime_call_rechecks_hostname_before_sending_credentials(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("169.254.169.254", 443)),
        ],
    )
    runtime = LLMRuntimeConfig(
        provider="custom",
        protocol="openai_chat",
        base_url="https://metadata.example.com/v1",
        api_key="test-key",
        model="test-model",
    )

    with pytest.raises(LLMUnavailableError, match="unsafe_endpoint"):
        LLMUtil.sync_call(
            "test",
            use_cache=False,
            allow_mock=False,
            runtime_config=runtime,
        )


def test_runtime_cache_key_is_partitioned_by_account_and_credentials():
    runtime = LLMRuntimeConfig(
        provider="custom",
        protocol="openai_chat",
        base_url="https://example.com/v1",
        api_key="credential-a",
        model="model-a",
    )
    messages = [{"role": "user", "content": "same prompt"}]

    with use_runtime_user_id(101):
        first_key = LLMUtil._runtime_cache_key(runtime, messages, 0.2)
    with use_runtime_user_id(202):
        second_key = LLMUtil._runtime_cache_key(runtime, messages, 0.2)

    assert first_key != second_key
    assert "credential-a" not in first_key


def test_generation_params_are_sparse_model_scoped_and_require_a_fresh_test(
    client, db_session, sample_user, auth_headers, monkeypatch
):
    """A model switch starts clean, while returning to a model restores its profile."""

    monkeypatch.setattr(
        AIConfigService,
        "test_connection",
        lambda runtime: ConnectionTestResult(
            True,
            ["model-a", "model-b"],
            8,
            "连接成功",
        ),
    )

    first = client.post(
        "/api/v1/ai-config/test",
        headers=auth_headers,
        json={
            "provider": "deepseek",
            "apiKey": "placeholder-key",
            "selectedModel": "model-a",
            "generationParams": {"temperature": 0.35, "top_p": 0.8},
        },
    )

    assert first.status_code == 200
    first_data = first.json()["data"]
    assert first_data["generationParams"] == {"temperature": 0.35, "top_p": 0.8}
    assert {item["key"] for item in first_data["generationParamsMeta"]} == {
        "temperature",
        "top_p",
        "frequency_penalty",
        "presence_penalty",
    }

    # PUT cannot persist a changed sampling value without a real connection
    # check. The UI uses POST /test, but the server owns the enforcement.
    blocked = client.put(
        "/api/v1/ai-config",
        headers=auth_headers,
        json={
            "provider": "deepseek",
            "selectedModel": "model-a",
            "generationParams": {"temperature": 0.45, "top_p": 0.8},
        },
    )
    assert blocked.status_code == 400
    assert "先点击连接测试" in blocked.json()["message"]

    second = client.post(
        "/api/v1/ai-config/test",
        headers=auth_headers,
        json={
            "provider": "deepseek",
            "selectedModel": "model-b",
            "generationParams": {},
        },
    )
    assert second.status_code == 200
    assert second.json()["data"]["generationParams"] == {}

    # No generationParams field means reuse the selected model's stored sparse
    # profile. It must not pick up model-b's empty/default state.
    restored = client.post(
        "/api/v1/ai-config/test",
        headers=auth_headers,
        json={"provider": "deepseek", "selectedModel": "model-a"},
    )
    assert restored.status_code == 200
    assert restored.json()["data"]["generationParams"] == {
        "temperature": 0.35,
        "top_p": 0.8,
    }

    stored = db_session.query(UserAIConfig).filter(UserAIConfig.user_id == sample_user.id).one()
    assert "_generationParamsProfiles" in (stored.extra_config or {})
    public_data = client.get("/api/v1/ai-config", headers=auth_headers).json()["data"]
    assert public_data["generationParams"] == {"temperature": 0.35, "top_p": 0.8}
    assert "_generationParamsProfiles" not in public_data["extraConfig"]


def test_generation_params_validate_model_capabilities_before_connection():
    with pytest.raises(ValueError, match="允许范围"):
        AIConfigService.prepare_runtime_config(
            AIConfigUpdate(
                provider="anthropic",
                apiKey="placeholder-key",
                selectedModel="claude-sonnet-4-5",
                generationParams={"temperature": 1.2},
            ),
            None,
        )

    with pytest.raises(ValueError, match="不能同时调整"):
        AIConfigService.prepare_runtime_config(
            AIConfigUpdate(
                provider="anthropic",
                apiKey="placeholder-key",
                selectedModel="claude-sonnet-4-5",
                generationParams={"temperature": 0.5, "top_p": 0.8},
            ),
            None,
        )

    custom_provider, custom_runtime, _ = AIConfigService.prepare_runtime_config(
        AIConfigUpdate(
            provider="custom",
            baseUrl="https://example.com/v1",
            apiKey="placeholder-key",
            selectedModel="unknown-compatible-model",
            generationParams={"temperature": 0.5},
        ),
        None,
    )
    assert custom_provider.id == "custom"
    assert custom_runtime.generation_params == {"temperature": 0.5}

    custom_meta = AIProtocolClient.generation_params_meta(
        LLMRuntimeConfig(provider="custom", protocol="openai_chat", model="unknown-compatible-model")
    )
    assert all(item["supported"] is True for item in custom_meta)


def test_generation_param_shape_changes_require_a_fresh_connection_test():
    record = UserAIConfig(
        user_id=1,
        provider="openai",
        protocol="openai_chat",
        base_url="https://api.openai.com/v1",
        selected_model="gpt-4o",
        api_key_encrypted=AIConfigService.encrypt_secret("placeholder-key"),
        extra_config={},
    )

    provider, runtime, metadata = AIConfigService.prepare_runtime_config(
        AIConfigUpdate(
            provider="openai",
            selectedModel="gpt-4o",
            generationParams={"temperature": 1},
        ),
        record,
    )

    assert provider.id == "openai"
    assert metadata["generation_params_changed"] is True
    assert AIConfigService._generation_change_requires_test(
        record,
        runtime,
        metadata,
        AIConfigUpdate(
            provider="openai",
            selectedModel="gpt-4o",
            generationParams={"temperature": 1},
        ),
    ) is True


def test_explicit_generation_params_are_sent_and_empty_profiles_do_not_inject_them(monkeypatch):
    original_client = httpx.Client
    payloads = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original_client(
            transport=httpx.MockTransport(handle_request), **kwargs
        ),
    )
    configured_runtime = LLMRuntimeConfig(
        provider="deepseek",
        protocol="openai_chat",
        base_url="https://api.deepseek.com",
        api_key="placeholder-key",
        model="deepseek-chat",
        generation_params={
            "temperature": 0.35,
            "top_p": 0.8,
            "frequency_penalty": 0.2,
            "presence_penalty": -0.1,
        },
    )
    empty_runtime = LLMRuntimeConfig(
        provider="deepseek",
        protocol="openai_chat",
        base_url="https://api.deepseek.com",
        api_key="placeholder-key",
        model="deepseek-chat",
        generation_params={},
    )

    AIProtocolClient.complete(
        configured_runtime,
        [{"role": "user", "content": "reply OK"}],
        temperature=0.9,
        max_tokens=64,
    )
    AIProtocolClient.complete(
        empty_runtime,
        [{"role": "user", "content": "reply OK"}],
        temperature=0.1,
        max_tokens=64,
    )

    assert payloads[0]["temperature"] == 0.35
    assert payloads[0]["top_p"] == 0.8
    assert payloads[0]["frequency_penalty"] == 0.2
    assert payloads[0]["presence_penalty"] == -0.1
    assert not {
        "temperature",
        "top_p",
        "frequency_penalty",
        "presence_penalty",
    }.intersection(payloads[1])


def test_legacy_fallback_cache_key_is_partitioned_by_account():
    with use_runtime_user_id(101):
        first_key = LLMUtil._compute_prompt_hash("same prompt", None, None, 0.2)
    with use_runtime_user_id(202):
        second_key = LLMUtil._compute_prompt_hash("same prompt", None, None, 0.2)

    assert first_key != second_key


def test_logger_redacts_camel_case_ai_secrets():
    sanitized = _sanitize_dict(
        {
            "apiKey": "secret-a",
            "proxyPassword": "secret-b",
            "x-goog-api-key": "secret-c",
            "name": "safe",
        }
    )

    assert sanitized == {
        "apiKey": "***REDACTED***",
        "proxyPassword": "***REDACTED***",
        "x-goog-api-key": "***REDACTED***",
        "name": "safe",
    }


def test_provider_options_expose_camel_case_default_model_and_verified_urls():
    from app.services.ai_providers import get_provider, provider_options

    options = {item["id"]: item for item in provider_options()}

    assert options["stepfun"]["defaultBaseUrl"] == "https://api.stepfun.com/step_plan/v1"
    assert options["baichuan"]["defaultBaseUrl"] == "https://api.baichuan-ai.com/v1"
    assert options["moonshot"]["defaultModel"] == "kimi-k2.5"
    assert options["minimax"]["defaultModel"] == "MiniMax-M2.7"
    assert "default_model" not in options["moonshot"]
    assert get_provider("anthropic").supports_models_endpoint is False
    assert get_provider("perplexity").supports_models_endpoint is False


@pytest.mark.parametrize(
    ("runtime", "generation_path", "generation_response"),
    [
        (
            LLMRuntimeConfig(
                provider="anthropic",
                protocol=PROTOCOL_ANTHROPIC,
                base_url="https://api.anthropic.com/v1",
                api_key="placeholder-key",
                model="claude-sonnet-4-5",
            ),
            "/v1/messages",
            {"content": [{"type": "text", "text": "OK"}], "usage": {}},
        ),
        (
            LLMRuntimeConfig(
                provider="perplexity",
                protocol="openai_chat",
                base_url="https://api.perplexity.ai",
                api_key="placeholder-key",
                model="sonar",
            ),
            "/chat/completions",
            {"choices": [{"message": {"content": "OK"}}], "usage": {}},
        ),
        (
            LLMRuntimeConfig(
                provider="zai",
                protocol="openai_chat",
                base_url="https://api.z.ai/api/paas/v4",
                api_key="placeholder-key",
                model="glm-4.5",
            ),
            "/api/paas/v4/chat/completions",
            {"choices": [{"message": {"content": "OK"}}], "usage": {}},
        ),
        (
            LLMRuntimeConfig(
                provider="minimax",
                protocol="openai_chat",
                base_url="https://api.minimaxi.com/v1",
                api_key="placeholder-key",
                model="MiniMax-M2.7",
            ),
            "/v1/chat/completions",
            {"choices": [{"message": {"content": "OK"}}], "usage": {}},
        ),
    ],
)
def test_connection_uses_text_generation_when_provider_has_no_model_listing(
    runtime, generation_path, generation_response, monkeypatch
):
    original_client = httpx.Client
    requests = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.method == "POST"
        assert request.url.path == generation_path
        return httpx.Response(200, json=generation_response)

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original_client(
            transport=httpx.MockTransport(handle_request), **kwargs
        ),
    )

    result = AIConfigService.test_connection(runtime)

    assert result.success is True
    assert result.models == []
    assert "未提供模型列表" in result.message
    assert [request.method for request in requests] == ["POST"]


def test_connection_falls_back_to_generation_when_a_compatible_models_endpoint_is_missing(monkeypatch):
    original_client = httpx.Client
    requests = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            assert request.url.path == "/v1/models"
            return httpx.Response(404, json={"error": {"message": "not found"}})
        assert request.url.path == "/v1/chat/completions"
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original_client(
            transport=httpx.MockTransport(handle_request), **kwargs
        ),
    )
    runtime = LLMRuntimeConfig(
        provider="custom",
        protocol="openai_chat",
        base_url="https://example.com/v1",
        api_key="placeholder-key",
        model="manual-model",
    )

    result = AIConfigService.test_connection(runtime)

    assert result.success is True
    assert result.models == []
    assert "未提供模型列表" in result.message
    assert [request.method for request in requests] == ["GET", "POST"]


def test_connection_uses_the_configured_timeout_for_text_generation(monkeypatch):
    captured = {}

    def complete(runtime, messages, *, temperature, max_tokens, timeout):
        captured["timeout"] = timeout
        return "OK", {}

    monkeypatch.setattr(AIProtocolClient, "complete", complete)
    runtime = LLMRuntimeConfig(
        provider="anthropic",
        protocol=PROTOCOL_ANTHROPIC,
        base_url="https://api.anthropic.com/v1",
        api_key="placeholder-key",
        model="claude-sonnet-4-5",
    )

    result = AIConfigService.test_connection(runtime)

    assert result.success is True
    assert captured["timeout"] == float(settings.AI_CONFIG_TEST_TIMEOUT_SECONDS)


def test_openai_reasoning_models_use_supported_generation_parameters(monkeypatch):
    original_client = httpx.Client
    captured = {}

    def handle_request(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original_client(
            transport=httpx.MockTransport(handle_request), **kwargs
        ),
    )
    runtime = LLMRuntimeConfig(
        provider="openai",
        protocol="openai_chat",
        base_url="https://api.openai.com/v1",
        api_key="placeholder-key",
        model="gpt-5-mini",
    )

    content, _ = AIProtocolClient.complete(
        runtime,
        [{"role": "user", "content": "reply OK"}],
        temperature=0.2,
        max_tokens=64,
    )

    assert content == "OK"
    assert "temperature" not in captured
    assert "max_tokens" not in captured
    assert captured["max_completion_tokens"] == 64


def test_minimax_uses_supported_sampling_and_token_fields(monkeypatch):
    original_client = httpx.Client
    captured = {}

    def handle_request(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original_client(
            transport=httpx.MockTransport(handle_request), **kwargs
        ),
    )
    runtime = LLMRuntimeConfig(
        provider="minimax",
        protocol="openai_chat",
        base_url="https://api.minimaxi.com/v1",
        api_key="placeholder-key",
        model="MiniMax-M2.7",
    )

    content, _ = AIProtocolClient.complete(
        runtime,
        [{"role": "user", "content": "reply OK"}],
        temperature=0.0,
        max_tokens=64,
    )

    assert content == "OK"
    assert 0.0 < captured["temperature"] <= 1.0
    assert "max_tokens" not in captured
    assert captured["max_completion_tokens"] == 64


def test_claude_temperature_is_clamped_to_supported_range(monkeypatch):
    original_client = httpx.Client
    captured = {}

    def handle_request(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"content": [{"type": "text", "text": "OK"}]})

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original_client(
            transport=httpx.MockTransport(handle_request), **kwargs
        ),
    )
    runtime = LLMRuntimeConfig(
        provider="anthropic",
        protocol=PROTOCOL_ANTHROPIC,
        base_url="https://api.anthropic.com/v1",
        api_key="placeholder-key",
        model="claude-sonnet-4-5",
    )

    content, _ = AIProtocolClient.complete(
        runtime,
        [{"role": "user", "content": "reply OK"}],
        temperature=1.7,
        max_tokens=64,
    )

    assert content == "OK"
    assert captured["temperature"] == 1.0


def test_openai_responses_reasoning_models_omit_temperature(monkeypatch):
    original_client = httpx.Client
    captured = {}

    def handle_request(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"output_text": "OK"})

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original_client(
            transport=httpx.MockTransport(handle_request), **kwargs
        ),
    )
    runtime = LLMRuntimeConfig(
        provider="openai_responses",
        protocol=PROTOCOL_OPENAI_RESPONSES,
        base_url="https://api.openai.com/v1",
        api_key="placeholder-key",
        model="gpt-5-mini",
    )

    content, _ = AIProtocolClient.complete(
        runtime,
        [{"role": "user", "content": "reply OK"}],
        temperature=0.2,
        max_tokens=64,
    )

    assert content == "OK"
    assert "temperature" not in captured
    assert captured["max_output_tokens"] == 64


def test_gemini_uses_its_native_temperature_and_output_token_fields(monkeypatch):
    original_client = httpx.Client
    captured = {}

    def handle_request(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "OK"}]}}]},
        )

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original_client(
            transport=httpx.MockTransport(handle_request), **kwargs
        ),
    )
    runtime = LLMRuntimeConfig(
        provider="gemini",
        protocol=PROTOCOL_GEMINI,
        base_url="https://generativelanguage.googleapis.com/v1beta",
        api_key="placeholder-key",
        model="gemini-2.0-flash",
    )

    content, _ = AIProtocolClient.complete(
        runtime,
        [{"role": "user", "content": "reply OK"}],
        temperature=0.2,
        max_tokens=64,
    )

    assert content == "OK"
    assert captured["generationConfig"] == {"temperature": 0.2, "maxOutputTokens": 64}


def test_gemini_3_omits_incompatible_temperature(monkeypatch):
    original_client = httpx.Client
    captured = {}

    def handle_request(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "OK"}]}}]},
        )

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original_client(
            transport=httpx.MockTransport(handle_request), **kwargs
        ),
    )
    runtime = LLMRuntimeConfig(
        provider="gemini",
        protocol=PROTOCOL_GEMINI,
        base_url="https://generativelanguage.googleapis.com/v1beta",
        api_key="placeholder-key",
        model="gemini-3-pro-preview",
    )

    content, _ = AIProtocolClient.complete(
        runtime,
        [{"role": "user", "content": "reply OK"}],
        temperature=0.2,
        max_tokens=64,
    )

    assert content == "OK"
    assert captured["generationConfig"] == {"maxOutputTokens": 64}


def test_deepseek_thinking_and_claude_opus_without_sampling_omit_temperature(monkeypatch):
    original_client = httpx.Client
    payloads = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        if request.url.path.endswith("/messages"):
            return httpx.Response(200, json={"content": [{"type": "text", "text": "OK"}]})
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original_client(
            transport=httpx.MockTransport(handle_request), **kwargs
        ),
    )
    deepseek_runtime = LLMRuntimeConfig(
        provider="deepseek",
        protocol="openai_chat",
        base_url="https://api.deepseek.com",
        api_key="placeholder-key",
        model="deepseek-v4-flash",
        thinking_param=True,
        thinking_enabled=True,
    )
    claude_runtime = LLMRuntimeConfig(
        provider="anthropic",
        protocol=PROTOCOL_ANTHROPIC,
        base_url="https://api.anthropic.com/v1",
        api_key="placeholder-key",
        model="claude-opus-4-7",
    )

    AIProtocolClient.complete(
        deepseek_runtime,
        [{"role": "user", "content": "reply OK"}],
        temperature=0.2,
        max_tokens=64,
    )
    AIProtocolClient.complete(
        claude_runtime,
        [{"role": "user", "content": "reply OK"}],
        temperature=0.2,
        max_tokens=64,
    )

    assert payloads[0]["thinking"] == {"type": "enabled"}
    assert "temperature" not in payloads[0]
    assert "temperature" not in payloads[1]
