from contextlib import contextmanager

import pytest
from sqlalchemy.orm import Session

from app.agents import task_repository as task_repository_module
from app.agents.task_repository import TaskRepository
from app.domains.resource import service as resource_service_module
from app.domains.resource.router import generate_resources_sync
from app.domains.resource.service import ResourceGenerationService
from app.models import AnswerRecord, IssuedTutoringQuestion, LearningResource
from app.services.common import ResourceServiceHelper
from app.schemas.core import GenerateResourcesRequest
from app.services import tutoring_service as tutoring_service_module
from app.services import lecture_supplement_service as lecture_supplement_module
from app.services.tutoring_service import AdaptiveTutoringService
from app.utils.auth import CurrentUser


@pytest.fixture(autouse=True)
def patch_sync_db_context(db_session: Session, monkeypatch):
    @contextmanager
    def override_get_db_context():
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    monkeypatch.setattr(task_repository_module, "get_db_context", override_get_db_context)
    monkeypatch.setattr(tutoring_service_module, "get_db_context", override_get_db_context)
    monkeypatch.setattr(lecture_supplement_module, "get_db_context", override_get_db_context)
    monkeypatch.setattr(resource_service_module, "get_db_context", override_get_db_context)


def exercise_result():
    return {
        "resource_title": "机器学习分阶测试题",
        "resource_type": "exercise",
        "difficulty_level": 3,
        "content": "# 机器学习分阶测试题",
        "content_json": {
            "basic_questions": [
                {
                    "question": "基础题",
                    "options": ["选项A", "选项B"],
                    "correct_answer": 1,
                    "difficulty": 2,
                    "explanation": "基础解析",
                    "knowledge_points": ["机器学习基础"],
                }
            ],
            "advanced_questions": [
                {
                    "question": "进阶题",
                    "options": ["选项A", "选项B"],
                    "correct_answer": 0,
                    "difficulty": 4,
                    "explanation": "进阶解析",
                    "knowledge_points": ["模型评估"],
                }
            ],
        },
        "source_slice_ids": [10],
        "source_doc_ids": [20],
        "generation_method": "deterministic_fallback",
    }


def create_exercise_resource(db_session, learner, title="机器学习分阶测试题"):
    resource = LearningResource(
        learner_id=learner.id,
        title=title,
        resource_type="exercise",
        knowledge_topic="机器学习",
        difficulty_level=3,
        version="1.0",
        content="# 机器学习分阶测试题",
        content_json=exercise_result()["content_json"],
        source_slice_ids=[10],
        source_doc_ids=[20],
        generation_method="deterministic_fallback",
        validation_passed=True,
        status="ready",
    )
    db_session.add(resource)
    db_session.commit()
    db_session.refresh(resource)
    return resource


def test_approved_exercise_is_published_for_the_matching_learner(
    db_session, sample_agent_task, sample_learner_profile, sample_user,
):
    sample_agent_task.input_data = {"target_topic": "机器学习"}
    db_session.commit()

    result = TaskRepository().save_resource_and_complete(
        task_id=sample_agent_task.id,
        learner_id=sample_learner_profile.id,
        generation_result=exercise_result(),
        audit_result={"passed": True, "overall_score": 90},
        debate_rounds=1,
    )

    assert result["issued_question_count"] == 2
    issued = db_session.query(IssuedTutoringQuestion).order_by(IssuedTutoringQuestion.id).all()
    assert [question.user_id for question in issued] == [sample_user.id, sample_user.id]
    assert [question.answer_key for question in issued] == [["B"], ["A"]]
    assert all(question.ability_dimension == "algorithm_design" for question in issued)

    public_questions = AdaptiveTutoringService.get_issued_questions(sample_learner_profile.id)
    assert [question["question"] for question in public_questions] == ["基础题", "进阶题"]
    assert all("answer_key" not in question and "answerKey" not in question for question in public_questions)


def test_failed_exercise_is_not_published(db_session, sample_agent_task, sample_learner_profile):
    result = TaskRepository().save_resource_and_complete(
        task_id=sample_agent_task.id,
        learner_id=sample_learner_profile.id,
        generation_result=exercise_result(),
        audit_result={"passed": False, "overall_score": 40},
        debate_rounds=1,
    )

    assert result["issued_question_count"] == 0
    assert db_session.query(IssuedTutoringQuestion).count() == 0


