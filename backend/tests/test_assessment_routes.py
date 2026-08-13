"""能力评估接口权限与学员范围测试。"""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.domains.assessment.models import AssessmentRecord, AssessmentStatusEnum, AssessmentTemplate
from app.domains.position.models import Position
from app.models import LearnerProfile, User, UserRoleEnum
from app.utils.auth import create_access_token, hash_password


def _headers(user: User) -> dict[str, str]:
    token = create_access_token({
        "user_id": user.id,
        "username": user.username,
        "role": user.role.value,
    })
    return {"Authorization": f"Bearer {token}"}


def test_learner_cannot_start_or_submit_assessment(
    client: TestClient,
    sample_user: User,
):
    headers = _headers(sample_user)

    start_response = client.post(
        "/api/v1/assessments/start",
        json={"template_id": 1, "learner_id": 1},
        headers=headers,
    )
    submit_response = client.post(
        "/api/v1/assessments/records/1/submit",
        json={"scores": []},
        headers=headers,
    )

    assert start_response.status_code == 403
    assert submit_response.status_code == 403


def test_learner_record_list_is_scoped_to_current_user(
    client: TestClient,
    db_session: Session,
    sample_user: User,
    sample_learner_profile: LearnerProfile,
):
    other_user = User(
        username="assessment_other_learner",
        password_hash=hash_password("test_password"),
        role=UserRoleEnum.LEARNER,
        is_active=True,
    )
    db_session.add(other_user)
    db_session.commit()
    db_session.refresh(other_user)
    other_learner = LearnerProfile(user_id=other_user.id, real_name="其他学习者")
    position = Position(code="ASSESSMENT-ROUTE", name="评估测试岗位")
    db_session.add_all([other_learner, position])
    db_session.commit()
    db_session.refresh(other_learner)
    db_session.refresh(position)
    template = AssessmentTemplate(position_id=position.id, name="评估测试模板")
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)
    db_session.add_all([
        AssessmentRecord(
            template_id=template.id,
            user_id=sample_user.id,
            learner_id=sample_learner_profile.id,
            position_id=position.id,
            status=AssessmentStatusEnum.IN_PROGRESS.value,
        ),
        AssessmentRecord(
            template_id=template.id,
            user_id=other_user.id,
            learner_id=other_learner.id,
            position_id=position.id,
            status=AssessmentStatusEnum.IN_PROGRESS.value,
        ),
    ])
    db_session.commit()

    response = client.get(
        f"/api/v1/assessments/records?learner_id={other_learner.id}",
        headers=_headers(sample_user),
    )

    assert response.status_code == 200
    items = response.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["learner_id"] == sample_learner_profile.id
