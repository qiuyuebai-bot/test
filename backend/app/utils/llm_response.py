"""Helpers for treating LLM responses as untrusted structured data."""
import json
import re
from typing import Any, Dict


class LLMResponseError(ValueError):
    """Raised when an LLM response cannot satisfy an adapter contract."""


def parse_json_object(response: str) -> Dict[str, Any]:
    """Parse one JSON object, accepting an optional Markdown code fence."""
    text = (response or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text).strip()
    try:
        value = json.loads(text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise LLMResponseError("LLM response is not valid JSON") from exc
    if not isinstance(value, dict):
        raise LLMResponseError("LLM response must be a JSON object")
    return value


def bounded_text(value: Any, field: str, *, minimum: int = 1, maximum: int = 12000) -> str:
    """Return a non-empty, bounded string supplied by an LLM."""
    if not isinstance(value, str):
        raise LLMResponseError(f"{field} must be text")
    text = value.strip()
    if len(text) < minimum:
        raise LLMResponseError(f"{field} is too short")
    if len(text) > maximum:
        return text[:maximum]
    return text


def bounded_int(value: Any, field: str, *, minimum: int, maximum: int) -> int:
    """Return an integer inside the adapter-defined range."""
    if isinstance(value, bool):
        raise LLMResponseError(f"{field} must be an integer")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise LLMResponseError(f"{field} must be an integer") from exc
    if not minimum <= result <= maximum:
        raise LLMResponseError(f"{field} must be between {minimum} and {maximum}")
    return result


def bounded_list(value: Any, field: str, *, minimum: int = 0, maximum: int = 10) -> list:
    """Return a list with a bounded number of elements."""
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise LLMResponseError(f"{field} must contain {minimum} to {maximum} items")
    return value
