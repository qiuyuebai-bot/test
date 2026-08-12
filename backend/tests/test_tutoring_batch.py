from contextlib import contextmanager
from unittest.mock import patch

import pytest

from app.models import AnswerRecord, BatchSubmission, IssuedTutoringQuestion
from app.services import tutoring_service as tutoring_service_module
from app.services.tutoring_service import AdaptiveTutoringService


@pytest.fixture(autouse=True)
def patch_batch_db_context(db_session, monkeypatch):
    @contextmanager
    def override_get_db_context():
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    monkeypatch.setattr(tutoring_service_module, "get_db_context", override_get_db_context)


def issue_batch_questions(db_session, learner, user):
    questions = [
        IssuedTutoringQuestion(
            user_id=user.id,
            learner_id=learner.id,
            question_type="single",
            topic="algorithm design",
            difficulty=3,
            content="Which option is correct?",
            options=["A", "B"],
            answer_key=["A"],
            explanation="A is the correct choice.",
            knowledge_points=["algorithm"],
            generation_method="test",
            assessment_mode="batch_practice",
            session_id="batch-test-1",
            ability_dimension="algorithm_design",
            status="issued",
        ),
        IssuedTutoringQuestion(
            user_id=user.id,
            learner_id=learner.id,
            question_type="single",
            topic="unmapped topic",
            difficulty=2,
            content="Which option is also correct?",
            options=["A", "B"],
            answer_key=["B"],
            explanation="B is the correct choice.",
            knowledge_points=["unmapped"],
            generation_method="test",
            assessment_mode="batch_practice",
            session_id="batch-test-1",
            status="issued",
        ),
    ]
    db_session.add_all(questions)
    db_session.commit()
    for question in questions:
        db_session.refresh(question)
    return questions


def test_batch_submission_is_idempotent_and_updates_profile_once(
    db_session, sample_learner_profile, sample_user
):
    questions = issue_batch_questions(db_session, sample_learner_profile, sample_user)
    original_algorithm = sample_learner_profile.algorithm_design
    original_theory = sample_learner_profile.theoretical_foundation
    payload = [
        {"question_id": str(questions[0].id), "user_answer": "A", "sequence_index": 1},
        {"question_id": str(questions[1].id), "user_answer": "A", "sequence_index": 2},
    ]

    result = AdaptiveTutoringService.submit_batch(
        sample_user.id, sample_learner_profile.id, "batch-test-1", payload
    )

    assert result["success"] is True
    assert result["total"] == 2
    assert result["correctCount"] == 1
    assert result["score"] == 50.0
    assert len(result["questions"]) == 2
    assert db_session.query(AnswerRecord).count() == 2
    assert db_session.query(BatchSubmission).count() == 1
    assert sample_learner_profile.algorithm_design == original_algorithm + 2
    assert sample_learner_profile.theoretical_foundation == original_theory

    repeated = AdaptiveTutoringService.submit_batch(
        sample_user.id,
        sample_learner_profile.id,
        "batch-test-1",
        list(reversed(payload)),
    )
    assert repeated == result
    assert db_session.query(AnswerRecord).count() == 2
    assert db_session.query(BatchSubmission).count() == 1

    conflict = AdaptiveTutoringService.submit_batch(
        sample_user.id,
        sample_learner_profile.id,
        "batch-test-1",
        [
            payload[0],
            {**payload[1], "user_answer": "B"},
        ],
    )
    assert conflict["success"] is False
    assert conflict["status_code"] == 409
    assert db_session.query(AnswerRecord).count() == 2


def test_batch_submission_rejects_incomplete_or_duplicate_sets(
    db_session, sample_learner_profile, sample_user
):
    questions = issue_batch_questions(db_session, sample_learner_profile, sample_user)
    missing = AdaptiveTutoringService.submit_batch(
        sample_user.id,
        sample_learner_profile.id,
        "batch-test-1",
        [{"question_id": str(questions[0].id), "user_answer": "A", "sequence_index": 1}],
    )
    assert missing["status_code"] == 409
    assert db_session.query(AnswerRecord).count() == 0

    duplicate = AdaptiveTutoringService.submit_batch(
        sample_user.id,
        sample_learner_profile.id,
        "batch-test-1",
        [
            {"question_id": str(questions[0].id), "user_answer": "A", "sequence_index": 1},
            {"question_id": str(questions[0].id), "user_answer": "B", "sequence_index": 2},
        ],
    )
    assert duplicate["status_code"] == 409
    assert db_session.query(AnswerRecord).count() == 0
    assert all(question.status == "issued" for question in questions)


def test_batch_failure_rolls_back_all_changes(
    db_session, sample_learner_profile, sample_user
):
    questions = issue_batch_questions(db_session, sample_learner_profile, sample_user)
    payload = [
        {"question_id": str(questions[0].id), "user_answer": "A", "sequence_index": 1},
        {"question_id": str(questions[1].id), "user_answer": "B", "sequence_index": 2},
    ]

    with patch.object(
        AdaptiveTutoringService,
        "_update_learner_profile_batch",
        side_effect=RuntimeError("profile update failed"),
    ):
        with pytest.raises(RuntimeError):
            AdaptiveTutoringService.submit_batch(
                sample_user.id, sample_learner_profile.id, "batch-test-1", payload
            )

    assert db_session.query(AnswerRecord).count() == 0
    assert db_session.query(BatchSubmission).count() == 0
    assert all(question.status == "issued" for question in questions)


def test_batch_result_is_only_available_after_submission(
    sample_learner_profile, sample_user
):
    assert AdaptiveTutoringService.get_batch_result(
        sample_user.id, sample_learner_profile.id, "missing-session"
    ) is None


def test_batch_http_submit_and_result_query_are_idempotent(
    client, db_session, sample_learner_profile, sample_user, auth_headers
):
    questions = issue_batch_questions(db_session, sample_learner_profile, sample_user)
    payload = {
        "learner_id": sample_learner_profile.id,
        "session_id": "batch-test-1",
        "answers": [
            {"question_id": str(questions[0].id), "user_answer": "A", "sequence_index": 1},
            {"question_id": str(questions[1].id), "user_answer": "B", "sequence_index": 2},
        ],
    }

    submitted = client.post(
        "/api/v1/tutoring/answers/batch", json=payload, headers=auth_headers
    )
    assert submitted.status_code == 200
    assert submitted.json()["code"] == 200
    assert submitted.json()["data"]["correctCount"] == 2

    recovered = client.get(
        "/api/v1/tutoring/answers/batch/batch-test-1",
        params={"learner_id": sample_learner_profile.id},
        headers=auth_headers,
    )
    assert recovered.status_code == 200
    assert recovered.json()["data"] == submitted.json()["data"]

    repeated = client.post(
        "/api/v1/tutoring/answers/batch", json=payload, headers=auth_headers
    )
    assert repeated.status_code == 200
    assert repeated.json()["data"] == submitted.json()["data"]
    assert db_session.query(AnswerRecord).count() == 2
    assert db_session.query(BatchSubmission).count() == 1
