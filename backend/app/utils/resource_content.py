"""Validation helpers for generated learning-resource Markdown content.

LLM output is untrusted.  Resource bodies are persisted as Markdown text, so
structured model envelopes, mock responses, and audit payloads must never be
stored in ``LearningResource.content``.
"""
import json
import math
import re
from collections.abc import Mapping
from typing import Any, Iterable


class ResourceContentError(ValueError):
    """Raised when generated resource content is not safe Markdown text."""


def record_resource_quality_event(event: str, reason: str) -> None:
    """Record a quality guard event without making metrics a hard dependency."""
    try:
        from app.middleware.prometheus import resource_quality_events_total

        resource_quality_events_total.inc(event=event, reason=reason)
    except Exception:
        # Observability must never change validation or persistence behavior.
        pass


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

_SOURCE_KEYWORD_STOPWORDS = frozenset(
    {
        "这个",
        "过程",
        "内容",
        "方法",
        "通过",
        "用于",
        "进行",
        "以及",
        "一个",
        "主要",
        "核心",
        "步骤",
        "需要",
        "如果",
        "然后",
        "因为",
        "所以",
        "可以",
        "使用",
        "相关",
        "其中",
        "以及",
    }
)
_MARKDOWN_BOLD_RE = re.compile(r"\*\*([^*\n]{2,40})\*\*")
_CODE_SPAN_RE = re.compile(r"`([^`\n]{2,60})`")
_HEADING_RE = re.compile(r"^#{1,4}[ \t]+(.{2,60})$", re.MULTILINE)
_ENGLISH_TERM_RE = re.compile(r"[A-Za-z][A-Za-z0-9_+#.-]{1,}")
_CHINESE_RUN_RE = re.compile(r"[\u4e00-\u9fff]+")
# 覆盖判定按“生成内容逐字包含关键词”计分，关键词必须是完整术语而非句子碎片：
# 长滑窗片段（旧实现）几乎不可能在重组后的生成内容中逐字复现，会系统性低估覆盖率。
_EMPHASIS_TERM_MAX_CHARS = 12
_SHORT_TEXT_MAX_CHARS = 12
_NGRAM_SIZES = (4, 3)


def normalize_source_slice_ids(raw_ids: Any) -> list[int]:
    """Normalize persisted source-slice identifiers without losing valid IDs."""
    if isinstance(raw_ids, str):
        try:
            raw_ids = json.loads(raw_ids)
        except (TypeError, ValueError, json.JSONDecodeError):
            raw_ids = [raw_ids]
    if not isinstance(raw_ids, (list, tuple, set)):
        raw_ids = [raw_ids]

    normalized: list[int] = []
    seen: set[int] = set()
    for value in raw_ids:
        try:
            slice_id = int(value)
        except (TypeError, ValueError):
            continue
        if slice_id > 0 and slice_id not in seen:
            normalized.append(slice_id)
            seen.add(slice_id)
    return normalized


def _parse_source_keywords(raw_keywords: Any) -> list[str]:
    if isinstance(raw_keywords, str):
        try:
            parsed_keywords = json.loads(raw_keywords)
            raw_keywords = parsed_keywords if isinstance(parsed_keywords, list) else raw_keywords
        except (TypeError, ValueError, json.JSONDecodeError):
            raw_keywords = re.split(r"[,，、;；]", raw_keywords)
    if not isinstance(raw_keywords, (list, tuple, set)):
        return []
    keywords: list[str] = []
    seen: set[str] = set()
    for keyword in raw_keywords:
        normalized = str(keyword).strip()
        folded = normalized.casefold()
        if normalized and folded not in seen:
            keywords.append(normalized)
            seen.add(folded)
    return keywords


