"""Canonical metric definitions used by every metric consumer."""

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class MetricDefinition:
    metric_id: str
    display_name: str
    unit: str
    formula: str
    source: Tuple[str, ...]
    scopes: Tuple[str, ...] = ("global", "learner")
    minimum_sample_size: int = 0
    # Snapshots older than one day are stale. Real-time calculations omit the
    # ``now`` policy input, so they remain ready while they are being served.
    freshness_seconds: int | None = 86400


METRIC_REGISTRY: Dict[str, MetricDefinition] = {
    "resource_match_score": MetricDefinition(
        metric_id="resource_match_score",
        display_name="\u8d44\u6e90\u5339\u914d\u5206",
        unit="%",
        formula="average generation-time match score across generated resources",
        source=("learning_resources.match_score",),
        minimum_sample_size=1,
    ),
    "resource_match_effectiveness": MetricDefinition(
        metric_id="resource_match_effectiveness",
        display_name="\u8d44\u6e90\u5339\u914d\u6548\u679c",
        unit="%",
        formula="correct answers after a resource recommendation / completed answers linked to a resource",
        source=("answer_records.result", "answer_records.next_resource_id"),
        minimum_sample_size=3,
    ),
    "knowledge_index_coverage": MetricDefinition(
        metric_id="knowledge_index_coverage",
        display_name="\u77e5\u8bc6\u7d22\u5f15\u8986\u76d6\u7387",
        unit="%",
        formula="indexed knowledge slices / total knowledge slices",
        source=("knowledge_slices.is_indexed",),
        minimum_sample_size=1,
    ),
    "blind_spot_resource_coverage": MetricDefinition(
        metric_id="blind_spot_resource_coverage",
        display_name="\u76f2\u533a\u8d44\u6e90\u8986\u76d6\u7387",
        unit="%",
        formula="blind spots covered by at least one resource / identified blind spots",
        source=("learner_profiles.knowledge_blind_areas", "learning_resources.content"),
        minimum_sample_size=1,
    ),
    "answer_accuracy": MetricDefinition(
        metric_id="answer_accuracy",
        display_name="\u7b54\u9898\u6b63\u786e\u7387",
        unit="%",
        formula="correct answers / completed answers",
        source=("answer_records.result",),
        minimum_sample_size=1,
    ),
    "hallucination_rate": MetricDefinition(
        metric_id="hallucination_rate",
        display_name="\u5e7b\u89c9\u7387",
        unit="%",
        formula="confirmed hallucination reviews / completed evidence reviews",
        source=("debate_records.is_hallucination", "debate_records.resolution_status"),
        minimum_sample_size=5,
    ),
}


def normalize_scope(scope: str | None) -> str:
    """Keep the API terminology stable while accepting the legacy ``system`` scope."""
    return "global" if scope in (None, "system") else scope


def get_metric_definition(metric_id: str) -> MetricDefinition:
    try:
        return METRIC_REGISTRY[metric_id]
    except KeyError as exc:
        raise KeyError(f"Unknown metric: {metric_id}") from exc


def serialize_metric_definitions() -> list[dict]:
    return [
        {
            "metric_id": definition.metric_id,
            "display_name": definition.display_name,
            "unit": definition.unit,
            "formula": definition.formula,
            "source": list(definition.source),
            "scopes": list(definition.scopes),
            "minimum_sample_size": definition.minimum_sample_size,
            "freshness_seconds": definition.freshness_seconds,
        }
        for definition in METRIC_REGISTRY.values()
    ]
