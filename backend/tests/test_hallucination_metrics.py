"""Knowledge-grounded hallucination metric regression tests."""

import json
from datetime import datetime

from app.models import DebateRecord, TestMetrics
from app.utils.metrics import MetricsUtil


def _add_record(
    db_session,
    task_id: int,
    *,
    is_hallucination: bool,
    resolution_status: str = "unresolved",
    judge_decision: str = "needs_revision",
    conflict_points=None,
):
    record = DebateRecord(
        task_id=task_id,
        debate_round=1,
        original_content="generated answer",
        is_hallucination=is_hallucination,
        resolution_status=resolution_status,
        judge_decision=judge_decision,
        conflict_description=json.dumps(conflict_points or [], ensure_ascii=False),
    )
    db_session.add(record)
    db_session.flush()
    return record


def test_unresolved_evidence_gaps_are_pending_not_hallucinations(
    db_session, sample_agent_task
):
    for _ in range(3):
        _add_record(
            db_session,
            sample_agent_task.id,
            is_hallucination=True,
            conflict_points=[{"type": "knowledge_gap", "severity": "medium"}],
        )

    metrics = MetricsUtil.calculate_hallucination_metrics(db_session)

    assert metrics["total_checks"] == 3
    assert metrics["evaluated_checks"] == 0
    assert metrics["pending_checks"] == 3
    assert metrics["confirmed_hallucinations"] == 0
    assert metrics["evidence_gaps"] == 3
    assert metrics["hallucination_rate"] is None
    assert metrics["has_sufficient_sample"] is False


def test_resolved_records_produce_rate_only_after_minimum_sample(
    db_session, sample_agent_task
):
    for index in range(6):
        _add_record(
            db_session,
            sample_agent_task.id,
            is_hallucination=index < 2,
            resolution_status="resolved",
            judge_decision="rejected" if index < 2 else "approved",
            conflict_points=(
                [{"type": "hallucination_evidence", "severity": "high"}]
                if index < 2
                else []
            ),
        )

    metrics = MetricsUtil.calculate_hallucination_metrics(db_session)

    assert metrics["total_checks"] == 6
    assert metrics["evaluated_checks"] == 6
    assert metrics["pending_checks"] == 0
    assert metrics["confirmed_hallucinations"] == 2
    assert metrics["evidence_gaps"] == 0
    assert metrics["hallucination_rate"] == 33.33
    assert metrics["has_sufficient_sample"] is True


def test_hallucination_endpoint_exposes_pending_and_evidence_counts(
    client, auth_headers, sample_agent_task, db_session
):
    _add_record(
        db_session,
        sample_agent_task.id,
        is_hallucination=True,
        conflict_points=[{"type": "no_reference", "severity": "medium"}],
    )
    response = client.get(
        "/api/v1/agent/metrics/hallucination", headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total_checks"] == 1
    assert data["evaluated_checks"] == 0
    assert data["pending_checks"] == 1
    assert data["evidence_gaps"] == 1
    assert data["hallucination_rate"] is None
    assert data["has_sufficient_sample"] is False


def test_report_metrics_uses_the_same_evidence_aware_source(
    client, sample_agent_task, db_session
):
    _add_record(
        db_session,
        sample_agent_task.id,
        is_hallucination=True,
        conflict_points=[{"type": "knowledge_gap", "severity": "medium"}],
    )

    response = client.get("/api/v1/report/metrics")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["pending_checks"] == 1
    assert data["evidence_gaps"] == 1
    assert data["hallucination_rate"] is None
    assert data["has_sufficient_sample"] is False


def test_report_metrics_uses_live_index_coverage_and_flat_trends(
    client, db_session, sample_knowledge_doc, sample_knowledge_slices
):
    db_session.add(TestMetrics(
        record_date=datetime(2024, 1, 15),
        record_period="daily",
        hallucination_rate=2.5,
        resource_match_accuracy=94.0,
        knowledge_coverage_rate=96.0,
        detailed_metrics={"knowledge_index_coverage_rate": 88.0},
    ))
    db_session.commit()

    response = client.get("/api/v1/report/metrics")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["knowledge_coverage_rate"] == 100.0
    assert data["knowledge_index_coverage_rate"] == 100.0
    assert data["metrics_source"] == "realtime"
    assert data["metrics_status"] == "ready"
    assert data["snapshot_available"] is True
    assert data["trends"][0]["knowledge_coverage_rate"] == 88.0
    assert "metrics" not in data["trends"][0]


def test_report_metrics_marks_missing_knowledge_data_as_no_data(client):
    response = client.get("/api/v1/report/metrics")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["knowledge_coverage_rate"] is None
    assert data["metrics_status"] == "no_data"
