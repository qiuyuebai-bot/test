"""Unified server-side AI content gateway.

All outbound model calls remain behind ``LLMUtil`` so business services do not
need to know which OpenAI-compatible provider is configured.
"""
import json
from typing import Any, Dict, Optional

from app.utils.llm import LLMUtil
from app.utils.llm_response import bounded_list, bounded_text, parse_json_object


class AIContentError(ValueError):
    """Raised when a generated content contract cannot be satisfied."""


class AIContentService:
    """Generate validated content through the configured provider."""

    @classmethod
    def call_with_prompt_template(
        cls,
        template_name: str,
        variables: Optional[Dict[str, Any]] = None,
        *,
        temperature: Optional[float] = None,
        model: Optional[str] = None,
        use_cache: bool = True,
    ):
        """Single outbound prompt entry point used by content generators."""
        return LLMUtil.call_with_prompt_template(
            template_name,
            variables,
            temperature=temperature,
            model=model,
            use_cache=use_cache,
        )

    @classmethod
    def sync_call(cls, **kwargs: Any):
        """Single outbound raw-completion entry point for legacy adapters."""
        return LLMUtil.sync_call(**kwargs)

    @classmethod
    def generate(cls, content_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Generate one supported content type and validate its response."""
        if content_type == "tutoring_feedback":
            return cls._generate_tutoring_feedback(payload)
        raise AIContentError(f"unsupported AI content type: {content_type}")

    @classmethod
    def _generate_tutoring_feedback(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not LLMUtil.is_available():
            raise AIContentError("LLM is unavailable")

        response, _ = cls.call_with_prompt_template(
            "tutoring_feedback",
            {
                "decision": payload.get("decision", "review"),
                "knowledge_topic": str(payload.get("topic", "")).strip(),
                "question": str(payload.get("question", "")).strip()[:2000],
                "user_answer": str(payload.get("user_answer", "")).strip()[:500],
                "correct_answer": str(payload.get("correct_answer", "")).strip()[:200],
                "difficulty": payload.get("difficulty", 3),
                "learning_style": payload.get("learning_style", "visual"),
                "learner_summary": json.dumps(
                    payload.get("learner_summary", {}), ensure_ascii=False
                )[:3000],
                "reference_knowledge": payload.get("reference_knowledge") or "无可用参考资料",
            },
            temperature=0.4,
            use_cache=False,
        )
        result = parse_json_object(response)
        if result.get("_meta", {}).get("model") == "mock":
            raise AIContentError("LLM returned fallback mock response")

        title = bounded_text(result.get("title"), "title", maximum=200)
        explanation = bounded_text(
            result.get("simple_explanation"), "simple_explanation", maximum=3000
        )
        key_points = [
            bounded_text(item, "key_point", maximum=160)
            for item in bounded_list(result.get("key_points", []), "key_points", maximum=8)
        ]
        practice_tips = bounded_text(
            result.get("practice_tips"), "practice_tips", maximum=1200
        )
        recommendation = bounded_text(
            result.get("recommendation"), "recommendation", maximum=1200
        )
        challenge_description = str(result.get("challenge_description") or "").strip()[:2000]
        challenge_objectives = [
            bounded_text(item, "challenge_objective", maximum=300)
            for item in bounded_list(
                result.get("challenge_objectives", []),
                "challenge_objectives",
                maximum=8,
            )
        ]
        generated_type = result.get("type", payload.get("decision", "review"))
        if generated_type not in {"simplify", "advance", "consolidate", "review"}:
            generated_type = payload.get("decision", "review")

        return {
            "type": generated_type,
            "title": title,
            "simple_explanation": explanation,
            "key_points": key_points,
            "practice_tips": practice_tips,
            "recommendation": recommendation,
            "challenge_description": challenge_description,
            "challenge_objectives": challenge_objectives,
            "knowledge_source": "deepseek",
            "generation_method": "deepseek",
        }
