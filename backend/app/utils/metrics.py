"""
指标自动计算工具
计算幻觉率、资源匹配准确率、知识点覆盖率等核心量化指标
"""
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from loguru import logger
from app.utils.datetime import utcnow_naive


class MetricsUtil:
    """指标自动计算工具类"""
    
    @staticmethod
    def calculate_hallucination_rate(
        db: Session,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> float:
        """
        计算知识幻觉错误率
        
        Args:
            db: 数据库会话
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            幻觉率（百分比）
        """
        from app.models import DebateRecord
        
        # 查询辩论记录表
        query = db.query(DebateRecord)
        
        if start_date:
            query = query.filter(DebateRecord.created_at >= start_date)
        if end_date:
            query = query.filter(DebateRecord.created_at <= end_date)
        
        # 统计总数和幻觉数
        total_records = query.count()
        hallucination_records = query.filter(DebateRecord.is_hallucination == True).count()
        
        if total_records == 0:
            return 0.0
        
        rate = (hallucination_records / total_records) * 100
        
        logger.debug(f"幻觉率计算: 总数={total_records}, 幻觉数={hallucination_records}, rate={rate}%")
        
        return round(rate, 2)
    
    @staticmethod
    def calculate_resource_match_accuracy(
        db: Session,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> float:
        """
        计算资源匹配准确率
        
        Args:
            db: 数据库会话
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            匹配准确率（百分比）
        """
        from app.models import LearningResource
        
        query = db.query(LearningResource)
        
        if start_date:
            query = query.filter(LearningResource.created_at >= start_date)
        if end_date:
            query = query.filter(LearningResource.created_at <= end_date)
        
        # 统计总数和校验通过数
        total_resources = query.count()
        validated_passed = query.filter(
            LearningResource.is_validated == True,
            LearningResource.validation_passed == True
        ).count()
        
        if total_resources == 0:
            return 0.0
        
        rate = (validated_passed / total_resources) * 100
        
        logger.debug(f"匹配准确率: 总数={total_resources}, 通过数={validated_passed}, rate={rate}%")
        
        return round(rate, 2)
    
    @staticmethod
    def calculate_knowledge_coverage_rate(
        db: Session,
        industry: Optional[str] = None,
    ) -> float:
        """
        计算知识点覆盖率
        
        Args:
            db: 数据库会话
            industry: 行业领域（可选）
            
        Returns:
            覆盖率（百分比）
        """
        from app.models import KnowledgeDoc
        
        query = db.query(KnowledgeDoc)
        
        if industry:
            query = query.filter(KnowledgeDoc.industry == industry)
        
        # 统计切片总数和已索引数（SQL 聚合避免全表加载）
        total_slices = query.with_entities(func.sum(KnowledgeDoc.slice_count)).scalar() or 0
        indexed_slices = query.with_entities(func.sum(KnowledgeDoc.indexed_slice_count)).scalar() or 0
        
        if total_slices == 0:
            return 0.0
        
        rate = (indexed_slices / total_slices) * 100
        
        logger.debug(f"知识点覆盖率: 总切片={total_slices}, 已索引={indexed_slices}, rate={rate}%")
        
        return round(rate, 2)
    
    @staticmethod
    def calculate_all_metrics(db: Session) -> Dict[str, float]:
        """
        计算所有核心指标
        
        Args:
            db: 数据库会话
            
        Returns:
            指标字典
        """
        metrics = {
            "hallucination_rate": MetricsUtil.calculate_hallucination_rate(db),
            "resource_match_accuracy": MetricsUtil.calculate_resource_match_accuracy(db),
            "knowledge_coverage_rate": MetricsUtil.calculate_knowledge_coverage_rate(db),
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
            "accuracy_rate": round((correct_answers / total_answers * 100) if total_answers > 0 else 0, 2),
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
        start_date = date.replace(hour=0, minute=0, second=0)
        end_date = start_date + timedelta(days=1)
        
        report = {
            "date": date.strftime("%Y-%m-%d"),
            "hallucination_rate": MetricsUtil.calculate_hallucination_rate(db, start_date, end_date),
            "resource_match_accuracy": MetricsUtil.calculate_resource_match_accuracy(db, start_date, end_date),
            "knowledge_coverage_rate": MetricsUtil.calculate_knowledge_coverage_rate(db),
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
            hallucination_rate=metrics.get("hallucination_rate", 0),
            resource_match_accuracy=metrics.get("resource_match_accuracy", 0),
            knowledge_coverage_rate=metrics.get("knowledge_coverage_rate", 0),
            detailed_metrics=metrics,
        )
        
        db.add(record)
        db.commit()
        
        logger.info(f"指标记录已保存: id={record.id}")