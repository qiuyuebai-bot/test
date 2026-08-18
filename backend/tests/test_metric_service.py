"""Regression tests for the canonical metric contract."""

from datetime import timedelta

from app.models import DebateRecord
from app.services.metric_service import MetricService
from app.utils.datetime import utcnow_naive


def _by_id(results):
    return {result["metric_id"]: result for result in results}


def test_empty_database_reports_no_data_instead_of_zero(db_session):
    metrics = _by_id(MetricService.calculate_metrics(db_session, scope="global"))

    assert metrics["resource_match_score"]["value"] is None
    assert metrics["resource_match_score"]["status"] == "no_data"
    assert metrics["knowledge_index_coverage"]["value"] is None
    assert metrics["knowledge_index_coverage"]["status"] == "no_data"
    assert metrics["answer_accuracy"]["value"] is None
    assert metrics["answer_accuracy"]["status"] == "no_data"
    assert metrics["generated_content_coverage"]["value"] is None
    assert metrics["generated_content_coverage"]["status"] == "no_data"


def test_zero_is_a_ready_metric_value(db_session, sample_learning_resource):
    sample_learning_resource.match_score = 0
    db_session.commit()

    result = _by_id(
        MetricService.calculate_metrics(db_session, scope="learner", scope_id=sample_learning_resource.learner_id)
    )["resource_match_score"]

    assert result["value"] == 0
    assert result["status"] == "ready"
    assert result["numerator"] == 0
    assert result["denominator"] == 1


def test_snapshot_policy_marks_old_results_stale(db_session, sample_learning_resource):
    calculated_at = utcnow_naive() - timedelta(days=2)
    result = _by_id(
        MetricService.calculate_metrics(
            db_session,
            scope="global",
            calculated_at=calculated_at,
            now=utcnow_naive(),
            metric_ids=["resource_match_score"],
        )
    )["resource_match_score"]
    assert result["value"] is None
    assert result["status"] == "stale"


def test_blind_spot_policy_distinguishes_not_applicable_and_collecting(
    db_session, sample_learner_profile
):
    sample_learner_profile.knowledge_blind_areas = []
    db_session.commit()
    not_applicable = _by_id(
        MetricService.calculate_metrics(db_session, scope="learner", scope_id=sample_learner_profile.id)
    )["blind_spot_resource_coverage"]
    assert not_applicable["value"] is None
    assert not_applicable["status"] == "not_applicable"

    sample_learner_profile.knowledge_blind_areas = ["API"]
    db_session.commit()
    collecting = _by_id(
        MetricService.calculate_metrics(db_session, scope="learner", scope_id=sample_learner_profile.id)
    )["blind_spot_resource_coverage"]
    assert collecting["value"] is None
    assert collecting["status"] == "collecting"
    assert collecting["numerator"] == 0
    assert collecting["denominator"] == 1


def test_hallucination_rate_waits_for_five_reviewed_records(
    db_session, sample_agent_task
):
    for index in range(4):
        db_session.add(
            DebateRecord(
                task_id=sample_agent_task.id,
                debate_round=index + 1,
                original_content="content",
                is_hallucination=index == 0,
                resolution_status="resolved",
                judge_decision="rejected" if index == 0 else "approved",
                conflict_description="[]",
            )
        )
    db_session.commit()
    result = _by_id(MetricService.calculate_metrics(db_session, scope="global"))["hallucination_rate"]

    assert result["value"] is None
    assert result["status"] == "collecting"
    assert result["sample_count"] == 4
    assert result["minimum_sample_size"] == 5


def test_metrics_api_exposes_registry_and_standard_results(client):
    response = client.get("/api/v1/report/metrics")
    assert response.status_code == 200
    data = response.json()["data"]
    assert {metric["metric_id"] for metric in data["metrics"]} == {
        "resource_match_score",
        "resource_match_effectiveness",
        "knowledge_index_coverage",
        "generated_content_coverage",
        "blind_spot_resource_coverage",
        "answer_accuracy",
        "hallucination_rate",
    }
    assert data["metrics"][0]["status"] in {
        "ready",
        "collecting",
        "no_data",
        "not_applicable",
        "stale",
        "error",
    }
    definitions = client.get("/api/v1/report/metrics/definitions")
    assert definitions.status_code == 200
    assert len(definitions.json()["data"]) == 7
