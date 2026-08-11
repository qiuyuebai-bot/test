"""Certification 域 Service 单元测试"""
import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.domains.position.models import Position, Competency, PositionCompetency
from app.domains.assessment.models import (
    AssessmentTemplate, AssessmentRecord, CompetencyScore,
    AssessmentStatusEnum,
)
from app.domains.assessment.schemas import AssessmentSubmitRequest
from app.domains.assessment.service import AssessmentService
from app.domains.certification.models import (
    Certification, CertificationRule, CertificationRecord,
    RuleTypeEnum, CertificationStatusEnum,
)
from app.domains.certification.schemas import (
    CertificationCreate, CertificationUpdate,
    CertificationRuleCreate, CertificationApplyRequest,
)
from app.domains.certification.service import CertificationService


@pytest.fixture
def db():
    """内存 SQLite 测试数据库"""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def completed_assessment(db):
    """创建一个已完成的评估记录（含评分），返回 (position_id, competency_id, assessment_record_id)"""
    pos = Position(code="FE-001", name="前端工程师", category="technical", level="junior")
    db.add(pos)
    db.commit()
    db.refresh(pos)

    comp = Competency(code="HTML", name="HTML基础", category="technical")
    db.add(comp)
    db.commit()
    db.refresh(comp)

    pc = PositionCompetency(position_id=pos.id, competency_id=comp.id, required_level=3)
    db.add(pc)
    db.commit()

    tpl = AssessmentTemplate(position_id=pos.id, name="评估模板", pass_threshold=60.0)
    db.add(tpl)
    db.commit()
    db.refresh(tpl)

    record = AssessmentRecord(
        template_id=tpl.id,
        user_id=1,
        position_id=pos.id,
        status=AssessmentStatusEnum.COMPLETED.value,
        overall_score=80.0,
        overall_level=4,
        started_at=datetime.now(),
        completed_at=datetime.now(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    cs = CompetencyScore(
        assessment_record_id=record.id,
        competency_id=comp.id,
        current_level=4,
        current_score=80.0,
        required_level=3,
        gap=-1,
        assessment_method="quiz",
    )
    db.add(cs)
    db.commit()

    return pos.id, comp.id, record.id


class TestCertificationCRUD:
    def test_create_certification(self, db, completed_assessment):
        pos_id, _, _ = completed_assessment
        data = CertificationCreate(
            position_id=pos_id,
            name="前端初级认证",
            code="CERT-FE-J-001",
            level="junior",
            validity_period_months=24,
            issuer="技术学院",
        )
        result = CertificationService.create_certification(db, data)
        assert result["code"] == 200
        assert result["data"]["name"] == "前端初级认证"
        assert result["data"]["code"] == "CERT-FE-J-001"

    def test_create_certification_invalid_position(self, db):
        data = CertificationCreate(position_id=999, name="测试", code="X-001")
        result = CertificationService.create_certification(db, data)
        assert result["code"] == 404

    def test_create_certification_duplicate_code(self, db, completed_assessment):
        pos_id, _, _ = completed_assessment
        CertificationService.create_certification(db, CertificationCreate(
            position_id=pos_id, name="认证1", code="DUP-001"
        ))
        result = CertificationService.create_certification(db, CertificationCreate(
            position_id=pos_id, name="认证2", code="DUP-001"
        ))
        assert result["code"] == 400

    def test_get_certification_list(self, db, completed_assessment):
        pos_id, _, _ = completed_assessment
        CertificationService.create_certification(db, CertificationCreate(position_id=pos_id, name="认证A", code="A-001"))
        CertificationService.create_certification(db, CertificationCreate(position_id=pos_id, name="认证B", code="B-002"))
        result = CertificationService.get_certification_list(db, page=1, page_size=10)
        assert result["code"] == 200
        assert result["data"]["total"] == 2

    def test_get_certification_by_id(self, db, completed_assessment):
        pos_id, _, _ = completed_assessment
        created = CertificationService.create_certification(db, CertificationCreate(
            position_id=pos_id, name="认证X", code="X-001"
        ))
        cert_id = created["data"]["id"]
        result = CertificationService.get_certification_by_id(db, cert_id)
        assert result["code"] == 200
        assert result["data"]["name"] == "认证X"
        assert "rules" in result["data"]

    def test_update_certification(self, db, completed_assessment):
        pos_id, _, _ = completed_assessment
        created = CertificationService.create_certification(db, CertificationCreate(
            position_id=pos_id, name="旧名称", code="U-001"
        ))
        cert_id = created["data"]["id"]
        result = CertificationService.update_certification(db, cert_id, CertificationUpdate(name="新名称"))
        assert result["code"] == 200
        assert result["data"]["name"] == "新名称"

    def test_delete_certification(self, db, completed_assessment):
        pos_id, _, _ = completed_assessment
        created = CertificationService.create_certification(db, CertificationCreate(
            position_id=pos_id, name="待删除", code="D-001"
        ))
        cert_id = created["data"]["id"]
        result = CertificationService.delete_certification(db, cert_id)
        assert result["code"] == 200
        result2 = CertificationService.get_certification_by_id(db, cert_id)
        assert result2["code"] == 404


class TestCertificationRule:
    def test_add_overall_score_rule(self, db, completed_assessment):
        pos_id, _, _ = completed_assessment
        cert = CertificationService.create_certification(db, CertificationCreate(
            position_id=pos_id, name="认证", code="R-001"
        ))
        cert_id = cert["data"]["id"]
        result = CertificationService.add_rule(db, CertificationRuleCreate(
            certification_id=cert_id,
            rule_type="overall_score",
            rule_config={"min_score": 75},
        ))
        assert result["code"] == 200
        assert result["data"]["rule_type"] == "overall_score"

    def test_add_competency_level_rule(self, db, completed_assessment):
        pos_id, comp_id, _ = completed_assessment
        cert = CertificationService.create_certification(db, CertificationCreate(
            position_id=pos_id, name="认证", code="R-002"
        ))
        cert_id = cert["data"]["id"]
        result = CertificationService.add_rule(db, CertificationRuleCreate(
            certification_id=cert_id,
            rule_type="competency_level",
            rule_config={"competency_id": comp_id, "min_level": 3},
        ))
        assert result["code"] == 200

    def test_add_all_mandatory_met_rule(self, db, completed_assessment):
        pos_id, _, _ = completed_assessment
        cert = CertificationService.create_certification(db, CertificationCreate(
            position_id=pos_id, name="认证", code="R-003"
        ))
        cert_id = cert["data"]["id"]
        result = CertificationService.add_rule(db, CertificationRuleCreate(
            certification_id=cert_id,
            rule_type="all_mandatory_met",
            rule_config={"allow_gap": 0},
        ))
        assert result["code"] == 200

    def test_add_rule_invalid_type(self, db, completed_assessment):
        pos_id, _, _ = completed_assessment
        cert = CertificationService.create_certification(db, CertificationCreate(
            position_id=pos_id, name="认证", code="R-004"
        ))
        cert_id = cert["data"]["id"]
        result = CertificationService.add_rule(db, CertificationRuleCreate(
            certification_id=cert_id,
            rule_type="invalid_type",
            rule_config={},
        ))
        assert result["code"] == 400

    def test_add_rule_invalid_config(self, db, completed_assessment):
        pos_id, _, _ = completed_assessment
        cert = CertificationService.create_certification(db, CertificationCreate(
            position_id=pos_id, name="认证", code="R-005"
        ))
        cert_id = cert["data"]["id"]
        # overall_score 缺少 min_score
        result = CertificationService.add_rule(db, CertificationRuleCreate(
            certification_id=cert_id,
            rule_type="overall_score",
            rule_config={},
        ))
        assert result["code"] == 400

    def test_get_rules(self, db, completed_assessment):
        pos_id, _, _ = completed_assessment
        cert = CertificationService.create_certification(db, CertificationCreate(
            position_id=pos_id, name="认证", code="R-006"
        ))
        cert_id = cert["data"]["id"]
        CertificationService.add_rule(db, CertificationRuleCreate(
            certification_id=cert_id, rule_type="overall_score", rule_config={"min_score": 60}
        ))
        result = CertificationService.get_rules(db, cert_id)
        assert result["code"] == 200
        assert len(result["data"]) == 1

    def test_delete_rule(self, db, completed_assessment):
        pos_id, _, _ = completed_assessment
        cert = CertificationService.create_certification(db, CertificationCreate(
            position_id=pos_id, name="认证", code="R-007"
        ))
        cert_id = cert["data"]["id"]
        rule = CertificationService.add_rule(db, CertificationRuleCreate(
            certification_id=cert_id, rule_type="overall_score", rule_config={"min_score": 60}
        ))
        rule_id = rule["data"]["id"]
        result = CertificationService.delete_rule(db, rule_id)
        assert result["code"] == 200


class TestCertificationRecord:
    def test_apply_with_no_rules(self, db, completed_assessment):
        """无规则时默认通过"""
        pos_id, _, ar_id = completed_assessment
        cert = CertificationService.create_certification(db, CertificationCreate(
            position_id=pos_id, name="认证", code="AR-001"
        ))
        cert_id = cert["data"]["id"]
        result = CertificationService.apply_for_certification(db, 1, CertificationApplyRequest(
            certification_id=cert_id, assessment_record_id=ar_id
        ))
        assert result["code"] == 200
        assert result["data"]["status"] == "pending"
        assert result["data"]["rule_evaluation"]["passed"] is True

    def test_apply_with_passing_score(self, db, completed_assessment):
        """overall_score 规则通过（得分80 >= 75）"""
        pos_id, _, ar_id = completed_assessment
        cert = CertificationService.create_certification(db, CertificationCreate(
            position_id=pos_id, name="认证", code="AR-002"
        ))
        cert_id = cert["data"]["id"]
        CertificationService.add_rule(db, CertificationRuleCreate(
            certification_id=cert_id, rule_type="overall_score", rule_config={"min_score": 75}
        ))
        result = CertificationService.apply_for_certification(db, 1, CertificationApplyRequest(
            certification_id=cert_id, assessment_record_id=ar_id
        ))
        assert result["code"] == 200
        assert result["data"]["rule_evaluation"]["passed"] is True

    def test_apply_with_failing_score(self, db, completed_assessment):
        """overall_score 规则未通过（得分80 < 90）"""
        pos_id, _, ar_id = completed_assessment
        cert = CertificationService.create_certification(db, CertificationCreate(
            position_id=pos_id, name="认证", code="AR-003"
        ))
        cert_id = cert["data"]["id"]
        CertificationService.add_rule(db, CertificationRuleCreate(
            certification_id=cert_id, rule_type="overall_score", rule_config={"min_score": 90}
        ))
        result = CertificationService.apply_for_certification(db, 1, CertificationApplyRequest(
            certification_id=cert_id, assessment_record_id=ar_id
        ))
        assert result["code"] == 200
        assert result["data"]["rule_evaluation"]["passed"] is False

    def test_apply_with_competency_level_pass(self, db, completed_assessment):
        """competency_level 规则通过（等级4 >= 3）"""
        pos_id, comp_id, ar_id = completed_assessment
        cert = CertificationService.create_certification(db, CertificationCreate(
            position_id=pos_id, name="认证", code="AR-004"
        ))
        cert_id = cert["data"]["id"]
        CertificationService.add_rule(db, CertificationRuleCreate(
            certification_id=cert_id,
            rule_type="competency_level",
            rule_config={"competency_id": comp_id, "min_level": 3},
        ))
        result = CertificationService.apply_for_certification(db, 1, CertificationApplyRequest(
            certification_id=cert_id, assessment_record_id=ar_id
        ))
        assert result["code"] == 200
        assert result["data"]["rule_evaluation"]["passed"] is True

    def test_apply_with_all_mandatory_met_pass(self, db, completed_assessment):
        """all_mandatory_met 规则通过（gap=-1 <= 0）"""
        pos_id, _, ar_id = completed_assessment
        cert = CertificationService.create_certification(db, CertificationCreate(
            position_id=pos_id, name="认证", code="AR-005"
        ))
        cert_id = cert["data"]["id"]
        CertificationService.add_rule(db, CertificationRuleCreate(
            certification_id=cert_id,
            rule_type="all_mandatory_met",
            rule_config={"allow_gap": 0},
        ))
        result = CertificationService.apply_for_certification(db, 1, CertificationApplyRequest(
            certification_id=cert_id, assessment_record_id=ar_id
        ))
        assert result["code"] == 200
        assert result["data"]["rule_evaluation"]["passed"] is True

    def test_apply_position_mismatch(self, db, completed_assessment):
        """评估记录的岗位与认证岗位不匹配"""
        pos_id, _, ar_id = completed_assessment
        # 创建另一个岗位
        pos2 = Position(code="BE-001", name="后端工程师", category="technical", level="junior")
        db.add(pos2)
        db.commit()
        db.refresh(pos2)
        cert = CertificationService.create_certification(db, CertificationCreate(
            position_id=pos2.id, name="后端认证", code="AR-006"
        ))
        cert_id = cert["data"]["id"]
        result = CertificationService.apply_for_certification(db, 1, CertificationApplyRequest(
            certification_id=cert_id, assessment_record_id=ar_id
        ))
        assert result["code"] == 400

    def test_approve_record(self, db, completed_assessment):
        """批准认证 → 生成证书编号"""
        pos_id, _, ar_id = completed_assessment
        cert = CertificationService.create_certification(db, CertificationCreate(
            position_id=pos_id, name="认证", code="AP-001", validity_period_months=12
        ))
        cert_id = cert["data"]["id"]
        apply_result = CertificationService.apply_for_certification(db, 1, CertificationApplyRequest(
            certification_id=cert_id, assessment_record_id=ar_id
        ))
        record_id = apply_result["data"]["id"]
        result = CertificationService.approve_record(db, record_id, reviewer_id=2, comment="通过")
        assert result["code"] == 200
        assert result["data"]["status"] == "approved"
        assert result["data"]["certificate_number"] is not None
        assert result["data"]["certificate_number"].startswith("CERT-")
        assert result["data"]["issued_at"] is not None
        assert result["data"]["expires_at"] is not None

    def test_approve_record_failing_rules(self, db, completed_assessment):
        """规则未通过时不能批准"""
        pos_id, _, ar_id = completed_assessment
        cert = CertificationService.create_certification(db, CertificationCreate(
            position_id=pos_id, name="认证", code="AP-002"
        ))
        cert_id = cert["data"]["id"]
        CertificationService.add_rule(db, CertificationRuleCreate(
            certification_id=cert_id, rule_type="overall_score", rule_config={"min_score": 90}
        ))
        apply_result = CertificationService.apply_for_certification(db, 1, CertificationApplyRequest(
            certification_id=cert_id, assessment_record_id=ar_id
        ))
        record_id = apply_result["data"]["id"]
        result = CertificationService.approve_record(db, record_id, reviewer_id=2)
        assert result["code"] == 400

    def test_reject_record(self, db, completed_assessment):
        """拒绝认证"""
        pos_id, _, ar_id = completed_assessment
        cert = CertificationService.create_certification(db, CertificationCreate(
            position_id=pos_id, name="认证", code="AP-003"
        ))
        cert_id = cert["data"]["id"]
        apply_result = CertificationService.apply_for_certification(db, 1, CertificationApplyRequest(
            certification_id=cert_id, assessment_record_id=ar_id
        ))
        record_id = apply_result["data"]["id"]
        result = CertificationService.reject_record(db, record_id, reviewer_id=2, comment="不达标")
        assert result["code"] == 200
        assert result["data"]["status"] == "rejected"
        assert result["data"]["review_comment"] == "不达标"

    def test_get_record_list(self, db, completed_assessment):
        pos_id, _, ar_id = completed_assessment
        cert = CertificationService.create_certification(db, CertificationCreate(
            position_id=pos_id, name="认证", code="AL-001"
        ))
        cert_id = cert["data"]["id"]
        CertificationService.apply_for_certification(db, 1, CertificationApplyRequest(
            certification_id=cert_id, assessment_record_id=ar_id
        ))
        result = CertificationService.get_record_list(db, user_id=1)
        assert result["code"] == 200
        assert result["data"]["total"] == 1

    def test_get_record_detail(self, db, completed_assessment):
        pos_id, _, ar_id = completed_assessment
        cert = CertificationService.create_certification(db, CertificationCreate(
            position_id=pos_id, name="详情认证", code="AD-001"
        ))
        cert_id = cert["data"]["id"]
        apply_result = CertificationService.apply_for_certification(db, 1, CertificationApplyRequest(
            certification_id=cert_id, assessment_record_id=ar_id
        ))
        record_id = apply_result["data"]["id"]
        result = CertificationService.get_record_detail(db, record_id)
        assert result["code"] == 200
        assert result["data"]["certification_name"] == "详情认证"
        assert result["data"]["assessment_score"] == 80.0
