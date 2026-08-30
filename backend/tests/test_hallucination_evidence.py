import logging

from app.agents.judge_agent import JudgeAgent
from app.utils.hallucination import HallucinationUtil


def test_strong_evidence_is_supported_and_cited():
    detected, info = HallucinationUtil.detect_hallucination(
        "Python 3.12 adds the improved error messages.",
        reference_knowledge=[{
            "title": "Python Release Notes",
            "content": "Python 3.12 adds improved error messages.",
            "similarity": 0.86,
            "slice_index": 2,
            "slice_id": 12,
            "doc_id": 4,
        }],
    )

    assert detected is False
    assert info["credibility"] == "high"
    assert info["claims"][0]["status"] == "supported"
    assert info["citations"][0]["label"] == "[Python Release Notes-Paragraph 3]"


def test_insufficient_evidence_returns_knowledge_gap_and_logs_marker(caplog):
    caplog.set_level(logging.WARNING)
    detected, info = HallucinationUtil.detect_hallucination(
        "The Aurora protocol supports seven independent recovery modes.",
        reference_knowledge=[{
            "title": "Unrelated Notes",
            "content": "A short history of databases.",
            "similarity": 0.21,
        }],
    )

    assert detected is False
    assert info["credibility"] == "no_evidence"
    assert info["knowledge_gap"]["present"] is True
    assert "Aurora" in info["knowledge_gap"]["entities"]
    assert "EVIDENCE_GAP" in caplog.text


def test_explicit_numeric_conflict_is_an_evidence_issue():
    result = JudgeAgent().execute({
        "generated_content": "Python 3.12 was released in 2020.",
        "reference_knowledge": [{
            "title": "Python Release Notes",
            "content": "Python 3.12 was released in 2023.",
            "similarity": 0.91,
            "slice_index": 0,
            "slice_id": 10,
            "doc_id": 4,
        }],
    })

    assert result["hallucination_detected"] is True
    assert any(issue["type"] == "hallucination_evidence" for issue in result["issues"])


def test_unrelated_years_do_not_create_a_conflict():
    assert HallucinationUtil._claim_conflict(
        "Python 3.12 was released in 2023.",
        {"content": "The project was founded in 2018.", "similarity": 0.91},
    ) is None


def test_same_relation_on_different_entities_does_not_create_a_conflict():
    assert HallucinationUtil._claim_conflict(
        "Python 3.12 was released in 2023.",
        {"content": "Java 17 was released in 2021.", "similarity": 0.91},
    ) is None


def test_judge_marks_weak_evidence_as_pending_not_hallucination():
    result = JudgeAgent().execute({
        "generated_content": "The Aurora protocol supports seven recovery modes.",
        "reference_knowledge": [{
            "title": "Unrelated Notes",
            "content": "A database history.",
            "similarity": 0.21,
        }],
    })

    assert result["hallucination_detected"] is False
    assert result["review_outcome"] == "pending"
    assert result["evidence_status"] == "gap"


def test_judge_flexibly_rejects_a_knowledge_gap():
    result = JudgeAgent().execute({
        "generated_content": "The Aurora protocol supports seven recovery modes.",
        "reference_knowledge": [],
    })

    assert result["hallucination_detected"] is False
    assert result["passed"] is False
    assert result["debate_record"]["judge_view"]["decision"] == "needs_revision"
    assert any(issue["type"] == "knowledge_gap" for issue in result["issues"])
