"""
指标自动计算工具
计算幻觉率、资源匹配准确率、知识点覆盖率等核心量化指标
"""
import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from loguru import logger
from app.utils.datetime import utcnow_naive


class MetricsUtil:
    """指标自动计算工具类"""
    
    HALLUCINATION_POLICY_VERSION = "hallucination-rate-v1"
    MIN_HALLUCINATION_SAMPLE = 10
    FORMAL_MIN_HALLUCINATION_SAMPLE = 60
    HALLUCINATION_TARGET_PERCENT = 5.0
    RECENT_WINDOW_DAYS = 30
    HALLUCINATION_STATES = (
        "reviewed_clean",
        "reviewed_hallucination",
        "evidence_gap",
        "pending_review",
        "invalid_record",
    )
    EVIDENCE_GAP_MARKERS = {
        "knowledge_gap",
        "no_reference",
        "evidence_gap",
        "insufficient_evidence",
    }

    @classmethod
    def _contains_evidence_gap(cls, value: Any) -> bool:
        """Recognize evidence-gap markers in old and new JSON payloads."""
        if value is None:
            return False
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return False
            try:
                return cls._contains_evidence_gap(json.loads(raw))
            except (TypeError, ValueError, json.JSONDecodeError):
                normalized = raw.lower().replace("-", "_").replace(" ", "_")
                return any(marker in normalized for marker in cls.EVIDENCE_GAP_MARKERS)
        if isinstance(value, dict):
            return any(cls._contains_evidence_gap(item) for item in value.values())
        if isinstance(value, (list, tuple, set)):
            return any(cls._contains_evidence_gap(item) for item in value)
        return False

    @classmethod
    def _is_reviewed_record(cls, record: Any) -> bool:
        status = str(getattr(record, "resolution_status", "") or "").lower()
        decision = str(getattr(record, "judge_decision", "") or "").lower()
        return status in {"resolved", "reviewed", "verified"} or decision in {
            "approved", "rejected", "confirmed", "resolved"
        }

    @classmethod
    def _audit_metadata(cls, record: Any) -> Dict[str, Any]:
        """Read the standardized audit metadata while supporting legacy JSON."""
        value = getattr(record, "agent_judge_view", None)
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return {}
            try:
                value = json.loads(raw)
            except (TypeError, ValueError, json.JSONDecodeError):
                return {}
        if not isinstance(value, dict):
            return {}
        metadata = value.get("audit_metadata")
        return metadata if isinstance(metadata, dict) else {}

    @classmethod
    def _is_invalid_record(cls, record: Any) -> bool:
        """Reject records that cannot be audited without guessing."""
        original_content = getattr(record, "original_content", None)
        if not isinstance(original_content, str) or not original_content.strip():
            return True

        json_fields = (
            "agent_judge_view",
            "agent_generation_view",
            "comparison_summary",
            "conflict_description",
            "judge_notes",
        )
        for field_name in json_fields:
            value = getattr(record, field_name, None)
            if not isinstance(value, str) or not value.strip():
                continue
            raw = value.strip()
            if raw[0] not in "[{":
                continue
            try:
                json.loads(raw)
            except (TypeError, ValueError, json.JSONDecodeError):
                return True
        return False

    @classmethod
    def _is_evidence_gap_record(cls, record: Any) -> bool:
        metadata = cls._audit_metadata(record)
        evidence_status = str(metadata.get("evidence_status", "") or "").lower()
        if evidence_status in {"gap", "evidence_gap", "insufficient_evidence"}:
            return True
        fields = (
            getattr(record, "hallucination_type", None),
            getattr(record, "hallucination_keywords", None),
            getattr(record, "comparison_summary", None),
            getattr(record, "conflict_description", None),
            getattr(record, "judge_notes", None),
        )
        return any(cls._contains_evidence_gap(field) for field in fields)

    @classmethod
    def _is_high_risk_record(cls, record: Any) -> bool:
        severity = str(getattr(record, "conflict_severity", "") or "").lower()
        if severity in {"high", "critical"}:
            return True
        metadata = cls._audit_metadata(record)
        risk_flags = metadata.get("risk_flags", [])
        if isinstance(risk_flags, dict):
            risk_flags = [risk_flags]
        if not isinstance(risk_flags, (list, tuple, set)):
            risk_flags = [risk_flags]
        for flag in risk_flags:
            if isinstance(flag, dict):
                flag_type = str(flag.get("type", "") or "").lower()
                flag_severity = str(flag.get("severity", "") or "").lower()
                if flag_type in {"safety", "regulatory", "security"}:
                    return True
                if flag_severity in {"high", "critical"}:
                    return True
            elif str(flag or "").lower() in {"safety", "regulatory", "security"}:
                return True
        return False

    @classmethod
    def classify_debate_record(cls, record: Any) -> str:
        """Classify one record into the mutually exclusive metric states."""
        if cls._is_invalid_record(record):
            return "invalid_record"

        metadata = cls._audit_metadata(record)
        evidence_status = str(metadata.get("evidence_status", "") or "").lower()
        review_outcome = str(metadata.get("review_outcome", "") or "").lower()
        if evidence_status in {"gap", "evidence_gap", "insufficient_evidence"}:
            return "evidence_gap"
        if review_outcome in {"pending", "pending_review", "needs_review"}:
            return "pending_review"
        if cls._is_evidence_gap_record(record):
            return "evidence_gap"
        if not cls._is_reviewed_record(record):
            return "pending_review"
        if review_outcome in {"hallucination", "reviewed_hallucination"}:
            return "reviewed_hallucination"
        if review_outcome in {"clean", "reviewed_clean"}:
            return "reviewed_clean"
        return "reviewed_hallucination" if bool(getattr(record, "is_hallucination", False)) else "reviewed_clean"

    @classmethod
    def calculate_hallucination_metrics(
        cls,
        db: Session,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        learner_id: Optional[int] = None,
        minimum_sample_size: Optional[int] = None,
        window_days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Calculate a rate from reviewed, evidence-backed records only."""
        from app.models import AgentTask, DebateRecord

        if start_date is not None and window_days is not None:
            raise ValueError("start_date and window_days cannot be used together")
        if window_days is not None:
            if not isinstance(window_days, int) or window_days <= 0:
                raise ValueError("window_days must be a positive integer")
            start_date = utcnow_naive() - timedelta(days=window_days)

        effective_minimum = (
            cls.MIN_HALLUCINATION_SAMPLE
            if minimum_sample_size is None
            else int(minimum_sample_size)
        )
        if effective_minimum < 0:
            raise ValueError("minimum_sample_size cannot be negative")

        query = db.query(DebateRecord)
        if learner_id is not None:
            query = query.join(AgentTask, DebateRecord.task_id == AgentTask.id).filter(
                AgentTask.learner_id == learner_id
            )
        if start_date:
            query = query.filter(DebateRecord.created_at >= start_date)
        if end_date:
            query = query.filter(DebateRecord.created_at <= end_date)

        records = query.all()
        state_counts = {state: 0 for state in cls.HALLUCINATION_STATES}
        high_risk_checks = 0
        high_risk_reviewed = 0
        for record in records:
            state = cls.classify_debate_record(record)
            state_counts[state] += 1
            if cls._is_high_risk_record(record):
                high_risk_checks += 1
                if state in {"reviewed_clean", "reviewed_hallucination"}:
                    high_risk_reviewed += 1

        total_checks = len(records)
        evidence_gap_count = state_counts["evidence_gap"]
        pending_checks = state_counts["pending_review"]
        evaluated_checks = state_counts["reviewed_clean"] + state_counts["reviewed_hallucination"]
        confirmed_hallucinations = state_counts["reviewed_hallucination"]
        has_sufficient_sample = evaluated_checks >= effective_minimum
        hallucination_rate = (
            round(confirmed_hallucinations / evaluated_checks * 100, 2)
            if has_sufficient_sample
            else None
        )
        pass_rate = (
            round((evaluated_checks - confirmed_hallucinations) / evaluated_checks * 100, 2)
            if has_sufficient_sample
            else None
        )
        high_risk_review_coverage = (
            round(high_risk_reviewed / high_risk_checks * 100, 2)
            if high_risk_checks
            else 100.0
        )

        return {
            "total_checks": total_checks,
            "total_count": total_checks,
            "evaluated_checks": evaluated_checks,
            "pending_checks": pending_checks,
            "confirmed_hallucinations": confirmed_hallucinations,
            "hallucination_count": confirmed_hallucinations,
            "evidence_gaps": evidence_gap_count,
            "invalid_records": state_counts["invalid_record"],
            "state_counts": state_counts,
            "high_risk_checks": high_risk_checks,
            "high_risk_reviewed": high_risk_reviewed,
            "high_risk_review_coverage": high_risk_review_coverage,
            "hallucination_rate": hallucination_rate,
            "pass_rate": pass_rate,
            "has_sufficient_sample": has_sufficient_sample,
            "minimum_sample_size": effective_minimum,
            "formal_minimum_sample_size": cls.FORMAL_MIN_HALLUCINATION_SAMPLE,
            "target_percent": cls.HALLUCINATION_TARGET_PERCENT,
            "policy_version": cls.HALLUCINATION_POLICY_VERSION,
            "window": {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None,
                "days": window_days,
            },
            "unit": "%",
        }

    @staticmethod
    def calculate_hallucination_rate(
        db: Session,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Optional[float]:
        """
        计算知识幻觉错误率
        
        Args:
            db: 数据库会话
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            幻觉率（百分比）
        """
        metrics = MetricsUtil.calculate_hallucination_metrics(db, start_date, end_date)
        return (
            float(metrics["hallucination_rate"])
            if metrics["hallucination_rate"] is not None
            else None
        )
    
    @staticmethod
    def calculate_resource_match_accuracy(
        db: Session,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Optional[float]:
        """
        计算资源匹配准确率
        
        Args:
            db: 数据库会话
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            匹配准确率（百分比）
        """
        from app.services.metric_service import MetricService

        result = MetricService.calculate_metrics(
            db,
            scope="global",
            metric_ids=["resource_match_score"],
        )
        return result[0]["value"] if result else None

    
    @staticmethod
    def calculate_knowledge_coverage_rate(
        db: Session,
        industry: Optional[str] = None,
    ) -> Optional[float]:
        """
        计算知识点覆盖率
        
        Args:
            db: 数据库会话
            industry: 行业领域（可选）
            
        Returns:
            覆盖率（百分比）
        """
        if industry:
            return MetricsUtil.calculate_knowledge_index_coverage_rate(db, industry)

        from app.services.metric_service import MetricService

        result = MetricService.calculate_metrics(
            db,
            scope="global",
            metric_ids=["knowledge_index_coverage"],
        )
        return result[0]["value"] if result else None


    @staticmethod
    def calculate_knowledge_index_coverage_rate(
        db: Session,
        industry: Optional[str] = None,
    ) -> Optional[float]:
        """Return the live vector-index coverage of knowledge slices.

        System-level dashboards must use the same source as the readiness
        checks.  A missing knowledge base is represented by ``None`` instead
        of ``0`` so callers can distinguish "no data" from a failed index.
        """
        from app.models import KnowledgeSlice

        query = db.query(KnowledgeSlice)
        if industry:
            query = query.filter(KnowledgeSlice.doc.has(industry=industry))

        total_slices = query.count()
        if total_slices == 0:
            return None

        indexed_slices = query.filter(KnowledgeSlice.is_indexed == True).count()
        return round(indexed_slices / total_slices * 100, 2)

    @staticmethod
    def calculate_learning_blind_spot_coverage_rate(db: Session) -> Optional[float]:
        """Return how many learner blind spots are covered by generated content.

        This is intentionally separate from knowledge-index coverage.  The
        two values answer different questions and must not share a field name.
        """
        from app.services.metric_service import MetricService

        result = MetricService.calculate_metrics(
            db,
            scope="global",
            metric_ids=["blind_spot_resource_coverage"],
        )
        return result[0]["value"] if result else None

    
    @staticmethod
    def calculate_all_metrics(db: Session) -> Dict[str, Any]:
        """
        计算所有核心指标
        
        Args:
            db: 数据库会话
            
        Returns:
            指标字典
        """
        # Compatibility adapter: MetricService owns canonical values/statuses.
        from app.services.metric_service import MetricService

        standard = MetricService.calculate_metrics(db, scope="global")
        by_id = MetricService.by_id(standard)
        metrics = {
            "metrics": standard,
            "hallucination_rate": by_id.get("hallucination_rate", {}).get("value"),
            "resource_match_accuracy": by_id.get("resource_match_score", {}).get("value"),
            "knowledge_coverage_rate": by_id.get("knowledge_index_coverage", {}).get("value"),
            "generated_content_coverage_rate": by_id.get("generated_content_coverage", {}).get("value"),
        }
        
        logger.info(f"核心指标计算完成: {metrics}")
        
        return metrics
    
    @staticmethod
    def calculate_agent_performance(
        db: Session,
        agent_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        计算Agent执行性能
        
        Args:
            db: 数据库会话
            agent_type: Agent类型（可选）
            
        Returns:
            性能指标字典
        """
        from app.models import AgentTask
        
        query = db.query(AgentTask)
        
        if agent_type:
            query = query.filter(AgentTask.agent_type == agent_type)
        
        # 统计任务
        total_tasks = query.count()
        success_tasks = query.filter(AgentTask.status == "completed").count()
        failed_tasks = query.filter(AgentTask.status == "failed").count()
        
        # 计算平均耗时
        avg_duration = db.query(func.avg(AgentTask.duration_ms)).filter(
            AgentTask.status == "completed"
        ).scalar() or 0
        
        # 计算Token消耗
        total_tokens = db.query(func.sum(AgentTask.total_tokens)).scalar() or 0
        
        metrics = {
            "total_tasks": total_tasks,
            "success_tasks": success_tasks,
            "failed_tasks": failed_tasks,
            "success_rate": round((success_tasks / total_tasks * 100) if total_tasks > 0 else 0, 2),
            "avg_duration_ms": round(avg_duration, 2),
            "total_tokens": total_tokens,
        }
        
        return metrics
    
    @staticmethod
    def calculate_answer_statistics(
        db: Session,
        learner_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        计算答题统计
        
        Args:
            db: 数据库会话
            learner_id: 学习者ID（可选）
            
        Returns:
            答题统计字典
        """
        from app.models import AnswerRecord
        
        query = db.query(AnswerRecord)
        
        if learner_id:
            query = query.filter(AnswerRecord.learner_id == learner_id)
        
        total_answers = query.count()
        correct_answers = query.filter(AnswerRecord.result == "correct").count()
        wrong_answers = query.filter(AnswerRecord.result == "wrong").count()
        
        # 计算平均答题耗时
        avg_time = db.query(func.avg(AnswerRecord.time_spent_ms)).scalar() or 0
        
        # 自适应决策分布
        advance_count = query.filter(AnswerRecord.agent_decision == "advance").count()
        simplify_count = query.filter(AnswerRecord.agent_decision == "simplify").count()
        maintain_count = query.filter(AnswerRecord.agent_decision == "maintain").count()
        
        metrics = {
            "total_answers": total_answers,
            "correct_answers": correct_answers,
            "wrong_answers": wrong_answers,
            "accuracy_rate": round((correct_answers / total_answers * 100), 2) if total_answers > 0 else None,
            "avg_time_ms": round(avg_time, 2),
            "adaptive_distribution": {
                "advance": advance_count,
                "simplify": simplify_count,
                "maintain": maintain_count,
            },
        }
        
        return metrics
    
    @staticmethod
    def generate_daily_report(db: Session, date: datetime) -> Dict[str, Any]:
        """
        生成每日指标报告
        
        Args:
            db: 数据库会话
            date: 报告日期
            
        Returns:
            每日报告字典
        """
        from app.services.metric_service import MetricService

        standard = MetricService.calculate_metrics(db, scope="global", calculated_at=date)
        by_id = MetricService.by_id(standard)
        report = {
            "date": date.strftime("%Y-%m-%d"),
            "metrics": standard,
            "hallucination_rate": by_id.get("hallucination_rate", {}).get("value"),
            "resource_match_accuracy": by_id.get("resource_match_score", {}).get("value"),
            "knowledge_coverage_rate": by_id.get("knowledge_index_coverage", {}).get("value"),
            "generated_content_coverage_rate": by_id.get("generated_content_coverage", {}).get("value"),
            "agent_performance": MetricsUtil.calculate_agent_performance(db),
            "answer_stats": MetricsUtil.calculate_answer_statistics(db),
        }
        
        logger.info(f"生成每日报告: {date.strftime('%Y-%m-%d')}")
        
        return report
    
    @staticmethod
    def save_metrics_record(db: Session, metrics: Dict[str, Any]) -> None:
        """
        保存指标记录到数据库
        
        Args:
            db: 数据库会话
            metrics: 指标字典
        """
        from app.models import TestMetrics
        
        record = TestMetrics(
            record_date=utcnow_naive(),
            record_period="daily",
            # Missing values must remain NULL.  A real zero is a calculated
            # result and must never be substituted for an unavailable value.
            hallucination_rate=metrics.get("hallucination_rate"),
            resource_match_accuracy=metrics.get("resource_match_accuracy"),
            knowledge_coverage_rate=metrics.get("knowledge_coverage_rate"),
            detailed_metrics=metrics,
        )
        
        db.add(record)
        db.commit()
        
        logger.info(f"指标记录已保存: id={record.id}")
