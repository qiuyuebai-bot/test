"""
评估域 Service 层
"""
import json
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.domains.assessment.models import (
    AssessmentTemplate, AssessmentRecord, CompetencyScore,
    AssessmentStatusEnum,
)
from app.domains.assessment.schemas import (
    AssessmentTemplateCreate, AssessmentTemplateUpdate,
    AssessmentStartRequest, AssessmentSubmitRequest,
)
from app.domains.position.models import Position, Competency, PositionCompetency
from app.domains.learner.models import LearnerProfile
from app.schemas.response import (
    success as _success,
    bad_request as _bad_request,
    forbidden as _forbidden,
    not_found as _not_found,
)
from app.utils.logger import LoggerUtil


def _unwrap(resp) -> Dict[str, Any]:
    """将 JSONResponse 解包为 dict"""
    return json.loads(resp.body)


def success(data: Any = None, message: str = "操作成功") -> Dict[str, Any]:
    return _unwrap(_success(data=data, message=message))


def bad_request(message: str = "请求参数错误", data: Any = None) -> Dict[str, Any]:
    return _unwrap(_bad_request(message=message, data=data))


def forbidden(message: str = "禁止访问") -> Dict[str, Any]:
    return _unwrap(_forbidden(message=message))


def not_found(message: str = "资源不存在") -> Dict[str, Any]:
    return _unwrap(_not_found(message=message))


