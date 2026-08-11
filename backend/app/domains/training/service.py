"""
培训项目域 Service 层
"""
import json
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session

from app.domains.training.models import (
    TrainingProject, TrainingEnrollment, TrainingPlan,
    ProjectStatusEnum, EnrollmentStatusEnum, PlanStatusEnum,
)
from app.domains.training.schemas import (
    TrainingProjectCreate, TrainingProjectUpdate,
)
from app.domains.position.models import Position, Competency, PositionCompetency
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
            project_type=data.project_type,
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
        status: Optional[str] = None, keyword: Optional[str] = None
    ) -> Dict[str, Any]:
        query = db.query(TrainingProject)
        if status:
            query = query.filter(TrainingProject.status == status)
        if keyword:
            query = query.filter(TrainingProject.name.contains(keyword))
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
    def get_project_by_id(db: Session, project_id: int) -> Dict[str, Any]:
        project = db.query(TrainingProject).filter(TrainingProject.id == project_id).first()
        if not project:
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
    def enroll(db: Session, project_id: int, user_id: int, learner_id: Optional[int] = None) -> Dict[str, Any]:
        project = db.query(TrainingProject).filter(TrainingProject.id == project_id).first()
        if not project:
            return not_found(message="培训项目不存在")
        if project.status != ProjectStatusEnum.ACTIVE.value:
            return bad_request(message="项目不在报名中")

        existing = db.query(TrainingEnrollment).filter(
            TrainingEnrollment.project_id == project_id,
            TrainingEnrollment.user_id == user_id,
        ).first()
        if existing:
            return bad_request(message="已报名该培训项目")

        enrollment = TrainingEnrollment(
            project_id=project_id,
            user_id=user_id,
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

    # ===========================================
    # AI 学习计划生成
    # ===========================================

    @staticmethod
    def generate_plan(db: Session, enrollment_id: int, user_id: int, assessment_record_id: int) -> Dict[str, Any]:
        enrollment = db.query(TrainingEnrollment).filter(TrainingEnrollment.id == enrollment_id).first()
        if not enrollment:
            return not_found(message="报名记录不存在")
        if enrollment.user_id != user_id:
            return bad_request(message="无权操作此报名记录")

        ar = db.query(AssessmentRecord).filter(AssessmentRecord.id == assessment_record_id).first()
        if not ar:
            return not_found(message="评估记录不存在")
        if ar.status != AssessmentStatusEnum.COMPLETED.value:
            return bad_request(message="评估尚未完成")

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
            user_id=user_id,
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
    def get_plan(db: Session, enrollment_id: int) -> Dict[str, Any]:
        enrollment = db.query(TrainingEnrollment).filter(TrainingEnrollment.id == enrollment_id).first()
        if not enrollment:
            return not_found(message="报名记录不存在")
        plan = db.query(TrainingPlan).filter(TrainingPlan.enrollment_id == enrollment_id).first()
        if not plan:
            return not_found(message="学习计划不存在")
        return success(data=TrainingService._plan_to_response(plan))

    @staticmethod
    def update_progress(db: Session, plan_id: int, completed_stages: int) -> Dict[str, Any]:
        plan = db.query(TrainingPlan).filter(TrainingPlan.id == plan_id).first()
        if not plan:
            return not_found(message="学习计划不存在")
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
    def complete_enrollment(db: Session, enrollment_id: int, final_score: Optional[float] = None) -> Dict[str, Any]:
        enrollment = db.query(TrainingEnrollment).filter(TrainingEnrollment.id == enrollment_id).first()
        if not enrollment:
            return not_found(message="报名记录不存在")
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
            plan_stages.append({
                "stage": idx,
                "title": node.get("name", f"阶段{idx}"),
                "competency_ids": [g["competency_id"] for g in gaps],
                "resources": node.get("resources", []),
                "estimated_hours": TrainingService._parse_hours(node.get("estimated_time", "2小时")),
                "target_level": node.get("difficulty", 3),
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
