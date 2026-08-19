"""Grounded LLM debate adapter for the judge/generation cross-validation step."""
import json
from typing import Any, Dict, List

from app.services.ai_content_service import AIContentService
from app.utils.llm_response import bounded_list, bounded_text, parse_json_object


class LLMDebater:
    """Produce a defense and a final judge decision constrained to supplied sources."""

    @classmethod
    def run_judge_round(
        cls,
        generated_content: str,
        reference_knowledge: List[Dict[str, Any]],
        audit_result: Dict[str, Any],
        generation_response: Dict[str, Any],
        round_num: int,
    ) -> Dict[str, Any]:
        """Run the judge's independent turn after the generation turn."""
        response, _ = AIContentService.call_with_prompt_template(
            "judge_review",
            {
                "round_num": round_num,
                "generated_content": generated_content[:12000],
                "reference_knowledge": cls._reference_text(reference_knowledge),
                "rule_issues": json.dumps(audit_result.get("issues", [])[:12], ensure_ascii=False),
                "generation_response": json.dumps(generation_response or {}, ensure_ascii=False),
            },
            temperature=0.2,
            use_cache=False,
            allow_mock=False,
        )
        payload = parse_json_object(response)
        if payload.get("_meta", {}).get("model") == "mock":
            raise ValueError("LLM returned fallback mock response")
        decision = payload.get("decision")
        if decision not in {"approved", "needs_revision", "rejected"}:
            raise ValueError("invalid LLM judge decision")
        issues = []
        for item in bounded_list(payload.get("issues", []), "issues", maximum=12):
            if not isinstance(item, dict):
                continue
            severity = item.get("severity", "medium")
            if severity not in {"high", "medium", "low"}:
                severity = "medium"
            issues.append({
                "type": bounded_text(item.get("type", "grounding"), "issue_type", maximum=80),
                "severity": severity,
                "description": bounded_text(item.get("description", "需根据证据复核"), "issue_description", maximum=1000),
                "suggested_fix": bounded_text(item.get("suggested_fix", "请根据参考资料修正"), "suggested_fix", maximum=1000),
            })
        rebuttal = payload.get("rebuttal") or "裁判已根据规则和参考资料完成独立复核。"
        return {
            "judge_rebuttal": bounded_text(rebuttal, "rebuttal", maximum=3000),
            "final_decision": decision,
            "issues": issues,
            "confidence": max(0.0, min(1.0, float(payload.get("confidence", 0.5)))),
            "method": "llm",
        }

    @classmethod
    def run_debate_round(
        cls, generated_content: str, reference_knowledge: List[Dict[str, Any]], audit_result: Dict[str, Any], round_num: int
    ) -> Dict[str, Any]:
        """Backward-compatible wrapper that no longer invents a defense."""
        judge_result = cls.run_judge_round(
            generated_content,
            reference_knowledge,
            audit_result,
            {
                "available": False,
                "status": "unavailable",
                "stance": "unavailable",
                "response": "生成Agent回应必须由GenerationAgent独立提供。",
                "requires_human_review": True,
            },
            round_num,
        )
        return {
            "generation_counterargument": {
                "available": False,
                "status": "unavailable",
                "stance": "unavailable",
                "accepts": None,
                "response": "生成Agent回应必须由GenerationAgent独立提供。",
                "revisions_made": 0,
                "requires_human_review": True,
            },
            **judge_result,
        }

    @staticmethod
    def _reference_text(knowledge: List[Dict[str, Any]]) -> str:
        return "\n\n".join(
            f"[{item.get('slice_id', 'unknown')}] {item.get('title', '知识片段')}: {str(item.get('content', ''))[:2200]}"
            for item in knowledge[:6]
            if item.get("content")
        ) or "无可用参考资料"
