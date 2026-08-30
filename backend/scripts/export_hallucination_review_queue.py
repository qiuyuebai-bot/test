"""Export a read-only, state-grouped hallucination review queue."""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal  # noqa: E402
from app.models import DebateRecord  # noqa: E402
from app.utils.metrics import MetricsUtil  # noqa: E402
from scripts.generate_metric_evidence import _required_additional_reviews  # noqa: E402


def _json_value(value: Any, default: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return default
        return parsed
    return default


def _citations(judge_view: Dict[str, Any]) -> list[Any]:
    citations = judge_view.get("citations", [])
    if isinstance(citations, list) and citations:
        return citations
    collected = []
    for issue in judge_view.get("issues", []):
        if not isinstance(issue, dict):
            continue
        details = issue.get("details", {})
        values = details.get("citations", []) if isinstance(details, dict) else []
        if isinstance(values, list):
            collected.extend(values)
    return collected


def _serialize_record(record: DebateRecord, state: str) -> Dict[str, Any]:
    original_content = record.original_content or ""
    judge_view = _json_value(record.agent_judge_view, {})
    if not isinstance(judge_view, dict):
        judge_view = {}
    return {
        "id": record.id,
        "task_id": record.task_id,
        "state": state,
        "original_content_sha256": hashlib.sha256(
            original_content.encode("utf-8")
        ).hexdigest(),
        "original_content": original_content,
        "reference_content": record.reference_content or "",
        "citations": _citations(judge_view),
        "conflict_type": record.conflict_type,
        "is_hallucination": bool(record.is_hallucination),
        "resolution_status": record.resolution_status,
        "judge_decision": record.judge_decision,
    }


def build_review_queue(db, limit: int | None = None) -> dict:
    """Read and group every debate record without mutating the database."""
    if limit is not None and (not isinstance(limit, int) or limit < 0):
        raise ValueError("limit must be a non-negative integer or None")

    records = db.query(DebateRecord).order_by(
        DebateRecord.created_at.asc(), DebateRecord.id.asc()
    ).all()
    grouped = {state: [] for state in MetricsUtil.HALLUCINATION_STATES}
    serialized_count = 0
    for record in records:
        state = MetricsUtil.classify_debate_record(record)
        if limit is not None and serialized_count >= limit:
            break
        grouped[state].append(_serialize_record(record, state))
        serialized_count += 1

    # The queue limit only caps serialized rows; metric facts always use all rows.
    all_metrics = MetricsUtil.calculate_hallucination_metrics(db)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy_version": MetricsUtil.HALLUCINATION_POLICY_VERSION,
        "records": grouped,
        "total_records": len(records),
        "evaluated_checks": all_metrics["evaluated_checks"],
        "confirmed_hallucinations": all_metrics["confirmed_hallucinations"],
        "required_additional_reviews": _required_additional_reviews(
            all_metrics["confirmed_hallucinations"],
            all_metrics["evaluated_checks"],
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="write JSON to this path")
    parser.add_argument("--limit", type=int, default=None, help="cap serialized records")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        queue = build_review_queue(db, limit=args.limit)
    finally:
        db.close()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(queue, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
