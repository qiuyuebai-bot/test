"""岗位培训默认数据的结构与幂等性回归测试。"""

from sqlalchemy.orm import sessionmaker

from app.domains.assessment.models import AssessmentTemplate
from app.domains.certification.models import Certification, CertificationRule
from app.domains.position.models import Competency, Position, PositionCompetency
from app.domains.training.models import TrainingProject
from app.utils.seed_loader import load_seed_payload


def test_career_training_seed_is_complete_and_idempotent(db_session, monkeypatch):
    from app import seed_data

    payload = load_seed_payload("career_training.json")
    test_session_factory = sessionmaker(bind=db_session.get_bind())
    monkeypatch.setattr(seed_data, "SessionLocal", test_session_factory)

    seed_data.init_career_training_seed_data()
    seed_data.init_career_training_seed_data()

    assert db_session.query(Competency).count() == len(payload["competencies"])
    assert db_session.query(Position).count() == len(payload["positions"])
    assert db_session.query(PositionCompetency).count() == sum(
        len(position["competencies"]) for position in payload["positions"]
    )
    assert db_session.query(AssessmentTemplate).count() == len(payload["assessment_templates"])
    assert db_session.query(Certification).count() == len(payload["certifications"])
    assert db_session.query(CertificationRule).count() == sum(
        len(certification["rules"]) for certification in payload["certifications"]
    )
    assert db_session.query(TrainingProject).count() == len(payload["training_projects"])
    assert db_session.query(TrainingProject).filter(TrainingProject.status == "active").count() == len(
        payload["training_projects"]
    )

    assert {position.code for position in db_session.query(Position).all()} == {
        position["code"] for position in payload["positions"]
    }
    assert {certification.code for certification in db_session.query(Certification).all()} == {
        certification["code"] for certification in payload["certifications"]
    }
