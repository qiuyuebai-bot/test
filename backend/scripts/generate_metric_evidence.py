"""Generate an auditable metrics evidence report without mutating the database.

The report intentionally separates legacy rows from rows written after the
match-score pipeline fix. Missing expert labels or insufficient samples are
reported as ``insufficient_evidence`` rather than inferred as a pass.
"""

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal  # noqa: E402
from app.models import KnowledgeSlice, LearningResource  # noqa: E402
from app.services.metric_service import MetricService  # noqa: E402


FORMULA_VERSION = "evidence-report-v2"
MATCH_SCORE_SOURCES = {"agent_generation_pipeline", "backfill_match_scores"}
FORMAL_MINIMUM_SAMPLE_SIZE = 10
FORMAL_TARGET_PERCENT = 85.0


def _claim(
    metric: Dict[str, Any] | None,
    *,
    target: float = FORMAL_TARGET_PERCENT,
    minimum_sample_size: int = FORMAL_MINIMUM_SAMPLE_SIZE,
    operator: str = ">=",
) -> Dict[str, Any]:
    """Turn a calculated metric into an explicit, auditable acceptance claim."""
    metric = metric or {}
    value = metric.get("value")
    denominator = metric.get("denominator", 0) or 0
    sample_count = metric.get("sample_count", denominator) or 0
    try:
        denominator = int(denominator)
    except (TypeError, ValueError):
        denominator = 0
    try:
        sample_count = int(sample_count)
    except (TypeError, ValueError):
        sample_count = 0

    if sample_count < minimum_sample_size:
        status = "insufficient_evidence"
        reason = (
            f"有效样本 {sample_count} 条，正式验收至少需要 "
            f"{minimum_sample_size} 条"
        )
    elif value is None:
        status = "insufficient_evidence"
        reason = "样本量达到门槛，但指标值不可用"
    else:
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            numeric_value = None
        if numeric_value is None:
            status = "insufficient_evidence"
            reason = "指标值不是有效数字"
        elif operator == ">=" and numeric_value >= target:
            status = "passed"
            reason = f"指标值 {numeric_value:.2f}% 达到目标 {target:.2f}%"
        else:
            status = "failed"
            reason = f"指标值 {numeric_value:.2f}% 未达到目标 {target:.2f}%"

    return {
        "metric_id": metric.get("metric_id"),
        "display_name": metric.get("display_name"),
        "value": value,
        "target": target,
        "operator": operator,
        "numerator": metric.get("numerator", 0),
        "denominator": denominator,
        "sample_count": sample_count,
        "minimum_sample_size": minimum_sample_size,
        "status": status,
        "reason": reason,
        "metric_status": metric.get("status"),
    }


def _aggregate_claim_status(claims: list[Dict[str, Any]]) -> str:
    """Return the strict overall status for a group of formal claims."""
    statuses = {claim["status"] for claim in claims}
    if "failed" in statuses:
        return "failed"
    if "insufficient_evidence" in statuses:
        return "insufficient_evidence"
    return "passed"


def _git_revision() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=BACKEND_DIR.parent,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _git_worktree_dirty() -> bool:
    try:
        return bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"],
                cwd=BACKEND_DIR.parent,
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        )
    except (OSError, subprocess.CalledProcessError):
        return True


def _content_json(resource: LearningResource) -> Dict[str, Any]:
    value = resource.content_json or {}
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
    return value if isinstance(value, dict) else {}


def _source(resource: LearningResource) -> str:
    return str(_content_json(resource).get("match_score_metadata", {}).get("source", "legacy"))


def _normalized_match_score(value: Any) -> float | None:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    return score * 100 if 0 <= score <= 1 else score


def _post_fix_match_score_metric(
    base_metric: Dict[str, Any] | None,
    resources: list[LearningResource],
) -> Dict[str, Any]:
    """Apply the canonical match-score formula to post-fix rows only."""
    scores = [
        score
        for score in (_normalized_match_score(item.match_score) for item in resources)
        if score is not None
    ]
    metric = dict(base_metric or {})
    denominator = len(scores)
    numerator = round(sum(scores), 2)
    metric.update(
        {
            "metric_id": "resource_match_score",
            "value": round(numerator / denominator, 2) if denominator else None,
            "numerator": numerator,
            "denominator": denominator,
            "sample_count": denominator,
            "status": "ready" if denominator else "no_data",
            "metadata": {
                "source_filter": sorted(MATCH_SCORE_SOURCES),
                "resources_evaluated": len(resources),
            },
        }
    )
    return metric


