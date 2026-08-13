"""Assessment 域 Service 单元测试"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.domains.position.models import Position, Competency, PositionCompetency
from app.domains.learner.models import LearnerProfile
from app.domains.assessment.models import (
    AssessmentTemplate, AssessmentRecord, CompetencyScore,
    AssessmentStatusEnum,
)
from app.domains.assessment.schemas import (
    AssessmentTemplateCreate, AssessmentTemplateUpdate,
    AssessmentStartRequest, AssessmentSubmitRequest,
)
from app.domains.assessment.service import AssessmentService


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
def position_with_competencies(db):
    """创建带胜任力的岗位，返回 (position_id, [competency_id, ...])"""
    pos = Position(code="FE-001", name="前端工程师", category="technical", level="junior")
    db.add(pos)
    db.commit()
    db.refresh(pos)

    comp_ids = []
    for code, name in [("HTML", "HTML基础"), ("CSS", "CSS样式"), ("JS", "JavaScript编程")]:
        comp = Competency(code=code, name=name, category="technical")
        db.add(comp)
        db.commit()
        db.refresh(comp)
        pc = PositionCompetency(position_id=pos.id, competency_id=comp.id, required_level=3)
        db.add(pc)
        comp_ids.append(comp.id)
    db.commit()
    return pos.id, comp_ids


class TestAssessmentTemplateService:
    def test_create_template(self, db, position_with_competencies):
        pos_id, comp_ids = position_with_competencies
        data = AssessmentTemplateCreate(
            position_id=pos_id,
            name="前端初级评估",
            competency_configs=[
                {"competency_id": comp_ids[0], "question_count": 5, "difficulty": 2, "assessment_method": "quiz"},
                {"competency_id": comp_ids[1], "question_count": 3, "difficulty": 2, "assessment_method": "quiz"},
            ],
            pass_threshold=60.0,
        )
        result = AssessmentService.create_template(db, data)
        assert result["code"] == 200
        assert result["data"]["name"] == "前端初级评估"
        assert result["data"]["position_id"] == pos_id
        assert len(result["data"]["competency_configs"]) == 2

    def test_create_template_invalid_position(self, db):
        data = AssessmentTemplateCreate(position_id=999, name="无效模板")
        result = AssessmentService.create_template(db, data)
        assert result["code"] == 404

    def test_get_template_list(self, db, position_with_competencies):
        pos_id, _ = position_with_competencies
        AssessmentService.create_template(db, AssessmentTemplateCreate(position_id=pos_id, name="模板1"))
        AssessmentService.create_template(db, AssessmentTemplateCreate(position_id=pos_id, name="模板2"))
        result = AssessmentService.get_template_list(db, page=1, page_size=10)
        assert result["code"] == 200
        assert result["data"]["total"] == 2

    def test_get_template_list_by_position(self, db, position_with_competencies):
        pos_id, _ = position_with_competencies
        # 创建另一个岗位
        pos2 = Position(code="BE-001", name="后端工程师")
        db.add(pos2)
        db.commit()
        db.refresh(pos2)

        AssessmentService.create_template(db, AssessmentTemplateCreate(position_id=pos_id, name="前端模板"))
        AssessmentService.create_template(db, AssessmentTemplateCreate(position_id=pos2.id, name="后端模板"))
        result = AssessmentService.get_template_list(db, page=1, page_size=10, position_id=pos_id)
        assert result["data"]["total"] == 1

    def test_get_template_by_id(self, db, position_with_competencies):
        pos_id, _ = position_with_competencies
        create_result = AssessmentService.create_template(db, AssessmentTemplateCreate(position_id=pos_id, name="模板"))
        tid = create_result["data"]["id"]
        result = AssessmentService.get_template_by_id(db, tid)
        assert result["code"] == 200
        assert result["data"]["name"] == "模板"

    def test_update_template(self, db, position_with_competencies):
        pos_id, _ = position_with_competencies
        create_result = AssessmentService.create_template(db, AssessmentTemplateCreate(position_id=pos_id, name="旧名称"))
        tid = create_result["data"]["id"]
        result = AssessmentService.update_template(db, tid, AssessmentTemplateUpdate(name="新名称", pass_threshold=75.0))
        assert result["code"] == 200
        assert result["data"]["name"] == "新名称"
        assert result["data"]["pass_threshold"] == 75.0

    def test_delete_template(self, db, position_with_competencies):
        pos_id, _ = position_with_competencies
        create_result = AssessmentService.create_template(db, AssessmentTemplateCreate(position_id=pos_id, name="模板"))
        tid = create_result["data"]["id"]
        result = AssessmentService.delete_template(db, tid)
        assert result["code"] == 200


class TestAssessmentRecordService:
    def _create_learner(self, db, user_id=1):
        learner = LearnerProfile(user_id=user_id, real_name=f"学习者{user_id}")
        db.add(learner)
        db.commit()
        db.refresh(learner)
        return learner

    def test_start_assessment(self, db, position_with_competencies):
        pos_id, comp_ids = position_with_competencies
        tpl_result = AssessmentService.create_template(db, AssessmentTemplateCreate(
            position_id=pos_id,
            name="评估模板",
            competency_configs=[{"competency_id": cid, "question_count": 3} for cid in comp_ids],
        ))
        tid = tpl_result["data"]["id"]
        result = AssessmentService.start_assessment(db, user_id=1, template_id=tid, learner_id=None)
        assert result["code"] == 200
        assert result["data"]["status"] == "in_progress"
        assert result["data"]["position_id"] == pos_id

    def test_start_assessment_invalid_template(self, db):
        result = AssessmentService.start_assessment(db, user_id=1, template_id=999, learner_id=None)
        assert result["code"] == 404

    def test_start_assessment_binds_selected_learner(self, db, position_with_competencies):
        pos_id, comp_ids = position_with_competencies
        learner = self._create_learner(db, user_id=7)
        tpl_result = AssessmentService.create_template(db, AssessmentTemplateCreate(
            position_id=pos_id,
            name="指定学习者评估",
            competency_configs=[{"competency_id": cid, "question_count": 3} for cid in comp_ids],
        ))
        result = AssessmentService.start_assessment(
            db, user_id=99, template_id=tpl_result["data"]["id"], learner_id=learner.id,
        )
        assert result["code"] == 200
        assert result["data"]["learner_id"] == learner.id
        assert result["data"]["user_id"] == 7

    def test_submit_assessment(self, db, position_with_competencies):
        pos_id, comp_ids = position_with_competencies
        tpl_result = AssessmentService.create_template(db, AssessmentTemplateCreate(
            position_id=pos_id,
            name="评估模板",
            competency_configs=[{"competency_id": cid, "question_count": 3} for cid in comp_ids],
        ))
        tid = tpl_result["data"]["id"]
        start_result = AssessmentService.start_assessment(db, user_id=1, template_id=tid)
        rid = start_result["data"]["id"]

        scores = [
            {"competency_id": comp_ids[0], "current_level": 3, "current_score": 75, "assessment_method": "quiz"},
            {"competency_id": comp_ids[1], "current_level": 2, "current_score": 50, "assessment_method": "quiz"},
            {"competency_id": comp_ids[2], "current_level": 4, "current_score": 90, "assessment_method": "quiz"},
        ]
        result = AssessmentService.submit_assessment(db, rid, AssessmentSubmitRequest(scores=scores))
        assert result["code"] == 200
        assert result["data"]["status"] == "completed"
        assert result["data"]["overall_score"] is not None
        assert len(result["data"]["competency_scores"]) == 3

    def test_submit_assessment_invalid_record(self, db):
        result = AssessmentService.submit_assessment(db, 999, AssessmentSubmitRequest(scores=[]))
        assert result["code"] == 404

    def test_get_record_detail(self, db, position_with_competencies):
        pos_id, comp_ids = position_with_competencies
        tpl_result = AssessmentService.create_template(db, AssessmentTemplateCreate(
            position_id=pos_id, name="模板",
            competency_configs=[{"competency_id": comp_ids[0], "question_count": 3}],
        ))
        tid = tpl_result["data"]["id"]
        start_result = AssessmentService.start_assessment(db, user_id=1, template_id=tid)
        rid = start_result["data"]["id"]
        result = AssessmentService.get_record_detail(db, rid)
        assert result["code"] == 200
        assert result["data"]["id"] == rid

    def test_get_record_list(self, db, position_with_competencies):
        pos_id, _ = position_with_competencies
        tpl_result = AssessmentService.create_template(db, AssessmentTemplateCreate(position_id=pos_id, name="模板"))
        tid = tpl_result["data"]["id"]
        AssessmentService.start_assessment(db, user_id=1, template_id=tid)
        AssessmentService.start_assessment(db, user_id=2, template_id=tid)
        result = AssessmentService.get_record_list(db, page=1, page_size=10)
        assert result["data"]["total"] == 2

    def test_get_record_list_by_user(self, db, position_with_competencies):
        pos_id, _ = position_with_competencies
        tpl_result = AssessmentService.create_template(db, AssessmentTemplateCreate(position_id=pos_id, name="模板"))
        tid = tpl_result["data"]["id"]
        AssessmentService.start_assessment(db, user_id=1, template_id=tid)
        AssessmentService.start_assessment(db, user_id=2, template_id=tid)
        result = AssessmentService.get_record_list(db, page=1, page_size=10, user_id=1)
        assert result["data"]["total"] == 1

    def test_get_record_list_by_learner(self, db, position_with_competencies):
        pos_id, _ = position_with_competencies
        learner_one = self._create_learner(db, user_id=1)
        learner_two = self._create_learner(db, user_id=2)
        tpl_result = AssessmentService.create_template(db, AssessmentTemplateCreate(position_id=pos_id, name="模板"))
        tid = tpl_result["data"]["id"]
        AssessmentService.start_assessment(db, user_id=99, template_id=tid, learner_id=learner_one.id)
        AssessmentService.start_assessment(db, user_id=99, template_id=tid, learner_id=learner_two.id)
        result = AssessmentService.get_record_list(
            db, page=1, page_size=10, learner_id=learner_two.id, is_staff=True,
        )
        assert result["data"]["total"] == 1
        assert result["data"]["items"][0]["learner_id"] == learner_two.id


class TestGapAnalysisService:
    def test_gap_analysis_all_met(self, db, position_with_competencies):
        pos_id, comp_ids = position_with_competencies
        tpl_result = AssessmentService.create_template(db, AssessmentTemplateCreate(
            position_id=pos_id, name="模板", pass_threshold=60.0,
            competency_configs=[{"competency_id": cid, "question_count": 3} for cid in comp_ids],
        ))
        tid = tpl_result["data"]["id"]
        start_result = AssessmentService.start_assessment(db, user_id=1, template_id=tid)
        rid = start_result["data"]["id"]
        # 全部达到 required_level=3
        scores = [{"competency_id": cid, "current_level": 4, "current_score": 85} for cid in comp_ids]
        AssessmentService.submit_assessment(db, rid, AssessmentSubmitRequest(scores=scores))

        result = AssessmentService.get_gap_analysis(db, rid)
        assert result["code"] == 200
        assert result["data"]["met_count"] == 3
        assert result["data"]["gap_count"] == 0
        assert result["data"]["is_passed"] is True

    def test_gap_analysis_with_gaps(self, db, position_with_competencies):
        pos_id, comp_ids = position_with_competencies
        tpl_result = AssessmentService.create_template(db, AssessmentTemplateCreate(
            position_id=pos_id, name="模板", pass_threshold=60.0,
            competency_configs=[{"competency_id": cid, "question_count": 3} for cid in comp_ids],
        ))
        tid = tpl_result["data"]["id"]
        start_result = AssessmentService.start_assessment(db, user_id=1, template_id=tid)
        rid = start_result["data"]["id"]
        # 第一个达标，第二个差1级，第三个差2级
        scores = [
            {"competency_id": comp_ids[0], "current_level": 3, "current_score": 70},
            {"competency_id": comp_ids[1], "current_level": 2, "current_score": 45},
            {"competency_id": comp_ids[2], "current_level": 1, "current_score": 30},
        ]
        AssessmentService.submit_assessment(db, rid, AssessmentSubmitRequest(scores=scores))

        result = AssessmentService.get_gap_analysis(db, rid)
        assert result["code"] == 200
        assert result["data"]["met_count"] == 1
        assert result["data"]["gap_count"] == 2
        gaps = {g["competency_id"]: g for g in result["data"]["gaps"]}
        assert gaps[comp_ids[1]]["gap"] == 1
        assert gaps[comp_ids[2]]["gap"] == 2
        assert gaps[comp_ids[1]]["is_met"] is False

    def test_gap_analysis_not_completed(self, db, position_with_competencies):
        pos_id, _ = position_with_competencies
        tpl_result = AssessmentService.create_template(db, AssessmentTemplateCreate(position_id=pos_id, name="模板"))
        tid = tpl_result["data"]["id"]
        start_result = AssessmentService.start_assessment(db, user_id=1, template_id=tid)
        rid = start_result["data"]["id"]
        # 未提交，状态为 in_progress
        result = AssessmentService.get_gap_analysis(db, rid)
        assert result["code"] == 400
