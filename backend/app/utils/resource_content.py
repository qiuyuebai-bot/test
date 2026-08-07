"""Validation helpers for generated learning-resource Markdown content.

LLM output is untrusted.  Resource bodies are persisted as Markdown text, so
structured model envelopes, mock responses, and audit payloads must never be
stored in ``LearningResource.content``.
"""
import json
import re
from collections.abc import Mapping
from typing import Any


class ResourceContentError(ValueError):
    """Raised when generated resource content is not safe Markdown text."""


_JSON_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.IGNORECASE | re.DOTALL)
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
