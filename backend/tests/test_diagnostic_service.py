from contextlib import contextmanager

from app.domains.diagnostic.service import DiagnosticService
from app.models import DiagnosticSession, IssuedTutoringQuestion
from app.services import tutoring_service as tutoring_service_module
from app.services import common as common_service_module


def test_diagnostic_session_scores_all_dimensions(db_session, sample_user, sample_learner_profile, monkeypatch):
    @contextmanager
    def shared_db_context():
        yield db_session
        db_session.commit()

    monkeypatch.setattr(tutoring_service_module, "get_db_context", shared_db_context)
    monkeypatch.setattr(common_service_module, "get_db_context", shared_db_context)
    monkeypatch.setattr(
        tutoring_service_module.LLMUtil,
        "is_available",
        classmethod(lambda cls: False),
    )

    payload = DiagnosticService.create_or_resume(
        db_session,
        sample_user.id,
        sample_learner_profile.id,
        questions_per_dimension=2,
    )

    assert payload["total_questions"] == 12
    assert len(payload["questions"]) == 12

    questions = (
        db_session.query(IssuedTutoringQuestion)
        .filter(IssuedTutoringQuestion.diagnostic_session_id == payload["session_id"])
        .order_by(IssuedTutoringQuestion.id.asc())
        .all()
    )
    for question in questions:
        result = DiagnosticService.submit_answer(
            db_session,
            sample_user.id,
            sample_learner_profile.id,
            payload["session_id"],
            str(question.id),
            question.answer_key,
            1000,
        )
        assert result["success"] is True
        if question.id == questions[0].id:
            session = db_session.query(DiagnosticSession).get(payload["session_id"])
            db_session.refresh(session)
            assert session.status == "active"
            assert session.answered_questions == 1

    session = db_session.query(DiagnosticSession).get(payload["session_id"])
    db_session.refresh(sample_learner_profile)
    assert session.status == "completed"
    assert session.answered_questions == 12
    assert sample_learner_profile.diagnostic_status == "completed"
    assert set(sample_learner_profile.ability_assessments) == {
        dimension for dimension, _ in DiagnosticService.DIMENSIONS
    }
    assert all(
        item["status"] == "estimated"
        for item in sample_learner_profile.ability_assessments.values()
    )


def test_diagnostic_session_resumes_active_questions(db_session, sample_user, sample_learner_profile, monkeypatch):
    @contextmanager
    def shared_db_context():
        yield db_session
        db_session.commit()

    monkeypatch.setattr(tutoring_service_module, "get_db_context", shared_db_context)
    monkeypatch.setattr(common_service_module, "get_db_context", shared_db_context)
    monkeypatch.setattr(
        tutoring_service_module.LLMUtil,
        "is_available",
        classmethod(lambda cls: False),
    )

    first = DiagnosticService.create_or_resume(db_session, sample_user.id, sample_learner_profile.id, 2)
    resumed = DiagnosticService.create_or_resume(db_session, sample_user.id, sample_learner_profile.id, 3)

    assert resumed["session_id"] == first["session_id"]
    assert resumed["total_questions"] == 12


def test_diagnostic_routes_create_resume_and_answer(
    client, sample_learner_profile, auth_headers, monkeypatch
):
    monkeypatch.setattr(
        tutoring_service_module.LLMUtil,
        "is_available",
        classmethod(lambda cls: False),
    )

    create_response = client.post(
        "/api/v1/diagnostic/sessions",
        json={"learner_id": sample_learner_profile.id, "questions_per_dimension": 3},
        headers=auth_headers,
    )
    assert create_response.status_code == 200
    created = create_response.json()["data"]
    assert created["total_questions"] == 18
    assert created["questions"][0]["assessmentMode"] == "diagnostic"

    resumed_response = client.post(
        "/api/v1/diagnostic/sessions",
        json={"learner_id": sample_learner_profile.id, "questions_per_dimension": 2},
        headers=auth_headers,
    )
    assert resumed_response.status_code == 200
    resumed = resumed_response.json()["data"]
    assert resumed["session_id"] == created["session_id"]
    assert resumed["total_questions"] == 18

    answer_response = client.post(
        f"/api/v1/diagnostic/sessions/{created['session_id']}/answers",
        json={"question_id": created["questions"][0]["id"], "user_answer": ["A"]},
        headers=auth_headers,
    )
    assert answer_response.status_code == 200
    assert answer_response.json()["data"]["success"] is True