def _fallback_source_keywords(value: Any, maximum: int = 12) -> list[str]:
    """Extract term-like keywords when a slice has no metadata.

    优先级：markdown 强调结构（加粗/行内代码/标题）中的术语 → 英文技术词 →
    高频 3-4 字中文 n-gram。关键词必须是对齐到术语边界的完整词，而非任意
    滑窗碎片——后者在重组后的生成内容中几乎不会逐字出现。
    """
    text = str(value or "")
    candidates: list[str] = []
    seen: set[str] = set()

    def add(candidate: str) -> bool:
        candidate = candidate.strip()
        folded = candidate.casefold()
        if len(candidate) < 2 or folded in seen:
            return False
        if candidate in _SOURCE_KEYWORD_STOPWORDS:
            return False
        seen.add(folded)
        candidates.append(candidate)
        return True

    def add_span_terms(span: str) -> None:
        for token in _ENGLISH_TERM_RE.findall(span):
            add(token)
        for run in _CHINESE_RUN_RE.findall(span):
            if 2 <= len(run) <= _EMPHASIS_TERM_MAX_CHARS:
                add(run)

    # 1. 生成方自己强调的术语（加粗/代码/标题），天然对齐术语边界。
    for pattern in (_MARKDOWN_BOLD_RE, _CODE_SPAN_RE, _HEADING_RE):
        for span in pattern.findall(text):
            add_span_terms(span)
            if len(candidates) >= maximum:
                return candidates

    # 2. 英文技术词在再生成内容中通常原样保留。
    for token in _ENGLISH_TERM_RE.findall(text):
        if add(token) and len(candidates) >= maximum:
            return candidates

    # 3. 中文术语：短文本（典型为文档标题）术语密集，取“整体 + 前缀窗口”，
    # 去掉“基础/指南”类后缀的前缀仍能命中正文；长文本改用高频 3-4 字
    # n-gram——重复出现的短片段指向核心概念。跳过包含停用词的窗口与已选
    # 关键词的子串，按 (频次, 长度, 首现位置) 排序保证确定性。
    runs = _CHINESE_RUN_RE.findall(text)
    if sum(len(run) for run in runs) <= _SHORT_TEXT_MAX_CHARS:
        for run in runs:
            add(run)
            for size in range(len(run) - 1, 2, -1):
                add(run[:size])
        if candidates:
            return candidates[:maximum]

    positions: dict[str, int] = {}
    counts: dict[str, int] = {}
    for run in runs:
        for size in _NGRAM_SIZES:
            if len(run) < size:
                continue
            for start in range(len(run) - size + 1):
                phrase = run[start : start + size]
                if any(stopword in phrase for stopword in _SOURCE_KEYWORD_STOPWORDS):
                    continue
                if phrase not in positions:
                    positions[phrase] = len(positions)
                counts[phrase] = counts.get(phrase, 0) + 1
    ranked = sorted(counts, key=lambda p: (-counts[p], -len(p), positions[p]))
    for phrase in ranked:
        if any(phrase in picked for picked in candidates):
            continue
        if add(phrase) and len(candidates) >= maximum:
            break
    return candidates


_FALLBACK_DISCLOSURE_SENTENCE_RE = re.compile(
    r"[ \t]*(?:[-*•][ \t]*)?"
    r"参考知识库资料不足[，,、]?\s*以下为模型生成的通用学习建议[。：:；;]?"
)


def strip_fallback_disclosure(content: Any) -> str:
    """Remove insufficient-knowledge disclosure sentences from lecture content.

    生成 prompt 要求讲义正文声明“参考知识库资料不足，以下为模型生成的通用
    学习建议”。该声明面向学习者保留在资源原文中，但发布到知识库前必须剥离，
    避免运维话术被当作知识内容切片并进入覆盖率分母。声明不总是独立成行：
    实际数据中会并入首句、藏在行中或带列表前缀，故按句式精确匹配，只删除
    命中的句子本身，其余正文原样保留。
    """
    kept: list[str] = []
    for line in str(content or "").split("\n"):
        if _FALLBACK_DISCLOSURE_SENTENCE_RE.search(line):
            line = _FALLBACK_DISCLOSURE_SENTENCE_RE.sub("", line)
            if not line.strip():
                continue
        kept.append(line)
    return "\n".join(kept).lstrip()


