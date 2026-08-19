"""Knowledge retrieval agent used by the generation pipeline."""

import time
from typing import Any, Dict, List

from loguru import logger

from app.agents.base import BaseAgent
from app import database
from app.domains.knowledge.service import KnowledgeService


class KnowledgeAgent(BaseAgent):
    """Own retrieval execution and expose its evidence quality metadata."""

    def __init__(self):
        super().__init__(
            agent_type="knowledge",
            agent_name="知识检索Agent",
        )

    def execute(self, input_data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        query = str(input_data.get("query", "")).strip()
        if not query:
            raise ValueError("知识检索缺少查询主题")

        started_at = time.perf_counter()
        with database.get_db_context() as db:
            results = KnowledgeService.search(
                db=db,
                query=query,
                industry=input_data.get("industry"),
                top_k=max(1, min(int(input_data.get("top_k", 8)), 50)),
                doc_id=input_data.get("doc_id"),
            )

        duration_ms = round((time.perf_counter() - started_at) * 1000, 1)
        similarities = [
            float(item.get("similarity", 0) or 0)
            for item in results
            if isinstance(item, dict)
        ]
        max_similarity = max(similarities, default=0.0)
        if not results:
            evidence_status = "no_results"
        elif max_similarity < 0.6:
            evidence_status = "low_relevance"
        else:
            evidence_status = "sufficient"

        logger.info(
            f"[知识检索Agent] query={query[:50]}, results={len(results)}, "
            f"max_similarity={max_similarity:.3f}, duration={duration_ms}ms"
        )
        return {
            "query": query,
            "results": results,
            "knowledge_results": results,
            "result_count": len(results),
            "max_similarity": round(max_similarity, 4),
            "evidence_status": evidence_status,
            "low_relevance": evidence_status == "low_relevance",
            "duration_ms": duration_ms,
            "search_method": "knowledge_service",
        }
