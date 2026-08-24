"""Generated lecture publication workflow tests."""

from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.domains.knowledge.publication_service import KnowledgePublicationService, PublicationError
from app.domains.resource.models import LearningResource
from app.domains.learner.models import LearnerProfile
from app.models import User, UserRoleEnum
from app.utils.auth import hash_password
from app.utils.auth import CurrentUser


def _lecture(db: Session, learner_id: int, content: str = "# 讲义\n\n正文") -> LearningResource:
    resource = LearningResource(
        learner_id=learner_id,
        title="测试专属讲义",
        resource_type="lecture",
        format_type="md",
        content=content,
        version="1.0",
        is_latest=True,
        status="ready",
        validation_passed=True,
        hallucination_detected=False,
        industry="软件开发",
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