class AssessmentService:
    """评估域服务"""

    # ===========================================
    # 评估模板 CRUD
    # ===========================================

    @staticmethod
    def create_template(db: Session, data: AssessmentTemplateCreate) -> Dict[str, Any]:
        position = db.query(Position).filter(Position.id == data.position_id).first()
        if not position:
            return not_found(message="岗位不存在")

        # 验证 competency_configs 中的胜任力ID存在
        for cfg in data.competency_configs:
            comp = db.query(Competency).filter(Competency.id == cfg.competency_id).first()
            if not comp:
                return bad_request(message=f"胜任力不存在: ID={cfg.competency_id}")

        tpl = AssessmentTemplate(
            position_id=data.position_id,
            name=data.name,
            description=data.description,
            competency_configs=[c.model_dump() for c in data.competency_configs],
            pass_threshold=data.pass_threshold,
            duration_minutes=data.duration_minutes,
        )
        db.add(tpl)
        db.commit()
        db.refresh(tpl)
        return success(data=AssessmentService._template_to_response(tpl), message="评估模板创建成功")

    @staticmethod
    def get_template_list(
        db: Session, page: int = 1, page_size: int = 20,
        position_id: Optional[int] = None, keyword: Optional[str] = None
    ) -> Dict[str, Any]:
        query = db.query(AssessmentTemplate)
        if position_id:
            query = query.filter(AssessmentTemplate.position_id == position_id)
        if keyword:
            query = query.filter(AssessmentTemplate.name.contains(keyword))
        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()
        return success(data={
            "items": [AssessmentService._template_to_response(t) for t in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        })

    @staticmethod
    def get_template_by_id(db: Session, template_id: int) -> Dict[str, Any]:
        tpl = db.query(AssessmentTemplate).filter(AssessmentTemplate.id == template_id).first()
        if not tpl:
            return not_found(message="评估模板不存在")
        return success(data=AssessmentService._template_to_response(tpl))

    @staticmethod
    def update_template(db: Session, template_id: int, data: AssessmentTemplateUpdate) -> Dict[str, Any]:
        tpl = db.query(AssessmentTemplate).filter(AssessmentTemplate.id == template_id).first()
        if not tpl:
            return not_found(message="评估模板不存在")
        update_data = data.model_dump(exclude_unset=True)
        if "competency_configs" in update_data and update_data["competency_configs"]:
            update_data["competency_configs"] = [c.model_dump() if hasattr(c, "model_dump") else c for c in update_data["competency_configs"]]
        for key, value in update_data.items():
            setattr(tpl, key, value)
        db.commit()
        db.refresh(tpl)
        return success(data=AssessmentService._template_to_response(tpl), message="更新成功")

    @staticmethod
    def delete_template(db: Session, template_id: int) -> Dict[str, Any]:
        tpl = db.query(AssessmentTemplate).filter(AssessmentTemplate.id == template_id).first()
        if not tpl:
            return not_found(message="评估模板不存在")
        db.delete(tpl)
        db.commit()
        return success(message="删除成功")

    # ===========================================
    # 评估记录管理
    # ===========================================

    @staticmethod
    def start_assessment(
        db: Session, user_id: int, template_id: int, learner_id: Optional[int] = None
    ) -> Dict[str, Any]:
        tpl = db.query(AssessmentTemplate).filter(AssessmentTemplate.id == template_id).first()
        if not tpl:
            return not_found(message="评估模板不存在")
        if not tpl.is_active:
            return bad_request(message="评估模板已停用")

        record_user_id = user_id
        if learner_id is not None:
            learner = db.query(LearnerProfile).filter(LearnerProfile.id == learner_id).first()
            if not learner:
                return not_found(message="学习者不存在")
            record_user_id = learner.user_id

        record = AssessmentRecord(
            template_id=template_id,
            user_id=record_user_id,
            learner_id=learner_id,
            position_id=tpl.position_id,
            status=AssessmentStatusEnum.IN_PROGRESS.value,
            started_at=datetime.now(),
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return success(data=AssessmentService._record_to_response(record), message="评估已开始")

    @staticmethod
    def submit_assessment(
        db: Session, record_id: int, data: AssessmentSubmitRequest
    ) -> Dict[str, Any]:
        record = db.query(AssessmentRecord).filter(AssessmentRecord.id == record_id).first()
        if not record:
            return not_found(message="评估记录不存在")
        if record.status != AssessmentStatusEnum.IN_PROGRESS.value:
            return bad_request(message=f"评估记录状态不允许提交: {record.status}")

        # 获取岗位的胜任力要求（required_level 快照）
        position_competencies = db.query(PositionCompetency).filter(
            PositionCompetency.position_id == record.position_id
        ).all()
        required_map = {pc.competency_id: pc.required_level for pc in position_competencies}

        # 创建评分明细
        total_score = 0.0
        score_count = 0
        for score_data in data.scores:
            comp_id = score_data.get("competency_id")
            current_level = score_data.get("current_level")
            current_score = score_data.get("current_score")
            required_level = required_map.get(comp_id, 3)
            gap = (required_level - current_level) if current_level is not None else None

            cs = CompetencyScore(
                assessment_record_id=record_id,
                competency_id=comp_id,
                current_level=current_level,
                current_score=current_score,
                required_level=required_level,
                gap=gap,
                assessment_method=score_data.get("assessment_method", "quiz"),
                evidence=score_data.get("evidence", []),
            )
            db.add(cs)
            if current_score is not None:
                total_score += current_score
                score_count += 1

        # 计算综合得分和等级
        overall_score = round(total_score / score_count, 2) if score_count > 0 else 0.0
        overall_level = AssessmentService._score_to_level(overall_score)

        # 生成差距摘要
        gap_summary = AssessmentService._build_gap_summary(db, record_id, required_map)

        record.status = AssessmentStatusEnum.COMPLETED.value
        record.overall_score = overall_score
        record.overall_level = overall_level
        record.gap_summary = gap_summary
        record.completed_at = datetime.now()

        db.commit()
        db.refresh(record)
        return success(data=AssessmentService._record_detail_to_response(db, record), message="评估已提交")

    @staticmethod
    def get_record_detail(
        db: Session, record_id: int, user_id: Optional[int] = None, is_staff: bool = False,
    ) -> Dict[str, Any]:
        record = db.query(AssessmentRecord).filter(AssessmentRecord.id == record_id).first()
        if not record:
            return not_found(message="评估记录不存在")
        if user_id is not None and not is_staff and record.user_id != user_id:
            return forbidden(message="无权查看此评估记录")
        return success(data=AssessmentService._record_detail_to_response(db, record))

    @staticmethod
    def get_record_list(
        db: Session, page: int = 1, page_size: int = 20,
        user_id: Optional[int] = None, position_id: Optional[int] = None,
        status: Optional[str] = None, learner_id: Optional[int] = None,
        is_staff: bool = False,
    ) -> Dict[str, Any]:
        query = db.query(AssessmentRecord)
        if user_id:
            query = query.filter(AssessmentRecord.user_id == user_id)
        if learner_id:
            query = query.filter(AssessmentRecord.learner_id == learner_id)
        if position_id:
            query = query.filter(AssessmentRecord.position_id == position_id)
        if status:
            query = query.filter(AssessmentRecord.status == status)
        total = query.count()
        items = query.order_by(AssessmentRecord.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return success(data={
            "items": [AssessmentService._record_to_response(r) for r in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        })

    # ===========================================
    # 差距分析
    # ===========================================

    @staticmethod
    def get_gap_analysis(
        db: Session, record_id: int, user_id: Optional[int] = None, is_staff: bool = False,
    ) -> Dict[str, Any]:
        record = db.query(AssessmentRecord).filter(AssessmentRecord.id == record_id).first()
        if not record:
            return not_found(message="评估记录不存在")
        if user_id is not None and not is_staff and record.user_id != user_id:
            return forbidden(message="无权查看此评估结果")
        if record.status != AssessmentStatusEnum.COMPLETED.value:
            return bad_request(message="评估尚未完成，无法生成差距分析")

        tpl = db.query(AssessmentTemplate).filter(AssessmentTemplate.id == record.template_id).first()
        pass_threshold = tpl.pass_threshold if tpl else 60.0

        scores = db.query(CompetencyScore).filter(
            CompetencyScore.assessment_record_id == record_id
        ).all()

        gaps = []
        met_count = 0
        for cs in scores:
            comp = db.query(Competency).filter(Competency.id == cs.competency_id).first()
            gap_val = cs.gap if cs.gap is not None else 0
            is_met = gap_val <= 0
            if is_met:
                met_count += 1
            gaps.append({
                "competency_id": cs.competency_id,
                "competency_name": comp.name if comp else None,
                "competency_code": comp.code if comp else None,
                "current_level": cs.current_level,
                "required_level": cs.required_level,
                "gap": gap_val,
                "is_met": is_met,
            })

        return success(data={
            "record_id": record_id,
            "overall_score": record.overall_score,
            "overall_level": record.overall_level,
            "pass_threshold": pass_threshold,
            "is_passed": (record.overall_score or 0) >= pass_threshold,
            "total_competencies": len(scores),
            "met_count": met_count,
            "gap_count": len(scores) - met_count,
            "gaps": gaps,
        })

    # ===========================================
    # 私有辅助方法
    # ===========================================

    @staticmethod
    def _score_to_level(score: float) -> int:
        """得分转等级(1-5)"""
        if score >= 90:
            return 5
        elif score >= 75:
            return 4
        elif score >= 60:
            return 3
        elif score >= 40:
            return 2
        else:
            return 1

    @staticmethod
    def _build_gap_summary(db: Session, record_id: int, required_map: Dict[int, int]) -> List[Dict]:
        """构建差距摘要"""
        scores = db.query(CompetencyScore).filter(
            CompetencyScore.assessment_record_id == record_id
        ).all()
        summary = []
        for cs in scores:
            comp = db.query(Competency).filter(Competency.id == cs.competency_id).first()
            summary.append({
                "competency_id": cs.competency_id,
                "competency_name": comp.name if comp else None,
                "current_level": cs.current_level,
                "required_level": cs.required_level,
                "gap": cs.gap,
            })
        return summary

    @staticmethod
    def _template_to_response(tpl: AssessmentTemplate) -> Dict[str, Any]:
        return {
            "id": tpl.id,
            "position_id": tpl.position_id,
            "name": tpl.name,
            "description": tpl.description,
            "competency_configs": tpl.competency_configs,
            "pass_threshold": tpl.pass_threshold,
            "duration_minutes": tpl.duration_minutes,
            "is_active": tpl.is_active,
            "created_at": tpl.created_at.isoformat() if tpl.created_at else None,
            "updated_at": tpl.updated_at.isoformat() if tpl.updated_at else None,
        }

    @staticmethod
    def _record_to_response(record: AssessmentRecord) -> Dict[str, Any]:
        return {
            "id": record.id,
            "template_id": record.template_id,
            "user_id": record.user_id,
            "learner_id": record.learner_id,
            "position_id": record.position_id,
            "status": record.status,
            "overall_score": record.overall_score,
            "overall_level": record.overall_level,
            "gap_summary": record.gap_summary,
            "ai_diagnosis": record.ai_diagnosis,
            "started_at": record.started_at.isoformat() if record.started_at else None,
            "completed_at": record.completed_at.isoformat() if record.completed_at else None,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        }

    @staticmethod
    def _record_detail_to_response(db: Session, record: AssessmentRecord) -> Dict[str, Any]:
        result = AssessmentService._record_to_response(record)
        scores = db.query(CompetencyScore).filter(
            CompetencyScore.assessment_record_id == record.id
        ).all()
        result["competency_scores"] = [
            AssessmentService._score_to_response(db, cs) for cs in scores
        ]
        tpl = db.query(AssessmentTemplate).filter(AssessmentTemplate.id == record.template_id).first()
        result["template_name"] = tpl.name if tpl else None
        pos = db.query(Position).filter(Position.id == record.position_id).first()
        result["position_name"] = pos.name if pos else None
        return result

    @staticmethod
    def _score_to_response(db: Session, cs: CompetencyScore) -> Dict[str, Any]:
        comp = db.query(Competency).filter(Competency.id == cs.competency_id).first()
        return {
            "id": cs.id,
            "assessment_record_id": cs.assessment_record_id,
            "competency_id": cs.competency_id,
            "competency_name": comp.name if comp else None,
            "competency_code": comp.code if comp else None,
            "current_level": cs.current_level,
            "current_score": cs.current_score,
            "required_level": cs.required_level,
            "gap": cs.gap,
            "assessment_method": cs.assessment_method,
            "evidence": cs.evidence,
            "created_at": cs.created_at.isoformat() if cs.created_at else None,
        }