def normalize_source_keywords(
    raw_keywords: Any,
    *,
    title: Any = None,
    content: Any = None,
    maximum: int = 12,
) -> list[str]:
    """Use explicit slice keywords, with title/content fallbacks for legacy rows."""
    keywords = _parse_source_keywords(raw_keywords)
    if keywords:
        return keywords[:maximum]
    keywords = _fallback_source_keywords(title, maximum=maximum)
    if keywords:
        return keywords
    return _fallback_source_keywords(content, maximum=maximum)


def build_source_references(knowledge: Iterable[Any] | None) -> list[dict[str, Any]]:
    """Build a deduplicated source snapshot used by prompts and persistence."""
    references: dict[int, dict[str, Any]] = {}
    for item in knowledge or []:
        if not isinstance(item, Mapping):
            continue
        slice_ids = normalize_source_slice_ids(item.get("slice_id"))
        if not slice_ids:
            continue
        slice_id = slice_ids[0]
        title = str(item.get("title") or item.get("doc_title") or "").strip()
        keywords = normalize_source_keywords(
            item.get("keywords"),
            title=title,
            content=item.get("content"),
        )
        reference = references.setdefault(
            slice_id,
            {
                "slice_id": slice_id,
                "doc_id": item.get("doc_id"),
                "title": title,
                "keywords": [],
            },
        )
        for keyword in keywords:
            if keyword.casefold() not in {existing.casefold() for existing in reference["keywords"]}:
                reference["keywords"].append(keyword)
        if not reference.get("title") and title:
            reference["title"] = title
        if reference.get("doc_id") is None and item.get("doc_id") is not None:
            reference["doc_id"] = item.get("doc_id")
    return list(references.values())


def calculate_source_coverage(
    content: Any,
    references: Iterable[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    """Measure whether generated text represents each referenced source slice."""
    normalized_content = str(content or "").casefold()
    source_refs = [item for item in references or [] if item.get("slice_id")]
    matched: list[int] = []
    missing: list[dict[str, Any]] = []
    for reference in source_refs:
        keywords = [
            str(keyword).strip()
            for keyword in (reference.get("keywords") or [])
            if str(keyword).strip()
        ]
        matched_keywords = [keyword for keyword in keywords if keyword.casefold() in normalized_content]
        slice_id = int(reference["slice_id"])
        if matched_keywords:
            matched.append(slice_id)
        else:
            missing.append({"slice_id": slice_id, "keywords": keywords})

    required = len(source_refs)
    covered = len(matched)
    return {
        "source_slice_ids": [int(item["slice_id"]) for item in source_refs],
        "matched_source_slice_ids": matched,
        "missing_sources": missing,
        "required_slice_count": required,
        "covered_slice_count": covered,
        "coverage_rate": round(covered / required * 100, 2) if required else None,
        "passed": covered == required if required else True,
    }


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


def validate_resource_title(raw_title: Any, *, record_event: bool = True) -> str:
    """Reject blank or placeholder titles before they reach persistence."""
    if not isinstance(raw_title, str):
        if record_event:
            record_resource_quality_event("title_rejected", "invalid_type")
        raise ResourceContentError("资源标题不能为空")
    title = raw_title.strip()
    if not title:
        if record_event:
            record_resource_quality_event("title_rejected", "blank")
        raise ResourceContentError("资源标题不能为空")
    if _PLACEHOLDER_TITLE.search(title):
        if record_event:
            record_resource_quality_event("title_rejected", "placeholder")
        raise ResourceContentError("资源标题包含无效占位符")
    return title


def validate_match_score(raw_score: Any) -> float | None:
    """Validate a persisted match score without inventing a missing value."""
    if raw_score is None:
        return None
    try:
        score = float(raw_score)
    except (TypeError, ValueError) as exc:
        record_resource_quality_event("match_score_rejected", "invalid_type")
        raise ResourceContentError("资源匹配度必须是数字") from exc
    if not math.isfinite(score) or not 0 <= score <= 100:
        record_resource_quality_event("match_score_rejected", "out_of_range")
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
