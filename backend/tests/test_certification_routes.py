"""认证申请与认证记录的权限测试。"""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.domains.assessment.models import AssessmentRecord, AssessmentStatusEnum, AssessmentTemplate
from app.domains.certification.models import Certification, CertificationRecord, CertificationStatusEnum
from app.domains.learner.models import LearnerProfile
from app.domains.position.models import Position
from app.models import User, UserRoleEnum
from app.utils.auth import create_access_token, hash_password


def _headers(user: User) -> dict[str, str]:
    token = create_access_token({
        "user_id": user.id,
        "username": user.username,
        "role": user.role.value,
    })
    return {"Authorization": f"Bearer {token}"}


def _create_certification_records(
    db_session: Session,
    sample_user: User,
    sample_learner_profile: LearnerProfile,
) -> tuple[LearnerProfile, CertificationRecord]:
    other_user = User(
        username="certification_other_learner",
        password_hash=hash_password("test_password"),
        role=UserRoleEnum.LEARNER,
        is_active=True,
        is_verified=True,
    )
    db_session.add(other_user)
    db_session.commit()
    db_session.refresh(other_user)

    other_learner = LearnerProfile(user_id=other_user.id, real_name="Other Learner")
    position = Position(code="CERT-ROUTE-001", name="Certification Route Position")
    db_session.add_all([other_learner, position])
    db_session.commit()
    db_session.refresh(other_learner)
    db_session.refresh(position)

    template = AssessmentTemplate(position_id=position.id, name="Certification Route Assessment")
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)

    sample_assessment = AssessmentRecord(
        template_id=template.id,
        user_id=sample_user.id,
        learner_id=sample_learner_profile.id,
        position_id=position.id,
        status=AssessmentStatusEnum.COMPLETED.value,
        overall_score=80,
    )
    other_assessment = AssessmentRecord(
        template_id=template.id,
        user_id=other_user.id,
        learner_id=other_learner.id,
        position_id=position.id,
        status=AssessmentStatusEnum.COMPLETED.value,
        overall_score=80,
    )
    certification = Certification(
        position_id=position.id,
        name="Certification Route Test",
        code="CERT-ROUTE-001",
        is_active=True,
    )
    db_session.add_all([sample_assessment, other_assessment, certification])
    db_session.commit()
    db_session.refresh(sample_assessment)
    db_session.refresh(other_assessment)
    db_session.refresh(certification)

    records = [
        CertificationRecord(
            certification_id=certification.id,
            user_id=sample_user.id,
            learner_id=sample_learner_profile.id,
            assessment_record_id=sample_assessment.id,
            status=CertificationStatusEnum.PENDING.value,
        ),
        CertificationRecord(
            certification_id=certification.id,
            user_id=other_user.id,
            learner_id=other_learner.id,
            assessment_record_id=other_assessment.id,
            status=CertificationStatusEnum.PENDING.value,
        ),
    ]
    db_session.add_all(records)
    db_session.commit()
    db_session.refresh(records[1])
    return other_learner, records[1]


def test_learner_cannot_apply_for_another_learner(
    client: TestClient,
    db_session: Session,
    sample_user: User,
    sample_learner_profile: LearnerProfile,
):
    other_learner, _ = _create_certification_records(db_session, sample_user, sample_learner_profile)
    assessment = db_session.query(AssessmentRecord).filter(
        AssessmentRecord.learner_id == sample_learner_profile.id,
    ).first()
    certification = db_session.query(Certification).first()

    response = client.post(
        "/api/v1/certifications/apply",
        json={
            "certification_id": certification.id,
            "assessment_record_id": assessment.id,
            "learner_id": other_learner.id,
        },
        headers=_headers(sample_user),
    )
    assert response.status_code == 200
    assert response.json()["code"] == 403


def test_learner_record_list_and_detail_are_scoped(
    client: TestClient,
    db_session: Session,
    sample_user: User,
    sample_learner_profile: LearnerProfile,
):
    _, other_record = _create_certification_records(db_session, sample_user, sample_learner_profile)

    list_response = client.get(
        "/api/v1/certifications/records/list?learner_id=999999",
        headers=_headers(sample_user),
    )
    detail_response = client.get(
        f"/api/v1/certifications/records/{other_record.id}",
        headers=_headers(sample_user),
    )
    assert list_response.status_code == 200
    assert list_response.json()["data"]["total"] == 1
    assert list_response.json()["data"]["items"][0]["learner_id"] == sample_learner_profile.id
    assert detail_response.status_code == 200
    assert detail_response.json()["code"] == 403
