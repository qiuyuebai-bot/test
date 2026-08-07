"""
任务数据仓库

封装 AgentTask 相关的数据库操作：创建、状态更新、日志、指标、辩论记录、资源保存。
将持久化逻辑与编排逻辑分离，便于单测与后续替换存储层。
"""
import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.attributes import flag_modified

from app.database import get_db_context
from app.models import AgentTask, DebateRecord, LearningResource, LearnerProfile
from app.utils.resource_content import normalize_resource_content


class TaskRepository:
    """AgentTask 数据访问与状态管理"""

    # 任务类型常量
    TASK_TYPE_DIAGNOSIS = "learner_diagnosis"
    TASK_TYPE_RESOURCE_GENERATION = "resource_generation"
    TASK_TYPE_FULL_PIPELINE = "full_pipeline"

    # 流程阶段
    FLOW_STAGES = [
        "init", "diagnosis", "knowledge_retrieval", "generation",
        "judge_first", "debate", "final_revision", "complete",
    ]

    def create_task(
        self,
        learner_id: int,
        task_name: str,
        task_type: str,
        input_data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """创建 Agent 任务并返回任务信息"""
        with get_db_context() as db:
            task = AgentTask(
                learner_id=learner_id,
                task_name=task_name,
                task_type=task_type,
                agent_type="system",
                flow_stage="init",
                flow_description="任务初始化",
                input_data=json.dumps(input_data or {}, ensure_ascii=False),
                status="pending",
                progress=0,
            )
            db.add(task)
            db.flush()
            db.commit()
            task_id = task.id
            logger.info(f"[TaskRepo] 创建任务: task_id={task_id}, type={task_type}")
        return self.get_task_info(task_id)

    def get_task_info(self, task_id: int) -> Dict[str, Any]:
        """获取任务基本信息"""
        with get_db_context() as db:
            task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
            if not task:
                return {}
            return {
                "task_id": task.id,
                "task_name": task.task_name,
                "task_type": task.task_type,
                "status": task.status,
                "progress": task.progress,
                "created_at": task.created_at.isoformat() if task.created_at else None,
            }

    def get_task_status(self, task_id: int, cached: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        获取任务状态，优先用内存缓存，回退到数据库

        Args:
            task_id: 任务ID
            cached: 内存缓存中的任务状态（由调用方提供）
        """
        if cached:
            return {
                "task_id": task_id,
                "status": cached.get("status", "running"),
                "progress": cached.get("progress", 0),
                "stage": cached.get("stage", ""),
                "description": cached.get("description", ""),
                "logs": cached.get("logs", []),
                "error": cached.get("error"),
                "source": "cache",
            }

        with get_db_context() as db:
            task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
            if not task:
                return {"error": "任务不存在", "task_id": task_id}
            return {
                "task_id": task.id,
                "task_name": task.task_name,
                "task_type": task.task_type,
                "status": task.status,
                "progress": task.progress or 0,
                "stage": task.flow_stage,
                "description": task.flow_description,
                "agent_type": task.agent_type,
                "logs": task.execution_logs or [],
                "error": task.error_message,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "duration_ms": task.duration_ms or 0,
                "source": "database",
            }

    def get_task_logs(self, task_id: int, cached_logs: Optional[List[Dict]] = None) -> List[Dict[str, Any]]:
        """获取任务日志，优先用内存缓存"""
        if cached_logs is not None:
            return list(cached_logs)

        with get_db_context() as db:
            task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
            if task and task.execution_logs:
                return task.execution_logs
        return []

    def update_stage(
        self,
        task_id: int,
        stage: str,
        progress: int,
        description: str,
    ) -> None:
        """更新任务阶段到数据库（权威数据源）"""
        log_entry = {
            "stage": stage,
            "progress": progress,
            "description": description,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        try:
            with get_db_context() as db:
                task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
                if task:
                    task.flow_stage = stage
                    task.flow_description = description
                    task.progress = progress
                    task.status = "running" if progress < 100 else "completed"
                    existing_logs = task.execution_logs or []
                    existing_logs.append(log_entry)
                    if len(existing_logs) > 200:
                        existing_logs = existing_logs[-200:]
                    task.execution_logs = existing_logs
                    flag_modified(task, "execution_logs")
                    if stage in ("diagnosis", "knowledge_retrieval") and not task.started_at:
                        task.started_at = datetime.now()
                    db.commit()
        except Exception as e:
            logger.warning(f"[TaskRepo] 更新阶段到DB失败: {e}")

    def update_output_data(self, task_id: int, stage: str, result: Dict[str, Any], agent_type: str = None) -> None:
        """更新任务输出数据"""
        with get_db_context() as db:
            task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
            if task:
                task.flow_stage = stage
                task.output_data = json.dumps(result, ensure_ascii=False, default=str)
                if agent_type:
                    task.agent_type = agent_type
                db.commit()

    def mark_failed(self, task_id: int, error: str) -> None:
        """标记任务失败"""
        try:
            with get_db_context() as db:
                task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
                if task:
                    task.status = "failed"
                    task.error_message = error
                    task.flow_stage = "failed"
                    existing_logs = task.execution_logs or []
                    existing_logs.append({
                        "stage": "failed",
                        "description": f"任务失败: {error}",
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    })
                    task.execution_logs = existing_logs
                    flag_modified(task, "execution_logs")
                    task.completed_at = datetime.now()
                    db.commit()
        except Exception as e:
            logger.warning(f"[TaskRepo] 标记失败到DB失败: {e}")

    def save_debate_record(
        self,
        task_id: int,
        round_num: int,
        debate_data: Dict[str, Any],
    ) -> None:
        """保存辩论记录到数据库"""
        with get_db_context() as db:
            record = DebateRecord(
                task_id=task_id,
                debate_round=round_num,
                debate_type="cross_validation",
                agent_diagnosis_view=json.dumps({}, ensure_ascii=False),
                agent_generation_view=json.dumps(
                    debate_data.get("generation_counterargument", {}),
                    ensure_ascii=False,
                    default=str,
                ),
                agent_judge_view=json.dumps(
                    debate_data.get("judge_standpoint", {}),
                    ensure_ascii=False,
                    default=str,
                ),
                original_content="",
                reference_content="",
                comparison_summary=json.dumps(
                    debate_data.get("conflict_points", []),
                    ensure_ascii=False,
                    default=str,
                ),
                has_conflict=len(debate_data.get("conflict_points", [])) > 0,
                conflict_type="content_audit" if debate_data.get("conflict_points") else "none",
                conflict_severity="high" if any(
                    p.get("severity") == "high"
                    for p in debate_data.get("conflict_points", [])
                ) else "medium",
                conflict_description=json.dumps(
                    debate_data.get("conflict_points", []),
                    ensure_ascii=False,
                    default=str,
                ),
                is_hallucination=any(
                    p.get("type") == "hallucination_evidence"
                    for p in debate_data.get("conflict_points", [])
                ),
                resolution_status="resolved" if debate_data.get(
                    "final_decision"
                ) == "approved" else "unresolved",
                corrected_content=debate_data.get("corrected_content", ""),
                correction_reason=json.dumps(
                    [c.get("description", "") for c in debate_data.get("corrections", [])],
                    ensure_ascii=False,
                ),
                judge_decision=debate_data.get("final_decision", ""),
                judge_confidence=debate_data.get("confidence", 0.0),
                judge_notes=json.dumps(
                    debate_data.get("corrections", []),
                    ensure_ascii=False,
                    default=str,
                ),
            )
            db.add(record)
            db.commit()

    def save_resource_and_complete(
        self,
        task_id: int,
        learner_id: int,
        generation_result: Dict[str, Any],
        audit_result: Dict[str, Any],
        debate_rounds: int,
    ) -> Dict[str, Any]:
        """保存学习资源并标记任务完成"""
        generation_result = dict(generation_result or {})
        generation_result["content"] = normalize_resource_content(
            generation_result.get("content")
        )
        generation_result["word_count"] = len(generation_result["content"])

        with get_db_context() as db:
            task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
            task_input = task.input_data if task else {}
            if isinstance(task_input, str):
                try:
                    task_input = json.loads(task_input)
                except json.JSONDecodeError:
                    task_input = {}
            topic = task_input.get("target_topic", "") if isinstance(task_input, dict) else ""
            resource = db.query(LearningResource).filter(
                LearningResource.generation_task_id == task_id
            ).first()
            if not resource:
                try:
                    with db.begin_nested():
                        resource = LearningResource(
                            learner_id=learner_id,
                            title=generation_result.get("resource_title", "未命名资源"),
                            resource_type=generation_result.get("resource_type", "guide"),
                            knowledge_topic=topic or None,
                            difficulty_level=generation_result.get("difficulty_level", 3),
                            version="1.0",
                            content=generation_result.get("content", ""),
                            content_json=generation_result.get("content_json", {}),
                            word_count=generation_result.get("word_count", 0),
                            source_slice_ids=generation_result.get("source_slice_ids", []),
                            source_doc_ids=generation_result.get("source_doc_ids", []),
                            generated_by_agent="generation_agent",
                            generation_task_id=task_id,
                            generation_method=generation_result.get("generation_method", "deterministic_fallback"),
                            is_validated=audit_result.get("passed", False),
                            validation_passed=audit_result.get("passed", False),
                            validation_score=audit_result.get("overall_score", 0),
                            hallucination_detected=audit_result.get("hallucination_detected", False),
                            status="ready" if audit_result.get("passed", False) else "failed",
                        )
                        db.add(resource)
                        db.flush()
                except IntegrityError:
                    resource = db.query(LearningResource).filter(
                        LearningResource.generation_task_id == task_id
                    ).first()
                    if not resource:
                        raise
            resource_id = resource.id

            issued_question_count = 0
            if resource.validation_passed and resource.resource_type == "exercise":
                from app.services.tutoring_service import AdaptiveTutoringService

                learner = db.query(LearnerProfile).filter(LearnerProfile.id == learner_id).first()
                if not learner:
                    raise ValueError("学习者不存在，无法发布导学题目")
                issued_question_count = AdaptiveTutoringService.publish_resource_questions(
                    db=db,
                    resource=resource,
                    learner=learner,
                    topic=topic,
                )

            if task:
                task.status = "completed"
                task.progress = 100
                task.flow_stage = "complete"
                task.output_data = json.dumps(
                    {"resource_id": resource_id},
                    ensure_ascii=False,
                )
                task.completed_at = datetime.now()
                if audit_result.get("_meta", {}).get("duration_ms"):
                    task.duration_ms = audit_result["_meta"]["duration_ms"]
            db.commit()

        return {
            "task_id": task_id,
            "resource_id": resource_id,
            "generation_result": generation_result,
            "audit_result": audit_result,
            "debate_rounds": debate_rounds,
            "final_score": audit_result.get("overall_score", 0),
            "passed": audit_result.get("passed", False),
            "issued_question_count": issued_question_count,
        }

    def find_reusable_resource(
        self,
        learner_id: int,
        target_topic: str,
        resource_type: str,
    ) -> Optional[Dict[str, Any]]:
        """Find the latest validated resource matching a learner and topic."""
        topic = (target_topic or "").strip()
        if not topic:
            return None

        with get_db_context() as db:
            resource = (
                db.query(LearningResource)
                .filter(
                    LearningResource.learner_id == learner_id,
                    LearningResource.resource_type == resource_type,
                    LearningResource.status == "ready",
                    LearningResource.content.isnot(None),
                    LearningResource.content != "",
                    LearningResource.word_count >= 200,
                    or_(
                        LearningResource.knowledge_topic == topic,
                        and_(
                            LearningResource.knowledge_topic.is_(None),
                            LearningResource.title.contains(topic),
                        ),
                    ),
                )
                .order_by(LearningResource.created_at.desc(), LearningResource.id.desc())
                .first()
            )
            if not resource:
                return None
            return {
                "id": resource.id,
                "title": resource.title,
                "resource_type": resource.resource_type,
                "knowledge_topic": resource.knowledge_topic or topic,
                "difficulty_level": resource.difficulty_level,
                "content": resource.content,
                "content_json": resource.content_json or {},
                "word_count": resource.word_count or len(resource.content or ""),
                "source_slice_ids": resource.source_slice_ids or [],
                "source_doc_ids": resource.source_doc_ids or [],
                "generation_method": resource.generation_method or "deterministic_fallback",
                "validation_score": resource.validation_score or 0,
                "hallucination_detected": bool(resource.hallucination_detected),
            }

    def save_reused_resource_and_complete(
        self,
        task_id: int,
        learner_id: int,
        reusable_resource: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Copy an existing resource and complete the current task."""
        generation_result = {
            "resource_type": reusable_resource.get("resource_type", "guide"),
            "knowledge_topic": reusable_resource.get("knowledge_topic"),
            "resource_title": reusable_resource.get("title", "Unnamed resource"),
            "difficulty_level": reusable_resource.get("difficulty_level", 3),
            "content": reusable_resource.get("content", ""),
            "content_json": reusable_resource.get("content_json", {}),
            "word_count": reusable_resource.get("word_count") or len(reusable_resource.get("content", "")),
            "source_slice_ids": reusable_resource.get("source_slice_ids", []),
            "source_doc_ids": reusable_resource.get("source_doc_ids", []),
            "generation_method": "reused_existing",
            "reused_from_resource_id": reusable_resource.get("id"),
        }
        generation_result["content"] = normalize_resource_content(
            generation_result["content"]
        )
        generation_result["word_count"] = len(generation_result["content"])
        audit_result = {
            "passed": True,
            "overall_score": reusable_resource.get("validation_score", 0),
            "hallucination_detected": reusable_resource.get("hallucination_detected", False),
        }

        with get_db_context() as db:
            resource = LearningResource(
                learner_id=learner_id,
                parent_resource_id=reusable_resource.get("id"),
                title=generation_result["resource_title"],
                resource_type=generation_result["resource_type"],
                knowledge_topic=generation_result["knowledge_topic"],
                difficulty_level=generation_result["difficulty_level"],
                version="1.0",
                content=generation_result["content"],
                content_json=generation_result["content_json"],
                word_count=generation_result["word_count"],
                source_slice_ids=generation_result["source_slice_ids"],
                source_doc_ids=generation_result["source_doc_ids"],
                generated_by_agent="generation_agent",
                generation_task_id=task_id,
                generation_method=generation_result["generation_method"],
                is_validated=True,
                validation_passed=True,
                validation_score=audit_result["overall_score"],
                hallucination_detected=audit_result["hallucination_detected"],
                status="ready",
            )
            db.add(resource)
            db.flush()
            resource_id = resource.id

            task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
            if task:
                task.status = "completed"
                task.progress = 100
                task.flow_stage = "complete"
                task.output_data = json.dumps(
                    {"resource_id": resource_id, "reused_from_resource_id": reusable_resource.get("id")},
                    ensure_ascii=False,
                )
                task.completed_at = datetime.now()
            db.commit()

        return {
            "task_id": task_id,
            "resource_id": resource_id,
            "generation_result": generation_result,
            "audit_result": audit_result,
            "debate_rounds": 0,
            "final_score": audit_result["overall_score"],
            "passed": True,
            "reused_from_resource_id": reusable_resource.get("id"),
        }

    def save_metrics(
        self,
        task_id: int,
        audit_result: Dict[str, Any],
        debate_results: List[Dict[str, Any]],
    ) -> None:
        """记录任务指标到 execution_logs"""
        hallucination_count = sum(
            1 for d in debate_results
            for c in d.get("corrections", [])
            if c.get("type") == "hallucination_evidence"
        )
        total_corrections = sum(len(d.get("corrections", [])) for d in debate_results)
        metrics = {
            "audit_score": audit_result.get("overall_score", 0),
            "audit_passed": audit_result.get("passed", False),
            "debate_rounds": len(debate_results),
            "total_corrections": total_corrections,
            "hallucination_detected": hallucination_count,
        }
        logger.info(f"[TaskRepo] 任务指标 task_id={task_id}: {metrics}")
        try:
            with get_db_context() as db:
                task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
                if task:
                    existing = task.execution_logs or []
                    existing.append({
                        "stage": "metrics",
                        "description": "任务指标统计",
                        "metrics": metrics,
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    })
                    task.execution_logs = existing[-200:]
                    flag_modified(task, "execution_logs")
                    db.commit()
        except Exception as e:
            logger.warning(f"[TaskRepo] 指标保存失败: {e}")
