"""
Agent 调度中心
统一分发任务、控制Agent执行顺序、存储每一轮Agent执行日志、
记录Agent交互中间数据，支持前端可视化读取执行流程
"""
import time
import json
import re
import queue
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from loguru import logger

from app.agents.diagnosis_agent import DiagnosisAgent
from app.agents.generation_agent import GenerationAgent
from app.agents.judge_agent import JudgeAgent
from app.services.knowledge_service import KnowledgeService
from app.services.learner_service import LearnerService
from app.database import get_db_context
from app.models import AgentTask, DebateRecord, LearningResource
from app.utils.llm import LLMUtil


class AgentOrchestrator:
    """
    Agent 调度中心（核心调度器）
    
    负责：
    - 三大Agent的统一调度与执行顺序控制
    - 任务全流程日志记录（agent_task表）
    - 辩论交叉验证流程管理
    - 中间数据存储与传递
    - 幻觉率等指标自动统计
    """
    
    # 任务类型
    TASK_TYPE_DIAGNOSIS = "learner_diagnosis"
    TASK_TYPE_RESOURCE_GENERATION = "resource_generation"
    TASK_TYPE_FULL_PIPELINE = "full_pipeline"
    
    # 流程阶段
    FLOW_STAGES = [
        "init",           # 初始化
        "diagnosis",      # 学情诊断
        "knowledge_retrieval",  # 知识库检索
        "generation",     # 内容生成
        "judge_first",    # 初次审核
        "debate",         # 辩论交叉验证
        "final_revision", # 最终修正
        "complete",       # 完成
    ]
    
    def __init__(self):
        """初始化调度中心"""
        self.diagnosis_agent = DiagnosisAgent()
        self.generation_agent = GenerationAgent()
        self.judge_agent = JudgeAgent()
        self.knowledge_service = KnowledgeService()
        self.learner_service = LearnerService()
        
        # 运行中的任务状态（内存缓存，仅用于SSE实时推送）
        # 任务完成/失败后自动清理，不做持久化依赖
        self._running_tasks: Dict[int, Dict[str, Any]] = {}
        self._running_tasks_lock = threading.Lock()
        
        # SSE 事件订阅者：task_id -> list of queue.Queue
        self._subscribers: Dict[int, List[queue.Queue]] = {}
        self._subscribers_lock = threading.Lock()
        
        # 内存缓存最大保留时间（秒），任务完成后保留5分钟供最后一次查询
        self._CACHE_TTL = 300
    
    def get_all_agents_status(self) -> List[Dict[str, Any]]:
        """
        获取所有Agent状态
        
        Returns:
            Agent状态列表
        """
        return [
            self.diagnosis_agent.get_status(),
            self.generation_agent.get_status(),
            self.judge_agent.get_status(),
        ]
    
    def get_agent_status(self, agent_type: str) -> Optional[Dict[str, Any]]:
        """
        获取指定Agent状态
        
        Args:
            agent_type: Agent类型
            
        Returns:
            Agent状态
        """
        statuses = self.get_all_agents_status()
        for s in statuses:
            if s["agent_type"] == agent_type:
                return s
        return None
    
    def create_task(
        self,
        learner_id: int,
        task_name: str,
        task_type: str,
        input_data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        创建Agent任务
        
        Args:
            learner_id: 学习者ID
            task_name: 任务名称
            task_type: 任务类型
            input_data: 输入数据
            
        Returns:
            任务信息
        """
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
            
            logger.info(f"[Agent调度中心] 创建任务: task_id={task_id}, type={task_type}")
        
        return self._get_task_info(task_id)
    
    def run_full_pipeline(
        self,
        task_id: int,
        learner_id: int,
        target_topic: str,
        resource_type: str = "guide",
        industry: str = None,
    ) -> Dict[str, Any]:
        """
        执行完整流水线：诊断 → 检索 → 生成 → 审核 → 辩论 → 完成
        
        Args:
            task_id: 任务ID
            learner_id: 学习者ID
            target_topic: 目标主题
            resource_type: 资源类型
            industry: 行业
            
        Returns:
            最终结果
        """
        logger.info(
            f"[Agent调度中心] 开始完整流水线任务: "
            f"task_id={task_id}, learner_id={learner_id}, topic={target_topic}"
        )
        
        # 内存中记录运行状态（仅缓存，DB为权威数据源）
        with self._running_tasks_lock:
            self._running_tasks[task_id] = {
                "stage": "init",
                "progress": 0,
                "start_time": time.time(),
                "logs": [],
            }

        try:
            # ========= 阶段1：学情诊断 =========
            self._update_task_stage(task_id, "diagnosis", 10, "正在进行学情诊断...")
            
            diagnosis_result = self._run_diagnosis(task_id, learner_id)
            self._update_running_task(task_id, diagnosis_result=diagnosis_result)
            
            # ========= 阶段2：知识库检索 =========
            self._update_task_stage(task_id, "knowledge_retrieval", 30, "正在检索相关知识库...")
            
            knowledge_results = self._retrieve_knowledge(
                target_topic=target_topic,
                industry=industry,
                diagnosis_result=diagnosis_result,
            )
            self._update_running_task(task_id, knowledge_results=knowledge_results)
            
            # ========= 阶段3：内容生成 =========
            self._update_task_stage(task_id, "generation", 50, "正在生成学习资源...")
            
            generation_result = self._run_generation(
                task_id=task_id,
                learner_id=learner_id,
                diagnosis_result=diagnosis_result,
                knowledge_results=knowledge_results,
                target_topic=target_topic,
                resource_type=resource_type,
            )
            self._update_running_task(task_id, generation_result=generation_result)
            
            # ========= 阶段4：初次审核 =========
            self._update_task_stage(task_id, "judge_first", 70, "初次审核中...")
            
            audit_result = self._run_audit(
                task_id=task_id,
                generated_content=generation_result.get("content", ""),
                reference_knowledge=knowledge_results,
                debate_round=1,
            )
            self._update_running_task(task_id, audit_result=audit_result)
            
            # ========= 阶段5：辩论交叉验证 =========
            self._update_task_stage(task_id, "debate", 85, "正在进行辩论交叉验证...")
            
            debate_results, corrected_content = self._run_debate_process(
                task_id=task_id,
                generated_content=generation_result.get("content", ""),
                reference_knowledge=knowledge_results,
                initial_audit=audit_result,
                max_rounds=3,
            )
            self._update_running_task(
                task_id,
                debate_results=debate_results,
                corrected_content=corrected_content,
            )
            
            # ========= 阶段6：最终修正与完成 =========
            self._update_task_stage(task_id, "final_revision", 95, "生成最终版本...")
            
            # 用辩论修正后的内容更新生成结果
            if corrected_content != generation_result.get("content", ""):
                generation_result["content"] = corrected_content
                generation_result["word_count"] = len(corrected_content)
                generation_result["_debate_corrected"] = True
                generation_result["_debate_rounds"] = len(debate_results)
            
            final_result = self._finalize_result(
                task_id=task_id,
                learner_id=learner_id,
                generation_result=generation_result,
                audit_result=audit_result,
                debate_results=debate_results,
            )
            self._update_running_task(task_id, final_result=final_result)
            
            # ========= 统计指标 =========
            self._update_task_stage(task_id, "complete", 100, "任务完成")
            
            self._save_metrics(task_id, audit_result, debate_results)
            
            # 广播任务完成事件
            self._broadcast_event(task_id, "task_completed", {
                "task_id": task_id,
                "result": {
                    "resource_id": final_result.get("resource_id"),
                    "word_count": final_result.get("word_count", 0),
                    "validation_score": final_result.get("validation_score", 0),
                    "debate_rounds": len(debate_results),
                },
                "timestamp": time.time(),
            })
            
            logger.info(f"[Agent调度中心] 任务完成: task_id={task_id}")
            
            # 延迟清理内存缓存（保留TTL时间供最后一次SSE查询）
            self._schedule_cache_cleanup(task_id)
            
            return final_result
            
        except Exception as e:
            self._mark_task_failed(task_id, str(e))
            logger.error(f"[Agent调度中心] 任务失败: task_id={task_id}, error={e}")
            self._schedule_cache_cleanup(task_id)
            raise
    
    def _run_diagnosis(self, task_id: int, learner_id: int) -> Dict[str, Any]:
        """
        运行学情诊断Agent
        
        Args:
            task_id: 任务ID
            learner_id: 学习者ID
            
        Returns:
            诊断结果
        """
        # 获取学习者画像
        with get_db_context() as db:
            learner = LearnerService.get_learner_by_id(db, learner_id)
            if not learner:
                raise ValueError(f"学习者不存在: {learner_id}")
            learner_dict = self._model_to_dict(learner)
        
        # 调用诊断Agent
        result = self.diagnosis_agent.run(
            task_id=task_id,
            input_data={
                "learner_id": learner_id,
                "learner_profile": learner_dict,
            },
        )
        
        if not result.get("_meta", {}).get("success", False):
            raise Exception(f"学情诊断失败: {result.get('error')}")
        
        # 记录到任务日志
        with get_db_context() as db:
            task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
            if task:
                task.flow_stage = "diagnosis"
                task.output_data = json.dumps(result, ensure_ascii=False, default=str)
                db.commit()
        
        return result
    
    def _retrieve_knowledge(
        self,
        target_topic: str,
        diagnosis_result: Dict[str, Any],
        industry: str = None,
    ) -> List[Dict]:
        """
        检索知识库
        
        Args:
            target_topic: 目标主题
            diagnosis_result: 诊断结果
            industry: 行业
            
        Returns:
            检索结果
        """
        with get_db_context() as db:
            results = KnowledgeService.search(
                db=db,
                query=target_topic,
                industry=industry,
                top_k=8,
            )
        
        logger.debug(f"[Agent调度中心] 知识库检索: {len(results)} 条结果")
        return results
    
    def _run_generation(
        self,
        task_id: int,
        learner_id: int,
        diagnosis_result: Dict[str, Any],
        knowledge_results: List[Dict],
        target_topic: str,
        resource_type: str,
    ) -> Dict[str, Any]:
        """
        运行内容生成Agent

        Args:
            task_id: 任务ID
            learner_id: 学习者ID（用于查询真实画像）
            diagnosis_result: 诊断结果
            knowledge_results: 知识库结果
            target_topic: 主题
            resource_type: 资源类型

        Returns:
            生成结果
        """
        # 查询真实学习者画像，传入生成 Agent
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
        
        # 记录到任务日志
        with get_db_context() as db:
            task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
            if task:
                task.flow_stage = "generation"
                task.agent_type = "generation"
                db.commit()
        
        return result
    
    def _run_audit(
        self,
        task_id: int,
        generated_content: str,
        reference_knowledge: List[Dict],
        debate_round: int = 1,
    ) -> Dict[str, Any]:
        """
        运行审核裁判Agent
        
        Args:
            task_id: 任务ID
            generated_content: 生成内容
            reference_knowledge: 参考知识库
            debate_round: 辩论轮次
            
        Returns:
            审核结果
        """
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
        self,
        task_id: int,
        generated_content: str,
        reference_knowledge: List[Dict],
        initial_audit: Dict[str, Any],
        max_rounds: int = 3,
    ) -> Tuple[List[Dict[str, Any]], str]:
        """
        运行辩论交叉验证流程（核心创新机制）
        
        Args:
            task_id: 任务ID
            generated_content: 生成内容
            reference_knowledge: 参考知识库
            initial_audit: 初次审核结果
            max_rounds: 最大辩论轮次
            
        Returns:
            (辩论记录列表, 最终修正后的内容)
        """
        debate_records = []
        
        # 如果初次审核通过，不需要辩论
        if initial_audit.get("passed", False):
            return debate_records, generated_content
        
        current_content = generated_content
        current_round = 1
        
        while current_round <= max_rounds:
            # 广播辩论轮次开始事件
            debate_progress = 70 + int(current_round / max_rounds * 15)
            self._broadcast_event(task_id, "debate_round", {
                "task_id": task_id,
                "round": current_round,
                "max_rounds": max_rounds,
                "action": "questioning",
                "description": f"裁判Agent第{current_round}轮质疑中...",
                "progress": debate_progress,
                "timestamp": time.time(),
            })
            
            # 裁判Agent发起质疑
            debate_result = self.judge_agent.debate_with_generation(
                generated_content=current_content,
                reference_knowledge=reference_knowledge,
                previous_debates=debate_records,
            )
            
            # 保存辩论记录到数据库
            self._save_debate_record(
                task_id=task_id,
                round_num=current_round,
                debate_data=debate_result,
            )
            
            debate_records.append(debate_result)
            
            # 广播本轮辩论结果
            corrections_count = len(debate_result.get("corrections", []))
            decision = debate_result.get("final_decision", "needs_revision")
            self._broadcast_event(task_id, "debate_result", {
                "task_id": task_id,
                "round": current_round,
                "max_rounds": max_rounds,
                "decision": decision,
                "corrections_count": corrections_count,
                "description": f"第{current_round}轮辩论: {decision}, 发现{corrections_count}项问题",
                "progress": debate_progress + 3,
                "timestamp": time.time(),
            })
            
            # 如果通过或达到最大轮次，结束
            if debate_result.get("debate_ended", False):
                break
            
            if debate_result.get("final_decision") == "approved":
                break
            
            # 应用修正生成新版本内容
            self._broadcast_event(task_id, "debate_round", {
                "task_id": task_id,
                "round": current_round,
                "max_rounds": max_rounds,
                "action": "correcting",
                "description": f"正在应用第{current_round}轮修正...",
                "progress": debate_progress + 5,
                "timestamp": time.time(),
            })
            
            current_content = self._apply_corrections(
                current_content,
                debate_result.get("corrections", []),
                reference_knowledge,
            )
            
            # 更新辩论记录中的修正后内容
            debate_result["corrected_content"] = current_content
            
            current_round += 1
        
        logger.info(
            f"[Agent调度中心] 辩论完成: task_id={task_id}, "
            f"rounds={len(debate_records)}"
        )
        
        return debate_records, current_content
    
    def _save_debate_record(
        self,
        task_id: int,
        round_num: int,
        debate_data: Dict[str, Any],
    ) -> None:
        """
        保存辩论记录到数据库
        
        Args:
            task_id: 任务ID
            round_num: 轮次
            debate_data: 辩论数据
        """
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
    
    def _apply_corrections(
        self,
        content: str,
        corrections: List[Dict[str, Any]],
        reference_knowledge: List[Dict] = None,
    ) -> str:
        """
        应用修正到内容，生成修正后的版本
        
        策略：
        1. 优先调用 LLM 进行智能修正（当 LLM 可用时）
        2. LLM 不可用时使用规则-based 修正
        
        Args:
            content: 原始内容
            corrections: 修正列表
            reference_knowledge: 参考知识库
            
        Returns:
            修正后的内容
        """
        if not corrections:
            return content
        
        reference_knowledge = reference_knowledge or []
        
        # 分离高/中/低严重度问题
        high_corrections = [c for c in corrections if c.get("severity") == "high"]
        medium_corrections = [c for c in corrections if c.get("severity") == "medium"]
        
        if not high_corrections and not medium_corrections:
            return content
        
        # 尝试使用 LLM 进行智能修正
        if LLMUtil.is_available():
            revised = self._llm_correct_content(content, corrections, reference_knowledge)
            if revised and len(revised) > 50:
                logger.info(f"[Agent调度中心] LLM修正完成: 原长度={len(content)}, 修正后长度={len(revised)}")
                return revised
        
        # LLM不可用或修正失败，使用规则-based修正
        return self._rule_based_correct(content, corrections)
    
    def _llm_correct_content(
        self,
        content: str,
        corrections: List[Dict[str, Any]],
        reference_knowledge: List[Dict],
    ) -> Optional[str]:
        """
        使用 LLM 智能修正内容
        
        Args:
            content: 原始内容
            corrections: 修正列表
            reference_knowledge: 参考知识库
            
        Returns:
            修正后的内容，失败返回None
        """
        try:
            # 构建修正指令
            correction_text = "\n".join([
                f"- [{c.get('severity', 'medium').upper()}] {c.get('issue_type', 'unknown')}: "
                f"{c.get('description', '')} | 建议: {c.get('suggested_fix', '')}"
                for c in corrections
            ])
            
            ref_text = "\n".join([
                f"[参考] {k.get('title', '')}: {k.get('content', '')[:300]}"
                for k in reference_knowledge[:3]
            ])
            
            system_prompt = (
                "你是一位严谨的专业内容审校专家。你的任务是根据审核意见修正学习资源内容中的问题。"
                "请遵循以下规则：\n"
                "1. 删除或修正疑似幻觉/不实的表述\n"
                "2. 将绝对化表述改为更严谨的表述\n"
                "3. 核实技术术语和数据的准确性\n"
                "4. 保持原文的整体结构和风格\n"
                "5. 只输出修正后的完整内容，不要添加任何解释、标记或前言\n"
                "6. 不要使用markdown代码块包裹输出"
            )
            
            user_prompt = (
                f"## 待修正内容\n{content}\n\n"
                f"## 审核修正意见\n{correction_text}\n\n"
                f"## 参考知识\n{ref_text}\n\n"
                f"请根据以上审核意见修正内容，直接输出修正后的完整文本："
            )
            
            revised, _ = LLMUtil.sync_call(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.3,
            )
            
            # 清理可能的markdown代码块包裹
            revised = revised.strip()
            if revised.startswith("```"):
                revised = re.sub(r'^```\w*\n?', '', revised)
                revised = re.sub(r'\n?```$', '', revised)
            
            return revised.strip()
            
        except Exception as e:
            logger.warning(f"[Agent调度中心] LLM修正失败，回退到规则修正: {e}")
            return None
    
    def _rule_based_correct(
        self,
        content: str,
        corrections: List[Dict[str, Any]],
    ) -> str:
        """
        基于规则的内容修正（LLM不可用时的兜底方案）
        
        Args:
            content: 原始内容
            corrections: 修正列表
            
        Returns:
            修正后的内容
        """
        modified = content
        
        # 绝对化表述替换
        absolute_phrases = {
            "一定": "通常",
            "绝对": "一般情况下",
            "百分百": "大概率",
            "百分之百": "在大多数情况下",
            "必须": "建议",
            "肯定": "很可能",
            "必然": "往往",
        }
        
        for old, new in absolute_phrases.items():
            modified = modified.replace(old, new)
        
        # 处理幻觉关键词修正：添加审慎标注
        for c in corrections:
            if c.get("issue_type") == "hallucination_keyword":
                details = c.get("original_content", "")
                if isinstance(details, list) and details:
                    for keyword in details[:3]:
                        if isinstance(keyword, str) and keyword in modified:
                            modified = modified.replace(
                                keyword,
                                f"{keyword}（注：此表述需进一步核实）",
                                1
                            )
            
            elif c.get("issue_type") == "standard_issue":
                # 行业规范问题：添加修正说明
                suggested = c.get("suggested_fix", "")
                if suggested and suggested not in modified:
                    modified += f"\n\n> [审核修正] {suggested}"
        
        # 版本号和数字标记需要核实
        version_pattern = r'v?\d+\.\d+\.\d+'
        matches = re.findall(version_pattern, modified)
        if matches:
            for ver in set(matches):
                # 不重复标注
                if f"{ver}（版本号需核实）" not in modified:
                    modified = modified.replace(ver, f"{ver}（版本号需核实）", 1)
        
        # 添加修正轮次标记
        correction_round_marker = f"\n\n---\n*[系统提示：内容经过{len([c for c in corrections if c.get('severity') in ('high','medium')])}项审核修正]*"
        if correction_round_marker not in modified:
            modified += correction_round_marker
        
        logger.debug(f"[Agent调度中心] 规则-based修正完成: 修正项={len(corrections)}")
        return modified
    
    def _finalize_result(
        self,
        task_id: int,
        learner_id: int,
        generation_result: Dict[str, Any],
        audit_result: Dict[str, Any],
        debate_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        生成最终结果并保存资源
        
        Args:
            task_id: 任务ID
            learner_id: 学习者ID
            generation_result: 生成结果
            audit_result: 审核结果
            debate_results: 辩论结果
            
        Returns:
            最终结果
        """
        # 保存学习资源
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
            
            # 更新任务状态
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
            "debate_rounds": len(debate_results),
            "final_score": audit_result.get("overall_score", 0),
            "passed": audit_result.get("passed", False),
        }
    
    def _save_metrics(
        self,
        task_id: int,
        audit_result: Dict[str, Any],
        debate_results: List[Dict[str, Any]],
    ) -> None:
        """
        保存指标统计
        
        Args:
            task_id: 任务ID
            audit_result: 审核结果
            debate_results: 辩论结果
        """
        # 计算幻觉率（指标统计在metrics工具中实现）
        with get_db_context():
            # 这里简化处理，实际应该有更完善的指标统计逻辑
            pass  # 指标统计在metrics工具中实现
    
    def _update_running_task(self, task_id: int, **fields) -> None:
        """在锁内更新内存缓存中的任务字段

        Args:
            task_id: 任务ID
            **fields: 要更新的字段（如 diagnosis_result=...）
        """
        with self._running_tasks_lock:
            if task_id in self._running_tasks:
                self._running_tasks[task_id].update(fields)

    def _update_task_stage(
        self,
        task_id: int,
        stage: str,
        progress: int,
        description: str,
        extra: Dict[str, Any] = None,
    ) -> None:
        """
        更新任务阶段并广播 SSE 事件
        日志同时持久化到DB（agent_tasks.execution_logs）和内存缓存
        
        Args:
            task_id: 任务ID
            stage: 阶段
            progress: 进度(0-100)
            description: 描述
            extra: 附加数据
        """
        event_data = {
            "task_id": task_id,
            "stage": stage,
            "progress": progress,
            "description": description,
            "timestamp": time.time(),
        }
        if extra:
            event_data.update(extra)
        
        log_entry = {
            "stage": stage,
            "progress": progress,
            "description": description,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        
        # 更新内存缓存（线程安全）
        with self._running_tasks_lock:
            if task_id in self._running_tasks:
                self._running_tasks[task_id]["stage"] = stage
                self._running_tasks[task_id]["progress"] = progress
                self._running_tasks[task_id]["logs"].append(log_entry)
        
        # 广播 SSE 事件
        self._broadcast_event(task_id, "stage_update", event_data)
        
        # 持久化到数据库（权威数据源）
        try:
            with get_db_context() as db:
                task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
                if task:
                    task.flow_stage = stage
                    task.flow_description = description
                    task.progress = progress
                    task.status = "running" if progress < 100 else "completed"
                    # 追加日志到execution_logs（不超过200条防止JSON过大）
                    existing_logs = task.execution_logs or []
                    existing_logs.append(log_entry)
                    if len(existing_logs) > 200:
                        existing_logs = existing_logs[-200:]
                    task.execution_logs = existing_logs
                    if stage in ("diagnosis", "knowledge_retrieval") and not task.started_at:
                        task.started_at = datetime.now()
                    db.commit()
        except Exception as e:
            logger.warning(f"[Agent调度中心] 更新任务阶段到DB失败: {e}")
    
    def _broadcast_event(self, task_id: int, event_type: str, data: Dict[str, Any]) -> None:
        """
        向所有订阅者广播事件（线程安全）
        
        Args:
            task_id: 任务ID
            event_type: 事件类型
            data: 事件数据
        """
        event = {"event": event_type, "data": data}
        with self._subscribers_lock:
            subscribers = self._subscribers.get(task_id, [])
            dead_queues = []
            for q in subscribers:
                try:
                    q.put_nowait(event)
                except queue.Full:
                    dead_queues.append(q)
            # 清理满队列（消费过慢的订阅者）
            for q in dead_queues:
                subscribers.remove(q)
    
    def subscribe_task_events(self, task_id: int) -> "queue.Queue":
        """
        订阅任务 SSE 事件
        
        Args:
            task_id: 任务ID
            
        Returns:
            事件队列，调用方通过 get() 消费事件
        """
        q: queue.Queue = queue.Queue(maxsize=200)
        with self._subscribers_lock:
            if task_id not in self._subscribers:
                self._subscribers[task_id] = []
            self._subscribers[task_id].append(q)
        return q
    
    def unsubscribe_task_events(self, task_id: int, q: "queue.Queue") -> None:
        """
        取消订阅
        
        Args:
            task_id: 任务ID
            q: 订阅时返回的队列
        """
        with self._subscribers_lock:
            if task_id in self._subscribers:
                try:
                    self._subscribers[task_id].remove(q)
                except ValueError:
                    pass
                if not self._subscribers[task_id]:
                    del self._subscribers[task_id]
    
    def _mark_task_failed(self, task_id: int, error: str) -> None:
        """
        标记任务失败并广播失败事件
        
        Args:
            task_id: 任务ID
            error: 错误信息
        """
        with self._running_tasks_lock:
            if task_id in self._running_tasks:
                self._running_tasks[task_id]["stage"] = "failed"
                self._running_tasks[task_id]["error"] = error
                self._running_tasks[task_id]["logs"].append({
                    "stage": "failed",
                    "progress": 0,
                    "description": f"任务失败: {error}",
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                })
        
        self._broadcast_event(task_id, "task_failed", {
            "task_id": task_id,
            "error": error,
            "timestamp": time.time(),
        })
        
        try:
            with get_db_context() as db:
                task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
                if task:
                    task.status = "failed"
                    task.error_message = error
                    task.flow_stage = "failed"
                    # 追加失败日志
                    existing_logs = task.execution_logs or []
                    existing_logs.append({
                        "stage": "failed",
                        "description": f"任务失败: {error}",
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    })
                    task.execution_logs = existing_logs
                    task.completed_at = datetime.now()
                    db.commit()
        except Exception as e:
            logger.warning(f"[Agent调度中心] 标记任务失败到DB失败: {e}")
    
    def get_task_status(self, task_id: int) -> Dict[str, Any]:
        """
        获取任务实时状态
        优先读内存缓存（实时性最高），缓存不存在则读数据库
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务状态
        """
        # 先查内存缓存（正在运行的任务有最新状态），整个构造在锁内完成
        with self._running_tasks_lock:
            cached = self._running_tasks.get(task_id)
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

        # 查数据库
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

    def get_task_logs(self, task_id: int) -> List[Dict[str, Any]]:
        """
        获取任务执行日志（供前端可视化）
        优先读数据库（持久化），内存缓存作补充
        
        Args:
            task_id: 任务ID
            
        Returns:
            日志列表
        """
        with self._running_tasks_lock:
            cached = self._running_tasks.get(task_id)
            if cached:
                return list(cached.get("logs", []))

        with get_db_context() as db:
            task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
            if task and task.execution_logs:
                return task.execution_logs

        return []
    
    def _schedule_cache_cleanup(self, task_id: int) -> None:
        """
        安排延迟清理任务的内存缓存
        使用守护线程在TTL后清理，避免内存泄漏
        
        Args:
            task_id: 任务ID
        """
        def cleanup():
            time.sleep(self._CACHE_TTL)
            with self._running_tasks_lock:
                self._running_tasks.pop(task_id, None)
            with self._subscribers_lock:
                self._subscribers.pop(task_id, None)
            logger.debug(f"[Agent调度中心] 任务缓存已清理: task_id={task_id}")
        
        t = threading.Thread(target=cleanup, daemon=True, name=f"cleanup-task-{task_id}")
        t.start()
    
    def _get_task_info(self, task_id: int) -> Dict[str, Any]:
        """获取任务信息"""
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
    
    def _model_to_dict(self, model) -> Dict[str, Any]:
        """ORM模型转字典"""
        result = {}
        for column in model.__table__.columns:
            value = getattr(model, column.name)
            result[column.name] = value
        return result


# 全局单例
orchestrator = AgentOrchestrator()
