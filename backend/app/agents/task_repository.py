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
from sqlalchemy.orm.attributes import flag_modified

from app.database import get_db_context
from app.models import AgentTask, DebateRecord, LearningResource


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
                    p.get("type") == "hallucination_keyword"
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
        with get_db_context() as db:
            resource = LearningResource(
                learner_id=learner_id,
                title=generation_result.get("resource_title", "未命名资源"),
                resource_type=generation_result.get("resource_type", "guide"),
                difficulty_level=generation_result.get("difficulty_level", 3),
                version="1.0",
                content=generation_result.get("content", ""),
                content_json=json.dumps(
                    generation_result.get("content_json", {}),
                    ensure_ascii=False,
                    default=str,
                ),
                word_count=generation_result.get("word_count", 0),
                source_slice_ids=json.dumps(
                    generation_result.get("source_slice_ids", []),
                    ensure_ascii=False,
                ),
                source_doc_ids=json.dumps(
                    generation_result.get("source_doc_ids", []),
                    ensure_ascii=False,
                ),
                generated_by_agent="generation_agent",
                generation_task_id=task_id,
                generation_method="knowledge_based",
                is_validated=audit_result.get("passed", False),
                validation_passed=audit_result.get("passed", False),
                validation_score=audit_result.get("overall_score", 0),
                hallucination_detected=audit_result.get("hallucination_detected", False),
                status="published",
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
            if c.get("type") == "hallucination_keyword"
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
