"""Validated LLM-assisted learning-path planning."""
import json
from typing import Any, Dict, List

from app.utils.llm import LLMUtil
from app.utils.llm_response import bounded_int, bounded_list, bounded_text, parse_json_object


class PathPlanner:
    """Plan a small acyclic learner path, with explicit validation."""

    @classmethod
    def plan_path(cls, learner: Any, blind_areas: List[str], resources: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not LLMUtil.is_available():
            raise RuntimeError("LLM is unavailable")
        context = {
            "target_industry": getattr(learner, "target_industry", None),
            "target_position": getattr(learner, "target_position", None),
            "blind_areas": blind_areas[:5],
            "resources": resources[:12],
        }
        response, _ = LLMUtil.call_with_prompt_template(
            "path_planning", {"learner_context": json.dumps(context, ensure_ascii=False)}, temperature=0.3
        )
        payload = parse_json_object(response)
        if payload.get("_meta", {}).get("model") == "mock":
            raise ValueError("LLM returned fallback mock response")
        return cls._validate(payload, resources)

    @classmethod
    def suggest_next_step(cls, path: Dict[str, Any]) -> Dict[str, Any] | None:
        return next((node for node in path.get("nodes", []) if node.get("status") == "current"), None)

    @classmethod
    def _validate(cls, payload: Dict[str, Any], resources: List[Dict[str, Any]]) -> Dict[str, Any]:
        resource_ids = {item.get("resource_id") for item in resources}
        # A one-node plan is valid for a narrow topic with one available resource.
        raw_nodes = bounded_list(payload.get("nodes"), "nodes", minimum=1, maximum=8)
        nodes = []
        current_count = 0
        for index, item in enumerate(raw_nodes, 1):
            if not isinstance(item, dict):
                raise ValueError("path node must be an object")
            status = item.get("status", "locked")
            if status not in {"completed", "current", "locked"}:
                status = "locked"
            current_count += status == "current"
            node_resources = [resource for resource in item.get("resources", []) if isinstance(resource, dict) and resource.get("resource_id") in resource_ids]
            nodes.append({
                "id": f"step-{index}",
                "name": bounded_text(item.get("name"), "node name", maximum=120),
                "difficulty": bounded_int(item.get("difficulty", 3), "difficulty", minimum=1, maximum=5),
                "status": status,
                "estimated_time": bounded_text(item.get("estimated_time", "2小时"), "estimated_time", maximum=40),
                "resources": node_resources,
                "description": bounded_text(item.get("description"), "description", maximum=800),
            })
        if current_count != 1:
            for node in nodes:
                if node["status"] == "current":
                    node["status"] = "locked"
            next((node for node in nodes if node["status"] != "completed"), nodes[0])["status"] = "current"
        current_step = next(index for index, node in enumerate(nodes, 1) if node["status"] == "current")
        completed = sum(node["status"] == "completed" for node in nodes)
        return {
            "total_steps": len(nodes),
            "current_step": current_step,
            "progress": round(completed / len(nodes) * 100, 1),
            "estimated_total_time": f"{sum(cls._hours(node['estimated_time']) for node in nodes)}小时",
            "nodes": nodes,
            "edges": [{"source": nodes[index]["id"], "target": nodes[index + 1]["id"]} for index in range(len(nodes) - 1)],
        }

    @staticmethod
    def _hours(value: str) -> int:
        digits = "".join(char for char in value if char.isdigit())
        return max(1, int(digits or 1))
