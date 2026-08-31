"""
培训项目域 Service 层
"""
import json
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session

from app.domains.training.models import (
    TrainingProject, TrainingEnrollment, TrainingPlan,
    TrainingTaskPackage, TrainingTaskRubric, TrainingSubmission, TrainingSubmissionScore,
    ProjectStatusEnum, EnrollmentStatusEnum, PlanStatusEnum,
)
from app.domains.training.schemas import (
    TrainingProjectCreate, TrainingProjectUpdate, TaskPackageCreate, TaskPackageUpdate,
    SubmissionCreate, SubmissionReview,
)
from app.domains.position.models import Position, Competency, PositionCompetency
from app.domains.learner.models import LearnerProfile
from app.domains.assessment.models import (
    AssessmentRecord, CompetencyScore, AssessmentStatusEnum,
)
from app.domains.certification.models import Certification, CertificationRecord, CertificationStatusEnum
from app.schemas.response import (
    success as _success,
    bad_request as _bad_request,
    not_found as _not_found,
)
from app.utils.logger import LoggerUtil
from app.utils.llm import LLMUtil


def _unwrap(resp) -> Dict[str, Any]:
    """将 JSONResponse 解包为 dict"""
    return json.loads(resp.body)


def success(data: Any = None, message: str = "操作成功") -> Dict[str, Any]:
    return _unwrap(_success(data=data, message=message))


def bad_request(message: str = "请求参数错误", data: Any = None) -> Dict[str, Any]:
    return _unwrap(_bad_request(message=message, data=data))


def not_found(message: str = "资源不存在") -> Dict[str, Any]:
    return _unwrap(_not_found(message=message))


