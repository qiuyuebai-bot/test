"""Request schemas for the per-user AI configuration endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


def _clean_optional_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return value.strip()


def _validate_url(value: Optional[str], field_name: str) -> Optional[str]:
    if value is None or value == "":
        return value
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{field_name} 必须是 http:// 或 https:// URL")
    if parsed.username or parsed.password:
        raise ValueError(f"{field_name} 不得包含用户名或密码")
    return value.rstrip("/")


class AIConfigUpdate(BaseModel):
    """Fields accepted when creating or updating the current user config."""

    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
    )

    provider: Optional[str] = Field(default=None, max_length=64)
    protocol: Optional[str] = Field(default=None, max_length=64)
    base_url: Optional[str] = Field(
        default=None,
        max_length=500,
        validation_alias=AliasChoices("base_url", "baseUrl"),
    )
    api_key: Optional[str] = Field(
        default=None,
        max_length=4096,
        validation_alias=AliasChoices("api_key", "apiKey"),
    )
    selected_model: Optional[str] = Field(
        default=None,
        max_length=255,
        validation_alias=AliasChoices("selected_model", "selectedModel", "model"),
    )
    available_models: Optional[List[str]] = Field(
        default=None,
        max_length=500,
        validation_alias=AliasChoices("available_models", "availableModels", "testedModels"),
    )
    proxy_url: Optional[str] = Field(
        default=None,
        max_length=500,
        validation_alias=AliasChoices("proxy_url", "proxyUrl"),
    )
    proxy_password: Optional[str] = Field(
        default=None,
        max_length=4096,
        validation_alias=AliasChoices("proxy_password", "proxyPassword"),
    )
    extra_config: Optional[Dict[str, Any]] = Field(
        default=None,
        validation_alias=AliasChoices("extra_config", "extraConfig"),
    )
    generation_params: Optional[Dict[str, Any]] = Field(
        default=None,
        validation_alias=AliasChoices("generation_params", "generationParams"),
    )
    clear_api_key: bool = Field(
        default=False,
        validation_alias=AliasChoices("clear_api_key", "clearApiKey"),
    )
    clear_proxy_password: bool = Field(
        default=False,
        validation_alias=AliasChoices("clear_proxy_password", "clearProxyPassword"),
    )

    @field_validator("provider", "protocol", "selected_model", mode="before")
    @classmethod
    def clean_text_fields(cls, value: Optional[str]) -> Optional[str]:
        return _clean_optional_text(value)

    @field_validator("available_models")
    @classmethod
    def validate_available_models(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return None
        models: List[str] = []
        for item in value:
            model = str(item or "").strip()
            if not model:
                continue
            if len(model) > 255:
                raise ValueError("模型名称长度不能超过 255")
            if model not in models:
                models.append(model)
        return models

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: Optional[str]) -> Optional[str]:
        return _validate_url(value, "API Base URL")

    @field_validator("proxy_url")
    @classmethod
    def validate_proxy_url(cls, value: Optional[str]) -> Optional[str]:
        return _validate_url(value, "代理服务器 URL")


class AIConfigTestRequest(AIConfigUpdate):
    """Optional unsaved values used by the connection-test endpoint."""

    pass
