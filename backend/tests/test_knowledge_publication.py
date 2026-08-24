"""Generated lecture publication workflow tests."""

from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.domains.knowledge.publication_service import (
    KnowledgePublicationService,
    PublicationError,
    PUBLISH_FAILED,
    PUBLISHED,
    WAITING_VALIDATION,
)
from app.domains.knowledge.models import KnowledgePublicationRequest
from app.domains.resource.models import LearningResource
from app.domains.learner.models import LearnerProfile
from app.models import User, UserRoleEnum
from app.utils.auth import hash_password
from app.utils.auth import CurrentUser


def _lecture(
    db: Session,
    learner_id: int,
    content: str = "# 讲义\n\n正文",
    status: str = "ready",
    validation_passed: bool = True,
    title: str = "测试专属讲义",
    industry: str = "软件开发",
    hallucination_detected: bool = False,
    review_status: str = "approved",
) -> LearningResource:
    resource = LearningResource(
        learner_id=learner_id,
        title=title,
        resource_type="lecture",
        format_type="md",
        content=content,
        version="1.0",
        is_latest=True,
        status=status,
        validation_passed=validation_passed,
        hallucination_detected=hallucination_detected,
        industry=industry,
        review_status=review_status,
    )
    db.add(resource)
    db.commit()
    db.refresh(resource)
    return resource


def test_lecture_publication_uses_snapshot_and_is_idempotent(
    db_session: Session,
    sample_user,
    sample_learner_profile,
    sample_admin_user,
):
    resource = _lecture(db_session, sample_learner_profile.id)
    learner = CurrentUser(sample_user.id, sample_user.username, "learner")
    admin = CurrentUser(sample_admin_user.id, sample_admin_user.username, "admin")

    request = KnowledgePublicationService.create_request(db_session, resource.id, learner)
    with pytest.raises(PublicationError) as duplicate_error:
        KnowledgePublicationService.create_request(db_session, resource.id, learner)
    assert duplicate_error.value.code == "duplicate_request"

    resource.content = "# 申请后修改的正文"
    db_session.commit()

    with patch(
        "app.domains.knowledge.publication_service.KnowledgeService.process_doc",
        return_value=True,
    ):
        published = KnowledgePublicationService.approve_request(db_session, request.id, admin)

    assert published.status == "published"
    assert published.snapshot["content"] == "# 讲义\n\n正文"
    assert published.knowledge_doc_id is not None

    with pytest.raises(PublicationError) as changed_error:
        KnowledgePublicationService.create_request(db_session, resource.id, learner)
    assert changed_error.value.code == "content_changed"


def test_learner_cannot_submit_other_learners_lecture(
    db_session: Session,
    sample_user,
    sample_learner_profile,
    sample_admin_user,
):
    other_user = User(
        username="other_learner",
        password_hash=hash_password("password"),
        role=UserRoleEnum.LEARNER,
        is_active=True,
    )
    db_session.add(other_user)
    db_session.commit()
    other_profile = LearnerProfile(
        user_id=other_user.id,
        real_name="其他学习者",
        education_level="master",
        major="cs",
    )
    db_session.add(other_profile)
    db_session.commit()
    other = _lecture(db_session, other_profile.id)
    learner = CurrentUser(sample_user.id, sample_user.username, "learner")

    with pytest.raises(PublicationError) as exc_info:
        KnowledgePublicationService.create_request(db_session, other.id, learner)

    assert exc_info.value.code == "forbidden"