def test_resource_generation_service_also_publishes_exercise_questions(
    db_session, sample_learner_profile,
):
    resource = ResourceGenerationService._save_resource(
        learner_id=sample_learner_profile.id,
        resource_type="exercise",
        resource_data=exercise_result(),
        diagnosis_result={},
        target_topic="机器学习",
    )

    assert resource.id is not None
    assert db_session.query(IssuedTutoringQuestion).filter(
        IssuedTutoringQuestion.source_resource_id == resource.id
    ).count() == 2


def test_resource_publication_is_idempotent_and_supersedes_pending_questions(
    db_session, sample_learner_profile,
):
    first_resource = create_exercise_resource(db_session, sample_learner_profile)
    assert AdaptiveTutoringService.publish_resource_questions(
        db_session, first_resource, sample_learner_profile, "机器学习"
    ) == 2
    assert AdaptiveTutoringService.publish_resource_questions(
        db_session, first_resource, sample_learner_profile, "机器学习"
    ) == 2
    assert db_session.query(IssuedTutoringQuestion).count() == 2

    second_resource = create_exercise_resource(db_session, sample_learner_profile, "机器学习新版测试题")
    assert AdaptiveTutoringService.publish_resource_questions(
        db_session, second_resource, sample_learner_profile, "机器学习"
    ) == 2

    first_statuses = db_session.query(IssuedTutoringQuestion.status).filter(
        IssuedTutoringQuestion.source_resource_id == first_resource.id
    ).all()
    assert first_statuses == [("superseded",), ("superseded",)]
    assert len(AdaptiveTutoringService.get_issued_questions(sample_learner_profile.id)) == 2


def test_task_save_retry_reuses_the_existing_resource_and_questions(
    db_session, sample_agent_task, sample_learner_profile,
):
    sample_agent_task.input_data = {"target_topic": "机器学习"}
    db_session.commit()
    repository = TaskRepository()
    first = repository.save_resource_and_complete(
        sample_agent_task.id,
        sample_learner_profile.id,
        exercise_result(),
        {"passed": True, "overall_score": 90},
        1,
    )
    second = repository.save_resource_and_complete(
        sample_agent_task.id,
        sample_learner_profile.id,
        exercise_result(),
        {"passed": True, "overall_score": 90},
        1,
    )

    assert second["resource_id"] == first["resource_id"]
    assert db_session.query(LearningResource).filter(
        LearningResource.generation_task_id == sample_agent_task.id
    ).count() == 1
    assert db_session.query(IssuedTutoringQuestion).count() == 2


def test_server_grades_published_question_and_creates_answer_record(
    db_session, sample_learner_profile, sample_user, monkeypatch,
):
    resource = create_exercise_resource(db_session, sample_learner_profile)
    AdaptiveTutoringService.publish_resource_questions(
        db_session, resource, sample_learner_profile, "机器学习"
    )
    question = db_session.query(IssuedTutoringQuestion).filter(
        IssuedTutoringQuestion.source_resource_id == resource.id,
        IssuedTutoringQuestion.source_question_index == 0,
    ).first()
    monkeypatch.setattr(
        AdaptiveTutoringService,
        "_run_agent_decision",
        lambda **_: {"next_action": "maintain", "reason": "测试", "confidence": 1.0},
    )
    monkeypatch.setattr(
        AdaptiveTutoringService,
        "get_learner",
        lambda learner_id: sample_learner_profile if learner_id == sample_learner_profile.id else None,
    )

    result = AdaptiveTutoringService.process_answer(
        user_id=sample_user.id,
        learner_id=sample_learner_profile.id,
        question_id=str(question.id),
        user_answer="B",
        time_spent_ms=100,
    )

    assert result["success"] is True
    assert result["is_correct"] is True
    assert result["score"] == 100.0
    assert question.status == "answered"
    history = AdaptiveTutoringService.get_interaction_history(sample_learner_profile.id)
    assert "correct_answer" not in history["history"][0]


def test_failed_answer_processing_keeps_the_question_available_for_retry(
    db_session, sample_learner_profile, sample_user, monkeypatch,
):
    resource = create_exercise_resource(db_session, sample_learner_profile)
    AdaptiveTutoringService.publish_resource_questions(
        db_session, resource, sample_learner_profile, "机器学习"
    )
    question = db_session.query(IssuedTutoringQuestion).first()
    monkeypatch.setattr(
        AdaptiveTutoringService,
        "get_learner",
        lambda learner_id: sample_learner_profile if learner_id == sample_learner_profile.id else None,
    )
    monkeypatch.setattr(
        AdaptiveTutoringService,
        "_run_agent_decision",
        lambda **_: {"next_action": "maintain", "reason": "测试", "confidence": 1.0},
    )
    monkeypatch.setattr(
        AdaptiveTutoringService,
        "_save_answer_record",
        lambda **_: (_ for _ in ()).throw(RuntimeError("保存失败")),
    )

    result = AdaptiveTutoringService.process_answer(
        user_id=sample_user.id,
        learner_id=sample_learner_profile.id,
        question_id=str(question.id),
        user_answer="B",
        time_spent_ms=100,
    )

    db_session.refresh(question)
    assert result["success"] is False
    assert question.status == "issued"
    assert db_session.query(AnswerRecord).count() == 0


