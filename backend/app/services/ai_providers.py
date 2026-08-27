"""Provider catalogue and protocol metadata for the first AI configuration phase.

Only providers marked ``implemented=True`` are sent over the wire in phase one.
The remaining entries are intentionally exposed as framework metadata so the
UI can communicate that a provider is known but needs a protocol adapter; they
must never silently receive an OpenAI-shaped request.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Iterable, List, Optional


PROTOCOL_OPENAI_CHAT = "openai_chat"
PROTOCOL_OPENAI_RESPONSES = "openai_responses"
PROTOCOL_ANTHROPIC = "anthropic_messages"
PROTOCOL_GEMINI = "gemini"
PROTOCOL_AZURE_OPENAI = "azure_openai"
PROTOCOL_VERTEX_AI = "vertex_ai"
PROTOCOL_BEDROCK = "aws_bedrock"
PROTOCOL_OLLAMA = "ollama"


@dataclass(frozen=True)
class ProviderDefinition:
    id: str
    label: str
    protocol: str
    default_base_url: str
    group: str = "official"
    requires_api_key: bool = True
    supports_models_endpoint: bool = True
    supports_reverse_proxy: bool = True
    implemented: bool = True
    default_model: str = ""
    description: str = ""

    def to_public_dict(self) -> dict:
        """Serialize only non-secret provider metadata for the frontend."""

        data = asdict(self)
        # The browser-facing API uses camelCase consistently; keep private
        # dataclass names out of the public contract.
        data["defaultBaseUrl"] = data["default_base_url"]
        data["requiresApiKey"] = data["requires_api_key"]
        data["supportsModelsEndpoint"] = data["supports_models_endpoint"]
        data["supportsReverseProxy"] = data["supports_reverse_proxy"]
        data["defaultModel"] = data["default_model"]
        data.pop("default_base_url", None)
        data.pop("requires_api_key", None)
        data.pop("supports_models_endpoint", None)
        data.pop("supports_reverse_proxy", None)
        data.pop("default_model", None)
        return data


# The list intentionally includes the commonly used official and gateway
# options from Cherry Studio, while keeping protocol support explicit.
_PROVIDERS: tuple[ProviderDefinition, ...] = (
    ProviderDefinition("custom", "自定义（兼容 OpenAI）", PROTOCOL_OPENAI_CHAT, "", group="custom", default_model=""),
    ProviderDefinition("openai", "OpenAI", PROTOCOL_OPENAI_CHAT, "https://api.openai.com/v1", default_model="gpt-4o"),
    ProviderDefinition("openai_responses", "OpenAI Responses", PROTOCOL_OPENAI_RESPONSES, "https://api.openai.com/v1", default_model="gpt-4.1"),
    ProviderDefinition("deepseek", "DeepSeek", PROTOCOL_OPENAI_CHAT, "https://api.deepseek.com", default_model="deepseek-v4-flash"),
    ProviderDefinition("moonshot", "Moonshot / Kimi（中国）", PROTOCOL_OPENAI_CHAT, "https://api.moonshot.cn/v1", default_model="kimi-k2.5"),
    ProviderDefinition("moonshot_global", "Moonshot / Kimi（国际）", PROTOCOL_OPENAI_CHAT, "https://api.moonshot.ai/v1", default_model="kimi-k2.5"),
    ProviderDefinition("qwen", "通义千问 / DashScope", PROTOCOL_OPENAI_CHAT, "https://dashscope.aliyuncs.com/compatible-mode/v1", default_model="qwen-plus"),
    ProviderDefinition("zhipu", "智谱 GLM", PROTOCOL_OPENAI_CHAT, "https://open.bigmodel.cn/api/paas/v4", default_model="glm-4-plus"),
    ProviderDefinition("zai", "Z.ai", PROTOCOL_OPENAI_CHAT, "https://api.z.ai/api/paas/v4", supports_models_endpoint=False, default_model="glm-4.5"),
    ProviderDefinition("minimax", "MiniMax", PROTOCOL_OPENAI_CHAT, "https://api.minimaxi.com/v1", supports_models_endpoint=False, default_model="MiniMax-M2.7"),
    ProviderDefinition("minimax_global", "MiniMax Global", PROTOCOL_OPENAI_CHAT, "https://api.minimax.io/v1", supports_models_endpoint=False, default_model="MiniMax-M2.7"),
    ProviderDefinition("doubao", "豆包 / 火山引擎", PROTOCOL_OPENAI_CHAT, "https://ark.cn-beijing.volces.com/api/v3", default_model=""),
    ProviderDefinition("baichuan", "百川", PROTOCOL_OPENAI_CHAT, "https://api.baichuan-ai.com/v1", default_model="Baichuan4"),
    ProviderDefinition("yi", "零一万物 Yi", PROTOCOL_OPENAI_CHAT, "https://api.lingyiwanwu.com/v1", default_model="yi-large"),
    ProviderDefinition("stepfun", "阶跃星辰", PROTOCOL_OPENAI_CHAT, "https://api.stepfun.com/step_plan/v1", default_model="step-3.5-flash"),
    ProviderDefinition("mistral", "Mistral", PROTOCOL_OPENAI_CHAT, "https://api.mistral.ai/v1", default_model="mistral-large-latest"),
    ProviderDefinition("groq", "Groq", PROTOCOL_OPENAI_CHAT, "https://api.groq.com/openai/v1", default_model="llama-3.3-70b-versatile"),
    ProviderDefinition("grok", "xAI / Grok", PROTOCOL_OPENAI_CHAT, "https://api.x.ai/v1", default_model="grok-3-mini"),
    ProviderDefinition("perplexity", "Perplexity", PROTOCOL_OPENAI_CHAT, "https://api.perplexity.ai", supports_models_endpoint=False, default_model="sonar"),
    ProviderDefinition("openrouter", "OpenRouter", PROTOCOL_OPENAI_CHAT, "https://openrouter.ai/api/v1", group="gateway", default_model=""),
    ProviderDefinition("siliconflow", "SiliconFlow", PROTOCOL_OPENAI_CHAT, "https://api.siliconflow.cn/v1", group="gateway", default_model=""),
    ProviderDefinition("modelscope", "ModelScope", PROTOCOL_OPENAI_CHAT, "https://api-inference.modelscope.cn/v1", group="gateway", default_model=""),
    ProviderDefinition("aihubmix", "AiHubMix", PROTOCOL_OPENAI_CHAT, "https://aihubmix.com/v1", group="gateway", default_model=""),
    ProviderDefinition("together", "Together AI", PROTOCOL_OPENAI_CHAT, "https://api.together.xyz/v1", group="gateway", default_model=""),
    ProviderDefinition("fireworks", "Fireworks AI", PROTOCOL_OPENAI_CHAT, "https://api.fireworks.ai/inference/v1", group="gateway", default_model=""),
    ProviderDefinition("nvidia", "NVIDIA NIM", PROTOCOL_OPENAI_CHAT, "https://integrate.api.nvidia.com/v1", group="gateway", default_model=""),
    ProviderDefinition("huggingface", "Hugging Face Router", PROTOCOL_OPENAI_CHAT, "https://router.huggingface.co/v1", group="gateway", default_model=""),
    ProviderDefinition("ollama", "Ollama", PROTOCOL_OLLAMA, "http://127.0.0.1:11434", group="local", requires_api_key=False, supports_reverse_proxy=False, default_model=""),
    ProviderDefinition("lmstudio", "LM Studio", PROTOCOL_OPENAI_CHAT, "http://127.0.0.1:1234/v1", group="local", requires_api_key=False, supports_reverse_proxy=False, default_model=""),
    # These official protocols use dedicated authentication and/or request
    # adapters instead of silently assuming a generic provider contract.
    ProviderDefinition("anthropic", "Claude 官方", PROTOCOL_ANTHROPIC, "https://api.anthropic.com/v1", group="official", implemented=True, supports_models_endpoint=False, default_model="claude-sonnet-4-5"),
    ProviderDefinition("gemini", "Gemini 官方", PROTOCOL_GEMINI, "https://generativelanguage.googleapis.com/v1beta", group="official", implemented=True, default_model="gemini-2.0-flash"),
    ProviderDefinition(
        "azure_openai",
        "Azure OpenAI",
        PROTOCOL_AZURE_OPENAI,
        "",
        group="official",
        supports_models_endpoint=False,
        supports_reverse_proxy=False,
        description="填写 Azure 资源 Endpoint、API Key 和部署名称",
    ),
    ProviderDefinition(
        "vertex_ai",
        "Google Vertex AI",
        PROTOCOL_VERTEX_AI,
        "",
        group="official",
        supports_models_endpoint=False,
        supports_reverse_proxy=False,
        description="填写 Google Cloud 项目、区域和服务账号 JSON",
    ),
    ProviderDefinition(
        "bedrock",
        "AWS Bedrock",
        PROTOCOL_BEDROCK,
        "",
        group="official",
        supports_models_endpoint=True,
        supports_reverse_proxy=False,
        description="填写 Amazon Bedrock API Key 和 AWS 区域",
    ),
)

PROVIDERS: Dict[str, ProviderDefinition] = {item.id: item for item in _PROVIDERS}

ALIASES: Dict[str, str] = {
    "kimi": "moonshot",
    "moonshot_ai": "moonshot",
    "kimi_global": "moonshot_global",
    "moonshot_international": "moonshot_global",
    "dashscope": "qwen",
    "qwen_dashscope": "qwen",
    "claude": "anthropic",
    "google": "gemini",
    "google_gemini": "gemini",
    "lm_studio": "lmstudio",
    "lm-studio": "lmstudio",
    "xai": "grok",
    "openai_compatible": "custom",
}


def normalize_provider_id(provider_id: Optional[str]) -> str:
    value = (provider_id or "custom").strip().lower().replace(" ", "_")
    return ALIASES.get(value, value)


def get_provider(provider_id: Optional[str]) -> ProviderDefinition:
    normalized = normalize_provider_id(provider_id)
    try:
        return PROVIDERS[normalized]
    except KeyError as exc:
        raise ValueError(f"unsupported_provider:{normalized}") from exc


def list_providers() -> List[ProviderDefinition]:
    return list(_PROVIDERS)


def provider_options() -> List[dict]:
    return [provider.to_public_dict() for provider in _PROVIDERS]


def is_protocol_implemented(protocol: str) -> bool:
    """Return whether at least one phase-one adapter implements ``protocol``."""

    return any(item.protocol == protocol and item.implemented for item in _PROVIDERS)


def infer_provider_from_base_url(base_url: str) -> ProviderDefinition:
    """Infer a useful fallback provider for legacy ``.env`` settings."""

    normalized = (base_url or "").lower()
    for provider in _PROVIDERS:
        if provider.default_base_url and provider.default_base_url.lower() in normalized:
            return provider
    return PROVIDERS["custom"]