class TrainingService:
    """培训项目域服务"""

    PROJECT_TYPE_ALIASES = {
        "onboarding": "onboard",
        "reskilling": "transfer",
        "upskilling": "upskill",
        "certification": "compliance",
    }

    # ===========================================
    # 培训项目 CRUD
    # ===========================================

    @staticmethod
    def create_project(db: Session, data: TrainingProjectCreate, user_id: int) -> Dict[str, Any]:
        position = db.query(Position).filter(Position.id == data.position_id).first()
        if not position:
            return not_found(message="岗位不存在")

        if data.certification_id:
            cert = db.query(Certification).filter(Certification.id == data.certification_id).first()
            if not cert:
                return not_found(message="认证不存在")

        project = TrainingProject(
            name=data.name,
            description=data.description,
            position_id=data.position_id,
            certification_id=data.certification_id,
            project_type=TrainingService._normalize_project_type(data.project_type),
            enterprise_name=data.enterprise_name,
            start_date=data.start_date,
            end_date=data.end_date,
            config=data.config,
            created_by=user_id,
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return success(data=TrainingService._project_to_response(project), message="培训项目创建成功")

    @staticmethod
    def get_project_list(
        db: Session, page: int = 1, page_size: int = 20,
        status: Optional[str] = None, keyword: Optional[str] = None,
        position_id: Optional[int] = None, is_staff: bool = False,
    ) -> Dict[str, Any]:
        query = db.query(TrainingProject)
        if not is_staff:
            query = query.filter(TrainingProject.status == ProjectStatusEnum.ACTIVE.value)
        elif status:
            query = query.filter(TrainingProject.status == status)
        if keyword:
            query = query.filter(TrainingProject.name.contains(keyword))
        if position_id:
            query = query.filter(TrainingProject.position_id == position_id)
        total = query.count()
        items = query.order_by(TrainingProject.created_at.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        return success(data={
            "items": [TrainingService._project_to_response(p) for p in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        })

    @staticmethod
    def get_project_by_id(db: Session, project_id: int, is_staff: bool = False) -> Dict[str, Any]:
        project = db.query(TrainingProject).filter(TrainingProject.id == project_id).first()
        if not project:
            return not_found(message="培训项目不存在")
        if project.status != ProjectStatusEnum.ACTIVE.value and not is_staff:
            return not_found(message="培训项目不存在")
        result = TrainingService._project_to_response(project)
        # 附带岗位名称
        pos = db.query(Position).filter(Position.id == project.position_id).first()
        result["position_name"] = pos.name if pos else None
        if project.certification_id:
            cert = db.query(Certification).filter(Certification.id == project.certification_id).first()
            result["certification_name"] = cert.name if cert else None
        # 附带报名数
        enrollment_count = db.query(TrainingEnrollment).filter(
            TrainingEnrollment.project_id == project_id
        ).count()
        result["enrollment_count"] = enrollment_count
        return success(data=result)

    @staticmethod
    def update_project(db: Session, project_id: int, data: TrainingProjectUpdate) -> Dict[str, Any]:
        project = db.query(TrainingProject).filter(TrainingProject.id == project_id).first()
        if not project:
            return not_found(message="培训项目不存在")
        update_data = data.model_dump(exclude_unset=True)
        if "project_type" in update_data:
            update_data["project_type"] = TrainingService._normalize_project_type(update_data["project_type"])
        for key, value in update_data.items():
            setattr(project, key, value)
        db.commit()
        db.refresh(project)
        return success(data=TrainingService._project_to_response(project), message="更新成功")

    @staticmethod
    def delete_project(db: Session, project_id: int) -> Dict[str, Any]:
        project = db.query(TrainingProject).filter(TrainingProject.id == project_id).first()
        if not project:
            return not_found(message="培训项目不存在")
        db.delete(project)
        db.commit()
        return success(message="删除成功")

    # ===========================================
    # 报名管理
    # ===========================================

    @staticmethod
    def enroll(
        db: Session, project_id: int, user_id: int,
        learner_id: Optional[int] = None, is_staff: bool = False,
    ) -> Dict[str, Any]:
        project = db.query(TrainingProject).filter(TrainingProject.id == project_id).first()
        if not project:
            return not_found(message="培训项目不存在")
        if project.status != ProjectStatusEnum.ACTIVE.value:
            return bad_request(message="项目不在报名中")

        if learner_id:
            learner = db.query(LearnerProfile).filter(LearnerProfile.id == learner_id).first()
            if not learner:
                return not_found(message="学习者不存在")
            if learner.user_id != user_id and not is_staff:
                return bad_request(message="只能为本人关联的学习者报名")
            enrollment_user_id = learner.user_id
        else:
            enrollment_user_id = user_id

        existing = db.query(TrainingEnrollment).filter(
            TrainingEnrollment.project_id == project_id,
            TrainingEnrollment.user_id == enrollment_user_id,
        ).first()
        if existing:
            return success(data=TrainingService._enrollment_to_response(existing), message="已报名该培训项目")

        enrollment = TrainingEnrollment(
            project_id=project_id,
            user_id=enrollment_user_id,
            learner_id=learner_id,
            status=EnrollmentStatusEnum.ENROLLED.value,
        )
        db.add(enrollment)
        db.commit()
        db.refresh(enrollment)
        return success(data=TrainingService._enrollment_to_response(enrollment), message="报名成功")

    @staticmethod
    def get_enrollments(db: Session, project_id: int, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        project = db.query(TrainingProject).filter(TrainingProject.id == project_id).first()
        if not project:
            return not_found(message="培训项目不存在")
        query = db.query(TrainingEnrollment).filter(TrainingEnrollment.project_id == project_id)
        total = query.count()
        items = query.order_by(TrainingEnrollment.enrolled_at.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        return success(data={
            "items": [TrainingService._enrollment_to_response(e) for e in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        })

    @staticmethod
    def get_enrollment(
        db: Session, project_id: int, user_id: int,
        learner_id: Optional[int] = None, is_staff: bool = False,
    ) -> Dict[str, Any]:
        """查询当前用户在项目中的报名状态，不产生报名副作用。"""
        query = db.query(TrainingEnrollment).filter(TrainingEnrollment.project_id == project_id)
        if learner_id:
            query = query.filter(TrainingEnrollment.learner_id == learner_id)
            if not is_staff:
                query = query.filter(TrainingEnrollment.user_id == user_id)
        else:
            query = query.filter(TrainingEnrollment.user_id == user_id)
        enrollment = query.first()
        return success(data=TrainingService._enrollment_to_response(enrollment) if enrollment else None)

    @staticmethod
    def validate_training_context(
        db: Session, learner_id: int, context: Optional[Dict[str, Any]],
    ) -> Optional[str]:
        """Validate a stage context against the persisted training plan."""
        if not context:
            return None
        try:
            project_id = int(context.get("project_id", context.get("projectId")))
            enrollment_id = int(context.get("enrollment_id", context.get("enrollmentId")))
            plan_id = int(context.get("plan_id", context.get("planId")))
            position_id = int(context.get("position_id", context.get("positionId")))
            stage_data = context.get("stage") or {}
            stage_number = int(stage_data.get("stage"))
        except (TypeError, ValueError):
            return "岗位培训上下文格式无效"

        enrollment = db.query(TrainingEnrollment).filter(TrainingEnrollment.id == enrollment_id).first()
        plan = db.query(TrainingPlan).filter(TrainingPlan.id == plan_id).first()
        project = db.query(TrainingProject).filter(TrainingProject.id == project_id).first()
        if not enrollment or not plan or not project:
            return "岗位培训上下文对应的记录不存在"
        if enrollment.project_id != project_id or plan.enrollment_id != enrollment_id:
            return "岗位培训上下文关联关系无效"

        learner = db.query(LearnerProfile).filter(LearnerProfile.id == learner_id).first()
        if not learner:
            return "学习者不存在"
        if enrollment.learner_id is not None:
            learner_matches_enrollment = enrollment.learner_id == learner_id
        else:
            learner_matches_enrollment = learner.user_id == enrollment.user_id
        if (
            project.position_id != position_id
            or plan.user_id != enrollment.user_id
            or (plan.learner_id is not None and plan.learner_id != learner_id)
            or not learner_matches_enrollment
        ):
            return "岗位培训上下文与学习者或岗位不匹配"

        stages = plan.plan_content or []
        persisted_stage = next((stage for stage in stages if stage.get("stage") == stage_number), None)
        if not persisted_stage:
            return "岗位培训阶段不存在"

        requested_ids = stage_data.get("competency_ids", stage_data.get("competencyIds", [])) or []
        persisted_ids = persisted_stage.get("competency_ids", persisted_stage.get("competencyIds", [])) or []
        try:
            requested_id_set = {int(value) for value in requested_ids}
            persisted_id_set = {int(value) for value in persisted_ids}
        except (TypeError, ValueError):
            return "岗位培训阶段能力与计划不匹配"
        if requested_id_set != persisted_id_set:
            return "岗位培训阶段能力与计划不匹配"
        return None

    # ===========================================
    # AI 学习计划生成
    # ===========================================

    @staticmethod
    def generate_plan(db: Session, enrollment_id: int, user_id: int, assessment_record_id: int, is_staff: bool = False) -> Dict[str, Any]:
        enrollment = db.query(TrainingEnrollment).filter(TrainingEnrollment.id == enrollment_id).first()
        if not enrollment:
            return not_found(message="报名记录不存在")
        if enrollment.user_id != user_id and not is_staff:
            return bad_request(message="无权操作此报名记录")

        project = db.query(TrainingProject).filter(TrainingProject.id == enrollment.project_id).first()
        if not project:
            return not_found(message="培训项目不存在")

        ar = db.query(AssessmentRecord).filter(AssessmentRecord.id == assessment_record_id).first()
        if not ar:
            return not_found(message="评估记录不存在")
        if ar.status != AssessmentStatusEnum.COMPLETED.value:
            return bad_request(message="评估尚未完成")
        if ar.position_id != project.position_id:
            return bad_request(message="评估记录与培训项目岗位不匹配")
        if enrollment.learner_id and ar.learner_id != enrollment.learner_id:
            return bad_request(message="评估记录与报名学习者不匹配")
        if not enrollment.learner_id and ar.user_id != enrollment.user_id:
            return bad_request(message="评估记录与报名用户不匹配")
        if not is_staff and ar.user_id != user_id:
            return bad_request(message="无权使用此评估记录")

        # 获取差距数据
        scores = db.query(CompetencyScore).filter(
            CompetencyScore.assessment_record_id == assessment_record_id
        ).all()

        gap_competencies = []
        for cs in scores:
            comp = db.query(Competency).filter(Competency.id == cs.competency_id).first()
            if comp and (cs.gap or 0) > 0:
                gap_competencies.append({
                    "competency_id": cs.competency_id,
                    "competency_name": comp.name,
                    "current_level": cs.current_level,
                    "required_level": cs.required_level,
                    "gap": cs.gap,
                })

        # 尝试 AI 生成计划
        plan_content = None
        generated_by_ai = False

        if LLMUtil.is_available():
            try:
                plan_content = TrainingService._generate_ai_plan(db, enrollment, ar, gap_competencies)
                generated_by_ai = True
            except Exception as e:
                LoggerUtil().warning(f"AI 计划生成失败，使用 fallback: {e}")
                plan_content = None

        # Fallback: 规则引擎生成
        if plan_content is None:
            plan_content = TrainingService._generate_fallback_plan(gap_competencies)

        # 创建计划记录
        plan = TrainingPlan(
            project_id=enrollment.project_id,
            enrollment_id=enrollment_id,
            user_id=enrollment.user_id,
            learner_id=enrollment.learner_id,
            assessment_record_id=assessment_record_id,
            plan_content=plan_content,
            total_stages=len(plan_content),
            completed_stages=0,
            progress=0.0,
            status=PlanStatusEnum.ACTIVE.value,
            generated_by_ai=generated_by_ai,
        )
        db.add(plan)

        # 更新报名状态为学习中
        enrollment.status = EnrollmentStatusEnum.IN_PROGRESS.value

        db.commit()
        db.refresh(plan)
        return success(data=TrainingService._plan_to_response(plan), message="学习计划已生成")

    @staticmethod
    def get_plan(db: Session, enrollment_id: int, user_id: int, is_staff: bool = False) -> Dict[str, Any]:
        enrollment = db.query(TrainingEnrollment).filter(TrainingEnrollment.id == enrollment_id).first()
        if not enrollment:
            return not_found(message="报名记录不存在")
        if enrollment.user_id != user_id and not is_staff:
            return bad_request(message="无权查看此学习计划")
        plan = db.query(TrainingPlan).filter(TrainingPlan.enrollment_id == enrollment_id).first()
        if not plan:
            return not_found(message="学习计划不存在")
        return success(data=TrainingService._plan_to_response(plan))

    @staticmethod
    def update_progress(
        db: Session, plan_id: int, completed_stages: int,
        user_id: int, is_staff: bool = False,
    ) -> Dict[str, Any]:
        plan = db.query(TrainingPlan).filter(TrainingPlan.id == plan_id).first()
        if not plan:
            return not_found(message="学习计划不存在")
        if plan.user_id != user_id and not is_staff:
            return bad_request(message="无权操作此学习计划")
        if completed_stages < 0 or completed_stages > plan.total_stages:
            return bad_request(message=f"已完成阶段数无效，应在 0-{plan.total_stages} 之间")

        plan.completed_stages = completed_stages
        plan.progress = round(completed_stages / plan.total_stages * 100, 1) if plan.total_stages > 0 else 0.0
        if completed_stages >= plan.total_stages:
            plan.status = PlanStatusEnum.COMPLETED.value

        db.commit()
        db.refresh(plan)
        return success(data=TrainingService._plan_to_response(plan), message="进度已更新")

    @staticmethod
    def complete_enrollment(
        db: Session, enrollment_id: int, user_id: int,
        final_score: Optional[float] = None, is_staff: bool = False,
    ) -> Dict[str, Any]:
        enrollment = db.query(TrainingEnrollment).filter(TrainingEnrollment.id == enrollment_id).first()
        if not enrollment:
            return not_found(message="报名记录不存在")
        if enrollment.user_id != user_id and not is_staff:
            return bad_request(message="无权完成此培训")
        if enrollment.status not in (EnrollmentStatusEnum.ENROLLED.value, EnrollmentStatusEnum.IN_PROGRESS.value):
            return bad_request(message=f"报名状态不允许完成: {enrollment.status}")

        enrollment.status = EnrollmentStatusEnum.COMPLETED.value
        enrollment.completed_at = datetime.now()
        if final_score is not None:
            enrollment.final_score = final_score

        db.commit()
        db.refresh(enrollment)
        return success(data=TrainingService._enrollment_to_response(enrollment), message="培训已完成")

    # ===========================================
    # 培训任务包与实操提交
    # ===========================================

    @staticmethod
    def list_task_packages(db: Session, project_id: int, is_staff: bool = False) -> Dict[str, Any]:
        project = db.query(TrainingProject).filter(TrainingProject.id == project_id).first()
        if not project or (project.status != ProjectStatusEnum.ACTIVE.value and not is_staff):
            return not_found(message="培训项目不存在")
        packages = db.query(TrainingTaskPackage).filter(
            TrainingTaskPackage.project_id == project_id,
        )
        if not is_staff:
            packages = packages.filter(TrainingTaskPackage.status == "active")
        items = packages.order_by(TrainingTaskPackage.sequence.asc(), TrainingTaskPackage.id.asc()).all()
        return success(data=[TrainingService._task_package_to_response(item) for item in items])

    @staticmethod
    def create_task_package(db: Session, project_id: int, data: TaskPackageCreate, user_id: int) -> Dict[str, Any]:
        project = db.query(TrainingProject).filter(TrainingProject.id == project_id).first()
        if not project:
            return not_found(message="培训项目不存在")
        package = TrainingTaskPackage(
            project_id=project_id,
            name=data.name,
            description=data.description,
            sequence=data.sequence,
            task_type=data.task_type,
            key_task_code=data.key_task_code,
            learning_objectives=data.learning_objectives,
            resources=data.resources,
            submission_required=data.submission_required,
            passing_score=data.passing_score,
            is_mandatory=data.is_mandatory,
            status=data.status,
            created_by=user_id,
        )
        db.add(package)
        db.flush()
        TrainingService._replace_rubrics(db, package, data.rubrics)
        db.commit()
        db.refresh(package)
        return success(data=TrainingService._task_package_to_response(package), message="任务包创建成功")

    @staticmethod
    def update_task_package(db: Session, package_id: int, data: TaskPackageUpdate) -> Dict[str, Any]:
        package = db.query(TrainingTaskPackage).filter(TrainingTaskPackage.id == package_id).first()
        if not package:
            return not_found(message="任务包不存在")
        values = data.model_dump(exclude_unset=True)
        rubrics = values.pop("rubrics", None)
        for key, value in values.items():
            setattr(package, key, value)
        if rubrics is not None:
            TrainingService._replace_rubrics(db, package, rubrics)
        db.commit()
        db.refresh(package)
        return success(data=TrainingService._task_package_to_response(package), message="任务包已更新")

    @staticmethod
    def delete_task_package(db: Session, package_id: int) -> Dict[str, Any]:
        package = db.query(TrainingTaskPackage).filter(TrainingTaskPackage.id == package_id).first()
        if not package:
            return not_found(message="任务包不存在")
        if db.query(TrainingSubmission).filter(TrainingSubmission.task_package_id == package_id).first():
            package.status = "archived"
            db.commit()
            return success(message="任务包已有提交记录，已归档")
        db.delete(package)
        db.commit()
        return success(message="任务包已删除")

    @staticmethod
    def create_submission(db: Session, package_id: int, enrollment_id: int, user_id: int, data: SubmissionCreate, is_staff: bool = False) -> Dict[str, Any]:
        package = db.query(TrainingTaskPackage).filter(TrainingTaskPackage.id == package_id).first()
        enrollment = db.query(TrainingEnrollment).filter(TrainingEnrollment.id == enrollment_id).first()
        if not package or not enrollment or package.project_id != enrollment.project_id:
            return not_found(message="任务包或报名记录不存在")
        if enrollment.user_id != user_id and not is_staff:
            return bad_request(message="只能提交本人的培训任务")
        if enrollment.status in (EnrollmentStatusEnum.WITHDRAWN.value, EnrollmentStatusEnum.FAILED.value):
            return bad_request(message="当前报名状态不能提交任务")
        latest_attempt = db.query(TrainingSubmission).filter(
            TrainingSubmission.task_package_id == package_id,
            TrainingSubmission.enrollment_id == enrollment_id,
        ).order_by(TrainingSubmission.attempt_number.desc()).first()
        submission = TrainingSubmission(
            task_package_id=package_id,
            enrollment_id=enrollment_id,
            learner_id=enrollment.learner_id,
            user_id=enrollment.user_id,
            attempt_number=(latest_attempt.attempt_number + 1) if latest_attempt else 1,
            content=data.content,
            attachments=data.attachments,
            demo_url=data.demo_url,
            status="submitted",
        )
        db.add(submission)
        enrollment.status = EnrollmentStatusEnum.IN_PROGRESS.value
        db.commit()
        db.refresh(submission)
        return success(data=TrainingService._submission_to_response(submission), message="实操任务已提交")

    @staticmethod
    def list_submissions(db: Session, package_id: int, enrollment_id: Optional[int], user_id: int, is_staff: bool = False) -> Dict[str, Any]:
        package = db.query(TrainingTaskPackage).filter(TrainingTaskPackage.id == package_id).first()
        if not package:
            return not_found(message="任务包不存在")
        query = db.query(TrainingSubmission).filter(TrainingSubmission.task_package_id == package_id)
        if enrollment_id:
            query = query.filter(TrainingSubmission.enrollment_id == enrollment_id)
        if not is_staff:
            query = query.filter(TrainingSubmission.user_id == user_id)
        submissions = query.order_by(TrainingSubmission.attempt_number.desc()).all()
        return success(data=[TrainingService._submission_to_response(item) for item in submissions])

    @staticmethod
    def review_submission(db: Session, submission_id: int, reviewer_id: int, data: SubmissionReview) -> Dict[str, Any]:
        submission = db.query(TrainingSubmission).filter(TrainingSubmission.id == submission_id).first()
        if not submission:
            return not_found(message="提交记录不存在")
        package = db.query(TrainingTaskPackage).filter(TrainingTaskPackage.id == submission.task_package_id).first()
        rubric_map = {rubric.id: rubric for rubric in (package.rubrics if package else [])}
        db.query(TrainingSubmissionScore).filter(TrainingSubmissionScore.submission_id == submission_id).delete(synchronize_session=False)
        total_weight = 0.0
        weighted_score = 0.0
        score_items = []
        for item in data.scores:
            try:
                rubric_id = int(item.get("rubric_id", item.get("rubricId")))
                score = float(item.get("score", 0))
            except (TypeError, ValueError):
                continue
            rubric = rubric_map.get(rubric_id)
            if rubric is None:
                continue
            score = max(0.0, min(score, rubric.max_score or 100.0))
            db.add(TrainingSubmissionScore(submission_id=submission_id, rubric_id=rubric.id, score=score, comment=item.get("comment")))
            weight = rubric.weight or 1.0
            total_weight += weight
            weighted_score += (score / (rubric.max_score or 100.0) * 100.0) * weight
            score_items.append({"rubric_id": rubric.id, "score": score, "comment": item.get("comment")})
        submission.overall_score = round(weighted_score / total_weight, 1) if total_weight else None
        submission.status = data.status
        submission.teacher_comment = data.teacher_comment
        submission.reviewed_by = reviewer_id
        submission.reviewed_at = datetime.now()
        db.commit()
        db.refresh(submission)
        return success(data=TrainingService._submission_to_response(submission), message="提交已评分")

    @staticmethod
    def dashboard_overview(db: Session, user_id: int, is_staff: bool = False) -> Dict[str, Any]:
        projects = db.query(TrainingProject).filter(TrainingProject.status.in_(["active", "completed"])).all()
        enrollments = db.query(TrainingEnrollment)
        if not is_staff:
            enrollments = enrollments.filter(TrainingEnrollment.user_id == user_id)
        enrollment_rows = enrollments.all()
        project_ids = {item.project_id for item in enrollment_rows}
        if not is_staff:
            projects = [item for item in projects if item.id in project_ids]
        package_counts = {project.id: db.query(TrainingTaskPackage).filter(TrainingTaskPackage.project_id == project.id, TrainingTaskPackage.status == "active").count() for project in projects}
        submission_query = db.query(TrainingSubmission)
        if not is_staff:
            submission_query = submission_query.filter(TrainingSubmission.user_id == user_id)
        submissions = submission_query.all()
        passed = [item for item in submissions if item.status == "passed"]
        avg_score = round(sum(item.overall_score for item in passed if item.overall_score is not None) / len([item for item in passed if item.overall_score is not None]), 1) if any(item.overall_score is not None for item in passed) else None
        project_rows = []
        for project in projects:
            project_enrollments = [item for item in enrollment_rows if item.project_id == project.id] if not is_staff else db.query(TrainingEnrollment).filter(TrainingEnrollment.project_id == project.id).all()
            project_submissions = [item for item in submissions if item.task_package and item.task_package.project_id == project.id] if not is_staff else db.query(TrainingSubmission).join(TrainingTaskPackage).filter(TrainingTaskPackage.project_id == project.id).all()
            project_rows.append({
                "project_id": project.id,
                "project_name": project.name,
                "enrollment_count": len(project_enrollments),
                "completed_count": sum(1 for item in project_enrollments if item.status == EnrollmentStatusEnum.COMPLETED.value),
                "package_count": package_counts.get(project.id, 0),
                "submission_count": len(project_submissions),
                "passed_submission_count": sum(1 for item in project_submissions if item.status == "passed"),
                "average_score": round(sum(item.overall_score for item in project_submissions if item.overall_score is not None) / len([item for item in project_submissions if item.overall_score is not None]), 1) if any(item.overall_score is not None for item in project_submissions) else None,
            })
        return success(data={
            "project_count": len(projects),
            "enrollment_count": len(enrollment_rows),
            "completed_count": sum(1 for item in enrollment_rows if item.status == EnrollmentStatusEnum.COMPLETED.value),
            "submission_count": len(submissions),
            "passed_submission_count": len(passed),
            "average_score": avg_score,
            "projects": project_rows,
        })

    # ===========================================
    # AI 计划生成（私有）
    # ===========================================

    @staticmethod
    def _generate_ai_plan(db: Session, enrollment: TrainingEnrollment, ar: AssessmentRecord, gaps: List[Dict]) -> List[Dict]:
        """调用 LLM 生成学习计划"""
        project = db.query(TrainingProject).filter(TrainingProject.id == enrollment.project_id).first()
        position = db.query(Position).filter(Position.id == ar.position_id).first()

        context = {
            "position_name": position.name if position else None,
            "overall_score": ar.overall_score,
            "overall_level": ar.overall_level,
            "gap_competencies": gaps,
            "project_type": project.project_type if project else None,
            "required_output": {
                "competency_ids": [g["competency_id"] for g in gaps],
                "target_level": "每个阶段目标等级",
            },
        }

        response, _ = LLMUtil.call_with_prompt_template(
            "path_planning",
            {"learner_context": json.dumps(context, ensure_ascii=False)},
            temperature=0.3,
        )

        # 解析 LLM 返回的 JSON
        data = json.loads(response)
        nodes = data.get("nodes", [])

        # 转换为培训计划格式
        plan_stages = []
        for idx, node in enumerate(nodes, 1):
            valid_ids = {g["competency_id"] for g in gaps}
            requested_ids = node.get("competency_ids", []) or []
            competency_ids = []
            for value in requested_ids:
                try:
                    competency_id = int(value)
                except (TypeError, ValueError):
                    continue
                if competency_id in valid_ids and competency_id not in competency_ids:
                    competency_ids.append(competency_id)
            if not competency_ids:
                competency_ids = [gaps[min(idx - 1, len(gaps) - 1)]["competency_id"]] if gaps else []
            matching_gaps = [g for g in gaps if g["competency_id"] in competency_ids]
            plan_stages.append({
                "stage": idx,
                "title": node.get("name", f"阶段{idx}"),
                "competency_ids": competency_ids,
                "resources": node.get("resources", []),
                "estimated_hours": TrainingService._parse_hours(node.get("estimated_time", "2小时")),
                "target_level": max((g.get("required_level", 3) for g in matching_gaps), default=node.get("difficulty", 3)),
                "deadline": None,
                "description": node.get("description", ""),
            })
        return plan_stages

    @staticmethod
    def _generate_fallback_plan(gaps: List[Dict]) -> List[Dict]:
        """规则引擎生成 fallback 计划（当 LLM 不可用时）"""
        if not gaps:
            return [{
                "stage": 1,
                "title": "综合复习",
                "competency_ids": [],
                "resources": [],
                "estimated_hours": 4,
                "target_level": 3,
                "deadline": None,
                "description": "无差距项，进行综合复习巩固",
            }]

        plan_stages = []
        for idx, gap in enumerate(gaps, 1):
            gap_val = gap.get("gap", 1)
            hours = gap_val * 4  # 每级差距 4 小时
            plan_stages.append({
                "stage": idx,
                "title": f"提升{gap['competency_name']}（当前L{gap.get('current_level', 1)}→目标L{gap.get('required_level', 3)}）",
                "competency_ids": [gap["competency_id"]],
                "resources": [],
                "estimated_hours": hours,
                "target_level": gap.get("required_level", 3),
                "deadline": None,
                "description": f"针对{gap['competency_name']}进行专项提升，缩小{gap_val}级差距",
            })
        return plan_stages

    @staticmethod
    def _parse_hours(time_str: str) -> int:
        """从时间字符串中解析小时数"""
        digits = "".join(c for c in str(time_str) if c.isdigit())
        return max(1, int(digits or 2))

    @staticmethod
    def _normalize_project_type(project_type: Optional[str]) -> Optional[str]:
        if not project_type:
            return project_type
        return TrainingService.PROJECT_TYPE_ALIASES.get(project_type, project_type)

    # ===========================================
    # 私有辅助方法
    # ===========================================

    @staticmethod
    def _project_to_response(project: TrainingProject) -> Dict[str, Any]:
        return {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "position_id": project.position_id,
            "certification_id": project.certification_id,
            "project_type": project.project_type,
            "enterprise_name": project.enterprise_name,
            "status": project.status,
            "start_date": project.start_date.isoformat() if project.start_date else None,
            "end_date": project.end_date.isoformat() if project.end_date else None,
            "config": project.config,
            "created_by": project.created_by,
            "created_at": project.created_at.isoformat() if project.created_at else None,
            "updated_at": project.updated_at.isoformat() if project.updated_at else None,
        }

    @staticmethod
    def _enrollment_to_response(enrollment: TrainingEnrollment) -> Dict[str, Any]:
        return {
            "id": enrollment.id,
            "project_id": enrollment.project_id,
            "user_id": enrollment.user_id,
            "learner_id": enrollment.learner_id,
            "status": enrollment.status,
            "enrolled_at": enrollment.enrolled_at.isoformat() if enrollment.enrolled_at else None,
            "completed_at": enrollment.completed_at.isoformat() if enrollment.completed_at else None,
            "final_score": enrollment.final_score,
            "certification_record_id": enrollment.certification_record_id,
            "created_at": enrollment.created_at.isoformat() if enrollment.created_at else None,
            "updated_at": enrollment.updated_at.isoformat() if enrollment.updated_at else None,
        }

    @staticmethod
    def _plan_to_response(plan: TrainingPlan) -> Dict[str, Any]:
        return {
            "id": plan.id,
            "project_id": plan.project_id,
            "enrollment_id": plan.enrollment_id,
            "user_id": plan.user_id,
            "learner_id": plan.learner_id,
            "assessment_record_id": plan.assessment_record_id,
            "plan_content": plan.plan_content,
            "total_stages": plan.total_stages,
            "completed_stages": plan.completed_stages,
            "progress": plan.progress,
            "status": plan.status,
            "generated_by_ai": plan.generated_by_ai,
            "created_at": plan.created_at.isoformat() if plan.created_at else None,
            "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
        }

    @staticmethod
    def _replace_rubrics(db: Session, package: TrainingTaskPackage, rubrics: List[Dict[str, Any]]) -> None:
        package.rubrics[:] = []
        for index, item in enumerate(rubrics or [], 1):
            criterion = str(item.get("criterion", "")).strip()
            if not criterion:
                continue
            package.rubrics.append(TrainingTaskRubric(
                criterion=criterion,
                description=item.get("description"),
                max_score=float(item.get("max_score", item.get("maxScore", 100)) or 100),
                weight=float(item.get("weight", 1) or 1),
                sequence=int(item.get("sequence", index) or index),
            ))

    @staticmethod
    def _task_package_to_response(package: TrainingTaskPackage) -> Dict[str, Any]:
        return {
            "id": package.id,
            "project_id": package.project_id,
            "name": package.name,
            "description": package.description,
            "sequence": package.sequence,
            "task_type": package.task_type,
            "key_task_code": package.key_task_code,
            "learning_objectives": package.learning_objectives or [],
            "resources": package.resources or [],
            "submission_required": package.submission_required,
            "passing_score": package.passing_score,
            "is_mandatory": package.is_mandatory,
            "status": package.status,
            "created_by": package.created_by,
            "created_at": package.created_at.isoformat() if package.created_at else None,
            "updated_at": package.updated_at.isoformat() if package.updated_at else None,
            "rubrics": [
                {
                    "id": rubric.id,
                    "task_package_id": rubric.task_package_id,
                    "criterion": rubric.criterion,
                    "description": rubric.description,
                    "max_score": rubric.max_score,
                    "weight": rubric.weight,
                    "sequence": rubric.sequence,
                }
                for rubric in package.rubrics
            ],
        }

    @staticmethod
    def _submission_to_response(submission: TrainingSubmission) -> Dict[str, Any]:
        return {
            "id": submission.id,
            "task_package_id": submission.task_package_id,
            "enrollment_id": submission.enrollment_id,
            "learner_id": submission.learner_id,
            "user_id": submission.user_id,
            "attempt_number": submission.attempt_number,
            "content": submission.content,
            "attachments": submission.attachments or [],
            "demo_url": submission.demo_url,
            "status": submission.status,
            "overall_score": submission.overall_score,
            "teacher_comment": submission.teacher_comment,
            "reviewed_by": submission.reviewed_by,
            "submitted_at": submission.submitted_at.isoformat() if submission.submitted_at else None,
            "reviewed_at": submission.reviewed_at.isoformat() if submission.reviewed_at else None,
            "scores": [
                {
                    "id": score.id,
                    "rubric_id": score.rubric_id,
                    "score": score.score,
                    "comment": score.comment,
                }
                for score in submission.scores
            ],
        }
