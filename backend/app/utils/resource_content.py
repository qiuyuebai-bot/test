"""Validation helpers for generated learning-resource Markdown content.

LLM output is untrusted.  Resource bodies are persisted as Markdown text, so
structured model envelopes, mock responses, and audit payloads must never be
stored in ``LearningResource.content``.
"""
import json
import math
import re
from collections.abc import Mapping
from typing import Any


class ResourceContentError(ValueError):
    """Raised when generated resource content is not safe Markdown text."""


_JSON_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.IGNORECASE | re.DOTALL)
_PLACEHOLDER_TITLE = re.compile(
    r"(?:^|[\s:_-])(none|null|undefined)(?=$|[\s:_-])",
    re.IGNORECASE,
)
_RESOURCE_TYPE_LABELS = {
    "guide": "实操指南",
    "exercise": "分阶测试题",
    "lecture": "专属知识讲义",
}
_DIFFICULTY_LABELS = ("入门级", "基础级", "进阶级", "精通级", "专家级")
_AUDIT_PAYLOAD_KEYS = frozenset(
    {
        "passed",
        "overall_score",
        "score",
        "issues",
        "suggestions",
        "corrections",
        "hallucination_detected",
        "hallucination_score",
        "debate_record",
    }
)


def normalize_resource_topic(raw_topic: Any) -> str:
    """Return a non-empty topic for resource generation."""
    if not isinstance(raw_topic, str) or not raw_topic.strip():
        raise ValueError("目标主题不能为空")
    return raw_topic.strip()


def build_resource_title(topic: Any, resource_type: str, difficulty: Any) -> str:
    """Build the deterministic fallback title used by generation and repair."""
    normalized_topic = normalize_resource_topic(topic)
    try:
        difficulty_value = int(difficulty)
    except (TypeError, ValueError):
        difficulty_value = 3
    difficulty_value = min(max(difficulty_value, 1), len(_DIFFICULTY_LABELS))
    type_label = _RESOURCE_TYPE_LABELS.get(resource_type, "学习资源")
    return validate_resource_title(
        f"{normalized_topic} - {_DIFFICULTY_LABELS[difficulty_value - 1]}{type_label}"
    )


def validate_resource_title(raw_title: Any) -> str:
    """Reject blank or placeholder titles before they reach persistence."""
    if not isinstance(raw_title, str):
        raise ResourceContentError("资源标题不能为空")
    title = raw_title.strip()
    if not title:
        raise ResourceContentError("资源标题不能为空")
    if _PLACEHOLDER_TITLE.search(title):
        raise ResourceContentError("资源标题包含无效占位符")
    return title


def validate_match_score(raw_score: Any) -> float | None:
    """Validate a persisted match score without inventing a missing value."""
    if raw_score is None:
        return None
    try:
        score = float(raw_score)
    except (TypeError, ValueError) as exc:
        raise ResourceContentError("资源匹配度必须是数字") from exc
    if not math.isfinite(score) or not 0 <= score <= 100:
        raise ResourceContentError("资源匹配度必须在 0 到 100 之间")
    return score


def normalize_resource_content(raw_content: Any, *, allow_mock: bool = False) -> str:
    """Return Markdown text from a valid resource response.

    A provider may wrap valid Markdown in a JSON object with a ``content``
    field.  That envelope is unwrapped, but mock and audit payloads are
    rejected.  The small recursion limit handles accidentally double-encoded
    JSON without treating ordinary Markdown code samples as JSON responses.
    """
    value = raw_content

    for _ in range(3):
        if isinstance(value, str):
            parsed = _parse_complete_json(value)
            if parsed is None:
                content = value.strip()
                if not content:
                    raise ResourceContentError("Generated resource content is empty")
                return content
            value = parsed
            continue

        if not isinstance(value, Mapping):
            raise ResourceContentError("Generated resource content must be Markdown text")

        _reject_unsafe_payload(value, allow_mock=allow_mock)
        if "content" not in value:
            raise ResourceContentError(
                "Generated resource content is a JSON object instead of Markdown text"
            )
        value = value["content"]

    raise ResourceContentError("Generated resource content is nested too deeply")


def _parse_complete_json(value: str) -> Any | None:
    """Parse a string only when its complete value is JSON or a JSON fence."""
    text = value.strip()
    fenced = _JSON_FENCE.match(text)
    if fenced:
        text = fenced.group(1).strip()

    # Do not parse ordinary Markdown that merely contains a JSON example.
    if not (
        text.startswith("{")
        or text.startswith("[")
        or text.startswith('"{')
        or text.startswith('"[')
    ):
        return None

    try:
        return json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return None


def _reject_unsafe_payload(payload: Mapping[str, Any], *, allow_mock: bool = False) -> None:
    meta = payload.get("_meta")
    if (
        not allow_mock
        and isinstance(meta, Mapping)
        and str(meta.get("model", "")).strip().lower() == "mock"
    ):
        raise ResourceContentError("Generated resource content is an LLM mock response")

    if _AUDIT_PAYLOAD_KEYS.intersection(payload.keys()):
        raise ResourceContentError("Generated resource content is an audit payload")
