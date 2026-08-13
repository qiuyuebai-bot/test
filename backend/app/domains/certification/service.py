"""
认证发证域 Service 层
"""
import json
from typing import Optional, Dict, Any, List
from datetime import datetime
from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session

from app.domains.certification.models import (
    Certification, CertificationRule, CertificationRecord,
    RuleTypeEnum, CertificationStatusEnum,
)
from app.domains.certification.schemas import (
    CertificationCreate, CertificationUpdate,
    CertificationRuleCreate, CertificationApplyRequest,
)
from app.domains.position.models import Position, Competency, PositionCompetency
from app.domains.learner.models import LearnerProfile
from app.domains.assessment.models import (
    AssessmentTemplate, AssessmentRecord, CompetencyScore,
    AssessmentStatusEnum,
)
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


class CertificationService:
    """认证发证域服务"""

    # ===========================================
    # 认证定义 CRUD
    # ===========================================

    @staticmethod
    def create_certification(db: Session, data: CertificationCreate) -> Dict[str, Any]:
        # 验证岗位存在
        position = db.query(Position).filter(Position.id == data.position_id).first()
        if not position:
            return not_found(message="岗位不存在")

        # 验证编码唯一
        existing = db.query(Certification).filter(Certification.code == data.code).first()
        if existing:
            return bad_request(message=f"认证编码已存在: {data.code}")

        cert = Certification(
            position_id=data.position_id,
            name=data.name,
            code=data.code,
            level=data.level,
            description=data.description,
            validity_period_months=data.validity_period_months,
            issuer=data.issuer,
        )
        db.add(cert)
        db.commit()
        db.refresh(cert)
        return success(data=CertificationService._certification_to_response(cert), message="认证创建成功")

    @staticmethod
    def get_certification_list(
        db: Session, page: int = 1, page_size: int = 20,
        position_id: Optional[int] = None, keyword: Optional[str] = None
    ) -> Dict[str, Any]:
        query = db.query(Certification)
        if position_id:
            query = query.filter(Certification.position_id == position_id)
        if keyword:
            query = query.filter(Certification.name.contains(keyword))
        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()
        return success(data={
            "items": [CertificationService._certification_to_response(c) for c in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        })

    @staticmethod
    def get_certification_by_id(db: Session, cert_id: int) -> Dict[str, Any]:
        cert = db.query(Certification).filter(Certification.id == cert_id).first()
        if not cert:
            return not_found(message="认证不存在")
        result = CertificationService._certification_to_response(cert)
        # 附带规则列表
        rules = db.query(CertificationRule).filter(
            CertificationRule.certification_id == cert_id
        ).all()
        result["rules"] = [CertificationService._rule_to_response(r) for r in rules]
        return success(data=result)

    @staticmethod
    def update_certification(db: Session, cert_id: int, data: CertificationUpdate) -> Dict[str, Any]:
        cert = db.query(Certification).filter(Certification.id == cert_id).first()
        if not cert:
            return not_found(message="认证不存在")
        update_data = data.model_dump(exclude_unset=True)
        if update_data.get("is_active") is True:
            has_rules = db.query(CertificationRule).filter(
                CertificationRule.certification_id == cert_id,
            ).first()
            if not has_rules:
                return bad_request(message="认证尚未配置发证规则，不能启用")
        for key, value in update_data.items():
            setattr(cert, key, value)
        db.commit()
        db.refresh(cert)
        return success(data=CertificationService._certification_to_response(cert), message="更新成功")

    @staticmethod
    def delete_certification(db: Session, cert_id: int) -> Dict[str, Any]:
        cert = db.query(Certification).filter(Certification.id == cert_id).first()
        if not cert:
            return not_found(message="认证不存在")
        has_records = db.query(CertificationRecord).filter(
            CertificationRecord.certification_id == cert_id,
        ).first()
        if has_records:
            return bad_request(message="认证已有申请或发证记录，不能删除，请停用认证")
        db.delete(cert)
        db.commit()
        return success(message="删除成功")

    # ===========================================
    # 发证规则管理
    # ===========================================

    @staticmethod
    def add_rule(db: Session, data: CertificationRuleCreate) -> Dict[str, Any]:
        cert = db.query(Certification).filter(Certification.id == data.certification_id).first()
        if not cert:
            return not_found(message="认证不存在")

        # 验证 rule_type
        valid_types = [e.value for e in RuleTypeEnum]
        if data.rule_type not in valid_types:
            return bad_request(message=f"无效规则类型: {data.rule_type}，可选: {valid_types}")

        # 验证 rule_config
        err = CertificationService._validate_rule_config(data.rule_type, data.rule_config)
        if err:
            return bad_request(message=err)

        rule = CertificationRule(
            certification_id=data.certification_id,
            rule_type=data.rule_type,
            rule_config=data.rule_config,
        )
        db.add(rule)
        db.commit()
        db.refresh(rule)
        return success(data=CertificationService._rule_to_response(rule), message="规则创建成功")

    @staticmethod
    def get_rules(db: Session, cert_id: int) -> Dict[str, Any]:
        cert = db.query(Certification).filter(Certification.id == cert_id).first()
        if not cert:
            return not_found(message="认证不存在")
        rules = db.query(CertificationRule).filter(
            CertificationRule.certification_id == cert_id
        ).all()
        return success(data=[CertificationService._rule_to_response(r) for r in rules])

    @staticmethod
    def delete_rule(db: Session, rule_id: int) -> Dict[str, Any]:
        rule = db.query(CertificationRule).filter(CertificationRule.id == rule_id).first()
        if not rule:
            return not_found(message="规则不存在")
        db.delete(rule)
        db.commit()
        return success(message="删除成功")

    # ===========================================
    # 认证记录管理
    # ===========================================

    @staticmethod
    def apply_for_certification(
        db: Session, user_id: int, data: CertificationApplyRequest, is_staff: bool = False,
    ) -> Dict[str, Any]:
        cert = db.query(Certification).filter(Certification.id == data.certification_id).first()
        if not cert:
            return not_found(message="认证不存在")
        if not cert.is_active:
            return bad_request(message="认证已停用")

        learner = db.query(LearnerProfile).filter(
            LearnerProfile.id == data.learner_id,
        ).first()
        if not learner:
            return not_found(message="学习者不存在")
        if not is_staff and learner.user_id != user_id:
            return forbidden(message="只能为当前学习者申请认证")

        record = db.query(AssessmentRecord).filter(
            AssessmentRecord.id == data.assessment_record_id
        ).first()
        if not record:
            return not_found(message="评估记录不存在")
        if record.status != AssessmentStatusEnum.COMPLETED.value:
            return bad_request(message="评估尚未完成，无法申请认证")

        if record.user_id != learner.user_id:
            return forbidden(message="评估记录不属于所选学习者")
        if record.learner_id != learner.id:
            return forbidden(message="评估记录不属于所选学习者")

        # 评估记录的岗位需与认证岗位匹配
        if record.position_id != cert.position_id:
            return bad_request(message="评估记录的岗位与认证岗位不匹配")

        rules = db.query(CertificationRule).filter(
            CertificationRule.certification_id == cert.id,
        ).all()
        if not rules:
            return bad_request(message="认证尚未配置发证规则，暂不能申请")

        existing_pending = db.query(CertificationRecord).filter(
            CertificationRecord.certification_id == cert.id,
            CertificationRecord.learner_id == learner.id,
            CertificationRecord.status == CertificationStatusEnum.PENDING.value,
        ).first()
        if existing_pending:
            return bad_request(message="该学习者已有待审核的认证申请")

        existing_assessment = db.query(CertificationRecord).filter(
            CertificationRecord.certification_id == cert.id,
            CertificationRecord.learner_id == learner.id,
            CertificationRecord.assessment_record_id == record.id,
        ).first()
        if existing_assessment:
            return bad_request(message="该评估记录已用于此认证，不能重复申请")

        now = datetime.now()
        existing_approved = db.query(CertificationRecord).filter(
            CertificationRecord.certification_id == cert.id,
            CertificationRecord.learner_id == learner.id,
            CertificationRecord.status == CertificationStatusEnum.APPROVED.value,
        ).all()
        if any(item.expires_at is None or item.expires_at > now for item in existing_approved):
            return bad_request(message="该学习者已有有效的认证证书")

        # 自动评估规则
        evaluation = CertificationService._evaluate_rules(db, cert.id, record.id)
        if not evaluation.get("passed", False):
            return bad_request(message="当前评估结果未满足认证规则，暂不具备申请资格", data=evaluation)

        cert_record = CertificationRecord(
            certification_id=data.certification_id,
            user_id=learner.user_id,
            learner_id=learner.id,
            assessment_record_id=data.assessment_record_id,
            status=CertificationStatusEnum.PENDING.value,
            rule_evaluation=evaluation,
        )
        db.add(cert_record)
        db.commit()
        db.refresh(cert_record)
        return success(data=CertificationService._record_to_response(cert_record), message="认证申请已提交")

    @staticmethod
    def get_record_list(
        db: Session, page: int = 1, page_size: int = 20,
        user_id: Optional[int] = None, status: Optional[str] = None,
        learner_id: Optional[int] = None, is_staff: bool = False,
    ) -> Dict[str, Any]:
        CertificationService._sync_expired_records(db)
        query = db.query(CertificationRecord)
        if user_id:
            query = query.filter(CertificationRecord.user_id == user_id)
        if learner_id:
            query = query.filter(CertificationRecord.learner_id == learner_id)
        if status:
            query = query.filter(CertificationRecord.status == status)
        total = query.count()
        items = query.order_by(CertificationRecord.created_at.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        return success(data={
            "items": [CertificationService._record_to_response(r) for r in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        })

    @staticmethod
    def get_record_detail(
        db: Session, record_id: int, user_id: Optional[int] = None, is_staff: bool = False,
    ) -> Dict[str, Any]:
        CertificationService._sync_expired_records(db)
        rec = db.query(CertificationRecord).filter(CertificationRecord.id == record_id).first()
        if not rec:
            return not_found(message="认证记录不存在")
        if user_id is not None and not is_staff and rec.user_id != user_id:
            return forbidden(message="无权查看此认证记录")
        result = CertificationService._record_to_response(rec)
        # 附带认证名称和评估记录信息
        cert = db.query(Certification).filter(Certification.id == rec.certification_id).first()
        result["certification_name"] = cert.name if cert else None
        result["certification_code"] = cert.code if cert else None
        ar = db.query(AssessmentRecord).filter(AssessmentRecord.id == rec.assessment_record_id).first()
        result["assessment_score"] = ar.overall_score if ar else None
        result["assessment_level"] = ar.overall_level if ar else None
        return success(data=result)

    @staticmethod
    def approve_record(db: Session, record_id: int, reviewer_id: int, comment: Optional[str] = None) -> Dict[str, Any]:
        rec = db.query(CertificationRecord).filter(CertificationRecord.id == record_id).first()
        if not rec:
            return not_found(message="认证记录不存在")
        if rec.status != CertificationStatusEnum.PENDING.value:
            return bad_request(message=f"记录状态不允许审核: {rec.status}")

        # 检查规则评估是否通过
        evaluation = rec.rule_evaluation or {}
        if not evaluation.get("passed", False):
            return bad_request(message="规则评估未通过，无法批准")

        assessment = db.query(AssessmentRecord).filter(
            AssessmentRecord.id == rec.assessment_record_id,
        ).first()
        if not assessment or assessment.status != AssessmentStatusEnum.COMPLETED.value:
            return bad_request(message="关联评估已不存在或尚未完成，无法批准")
        current_evaluation = CertificationService._evaluate_rules(
            db, rec.certification_id, rec.assessment_record_id,
        )
        if not current_evaluation.get("passed", False):
            return bad_request(message="当前评估结果已不满足发证规则，无法批准", data=current_evaluation)
        rec.rule_evaluation = current_evaluation

        # 生成证书编号
        cert_number = CertificationService._generate_certificate_number(db)

        # 计算过期时间
        cert = db.query(Certification).filter(Certification.id == rec.certification_id).first()
        now = datetime.now()
        expires_at = None
        if cert and cert.validity_period_months and cert.validity_period_months > 0:
            expires_at = now + relativedelta(months=cert.validity_period_months)

        rec.status = CertificationStatusEnum.APPROVED.value
        rec.certificate_number = cert_number
        rec.issued_at = now
        rec.expires_at = expires_at
        rec.reviewed_by = reviewer_id
        rec.review_comment = comment

        db.commit()
        db.refresh(rec)
        return success(data=CertificationService._record_to_response(rec), message="认证已批准")

    @staticmethod
    def reject_record(db: Session, record_id: int, reviewer_id: int, comment: Optional[str] = None) -> Dict[str, Any]:
        rec = db.query(CertificationRecord).filter(CertificationRecord.id == record_id).first()
        if not rec:
            return not_found(message="认证记录不存在")
        if rec.status != CertificationStatusEnum.PENDING.value:
            return bad_request(message=f"记录状态不允许审核: {rec.status}")

        rec.status = CertificationStatusEnum.REJECTED.value
        rec.reviewed_by = reviewer_id
        rec.review_comment = comment

        db.commit()
        db.refresh(rec)
        return success(data=CertificationService._record_to_response(rec), message="认证已拒绝")

    @staticmethod
    def revoke_record(
        db: Session, record_id: int, reviewer_id: int, comment: Optional[str] = None,
    ) -> Dict[str, Any]:
        rec = db.query(CertificationRecord).filter(CertificationRecord.id == record_id).first()
        if not rec:
            return not_found(message="认证记录不存在")
        if rec.status != CertificationStatusEnum.APPROVED.value:
            return bad_request(message=f"仅能撤销已批准的证书: {rec.status}")

        rec.status = CertificationStatusEnum.REVOKED.value
        rec.reviewed_by = reviewer_id
        rec.review_comment = comment
        db.commit()
        db.refresh(rec)
        return success(data=CertificationService._record_to_response(rec), message="证书已撤销")

    @staticmethod
    def verify_certificate(db: Session, certificate_number: str) -> Dict[str, Any]:
        CertificationService._sync_expired_records(db)
        rec = db.query(CertificationRecord).filter(
            CertificationRecord.certificate_number == certificate_number,
        ).first()
        if not rec:
            return not_found(message="证书编号不存在")

        cert = db.query(Certification).filter(Certification.id == rec.certification_id).first()
        learner = db.query(LearnerProfile).filter(LearnerProfile.id == rec.learner_id).first()
        now = datetime.now()
        is_valid = rec.status == CertificationStatusEnum.APPROVED.value and (
            rec.expires_at is None or rec.expires_at > now
        )
        return success(data={
            "certificate_number": rec.certificate_number,
            "status": rec.status,
            "is_valid": is_valid,
            "certification_name": cert.name if cert else None,
            "certification_code": cert.code if cert else None,
            "certification_level": cert.level if cert else None,
            "issuer": cert.issuer if cert else None,
            "learner_name": learner.real_name if learner else None,
            "issued_at": rec.issued_at.isoformat() if rec.issued_at else None,
            "expires_at": rec.expires_at.isoformat() if rec.expires_at else None,
        })

    # ===========================================
    # 规则评估引擎（私有）
    # ===========================================

    @staticmethod
    def _evaluate_rules(db: Session, certification_id: int, assessment_record_id: int) -> Dict[str, Any]:
        """评估所有规则是否满足"""
        rules = db.query(CertificationRule).filter(
            CertificationRule.certification_id == certification_id
        ).all()

        if not rules:
            return {"passed": False, "details": [], "reason": "认证未配置发证规则"}

        record = db.query(AssessmentRecord).filter(
            AssessmentRecord.id == assessment_record_id
        ).first()
        if not record:
            return {"passed": False, "details": [], "reason": "评估记录不存在"}

        details = []
        all_passed = True
        for rule in rules:
            result = CertificationService._evaluate_single_rule(db, rule, record)
            details.append({
                "rule_id": rule.id,
                "rule_type": rule.rule_type,
                "rule_config": rule.rule_config,
                "passed": result["passed"],
                "message": result["message"],
            })
            if not result["passed"]:
                all_passed = False

        return {
            "passed": all_passed,
            "details": details,
            "reason": "所有规则满足" if all_passed else "部分规则未满足",
        }

    @staticmethod
    def _evaluate_single_rule(db: Session, rule: CertificationRule, record: AssessmentRecord) -> Dict[str, Any]:
        """评估单条规则"""
        cfg = rule.rule_config or {}

        if rule.rule_type == RuleTypeEnum.OVERALL_SCORE.value:
            min_score = cfg.get("min_score", 60)
            actual = record.overall_score or 0
            passed = actual >= min_score
            return {
                "passed": passed,
                "message": f"综合得分 {actual} {'>=' if passed else '<'} {min_score}",
            }

        elif rule.rule_type == RuleTypeEnum.COMPETENCY_LEVEL.value:
            comp_id = cfg.get("competency_id")
            min_level = cfg.get("min_level", 3)
            cs = db.query(CompetencyScore).filter(
                CompetencyScore.assessment_record_id == record.id,
                CompetencyScore.competency_id == comp_id,
            ).first()
            if not cs:
                return {"passed": False, "message": f"胜任力 {comp_id} 未评估"}
            actual = cs.current_level or 0
            passed = actual >= min_level
            return {
                "passed": passed,
                "message": f"胜任力等级 {actual} {'>=' if passed else '<'} {min_level}",
            }

        elif rule.rule_type == RuleTypeEnum.ALL_MANDATORY_MET.value:
            allow_gap = cfg.get("allow_gap", 0)
            mandatory_ids = {
                item.competency_id for item in db.query(PositionCompetency).filter(
                    PositionCompetency.position_id == record.position_id,
                    PositionCompetency.is_mandatory.is_(True),
                ).all()
            }
            scores = db.query(CompetencyScore).filter(
                CompetencyScore.assessment_record_id == record.id,
            ).all()
            scores_by_competency = {score.competency_id: score for score in scores}
            unmet = sum(
                1 for competency_id in mandatory_ids
                if competency_id not in scores_by_competency
                or (scores_by_competency[competency_id].gap or 0) > 0
            )
            passed = unmet <= allow_gap
            return {
                "passed": passed,
                "message": f"未达标胜任力 {unmet} 项，允许 {allow_gap} 项",
            }

        return {"passed": False, "message": f"未知规则类型: {rule.rule_type}"}

    @staticmethod
    def _validate_rule_config(rule_type: str, config: Dict[str, Any]) -> Optional[str]:
        """验证规则配置，返回错误信息或 None"""
        if rule_type == RuleTypeEnum.OVERALL_SCORE.value:
            if "min_score" not in config:
                return "overall_score 规则需要 min_score 参数"
            if not (0 <= config["min_score"] <= 100):
                return "min_score 必须在 0-100 之间"
        elif rule_type == RuleTypeEnum.COMPETENCY_LEVEL.value:
            if "competency_id" not in config:
                return "competency_level 规则需要 competency_id 参数"
            if "min_level" not in config:
                return "competency_level 规则需要 min_level 参数"
            if not (1 <= config["min_level"] <= 5):
                return "min_level 必须在 1-5 之间"
        elif rule_type == RuleTypeEnum.ALL_MANDATORY_MET.value:
            if "allow_gap" in config and config["allow_gap"] < 0:
                return "allow_gap 不能为负数"
        return None

    # ===========================================
    # 私有辅助方法
    # ===========================================

    @staticmethod
    def _generate_certificate_number(db: Session) -> str:
        """生成证书编号: CERT-YYYYMM-NNNNNN"""
        now = datetime.now()
        prefix = f"CERT-{now.strftime('%Y%m')}-"
        last = db.query(CertificationRecord).filter(
            CertificationRecord.certificate_number.like(f"{prefix}%")
        ).order_by(CertificationRecord.certificate_number.desc()).first()
        if last and last.certificate_number:
            try:
                seq = int(last.certificate_number[-6:]) + 1
            except ValueError:
                seq = 1
        else:
            seq = 1
        return f"{prefix}{seq:06d}"

    @staticmethod
    def _sync_expired_records(db: Session) -> None:
        now = datetime.now()
        records = db.query(CertificationRecord).filter(
            CertificationRecord.status == CertificationStatusEnum.APPROVED.value,
            CertificationRecord.expires_at.isnot(None),
            CertificationRecord.expires_at <= now,
        ).all()
        if not records:
            return
        for record in records:
            record.status = CertificationStatusEnum.EXPIRED.value
        db.commit()

    @staticmethod
    def _certification_to_response(cert: Certification) -> Dict[str, Any]:
        return {
            "id": cert.id,
            "position_id": cert.position_id,
            "name": cert.name,
            "code": cert.code,
            "level": cert.level,
            "description": cert.description,
            "validity_period_months": cert.validity_period_months,
            "issuer": cert.issuer,
            "is_active": cert.is_active,
            "created_at": cert.created_at.isoformat() if cert.created_at else None,
            "updated_at": cert.updated_at.isoformat() if cert.updated_at else None,
        }

    @staticmethod
    def _rule_to_response(rule: CertificationRule) -> Dict[str, Any]:
        return {
            "id": rule.id,
            "certification_id": rule.certification_id,
            "rule_type": rule.rule_type,
            "rule_config": rule.rule_config,
            "created_at": rule.created_at.isoformat() if rule.created_at else None,
        }

    @staticmethod
    def _record_to_response(rec: CertificationRecord) -> Dict[str, Any]:
        return {
            "id": rec.id,
            "certification_id": rec.certification_id,
            "user_id": rec.user_id,
            "learner_id": rec.learner_id,
            "assessment_record_id": rec.assessment_record_id,
            "status": rec.status,
            "certificate_number": rec.certificate_number,
            "rule_evaluation": rec.rule_evaluation,
            "issued_at": rec.issued_at.isoformat() if rec.issued_at else None,
            "expires_at": rec.expires_at.isoformat() if rec.expires_at else None,
            "reviewed_by": rec.reviewed_by,
            "review_comment": rec.review_comment,
            "created_at": rec.created_at.isoformat() if rec.created_at else None,
            "updated_at": rec.updated_at.isoformat() if rec.updated_at else None,
        }
