"""Persistence guarantees for evidence-backed hallucination reviews."""

import json
from contextlib import contextmanager

from app.agents.task_repository import TaskRepository
from app.models import DebateRecord


def _use_test_session(monkeypatch, db_session):
    import app.agents.task_repository as repository_module

    @contextmanager
    def same_session():
        yield db_session

    monkeypatch.setattr(repository_module, "get_db_context", same_session)


def test_final_review_persists_metadata_and_is_idempotent(
    db_session, sample_agent_task, monkeypatch
):
    _use_test_session(monkeypatch, db_session)
    payload = {
        "original_content": "supported content",
        "reference_content": "source",
        "final_decision": "approved",
        "evidence_status": "sufficient",
        "review_outcome": "clean",
        "review_source": "knowledge_grounded",
        "conflict_points": [],
        "corrections": [],
    }
    repo = TaskRepository()
    repo.save_debate_record(sample_agent_task.id, 1, payload, final_review=True)
    repo.save_debate_record(sample_agent_task.id, 1, payload, final_review=True)

    rows = db_session.query(DebateRecord).filter(
        DebateRecord.task_id == sample_agent_task.id
    ).all()
    assert len(rows) == 1
    metadata = json.loads(rows[0].agent_judge_view)["audit_metadata"]
    assert metadata["is_final_review"] is True
    assert metadata["policy_version"] == "hallucination-rate-v1"
    assert rows[0].resolution_status == "resolved"


def test_non_final_review_stays_unresolved_and_content_change_appends(
    db_session, sample_agent_task, monkeypatch
):
    _use_test_session(monkeypatch, db_session)
    repo = TaskRepository()
    repo.save_debate_record(
        sample_agent_task.id,
        1,
        {
            "original_content": "draft content",
            "final_decision": "approved",
            "review_outcome": "clean",
            "evidence_status": "sufficient",
        },
        final_review=False,
    )
    repo.save_debate_record(
        sample_agent_task.id,
        1,
        {
            "original_content": "draft content",
            "final_decision": "approved",
            "review_outcome": "clean",
            "evidence_status": "sufficient",
        },
        final_review=True,
    )
    repo.save_debate_record(
        sample_agent_task.id,
        1,
        {
            "original_content": "revised content",
            "final_decision": "approved",
            "review_outcome": "clean",
            "evidence_status": "sufficient",
        },
        final_review=True,
    )

    rows = db_session.query(DebateRecord).filter(
        DebateRecord.task_id == sample_agent_task.id
    ).order_by(DebateRecord.id).all()
    assert len(rows) == 2
    assert rows[0].resolution_status == "resolved"
    assert rows[1].original_content == "revised content"

