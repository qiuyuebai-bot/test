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


FORMULA_VERSION = "evidence-report-v1"
MATCH_SCORE_SOURCES = {"agent_generation_pipeline", "backfill_match_scores"}


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
        "knowledge_index_coverage",
        "generated_content_coverage",
    )
    metrics = MetricService.calculate_metrics(db, scope="global", metric_ids=metric_ids)
    by_id = {item["metric_id"]: item for item in metrics}

    resources = db.query(LearningResource).all()
    post_fix = [item for item in resources if _source(item) in MATCH_SCORE_SOURCES]
    legacy = [item for item in resources if _source(item) == "legacy"]
    expert_fixture = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "industrial_robotics_expert_annotations.json"
    expert_labels = 0
    if expert_fixture.exists():
        try:
            payload = json.loads(expert_fixture.read_text(encoding="utf-8"))
            expert_labels = len(payload.get("annotations", [])) if isinstance(payload, dict) else 0
        except (OSError, ValueError, json.JSONDecodeError):
            expert_labels = 0

    return {
        "report_version": FORMULA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_revision": _git_revision(),
        "working_tree_dirty": _git_worktree_dirty(),
        "model": {
            "provider": "configured_server_side_provider",
            "model_name": "redacted_in_report",
        },
        "knowledge_base": {
            "version": _knowledge_version(db),
            "slice_count": db.query(KnowledgeSlice).count(),
            "indexed_slice_count": db.query(KnowledgeSlice).filter(KnowledgeSlice.is_indexed == True).count(),
        },
        "target_thresholds": {
            "hallucination_rate_percent": {"operator": "<", "target": 5},
            "adaptation_accuracy_percent": {"operator": ">=", "target": 85},
            "generated_content_coverage_percent": {"operator": ">=", "target": 90},
        },
        "metrics": metrics,
        "evidence": {
            "hallucination": {
                "numerator": by_id.get("hallucination_rate", {}).get("numerator", 0),
                "denominator": by_id.get("hallucination_rate", {}).get("denominator", 0),
                "sample_count": by_id.get("hallucination_rate", {}).get("sample_count", 0),
                "status": by_id.get("hallucination_rate", {}).get("status", "no_data"),
            },
            "adaptation": {
                "resource_match_score": by_id.get("resource_match_score"),
                "resource_match_effectiveness": by_id.get("resource_match_effectiveness"),
                "resources_total": len(resources),
                "resources_post_fix": len(post_fix),
                "post_fix_nonzero_scores": sum(1 for item in post_fix if float(item.match_score or 0) > 0),
                "legacy_rows_excluded_from_post_fix_claim": len(legacy),
                "claim_status": "ready"
                if len(post_fix) >= 10
                and by_id.get("resource_match_score", {}).get("status") == "ready"
                else "insufficient_evidence",
                "minimum_post_fix_samples_for_competition_claim": 10,
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
