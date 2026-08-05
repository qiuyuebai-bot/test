"""Optional LLM enrichment for deterministic learner diagnoses."""
import json
from typing import Any, Dict

from app.services.ai_content_service import AIContentService
from app.utils.llm_response import bounded_list, bounded_text, parse_json_object


class LLMDiagnostician:
    """Enrich diagnosis narratives without changing rule-derived scores."""

    @classmethod
    def enhance_result(cls, result: Dict[str, Any]) -> Dict[str, Any]:
        response, _ = AIContentService.call_with_prompt_template(
            "learner_diagnosis",
            {
                "ability_summary": json.dumps(result.get("ability_levels", {}), ensure_ascii=False),
                "blind_areas": json.dumps(result.get("knowledge_blind_areas", []), ensure_ascii=False),
                "average_score": result.get("overall_score", 0),
            },
            temperature=0.3,
        )
        payload = parse_json_object(response)
        if payload.get("_meta", {}).get("model") == "mock":
            raise ValueError("LLM returned fallback mock response")
        suggestions = [
            bounded_text(item, "learning_suggestion", maximum=500)
            for item in bounded_list(payload.get("learning_suggestions", []), "learning_suggestions", maximum=8)
        ]
        descriptions = {}
        for item in bounded_list(payload.get("knowledge_blind_areas", []), "knowledge_blind_areas", maximum=12):
            if isinstance(item, dict) and isinstance(item.get("name"), str) and isinstance(item.get("description"), str):
                descriptions[item["name"]] = bounded_text(item["description"], "blind_area_description", maximum=800)

        enhanced = dict(result)
        enhanced["recommendations"] = suggestions or result.get("recommendations", [])
        enhanced["knowledge_blind_areas"] = [
            {**area, **({"description": descriptions[area.get("name")]} if area.get("name") in descriptions else {})}
            for area in result.get("knowledge_blind_areas", [])
        ]
        enhanced["diagnosis_method"] = "llm_enhanced"
        return enhanced