def test_lecture_can_be_requested_before_generation_validation_finishes(
    db_session: Session,
    sample_user,
    sample_learner_profile,
    sample_admin_user,
):
    resource = _lecture(
        db_session,
        sample_learner_profile.id,
        status="validating",
        validation_passed=False,
    )
    learner = CurrentUser(sample_user.id, sample_user.username, "learner")
    admin = CurrentUser(sample_admin_user.id, sample_admin_user.username, "admin")

    request = KnowledgePublicationService.create_request(db_session, resource.id, learner)
    assert request.status == "pending"

    waiting = KnowledgePublicationService.approve_request(db_session, request.id, admin)
    assert waiting.status == WAITING_VALIDATION

    resource.status = "ready"
    resource.validation_passed = True
    db_session.commit()
    with patch(
        "app.domains.knowledge.publication_service.KnowledgeService.process_doc",
        return_value=True,
    ):
        KnowledgePublicationService.sync_resource_generation_state(db_session, resource.id)

    assert db_session.get(type(request), request.id).status == PUBLISHED


def test_failed_lecture_cannot_be_requested(
    db_session: Session,
    sample_user,
    sample_learner_profile,
):
    resource = _lecture(db_session, sample_learner_profile.id, status="failed", validation_passed=False)
    learner = CurrentUser(sample_user.id, sample_user.username, "learner")

    with pytest.raises(PublicationError) as exc_info:
        KnowledgePublicationService.create_request(db_session, resource.id, learner)

    assert exc_info.value.code == "resource_not_publishable"


def test_approved_ready_but_unvalidated_lecture_fails_publication(
    db_session: Session,
    sample_user,
    sample_learner_profile,
    sample_admin_user,
):
    resource = _lecture(
        db_session,
        sample_learner_profile.id,
        status="ready",
        validation_passed=False,
    )
    learner = CurrentUser(sample_user.id, sample_user.username, "learner")
    admin = CurrentUser(sample_admin_user.id, sample_admin_user.username, "admin")

    request = KnowledgePublicationService.create_request(db_session, resource.id, learner)
    result = KnowledgePublicationService.approve_request(db_session, request.id, admin)

    assert result.status == PUBLISH_FAILED


def test_auto_publish_validated_lecture_is_idempotent(
    db_session: Session,
    sample_user,
    sample_learner_profile,
):
    resource = _lecture(db_session, sample_learner_profile.id)

    with patch(
        "app.domains.knowledge.publication_service.KnowledgeService.process_doc",
        return_value=True,
    ):
        published = KnowledgePublicationService.auto_publish_resource(db_session, resource.id)
        duplicate = KnowledgePublicationService.auto_publish_resource(db_session, resource.id)

    assert published is not None
    assert published.status == PUBLISHED
    assert published.reviewed_by is None
    assert published.review_note == "系统自动入库"
    assert published.submitted_by == sample_user.id
    assert duplicate is not None
    assert duplicate.id == published.id
    assert db_session.query(type(published)).filter_by(resource_id=resource.id).count() == 1


@pytest.mark.parametrize(
    ("status", "validation_passed", "title", "industry", "hallucination_detected"),
    [
        ("failed", False, "测试专属讲义", "软件开发", False),
        ("ready", True, "None", "软件开发", False),
        ("ready", True, "测试专属讲义", "", False),
        ("ready", True, "测试专属讲义", "软件开发", True),
    ],
)
def test_auto_publish_rejects_ineligible_lecture_without_request(
    db_session: Session,
    sample_learner_profile,
    status,
    validation_passed,
    title,
    industry,
    hallucination_detected,
):
    resource = _lecture(
        db_session,
        sample_learner_profile.id,
        status=status,
        validation_passed=validation_passed,
        title=title,
        industry=industry,
        hallucination_detected=hallucination_detected,
    )

    result = KnowledgePublicationService.auto_publish_resource(db_session, resource.id)

    assert result is None
    assert db_session.query(KnowledgePublicationRequest).filter_by(resource_id=resource.id).count() == 0


def test_generation_state_sync_does_not_discover_historical_lecture(
    db_session: Session,
    sample_learner_profile,
):
    resource = _lecture(db_session, sample_learner_profile.id)

    KnowledgePublicationService.sync_resource_generation_state(db_session, resource.id)

    assert db_session.query(KnowledgePublicationRequest).filter_by(resource_id=resource.id).count() == 0