def _knowledge_version(db) -> str:
    rows = db.query(KnowledgeSlice.id, KnowledgeSlice.updated_at, KnowledgeSlice.is_indexed).order_by(
        KnowledgeSlice.id
    ).all()
    material = "|".join(f"{row[0]}:{row[1]}:{row[2]}" for row in rows)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def build_report(db) -> Dict[str, Any]:
    metric_ids = (
        "hallucination_rate",
        "resource_match_score",
        "resource_match_effectiveness",
        "answer_accuracy",
        "knowledge_index_coverage",
        "generated_content_coverage",
    )
    metrics = MetricService.calculate_metrics(db, scope="global", metric_ids=metric_ids)
    by_id = {item["metric_id"]: item for item in metrics}

    resources = db.query(LearningResource).all()
    post_fix = [item for item in resources if _source(item) in MATCH_SCORE_SOURCES]
    legacy = [item for item in resources if _source(item) == "legacy"]
    post_fix_score_metric = _post_fix_match_score_metric(
        by_id.get("resource_match_score"),
        post_fix,
    )
    expert_fixture = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "industrial_robotics_expert_annotations.json"
    expert_labels = 0
    if expert_fixture.exists():
        try:
            payload = json.loads(expert_fixture.read_text(encoding="utf-8"))
            expert_labels = len(payload.get("annotations", [])) if isinstance(payload, dict) else 0
        except (OSError, ValueError, json.JSONDecodeError):
            expert_labels = 0

    claims = {
        "resource_match_score": _claim(post_fix_score_metric),
        "resource_match_effectiveness": _claim(by_id.get("resource_match_effectiveness")),
        "answer_accuracy": _claim(by_id.get("answer_accuracy")),
    }
    adaptation_claim_status = _aggregate_claim_status([
        claims["resource_match_score"],
        claims["resource_match_effectiveness"],
    ])
    working_tree_dirty = _git_worktree_dirty()

    return {
        "report_version": FORMULA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_revision": _git_revision(),
        "working_tree_dirty": working_tree_dirty,
        "report_kind": "development_validation" if working_tree_dirty else "formal_acceptance",
        "acceptance_eligible": not working_tree_dirty,
        "model": {
            "provider": "configured_server_side_provider",
            "model_name": "redacted_in_report",
        },
        "knowledge_base": {
            "version": _knowledge_version(db),
            "slice_count": db.query(KnowledgeSlice).count(),
            "indexed_slice_count": db.query(KnowledgeSlice).filter(KnowledgeSlice.is_indexed == True).count(),
        },
        "formal_evidence_policy": {
            "minimum_sample_size": FORMAL_MINIMUM_SAMPLE_SIZE,
            "target_percent": FORMAL_TARGET_PERCENT,
            "status_values": ["passed", "failed", "insufficient_evidence"],
        },
        "target_thresholds": {
            "hallucination_rate_percent": {"operator": "<", "target": 5},
            "adaptation_accuracy_percent": {"operator": ">=", "target": 85},
            "resource_match_score_percent": {"operator": ">=", "target": FORMAL_TARGET_PERCENT},
            "resource_match_effectiveness_percent": {"operator": ">=", "target": FORMAL_TARGET_PERCENT},
            "answer_accuracy_percent": {"operator": ">=", "target": FORMAL_TARGET_PERCENT},
            "generated_content_coverage_percent": {"operator": ">=", "target": 90},
        },
        "metrics": metrics,
        "evidence": {
            "claims": claims,
            "formal_claim_status": _aggregate_claim_status(list(claims.values())),
            "hallucination": {
                "numerator": by_id.get("hallucination_rate", {}).get("numerator", 0),
                "denominator": by_id.get("hallucination_rate", {}).get("denominator", 0),
                "sample_count": by_id.get("hallucination_rate", {}).get("sample_count", 0),
                "status": by_id.get("hallucination_rate", {}).get("status", "no_data"),
            },
            "adaptation": {
                "resource_match_score": post_fix_score_metric,
                "resource_match_effectiveness": by_id.get("resource_match_effectiveness"),
                "resources_total": len(resources),
                "resources_post_fix": len(post_fix),
                "post_fix_nonzero_scores": sum(
                    1
                    for item in post_fix
                    if (score := _normalized_match_score(item.match_score)) is not None
                    and score > 0
                ),
                "legacy_rows_excluded_from_post_fix_claim": len(legacy),
                "claim_status": adaptation_claim_status,
                "minimum_post_fix_samples_for_competition_claim": FORMAL_MINIMUM_SAMPLE_SIZE,
                "claims": {
                    "resource_match_score": claims["resource_match_score"],
                    "resource_match_effectiveness": claims["resource_match_effectiveness"],
                },
            },
            "coverage": {
                "index_coverage": by_id.get("knowledge_index_coverage"),
                "generated_content_coverage": by_id.get("generated_content_coverage"),
                "index_and_content_are_reported_separately": True,
            },
            "expert_review": {
                "domain": "industrial_robotics",
                "annotation_count": expert_labels,
                "status": "ready" if expert_labels else "insufficient_evidence",
                "message": "需要行业专家标注后才能证明领域规范与岗位需求符合度。"
                if not expert_labels
                else None,
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="write JSON to this path instead of stdout")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        report = build_report(db)
    finally:
        db.close()

    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
