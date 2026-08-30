"""Read-only review queue export tests."""

from scripts.export_hallucination_review_queue import build_review_queue
from tests.test_hallucination_metrics import _add_record


def test_review_queue_contains_confirmed_rows_and_required_sample_count(
    db_session, sample_agent_task
):
    for index in range(53):
        _add_record(
            db_session,
            sample_agent_task.id,
            is_hallucination=index < 3,
            resolution_status="resolved",
            judge_decision="rejected" if index < 3 else "approved",
            conflict_points=(
                [{"type": "hallucination_evidence"}] if index < 3 else []
            ),
        )
    db_session.commit()

    queue = build_review_queue(db_session)

    assert len(queue["records"]["reviewed_hallucination"]) == 3
    assert queue["required_additional_reviews"] == 8
    assert queue["policy_version"] == "hallucination-rate-v1"


def test_review_queue_limit_only_caps_serialized_rows(db_session, sample_agent_task):
    for index in range(3):
        _add_record(
            db_session,
            sample_agent_task.id,
            is_hallucination=index == 0,
            resolution_status="resolved",
            judge_decision="rejected" if index == 0 else "approved",
            conflict_points=(
                [{"type": "hallucination_evidence"}] if index == 0 else []
            ),
        )
    db_session.commit()

    queue = build_review_queue(db_session, limit=1)

    serialized_count = sum(len(items) for items in queue["records"].values())
    assert serialized_count == 1
    assert queue["total_records"] == 3
    assert queue["evaluated_checks"] == 3

