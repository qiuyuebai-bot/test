"""Validated LLM-assisted learning-path planning."""
import json
from typing import Any, Dict, List

from app.services.ai_content_service import AIContentService
from app.utils.llm import LLMUtil
from app.utils.llm_response import bounded_int, bounded_list, bounded_text, parse_json_object


class PathPlanner:
    """Plan a small acyclic learner path, with explicit validation."""

    @classmethod
    def plan_path(cls, learner: Any, blind_areas: List[str], resources: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not LLMUtil.is_available():
            raise RuntimeError("LLM is unavailable")
        context = {
            "ability_scores": {
                key: getattr(learner, key, 0) or 0
                for key in ("theoretical_foundation", "programming_ability", "algorithm_design", "system_architecture", "data_analysis", "engineering_practice")
            },
            "target_industry": getattr(learner, "target_industry", None),
            "target_position": getattr(learner, "target_position", None),
            "blind_areas": blind_areas[:5],
            "resources": resources[:12],
        }
        response, _ = AIContentService.call_with_prompt_template(
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
        name_to_id = {}
        pending_dependencies = {}
        for index, item in enumerate(raw_nodes, 1):
            if not isinstance(item, dict):
                raise ValueError("path node must be an object")
            node_name = bounded_text(item.get("name"), "node name", maximum=120)
            node_id = f"step-{index}"
            node_resources = [resource for resource in item.get("resources", []) if isinstance(resource, dict) and resource.get("resource_id") in resource_ids]
            nodes.append({
                "id": node_id,
                "name": node_name,
                "difficulty": bounded_int(item.get("difficulty", 3), "difficulty", minimum=1, maximum=5),
                "status": "locked",
                "estimated_time": bounded_text(item.get("estimated_time", "2小时"), "estimated_time", maximum=40),
                "resources": node_resources,
                "description": bounded_text(item.get("description"), "description", maximum=800),
            })
            name_to_id[node_name] = node_id
            pending_dependencies[node_id] = item.get("depends_on", [])

        edges = []
        for node in nodes:
            for dependency_name in pending_dependencies[node["id"]]:
                dependency_id = name_to_id.get(str(dependency_name))
                if dependency_id and dependency_id != node["id"]:
                    edges.append({"source": dependency_id, "target": node["id"]})
        if not edges:
            edges = [{"source": nodes[index]["id"], "target": nodes[index + 1]["id"]} for index in range(len(nodes) - 1)]
        if not cls._is_acyclic(nodes, edges):
            raise ValueError("learning path dependencies contain a cycle")

        dependent_ids = {edge["target"] for edge in edges}
        current_node = next((node for node in nodes if node["id"] not in dependent_ids), nodes[0])
        current_node["status"] = "current"
        current_step = nodes.index(current_node) + 1
        completed = 0
        return {
            "total_steps": len(nodes),
            "current_step": current_step,
            "progress": round(completed / len(nodes) * 100, 1),
            "estimated_total_time": f"{sum(cls._hours(node['estimated_time']) for node in nodes)}小时",
            "nodes": nodes,
            "edges": edges,
        }

    @staticmethod
    def _is_acyclic(nodes: List[Dict[str, Any]], edges: List[Dict[str, str]]) -> bool:
        adjacency = {node["id"]: [] for node in nodes}
        for edge in edges:
            adjacency[edge["source"]].append(edge["target"])
        visiting, visited = set(), set()

        def visit(node_id: str) -> bool:
            if node_id in visiting:
                return False
            if node_id in visited:
                return True
            visiting.add(node_id)
            if not all(visit(target) for target in adjacency[node_id]):
                return False
            visiting.remove(node_id)
            visited.add(node_id)
            return True

        return all(visit(node["id"]) for node in nodes)

    @staticmethod
    def _hours(value: str) -> int:
        digits = "".join(char for char in value if char.isdigit())
        return max(1, int(digits or 1))
