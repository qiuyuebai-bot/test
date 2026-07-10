"""
Agent 调度中心（重构版）

职责拆分：
- TaskRepository: 数据库持久化（任务CRUD、状态、指标、辩论记录、资源保存）
- TaskEventBus: SSE 事件发布/订阅（进程内 pub/sub）
- ContentCorrector: 内容修正（LLM 智能修正 + 规则兜底）
- AgentOrchestrator: 流水线编排（6阶段流程）+ 内存缓存管理

公共 API 保持不变，确保调用方（router、celery_app）无需修改。
"""
import time
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from loguru import logger

from app.agents.diagnosis_agent import DiagnosisAgent
from app.agents.generation_agent import GenerationAgent
from app.agents.judge_agent import JudgeAgent
from app.agents.event_bus import create_event_bus
from app.agents.task_repository import TaskRepository
from app.agents.content_corrector import ContentCorrector
from app.domains.knowledge.service import KnowledgeService
from app.domains.learner.service import LearnerService
from app.database import get_db_context


class AgentOrchestrator:
    """
    Agent 调度中心（核心编排器）

    组合 TaskRepository / TaskEventBus / ContentCorrector，
    仅负责流水线编排与内存缓存管理。
    """

    TASK_TYPE_DIAGNOSIS = TaskRepository.TASK_TYPE_DIAGNOSIS
    TASK_TYPE_RESOURCE_GENERATION = TaskRepository.TASK_TYPE_RESOURCE_GENERATION
    TASK_TYPE_FULL_PIPELINE = TaskRepository.TASK_TYPE_FULL_PIPELINE
    FLOW_STAGES = TaskRepository.FLOW_STAGES

    def __init__(self):
        self.diagnosis_agent = DiagnosisAgent()
        self.generation_agent = GenerationAgent()
        self.judge_agent = JudgeAgent()
        self.knowledge_service = KnowledgeService()
        self.learner_service = LearnerService()

        self.task_repo = TaskRepository()
        self.event_bus = create_event_bus()
        self.content_corrector = ContentCorrector()

        # 运行中的任务状态（内存缓存，仅用于SSE实时推送，DB为权威源）
        self._running_tasks: Dict[int, Dict[str, Any]] = {}
        self._running_tasks_lock = threading.Lock()
        self._CACHE_TTL = 300

    # ===========================================
    # Agent 状态查询
    # ===========================================

    def get_all_agents_status(self) -> List[Dict[str, Any]]:
        return [
            self.diagnosis_agent.get_status(),
            self.generation_agent.get_status(),
            self.judge_agent.get_status(),
        ]

    def get_agent_status(self, agent_type: str) -> Optional[Dict[str, Any]]:
        for s in self.get_all_agents_status():
            if s["agent_type"] == agent_type:
                return s
        return None

    # ===========================================
    # 任务管理（委托 TaskRepository）
    # ===========================================

    def create_task(
        self,
        learner_id: int,
        task_name: str,
        task_type: str,
        input_data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        return self.task_repo.create_task(learner_id, task_name, task_type, input_data)

    def get_task_status(self, task_id: int) -> Dict[str, Any]:
        with self._running_tasks_lock:
            cached = self._running_tasks.get(task_id)
        return self.task_repo.get_task_status(task_id, cached)

    def get_task_logs(self, task_id: int) -> List[Dict[str, Any]]:
        with self._running_tasks_lock:
            cached = self._running_tasks.get(task_id)
            cached_logs = cached.get("logs") if cached else None
        return self.task_repo.get_task_logs(task_id, cached_logs)

    # ===========================================
    # SSE 事件订阅（委托 TaskEventBus）
    # ===========================================

    def subscribe_task_events(self, task_id: int) -> "queue.Queue":
        return self.event_bus.subscribe(task_id)

    def unsubscribe_task_events(self, task_id: int, q: "queue.Queue") -> None:
        self.event_bus.unsubscribe(task_id, q)

    # ===========================================
    # 流水线编排（核心逻辑）
    # ===========================================

    def run_full_pipeline(
        self,
        task_id: int,
        learner_id: int,
        target_topic: str,
        resource_type: str = "guide",
        industry: str = None,
    ) -> Dict[str, Any]:
        """执行完整流水线：诊断 → 检索 → 生成 → 审核 → 辩论 → 完成"""
        logger.info(
            f"[Agent调度中心] 开始流水线: task_id={task_id}, learner_id={learner_id}, topic={target_topic}"
        )

        with self._running_tasks_lock:
            self._running_tasks[task_id] = {
                "stage": "init", "progress": 0, "start_time": time.time(), "logs": [],
            }

        try:
            # 阶段1：学情诊断
            self._update_task_stage(task_id, "diagnosis", 10, "正在进行学情诊断...")
            diagnosis_result = self._run_diagnosis(task_id, learner_id)
            self._update_running_task(task_id, diagnosis_result=diagnosis_result)

            # 阶段2：知识库检索
            self._update_task_stage(task_id, "knowledge_retrieval", 30, "正在检索相关知识库...")
            knowledge_results = self._retrieve_knowledge(target_topic, diagnosis_result, industry)
            self._update_running_task(task_id, knowledge_results=knowledge_results)

            # 阶段3：内容生成
            self._update_task_stage(task_id, "generation", 50, "正在生成学习资源...")
            generation_result = self._run_generation(
                task_id, learner_id, diagnosis_result, knowledge_results, target_topic, resource_type
            )
            self._update_running_task(task_id, generation_result=generation_result)

            # 阶段4：初次审核
            self._update_task_stage(task_id, "judge_first", 70, "初次审核中...")
            audit_result = self._run_audit(
                task_id, generation_result.get("content", ""), knowledge_results, debate_round=1
            )
            self._update_running_task(task_id, audit_result=audit_result)

            # 阶段5：辩论交叉验证
            self._update_task_stage(task_id, "debate", 85, "正在进行辩论交叉验证...")
            debate_results, corrected_content = self._run_debate_process(
                task_id, generation_result.get("content", ""), knowledge_results, audit_result
            )
            self._update_running_task(task_id, debate_results=debate_results, corrected_content=corrected_content)

            # 阶段6：最终修正与完成
            self._update_task_stage(task_id, "final_revision", 95, "生成最终版本...")
            if corrected_content != generation_result.get("content", ""):
                generation_result["content"] = corrected_content
                generation_result["word_count"] = len(corrected_content)
                generation_result["_debate_corrected"] = True
                generation_result["_debate_rounds"] = len(debate_results)

            final_result = self.task_repo.save_resource_and_complete(
                task_id, learner_id, generation_result, audit_result, len(debate_results)
            )
            self._update_running_task(task_id, final_result=final_result)

            # 统计指标
            self._update_task_stage(task_id, "complete", 100, "任务完成")
            self.task_repo.save_metrics(task_id, audit_result, debate_results)

            # 广播完成事件
            self.event_bus.broadcast(task_id, "task_completed", {
                "task_id": task_id,
                "result": {
                    "resource_id": final_result.get("resource_id"),
                    "word_count": final_result.get("generation_result", {}).get("word_count", 0),
                    "validation_score": final_result.get("final_score", 0),
                    "debate_rounds": len(debate_results),
                },
                "timestamp": time.time(),
            })
            logger.info(f"[Agent调度中心] 任务完成: task_id={task_id}")
            self._schedule_cache_cleanup(task_id)
            return final_result

        except Exception as e:
            self._mark_task_failed(task_id, str(e))
            logger.error(f"[Agent调度中心] 任务失败: task_id={task_id}, error={e}")
            self._schedule_cache_cleanup(task_id)
            raise

    # ===========================================
    # 流水线各阶段
    # ===========================================

    def _run_diagnosis(self, task_id: int, learner_id: int) -> Dict[str, Any]:
        with get_db_context() as db:
            learner = LearnerService.get_learner_by_id(db, learner_id)
            if not learner:
                raise ValueError(f"学习者不存在: {learner_id}")
            learner_dict = self._model_to_dict(learner)

        result = self.diagnosis_agent.run(
            task_id=task_id,
            input_data={"learner_id": learner_id, "learner_profile": learner_dict},
        )
        if not result.get("_meta", {}).get("success", False):
            raise Exception(f"学情诊断失败: {result.get('error')}")
        self.task_repo.update_output_data(task_id, "diagnosis", result)
        return result

    def _retrieve_knowledge(
        self, target_topic: str, diagnosis_result: Dict[str, Any], industry: str = None
    ) -> List[Dict]:
        with get_db_context() as db:
            results = KnowledgeService.search(db=db, query=target_topic, industry=industry, top_k=8)
        logger.debug(f"[Agent调度中心] 知识库检索: {len(results)} 条结果")
        return results

    def _run_generation(
        self, task_id: int, learner_id: int, diagnosis_result: Dict[str, Any],
        knowledge_results: List[Dict], target_topic: str, resource_type: str,
    ) -> Dict[str, Any]:
        with get_db_context() as db:
            learner = LearnerService.get_learner_by_id(db, learner_id)
            learner_dict = self._model_to_dict(learner) if learner else {}

        result = self.generation_agent.run(
            task_id=task_id,
            input_data={
                "diagnosis_result": diagnosis_result,
                "knowledge_results": knowledge_results,
                "learner_profile": learner_dict,
                "target_topic": target_topic,
                "resource_type": resource_type,
            },
        )
        if not result.get("_meta", {}).get("success", False):
            raise Exception(f"内容生成失败: {result.get('error')}")
        self.task_repo.update_output_data(task_id, "generation", result, agent_type="generation")
        return result

    def _run_audit(
        self, task_id: int, generated_content: str,
        reference_knowledge: List[Dict], debate_round: int = 1,
    ) -> Dict[str, Any]:
        result = self.judge_agent.run(
            task_id=task_id,
            input_data={
                "generated_content": generated_content,
                "reference_knowledge": reference_knowledge,
                "debate_round": debate_round,
            },
        )
        if not result.get("_meta", {}).get("success", False):
            raise Exception(f"审核失败: {result.get('error')}")
        return result

    def _run_debate_process(
        self, task_id: int, generated_content: str,
        reference_knowledge: List[Dict], initial_audit: Dict[str, Any],
        max_rounds: int = 3,
    ) -> Tuple[List[Dict[str, Any]], str]:
        """辩论交叉验证流程（核心创新机制）"""
        debate_records = []

        if initial_audit.get("passed", False):
            return debate_records, generated_content

        current_content = generated_content
        current_round = 1

        while current_round <= max_rounds:
            debate_progress = 70 + int(current_round / max_rounds * 15)
            self.event_bus.broadcast(task_id, "debate_round", {
                "task_id": task_id, "round": current_round, "max_rounds": max_rounds,
                "action": "questioning", "description": f"裁判Agent第{current_round}轮质疑中...",
                "progress": debate_progress, "timestamp": time.time(),
            })

            debate_result = self.judge_agent.debate_with_generation(
                generated_content=current_content,
                reference_knowledge=reference_knowledge,
                previous_debates=debate_records,
                max_rounds=max_rounds,
            )
            debate_records.append(debate_result)

            corrections_count = len(debate_result.get("corrections", []))
            decision = debate_result.get("final_decision", "needs_revision")
            self.event_bus.broadcast(task_id, "debate_result", {
                "task_id": task_id, "round": current_round, "max_rounds": max_rounds,
                "decision": decision, "corrections_count": corrections_count,
                "description": f"第{current_round}轮辩论: {decision}, 发现{corrections_count}项问题",
                "progress": debate_progress + 3, "timestamp": time.time(),
            })

            if debate_result.get("debate_ended", False) or decision == "approved":
                debate_result["corrected_content"] = current_content
                self.task_repo.save_debate_record(task_id, current_round, debate_result)
                break

            self.event_bus.broadcast(task_id, "debate_round", {
                "task_id": task_id, "round": current_round, "max_rounds": max_rounds,
                "action": "correcting", "description": f"正在应用第{current_round}轮修正...",
                "progress": debate_progress + 5, "timestamp": time.time(),
            })

            current_content = self.content_corrector.apply_corrections(
                current_content, debate_result.get("corrections", []), reference_knowledge
            )
            debate_result["corrected_content"] = current_content
            self.task_repo.save_debate_record(task_id, current_round, debate_result)
            current_round += 1

        logger.info(f"[Agent调度中心] 辩论完成: task_id={task_id}, rounds={len(debate_records)}")
        return debate_records, current_content

    # ===========================================
    # 内存缓存与状态管理
    # ===========================================

    def _update_running_task(self, task_id: int, **fields) -> None:
        with self._running_tasks_lock:
            if task_id in self._running_tasks:
                self._running_tasks[task_id].update(fields)

    def _update_task_stage(
        self, task_id: int, stage: str, progress: int, description: str,
        extra: Dict[str, Any] = None,
    ) -> None:
        """更新任务阶段：内存缓存 + SSE广播 + DB持久化"""
        event_data = {
            "task_id": task_id, "stage": stage, "progress": progress,
            "description": description, "timestamp": time.time(),
        }
        if extra:
            event_data.update(extra)

        log_entry = {
            "stage": stage, "progress": progress, "description": description,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        with self._running_tasks_lock:
            if task_id in self._running_tasks:
                self._running_tasks[task_id]["stage"] = stage
                self._running_tasks[task_id]["progress"] = progress
                self._running_tasks[task_id]["logs"].append(log_entry)

        self.event_bus.broadcast(task_id, "stage_update", event_data)
        self.task_repo.update_stage(task_id, stage, progress, description)

    def _mark_task_failed(self, task_id: int, error: str) -> None:
        with self._running_tasks_lock:
            if task_id in self._running_tasks:
                self._running_tasks[task_id]["stage"] = "failed"
                self._running_tasks[task_id]["error"] = error
                self._running_tasks[task_id]["logs"].append({
                    "stage": "failed", "progress": 0,
                    "description": f"任务失败: {error}",
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                })

        self.event_bus.broadcast(task_id, "task_failed", {
            "task_id": task_id, "error": error, "timestamp": time.time(),
        })
        self.task_repo.mark_failed(task_id, error)

    def _schedule_cache_cleanup(self, task_id: int) -> None:
        def cleanup():
            time.sleep(self._CACHE_TTL)
            with self._running_tasks_lock:
                self._running_tasks.pop(task_id, None)
            self.event_bus.cleanup(task_id)
            logger.debug(f"[Agent调度中心] 任务缓存已清理: task_id={task_id}")

        t = threading.Thread(target=cleanup, daemon=True, name=f"cleanup-task-{task_id}")
        t.start()

    @staticmethod
    def _model_to_dict(model) -> Dict[str, Any]:
        result = {}
        for column in model.__table__.columns:
            result[column.name] = getattr(model, column.name)
        return result


# 全局单例
orchestrator = AgentOrchestrator()
