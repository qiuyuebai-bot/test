"""Formal acceptance claims for the metrics evidence report."""

from scripts.generate_metric_evidence import (
    HALLUCINATION_FORMAL_MINIMUM_SAMPLE_SIZE,
    FORMAL_MINIMUM_SAMPLE_SIZE,
    _claim,
    _aggregate_claim_status,
    _required_additional_reviews,
    build_report,
)


def _metric(value, denominator, *, metric_id="test_metric"):
    return {
        "metric_id": metric_id,
        "display_name": metric_id,
        "value": value,
        "numerator": value,
        "denominator": denominator,
        "sample_count": denominator,
        "status": "ready",
    }


def test_claim_requires_formal_sample_gate():
    claim = _claim(_metric(100, FORMAL_MINIMUM_SAMPLE_SIZE - 1))

    assert claim["status"] == "insufficient_evidence"
    assert claim["value"] == 100
    assert claim["minimum_sample_size"] == FORMAL_MINIMUM_SAMPLE_SIZE


def test_claim_fails_when_target_is_missed_after_sample_gate():
    claim = _claim(_metric(84.99, FORMAL_MINIMUM_SAMPLE_SIZE))

    assert claim["status"] == "failed"
    assert "未达到目标" in claim["reason"]


def test_claim_passes_at_target():
    claim = _claim(_metric(85, FORMAL_MINIMUM_SAMPLE_SIZE))

    assert claim["status"] == "passed"


def test_hallucination_claim_is_strict_and_requires_formal_sample():
    metric = _metric(5.0, HALLUCINATION_FORMAL_MINIMUM_SAMPLE_SIZE, metric_id="hallucination_rate")
    claim = _claim(
        metric,
        target=5.0,
        minimum_sample_size=HALLUCINATION_FORMAL_MINIMUM_SAMPLE_SIZE,
        operator="<",
    )
    assert claim["status"] == "failed"

    insufficient = _claim(
        _metric(4.0, HALLUCINATION_FORMAL_MINIMUM_SAMPLE_SIZE - 1, metric_id="hallucination_rate"),
        target=5.0,
        minimum_sample_size=HALLUCINATION_FORMAL_MINIMUM_SAMPLE_SIZE,
        operator="<",
    )
    assert insufficient["status"] == "insufficient_evidence"


def test_required_additional_reviews_for_current_baseline():
    assert _required_additional_reviews(hallucinations=3, evaluated=53) == 8


def test_aggregate_status_is_strict():
    assert _aggregate_claim_status([_claim(_metric(100, 10))]) == "passed"
    assert _aggregate_claim_status([_claim(_metric(80, 10))]) == "failed"
    assert _aggregate_claim_status([_claim(_metric(100, 9))]) == "insufficient_evidence"


def test_build_report_includes_answer_accuracy_claim(db_session):
    report = build_report(db_session)
    metric_ids = {metric["metric_id"] for metric in report["metrics"]}

    assert "answer_accuracy" in metric_ids
    answer_claim = report["evidence"]["claims"]["answer_accuracy"]
    assert answer_claim["target"] == 85.0
    assert answer_claim["minimum_sample_size"] == FORMAL_MINIMUM_SAMPLE_SIZE


def test_build_report_includes_strict_hallucination_claim(db_session):
    report = build_report(db_session)
    claim = report["evidence"]["claims"]["hallucination_rate"]

    assert claim["target"] == 5.0
    assert claim["operator"] == "<"
    assert claim["minimum_sample_size"] == HALLUCINATION_FORMAL_MINIMUM_SAMPLE_SIZE
    assert "required_additional_reviews" in report["evidence"]["hallucination"]
