"""Training 域 Service 单元测试"""
import pytest
from datetime import datetime, date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.domains.position.models import Position, Competency, PositionCompetency
from app.domains.assessment.models import (
    AssessmentTemplate, AssessmentRecord, CompetencyScore,
    AssessmentStatusEnum,
)
from app.domains.certification.models import Certification
from app.domains.training.models import (
    TrainingProject, TrainingEnrollment, TrainingPlan,
    TrainingTaskPackage,
    ProjectStatusEnum, EnrollmentStatusEnum, PlanStatusEnum,
)
from app.domains.training.schemas import (
    TrainingProjectCreate, TrainingProjectUpdate, TaskPackageCreate, SubmissionCreate, SubmissionReview,
)
from app.domains.training.service import TrainingService


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
    """创建带胜任力的岗位"""
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
    return pos.id, comp.id


@pytest.fixture
def completed_assessment_with_gap(db, position_with_competencies):
    """创建一个已完成的评估记录（含差距：current_level=1, required_level=3, gap=2）"""
    pos_id, comp_id = position_with_competencies

    tpl = AssessmentTemplate(position_id=pos_id, name="评估模板", pass_threshold=60.0)
    db.add(tpl)
    db.commit()
    db.refresh(tpl)

    record = AssessmentRecord(
        template_id=tpl.id,
        user_id=1,
        position_id=pos_id,
        status=AssessmentStatusEnum.COMPLETED.value,
        overall_score=50.0,
        overall_level=2,
        started_at=datetime.now(),
        completed_at=datetime.now(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    cs = CompetencyScore(
        assessment_record_id=record.id,
        competency_id=comp_id,
        current_level=1,
        current_score=40.0,
        required_level=3,
        gap=2,
        assessment_method="quiz",
    )
    db.add(cs)
    db.commit()
    return pos_id, comp_id, record.id


@pytest.fixture
def active_project(db, position_with_competencies):
    """创建一个 active 状态的培训项目"""
    pos_id, _ = position_with_competencies
    project = TrainingProject(
        name="前端入职培训",
        position_id=pos_id,
        project_type="onboard",
        status=ProjectStatusEnum.ACTIVE.value,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 6, 30),
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project.id


class TestTrainingProjectCRUD:
    def test_create_project(self, db, position_with_competencies):
        pos_id, _ = position_with_competencies
        data = TrainingProjectCreate(
            name="新员工培训",
            position_id=pos_id,
            project_type="onboard",
            enterprise_name="技术公司",
        )
        result = TrainingService.create_project(db, data, user_id=1)
        assert result["code"] == 200
        assert result["data"]["name"] == "新员工培训"
        assert result["data"]["status"] == ProjectStatusEnum.DRAFT.value

    def test_create_project_invalid_position(self, db):
        data = TrainingProjectCreate(name="测试", position_id=999)
        result = TrainingService.create_project(db, data, user_id=1)
        assert result["code"] == 404

    def test_get_project_list(self, db, active_project):
        result = TrainingService.get_project_list(db, page=1, page_size=10)
        assert result["code"] == 200
        assert result["data"]["total"] >= 1

    def test_get_project_list_hides_drafts_for_learners(self, db, position_with_competencies, active_project):
        pos_id, _ = position_with_competencies
        db.add(TrainingProject(name="草稿项目", position_id=pos_id, status=ProjectStatusEnum.DRAFT.value))
        db.commit()
        result = TrainingService.get_project_list(db, page=1, page_size=10)
        assert result["code"] == 200
        assert all(item["status"] == ProjectStatusEnum.ACTIVE.value for item in result["data"]["items"])

    def test_get_project_list_ignores_requested_draft_status_for_learners(self, db, position_with_competencies):
        pos_id, _ = position_with_competencies
        db.add(TrainingProject(name="草稿项目", position_id=pos_id, status=ProjectStatusEnum.DRAFT.value))
        db.commit()
        result = TrainingService.get_project_list(db, status=ProjectStatusEnum.DRAFT.value)
        assert result["code"] == 200
        assert result["data"]["total"] == 0

    def test_get_project_by_id(self, db, active_project):
        result = TrainingService.get_project_by_id(db, active_project)
        assert result["code"] == 200
        assert result["data"]["name"] == "前端入职培训"
        assert result["data"]["position_name"] == "前端工程师"
        assert result["data"]["enrollment_count"] == 0

    def test_update_project(self, db, active_project):
        result = TrainingService.update_project(db, active_project, TrainingProjectUpdate(
            name="更新后的培训",
            status="archived",
        ))
        assert result["code"] == 200
        assert result["data"]["name"] == "更新后的培训"
        assert result["data"]["status"] == "archived"

    def test_delete_project(self, db, active_project):
        result = TrainingService.delete_project(db, active_project)
        assert result["code"] == 200
        result2 = TrainingService.get_project_by_id(db, active_project)
        assert result2["code"] == 404


class TestEnrollment:
    def test_enroll_success(self, db, active_project):
        result = TrainingService.enroll(db, active_project, user_id=1)
        assert result["code"] == 200
        assert result["data"]["status"] == EnrollmentStatusEnum.ENROLLED.value

    def test_enroll_duplicate(self, db, active_project):
        first = TrainingService.enroll(db, active_project, user_id=1)
        assert first["code"] == 200
        second = TrainingService.enroll(db, active_project, user_id=1)
        # 幂等报名：已报名时返回已有记录而非报错
        assert second["code"] == 200
        assert second["data"]["id"] == first["data"]["id"]

    def test_enroll_inactive_project(self, db, position_with_competencies):
        pos_id, _ = position_with_competencies
        project = TrainingProject(name="草稿项目", position_id=pos_id, status=ProjectStatusEnum.DRAFT.value)
        db.add(project)
        db.commit()
        db.refresh(project)
        result = TrainingService.enroll(db, project.id, user_id=1)
        assert result["code"] == 400

    def test_get_enrollments(self, db, active_project):
        TrainingService.enroll(db, active_project, user_id=1)
        TrainingService.enroll(db, active_project, user_id=2)
        result = TrainingService.get_enrollments(db, active_project)
        assert result["code"] == 200
        assert result["data"]["total"] == 2


class TestTrainingPlan:
    def test_generate_plan_with_gap(self, db, active_project, completed_assessment_with_gap):
        """生成学习计划（有差距项）"""
        pos_id, comp_id, ar_id = completed_assessment_with_gap
        enroll_result = TrainingService.enroll(db, active_project, user_id=1)
        enrollment_id = enroll_result["data"]["id"]

        result = TrainingService.generate_plan(db, enrollment_id, user_id=1, assessment_record_id=ar_id)
        assert result["code"] == 200
        assert result["data"]["total_stages"] >= 1
        assert result["data"]["status"] == PlanStatusEnum.ACTIVE.value
        assert result["data"]["progress"] == 0.0
        assert len(result["data"]["plan_content"]) >= 1
        # 验证计划内容包含差距胜任力
        stage = result["data"]["plan_content"][0]
        assert comp_id in stage["competency_ids"]

    def test_generate_plan_invalid_assessment(self, db, active_project):
        enroll_result = TrainingService.enroll(db, active_project, user_id=1)
        enrollment_id = enroll_result["data"]["id"]
        result = TrainingService.generate_plan(db, enrollment_id, user_id=1, assessment_record_id=999)
        assert result["code"] == 404

    def test_generate_plan_wrong_user(self, db, active_project, completed_assessment_with_gap):
        _, _, ar_id = completed_assessment_with_gap
        enroll_result = TrainingService.enroll(db, active_project, user_id=1)
        enrollment_id = enroll_result["data"]["id"]
        result = TrainingService.generate_plan(db, enrollment_id, user_id=999, assessment_record_id=ar_id)
        assert result["code"] == 400

    def test_generate_plan_rejects_assessment_from_another_position(self, db, active_project, completed_assessment_with_gap):
        _, _, ar_id = completed_assessment_with_gap
        other_position = Position(code="BE-001", name="后端工程师")
        db.add(other_position)
        db.commit()
        other_project = TrainingProject(
            name="后端培训", position_id=other_position.id,
            status=ProjectStatusEnum.ACTIVE.value,
        )
        db.add(other_project)
        db.commit()
        db.refresh(other_project)
        enrollment_id = TrainingService.enroll(db, other_project.id, user_id=1)["data"]["id"]
        result = TrainingService.generate_plan(db, enrollment_id, user_id=1, assessment_record_id=ar_id)
        assert result["code"] == 400

    def test_get_plan(self, db, active_project, completed_assessment_with_gap):
        _, _, ar_id = completed_assessment_with_gap
        enroll_result = TrainingService.enroll(db, active_project, user_id=1)
        enrollment_id = enroll_result["data"]["id"]
        TrainingService.generate_plan(db, enrollment_id, user_id=1, assessment_record_id=ar_id)
        result = TrainingService.get_plan(db, enrollment_id, user_id=1)
        assert result["code"] == 200
        assert result["data"]["total_stages"] >= 1

    def test_update_progress(self, db, active_project, completed_assessment_with_gap):
        _, _, ar_id = completed_assessment_with_gap
        enroll_result = TrainingService.enroll(db, active_project, user_id=1)
        enrollment_id = enroll_result["data"]["id"]
        plan_result = TrainingService.generate_plan(db, enrollment_id, user_id=1, assessment_record_id=ar_id)
        plan_id = plan_result["data"]["id"]
        total = plan_result["data"]["total_stages"]

        result = TrainingService.update_progress(db, plan_id, completed_stages=1, user_id=1)
        assert result["code"] == 200
        assert result["data"]["completed_stages"] == 1
        expected_progress = round(1 / total * 100, 1)
        assert result["data"]["progress"] == expected_progress

    def test_update_progress_complete(self, db, active_project, completed_assessment_with_gap):
        """完成所有阶段 → 计划状态变为 completed"""
        _, _, ar_id = completed_assessment_with_gap
        enroll_result = TrainingService.enroll(db, active_project, user_id=1)
        enrollment_id = enroll_result["data"]["id"]
        plan_result = TrainingService.generate_plan(db, enrollment_id, user_id=1, assessment_record_id=ar_id)
        plan_id = plan_result["data"]["id"]
        total = plan_result["data"]["total_stages"]

        result = TrainingService.update_progress(db, plan_id, completed_stages=total, user_id=1)
        assert result["code"] == 200
        assert result["data"]["status"] == PlanStatusEnum.COMPLETED.value
        assert result["data"]["progress"] == 100.0

    def test_update_progress_invalid(self, db, active_project, completed_assessment_with_gap):
        """无效阶段数"""
        _, _, ar_id = completed_assessment_with_gap
        enroll_result = TrainingService.enroll(db, active_project, user_id=1)
        enrollment_id = enroll_result["data"]["id"]
        plan_result = TrainingService.generate_plan(db, enrollment_id, user_id=1, assessment_record_id=ar_id)
        plan_id = plan_result["data"]["id"]

        result = TrainingService.update_progress(db, plan_id, completed_stages=999, user_id=1)
        assert result["code"] == 400

    def test_update_progress_rejects_other_user(self, db, active_project, completed_assessment_with_gap):
        _, _, ar_id = completed_assessment_with_gap
        enrollment_id = TrainingService.enroll(db, active_project, user_id=1)["data"]["id"]
        plan_id = TrainingService.generate_plan(
            db, enrollment_id, user_id=1, assessment_record_id=ar_id,
        )["data"]["id"]
        result = TrainingService.update_progress(db, plan_id, completed_stages=1, user_id=999)
        assert result["code"] == 400


class TestCompleteEnrollment:
    def test_complete_enrollment(self, db, active_project):
        enroll_result = TrainingService.enroll(db, active_project, user_id=1)
        enrollment_id = enroll_result["data"]["id"]
        result = TrainingService.complete_enrollment(db, enrollment_id, user_id=1, final_score=85.0)
        assert result["code"] == 200
        assert result["data"]["status"] == EnrollmentStatusEnum.COMPLETED.value
        assert result["data"]["final_score"] == 85.0
        assert result["data"]["completed_at"] is not None

    def test_complete_already_completed(self, db, active_project):
        enroll_result = TrainingService.enroll(db, active_project, user_id=1)
        enrollment_id = enroll_result["data"]["id"]
        TrainingService.complete_enrollment(db, enrollment_id, user_id=1)
        result = TrainingService.complete_enrollment(db, enrollment_id, user_id=1)
        assert result["code"] == 400


class TestTrainingTaskPackages:
    def test_submit_and_review_task(self, db, active_project):
        package = TrainingService.create_task_package(
            db,
            active_project,
            TaskPackageCreate(
                name="接口实操",
                rubrics=[{"criterion": "功能完成度", "weight": 1}, {"criterion": "代码质量", "weight": 1}],
            ),
            user_id=9,
        )["data"]
        enrollment_id = TrainingService.enroll(db, active_project, user_id=1)["data"]["id"]
        submission = TrainingService.create_submission(
            db, package["id"], enrollment_id, user_id=1,
            data=SubmissionCreate(content="已完成接口和测试"),
        )["data"]
        assert submission["status"] == "submitted"
        result = TrainingService.review_submission(
            db,
            submission["id"],
            reviewer_id=9,
            data=SubmissionReview(
                scores=[{"rubric_id": package["rubrics"][0]["id"], "score": 80}, {"rubric_id": package["rubrics"][1]["id"], "score": 100}],
                status="passed",
                teacher_comment="符合要求",
            ),
        )
        assert result["code"] == 200
        assert result["data"]["status"] == "passed"
        assert result["data"]["overall_score"] == 90.0

    def test_learner_cannot_submit_other_enrollment(self, db, active_project):
        package = TrainingService.create_task_package(db, active_project, TaskPackageCreate(name="实操"), user_id=9)["data"]
        enrollment_id = TrainingService.enroll(db, active_project, user_id=1)["data"]["id"]
        result = TrainingService.create_submission(db, package["id"], enrollment_id, user_id=2, data=SubmissionCreate(content="越权"))
        assert result["code"] == 400

    def test_dashboard_scoped_to_learner(self, db, active_project):
        package = TrainingService.create_task_package(db, active_project, TaskPackageCreate(name="实操"), user_id=9)["data"]
        enrollment_id = TrainingService.enroll(db, active_project, user_id=1)["data"]["id"]
        TrainingService.create_submission(db, package["id"], enrollment_id, user_id=1, data=SubmissionCreate(content="提交"))
        learner = TrainingService.dashboard_overview(db, user_id=1, is_staff=False)["data"]
        assert learner["enrollment_count"] == 1
        assert learner["submission_count"] == 1