def test_dynamic_questions_are_owned_by_the_learner_not_the_requester(
    db_session, sample_learner_profile, sample_user,
):
    questions = [{
        "question": "动态题",
        "options": ["选项A", "选项B"],
        "correctAnswer": 0,
        "topic": "机器学习",
    }]

    AdaptiveTutoringService._persist_issued_questions(
        user_id=sample_user.id + 100,
        learner_id=sample_learner_profile.id,
        questions=questions,
        knowledge=[],
    )

    issued = db_session.query(IssuedTutoringQuestion).one()
    assert issued.user_id == sample_learner_profile.user_id


def test_only_the_learner_can_submit_an_issued_question(
    db_session, sample_learner_profile, sample_user, monkeypatch,
):
    resource = create_exercise_resource(db_session, sample_learner_profile)
    AdaptiveTutoringService.publish_resource_questions(
        db_session, resource, sample_learner_profile, "机器学习"
    )
    question = db_session.query(IssuedTutoringQuestion).first()

    result = AdaptiveTutoringService.process_answer(
        user_id=sample_user.id + 100,
        learner_id=sample_learner_profile.id,
        question_id=str(question.id),
        user_answer="B",
        time_spent_ms=100,
    )

    assert result["success"] is False
    assert db_session.query(AnswerRecord).count() == 0


def test_submission_requires_a_server_issued_question(
    db_session, sample_learner_profile, sample_user,
):
    result = AdaptiveTutoringService.process_answer(
        user_id=sample_user.id,
        learner_id=sample_learner_profile.id,
        question_id="legacy-client-question",
        user_answer="A",
        time_spent_ms=100,
    )

    assert result["success"] is False
    assert db_session.query(AnswerRecord).count() == 0


def test_answer_record_is_linked_to_exactly_one_issued_question(
    db_session, sample_learner_profile, sample_user, monkeypatch,
):
    resource = create_exercise_resource(db_session, sample_learner_profile)
    AdaptiveTutoringService.publish_resource_questions(
        db_session, resource, sample_learner_profile, "机器学习"
    )
    question = db_session.query(IssuedTutoringQuestion).first()
    monkeypatch.setattr(
        AdaptiveTutoringService,
        "_run_agent_decision",
        lambda **_: {"next_action": "maintain", "reason": "测试", "confidence": 1.0},
    )
    monkeypatch.setattr(
        AdaptiveTutoringService,
        "get_learner",
        lambda learner_id: sample_learner_profile if learner_id == sample_learner_profile.id else None,
    )

    result = AdaptiveTutoringService.process_answer(
        user_id=sample_user.id,
        learner_id=sample_learner_profile.id,
        question_id=str(question.id),
        user_answer="B",
        time_spent_ms=100,
    )

    assert result["success"] is True
    record = db_session.query(AnswerRecord).one()
    assert record.issued_question_id == question.id


def test_sync_resource_generation_checks_learner_permission(
    db_session, sample_learner_profile,
):
    response = generate_resources_sync(
        request=GenerateResourcesRequest(
            learner_id=sample_learner_profile.id,
            target_topic="机器学习",
        ),
        db=db_session,
        current_user=CurrentUser(user_id=99999, username="other", role="learner"),
    )

    assert response.status_code == 401


def test_learner_resource_view_hides_exercise_answers(
    db_session, sample_learner_profile,
):
    resource = create_exercise_resource(db_session, sample_learner_profile)

    detail = ResourceServiceHelper.format_resource_detail(resource, include_answers=False)

    questions = detail["content_json"]["basic_questions"] + detail["content_json"]["advanced_questions"]
    assert all("correct_answer" not in question for question in questions)
    assert all("explanation" not in question for question in questions)


def test_resource_detail_exposes_markdown_format_and_summary(sample_learning_resource):
    detail = ResourceServiceHelper.format_resource_detail(sample_learning_resource)

    assert detail["format_type"] == "md"
    assert detail["summary"] == sample_learning_resource.summary
