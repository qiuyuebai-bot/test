"""
交互式自适应导学动态迭代服务
双分支逻辑：正确率偏低→简化解释；正确率达标→进阶挑战
"""
import json
import uuid
from typing import Dict, Any, List, Optional
from loguru import logger

from app.database import get_db_context
from app.models import (
    LearnerProfile,
    AnswerRecord,
    LearningResource,
)
from app.agents.diagnosis_agent import DiagnosisAgent
from app.services.common import BaseService
from app.constants import ADAPTIVE_DECISION_THRESHOLD, MAX_DIFFICULTY
from app.utils.seed_loader import load_seed_payload

# 题库与知识点解释从 JSON 配置加载，避免在源码中硬编码业务数据
_QUESTION_BANK_PAYLOAD = load_seed_payload("questions.json")
_QUESTION_BANK: List[Dict[str, Any]] = _QUESTION_BANK_PAYLOAD.get("records", [])
_QUESTION_EXPLANATIONS: Dict[str, str] = _QUESTION_BANK_PAYLOAD.get("explanations", {})
_QUESTION_KEY_POINTS: Dict[str, List[str]] = _QUESTION_BANK_PAYLOAD.get("key_points", {})


class AdaptiveTutoringService(BaseService):
    """
    交互式自适应导学服务
    """

    DECISION_THRESHOLD = ADAPTIVE_DECISION_THRESHOLD  # 正确率阈值

    @classmethod
    def get_questions(cls) -> List[Dict[str, Any]]:
        """获取题库列表"""
        return _QUESTION_BANK
    
    @classmethod
    def process_answer(
        cls,
        user_id: int,
        learner_id: int,
        question_id: str,
        question_type: str,
        question_topic: str,
        question_difficulty: int,
        question_content: str,
        user_answer: str,
        correct_answer: str,
        score: float,
        time_spent_ms: int,
        hints_used: int = 0,
    ) -> Dict[str, Any]:
        """处理用户答题结果，触发自适应决策"""
        logger.info(
            f"[自适应导学] 处理答题: user_id={user_id}, learner_id={learner_id}, "
            f"topic={question_topic}, score={score}"
        )

        try:
            learner = cls.get_learner(learner_id)
            if not learner:
                return {"success": False, "error": "学习者不存在"}

            is_correct = score >= 60
            accuracy_rate = score / 100

            # Agent协同决策
            agent_decision = cls._run_agent_decision(
                learner=learner,
                question_topic=question_topic,
                score=score,
                accuracy_rate=accuracy_rate,
                is_correct=is_correct,
            )

            next_action = agent_decision.get("next_action", "none")

            # 根据决策生成后续内容
            generated_content = {}
            if next_action == "simplify":
                generated_content = cls._generate_simplified_explanation(
                    learner, question_topic, question_content, user_answer, correct_answer
                )
            elif next_action == "advance":
                generated_content = cls._generate_advanced_challenge(
                    learner, question_topic, question_difficulty
                )

            # 保存答题记录
            answer_record = cls._save_answer_record(
                user_id=user_id,
                learner_id=learner_id,
                question_id=question_id,
                question_type=question_type,
                question_topic=question_topic,
                question_difficulty=question_difficulty,
                question_content=question_content,
                user_answer=user_answer,
                correct_answer=correct_answer,
                score=score,
                time_spent_ms=time_spent_ms,
                hints_used=hints_used,
                is_correct=is_correct,
                agent_decision=agent_decision,
                next_action=next_action,
                generated_content=generated_content,
            )
            
            # 更新学习者画像
            cls._update_learner_profile(learner, question_topic, score, is_correct)
            
            result = {
                "success": True,
                "learner_id": learner_id,
                "answer_record_id": answer_record.id,
                "is_correct": is_correct,
                "score": score,
                "accuracy_rate": accuracy_rate,
                "agent_decision": {
                    "decision": next_action,
                    "reason": agent_decision.get("reason", ""),
                    "confidence": agent_decision.get("confidence", 0),
                },
                "next_action": {
                    "type": next_action,
                    "description": cls._get_action_description(next_action),
                },
                "generated_content": generated_content,
            }
            
            cls.log_request("AdaptiveTutoringService", "process_answer", {
                "learner_id": learner_id,
                "score": score,
                "decision": next_action,
            })
            
            return result
            
        except Exception as e:
            logger.error(f"[自适应导学] 处理答题失败: {e}")
            cls.log_error("自适应导学失败", e)
            return {"success": False, "error": str(e)}
    
    @classmethod
    def _run_agent_decision(
        cls,
        learner: LearnerProfile,
        question_topic: str,
        score: float,
        accuracy_rate: float,
        is_correct: bool,
    ) -> Dict[str, Any]:
        """运行Agent协同决策"""
        learner_dict = cls.model_to_dict(learner)
        
        # 基础决策
        if accuracy_rate >= cls.DECISION_THRESHOLD:
            decision, reason, confidence = "advance", \
                f"答题正确率{accuracy_rate*100:.1f}%≥70%，已掌握当前知识点", \
                min(0.95, accuracy_rate)
        else:
            decision, reason, confidence = "simplify", \
                f"答题正确率{accuracy_rate*100:.1f}%<70%，需要简化解释", \
                min(0.95, (1 - accuracy_rate) * 1.2)
        
        # 诊断Agent验证
        agent = DiagnosisAgent()
        diagnosis = agent.run(task_id=-1, input_data={
            "learner_id": learner.id,
            "learner_profile": learner_dict,
        })
        
        blind_areas = diagnosis.get("knowledge_blind_areas", [])
        has_blind = any(question_topic in b.get("name", "") for b in blind_areas)
        
        if decision == "advance" and has_blind:
            decision, reason, confidence = "consolidate", \
                "虽然答题正确率达标，但检测到该主题存在知识盲区", 0.8
        
        return {
            "next_action": decision,
            "reason": reason,
            "confidence": round(confidence, 2),
        }
    
    @classmethod
    def _generate_simplified_explanation(
        cls,
        learner: LearnerProfile,
        question_topic: str,
        question_content: str,
        user_answer: str,
        correct_answer: str,
    ) -> Dict[str, Any]:
        """生成简化通俗知识点解释"""
        learning_style = learner.learning_style or "visual"
        
        style_prefixes = {
            "visual": "通过图解方式理解：",
            "auditory": "简单来说：",
            "reading": "核心要点是：",
            "kinesthetic": "动手实践中理解：",
        }
        
        explanations = _QUESTION_EXPLANATIONS

        style_prefix = style_prefixes.get(learning_style)
        explanation_text = explanations.get(question_topic)
        if explanation_text:
            simple_text = f"{style_prefix}{explanation_text}"
        else:
            simple_text = f"{style_prefix}{question_topic}的核心思想是..."
        
        # 查找相关资源
        suggested_resources = []
        with get_db_context() as db:
            resources = (
                db.query(LearningResource)
                .filter(
                    LearningResource.learner_id == learner.id,
                    LearningResource.difficulty_level <= 2,
                )
                .order_by(LearningResource.match_score.desc())
                .limit(3)
                .all()
            )
            for r in resources:
                suggested_resources.append({
                    "resource_id": r.id,
                    "title": r.title,
                    "type": r.resource_type,
                    "match_score": r.match_score,
                })
        
        return {
            "type": "simplify",
            "title": f"{question_topic} - 简化理解",
            "simple_explanation": simple_text,
            "key_points": cls._extract_key_points(question_topic),
            "practice_tips": f"建议从简单的{question_topic}基础问题开始练习",
            "suggested_resources": suggested_resources,
        }
    
    @classmethod
    def _generate_advanced_challenge(
        cls,
        learner: LearnerProfile,
        question_topic: str,
        current_difficulty: int,
    ) -> Dict[str, Any]:
        """生成高阶进阶挑战任务"""
        advanced_difficulty = min(MAX_DIFFICULTY, current_difficulty + 1)
        levels = ["基础", "进阶", "高级", "专家", "大师"]
        times = ["2小时", "4小时", "8小时", "12小时", "20小时"]
        
        challenge = {
            "type": "advance",
            "title": f"{question_topic} - 进阶挑战",
            "current_difficulty": current_difficulty,
            "advanced_difficulty": advanced_difficulty,
            "challenge_description": f"挑战：在理解{question_topic}基础概念的前提下，完成{levels[advanced_difficulty-1]}级实践任务。",
            "challenge_objectives": [
                "独立完成一个完整项目",
                "优化模型性能",
                "撰写技术文档",
            ],
            "estimated_time": times[advanced_difficulty - 1],
            "bonus_points": advanced_difficulty * 20,
            "suggested_resources": [],
        }
        
        # 查找高阶资源
        with get_db_context() as db:
            resources = (
                db.query(LearningResource)
                .filter(
                    LearningResource.learner_id == learner.id,
                    LearningResource.difficulty_level >= 3,
                )
                .order_by(LearningResource.difficulty_level.desc())
                .limit(3)
                .all()
            )
            for r in resources:
                challenge["suggested_resources"].append({
                    "resource_id": r.id,
                    "title": r.title,
                    "type": r.resource_type,
                    "difficulty_level": r.difficulty_level,
                })
        
        return challenge
    
    @classmethod
    def _save_answer_record(
        cls,
        user_id: int,
        learner_id: int,
        question_id: str,
        question_type: str,
        question_topic: str,
        question_difficulty: int,
        question_content: str,
        user_answer: str,
        correct_answer: str,
        score: float,
        time_spent_ms: int,
        hints_used: int,
        is_correct: bool,
        agent_decision: Dict[str, Any],
        next_action: str,
        generated_content: Dict[str, Any],
    ) -> AnswerRecord:
        """保存答题记录"""
        with get_db_context() as db:
            suggested_res = generated_content.get("suggested_resources", [])
            next_resource_id = suggested_res[0].get("resource_id") if suggested_res else None

            record = AnswerRecord(
                user_id=user_id,
                learner_id=learner_id,
                question_id=question_id,
                question_type=question_type,
                question_topic=question_topic,
                question_difficulty=question_difficulty,
                question_content=question_content,
                user_answer=user_answer,
                correct_answer=correct_answer,
                result="correct" if is_correct else "wrong",
                score=score,
                time_spent_ms=time_spent_ms,
                attempt_count=1,
                hints_used=hints_used,
                agent_decision=next_action,
                decision_reason=agent_decision.get("reason", ""),
                decision_confidence=agent_decision.get("confidence", 0),
                next_action=next_action,
                next_resource_id=next_resource_id,
                next_question_difficulty=(
                    question_difficulty + 1 if next_action == "advance" else question_difficulty
                ),
                feedback_given=True,
                feedback_content=generated_content.get("simple_explanation", "") or 
                                  generated_content.get("challenge_description", ""),
                decision_log=json.dumps(agent_decision, ensure_ascii=False),
                session_id=f"session_{uuid.uuid4().hex}",
                sequence_index=1,
            )
            db.add(record)
            db.flush()
            db.commit()
            return record
    
    @classmethod
    def _update_learner_profile(
        cls,
        learner: LearnerProfile,
        topic: str,
        score: float,
        is_correct: bool,
    ) -> None:
        """更新学习者画像"""
        topic_dimension_map = {
            "理论": "theoretical_foundation",
            "编程": "programming_ability",
            "算法": "algorithm_design",
            "架构": "system_architecture",
            "数据": "data_analysis",
            "工程": "engineering_practice",
        }
        
        with get_db_context() as db:
            attached = db.query(LearnerProfile).filter(
                LearnerProfile.id == learner.id
            ).first()
            if not attached:
                return
            for keyword, dimension in topic_dimension_map.items():
                if keyword in topic:
                    current = getattr(attached, dimension, 0) or 0
                    change = 2 if is_correct else -1
                    new_value = max(0, min(100, current + change))
                    setattr(attached, dimension, new_value)
                    db.commit()
                    break
    
    @classmethod
    def _extract_key_points(cls, topic: str) -> List[str]:
        """提取关键要点"""
        return _QUESTION_KEY_POINTS.get(topic, [f"{topic}的核心概念..."])
    
    @classmethod
    def _get_action_description(cls, action: str) -> str:
        """获取动作描述"""
        descriptions = {
            "simplify": "生成简化通俗的知识点解释",
            "advance": "生成高阶进阶挑战任务",
            "consolidate": "巩固当前知识点，建议复习基础",
            "none": "暂无后续动作",
        }
        return descriptions.get(action, "未知动作")
    
    @classmethod
    def get_interaction_history(
        cls,
        learner_id: int,
        session_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """获取历史交互记录"""
        with get_db_context() as db:
            query = db.query(AnswerRecord).filter(
                AnswerRecord.learner_id == learner_id
            )
            
            if session_id:
                query = query.filter(AnswerRecord.session_id == session_id)
            
            total = query.count()
            
            records = (
                query.order_by(AnswerRecord.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )
            
            history = [
                {
                    "record_id": r.id,
                    "session_id": r.session_id,
                    "sequence_index": r.sequence_index,
                    "question_id": r.question_id,
                    "question_type": r.question_type,
                    "question_topic": r.question_topic,
                    "question_difficulty": r.question_difficulty,
                    "user_answer": r.user_answer,
                    "correct_answer": r.correct_answer,
                    "result": r.result,
                    "score": r.score,
                    "time_spent_ms": r.time_spent_ms,
                    "agent_decision": r.agent_decision,
                    "decision_reason": r.decision_reason,
                    "decision_confidence": r.decision_confidence,
                    "next_action": r.next_action,
                    "next_resource_id": r.next_resource_id,
                    "feedback_given": r.feedback_given,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in records
            ]
            
            return {
                "learner_id": learner_id,
                "history": history,
                "total": total,
                "page": page,
                "page_size": page_size,
            }
