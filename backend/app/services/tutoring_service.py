"""
交互式自适应导学动态迭代服务
双分支逻辑：正确率偏低→简化解释；正确率达标→进阶挑战
"""
import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from loguru import logger

from app.database import get_db_context
from app.models import (
    LearnerProfile,
    AnswerRecord,
    LearningResource,
    IssuedTutoringQuestion,
)
from app.agents.diagnosis_agent import DiagnosisAgent
from app.services.common import BaseService
from app.constants import ADAPTIVE_DECISION_THRESHOLD, MAX_DIFFICULTY
from app.utils.seed_loader import load_seed_payload
from app.services.llm_question_generator import LLMQuestionGenerator
from app.utils.llm import LLMUtil
from app.domains.knowledge.service import KnowledgeService

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
        """获取旧版静态题库，供兼容接口使用。"""
        return _QUESTION_BANK

    @staticmethod
    def _normalize_answer_key(answer: Any) -> List[str]:
        """Normalize generated option indexes or letters to submitted option letters."""
        values = answer if isinstance(answer, list) else [answer]
        normalized = []
        for value in values:
            if isinstance(value, int):
                normalized.append(chr(65 + value))
            else:
                normalized.extend(
                    item.strip().upper()
                    for item in str(value).split(",")
                    if item.strip()
                )
        if not normalized or any(not value for value in normalized):
            raise ValueError("题目缺少正确答案")
        return normalized

    @staticmethod
    def _public_question(question: IssuedTutoringQuestion) -> Dict[str, Any]:
        """Serialize a question without its server-only answer key."""
        return {
            "id": str(question.id),
            "type": question.question_type,
            "topic": question.topic,
            "question": question.content,
            "options": question.options,
            "difficulty": question.difficulty,
            "knowledgePoints": question.knowledge_points or [],
            "generationMethod": question.generation_method,
        }

    @classmethod
    def get_issued_questions(cls, learner_id: int) -> List[Dict[str, Any]]:
        """Return the learner's unanswered, server-issued questions only."""
        with get_db_context() as db:
            questions = db.query(IssuedTutoringQuestion).filter(
                IssuedTutoringQuestion.learner_id == learner_id,
                IssuedTutoringQuestion.status == "issued",
            ).order_by(
                IssuedTutoringQuestion.created_at.asc(),
                IssuedTutoringQuestion.id.asc(),
            ).all()
            return [cls._public_question(question) for question in questions]

    @classmethod
    def publish_resource_questions(
        cls,
        db,
        resource: LearningResource,
        learner: LearnerProfile,
        topic: str,
    ) -> int:
        """Publish an approved exercise resource as learner-owned questions."""
        if resource.resource_type != "exercise" or not resource.validation_passed:
            return 0

        payload = resource.content_json or {}
        questions = list(payload.get("basic_questions") or []) + list(payload.get("advanced_questions") or [])
        if not questions:
            return 0

        existing = db.query(IssuedTutoringQuestion).filter(
            IssuedTutoringQuestion.source_resource_id == resource.id,
        ).count()
        if existing:
            return existing

        normalized_topic = str(topic or resource.knowledge_topic or resource.title).strip()
        db.query(IssuedTutoringQuestion).filter(
            IssuedTutoringQuestion.learner_id == learner.id,
            IssuedTutoringQuestion.topic == normalized_topic,
            IssuedTutoringQuestion.status == "issued",
            IssuedTutoringQuestion.source_resource_id.is_not(None),
        ).update({"status": "superseded"}, synchronize_session=False)

        for index, question in enumerate(questions):
            content = str(question.get("question", "")).strip()
            options = question.get("options") or []
            if not content or not isinstance(options, list) or len(options) < 2:
                raise ValueError("分阶测试题格式不完整")

            answer = question.get("correct_answer", question.get("correctAnswer", question.get("correctIndex")))
            issued = IssuedTutoringQuestion(
                user_id=learner.user_id,
                learner_id=learner.id,
                question_type=question.get("type", "single"),
                topic=normalized_topic,
                difficulty=max(1, min(5, int(question.get("difficulty", resource.difficulty_level or 3)))),
                content=content,
                options=options,
                answer_key=cls._normalize_answer_key(answer),
                explanation=question.get("explanation", ""),
                knowledge_points=question.get("knowledge_points", question.get("knowledgePoints", [])),
                source_slice_ids=resource.source_slice_ids or [],
                source_doc_ids=resource.source_doc_ids or [],
                source_resource_id=resource.id,
                source_question_index=index,
                generation_method=resource.generation_method or "resource_generation",
            )
            db.add(issued)
        db.flush()
        return len(questions)
    
    @classmethod
    def generate_dynamic_questions(
        cls, user_id: int, learner_id: int, topic: str, difficulty: int, question_count: int
    ) -> List[Dict[str, Any]]:
        """Issue server-owned questions; answer keys never leave this service."""
        learner = cls.get_learner(learner_id)
        if not learner:
            raise ValueError("学习者不存在")

        learner_profile = cls.model_to_dict(learner)
        diagnosis = DiagnosisAgent().execute({"learner_id": learner_id, "learner_profile": learner_profile})
        effective_difficulty = diagnosis.get("recommended_difficulty", {}).get("recommended_difficulty", difficulty)
        effective_difficulty = max(1, min(5, round((effective_difficulty + difficulty) / 2)))
        with get_db_context() as db:
            knowledge = KnowledgeService.search(
                db=db,
                query=topic,
                industry=learner.target_industry,
                top_k=6,
            )

        generated: List[Dict[str, Any]] = []
        if knowledge and LLMUtil.is_available():
            try:
                generated = LLMQuestionGenerator.generate_question_set(
                    topic, effective_difficulty, question_count, knowledge
                )
            except Exception as exc:
                logger.warning(f"[自适应导学] LLM 动态出题失败，使用题库兜底: {exc}")

        if not generated:
            fallback = [
                question for question in _QUESTION_BANK
                if question.get("topic") == topic and question.get("difficulty") == effective_difficulty
            ] or list(_QUESTION_BANK)
            generated = [
                {
                    "id": str(question.get("id", uuid.uuid4().hex)),
                    "type": question.get("type", "single"),
                    "topic": question.get("topic", topic),
                    "question": question["question"],
                    "options": question["options"],
                    "correctAnswer": question.get("correctAnswer", question.get("correct_answer")),
                    "correctIndex": question.get("correctIndex", question.get("correct_answer")),
                    "difficulty": question.get("difficulty", effective_difficulty),
                    "explanation": question.get("explanation", _QUESTION_EXPLANATIONS.get(topic, "")),
                    "knowledgePoints": _QUESTION_KEY_POINTS.get(topic, []),
                    "generation_method": "deterministic_fallback",
                }
                for question in fallback[:question_count]
            ]

        return cls._persist_issued_questions(user_id, learner_id, generated, knowledge)

    @classmethod
    def _persist_issued_questions(
        cls, user_id: int, learner_id: int, questions: List[Dict[str, Any]], knowledge: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Persist server-only keys and return only the public question payload."""
        public_questions = []
        source_slice_ids = [item["slice_id"] for item in knowledge if item.get("slice_id") is not None]
        source_doc_ids = list({item["doc_id"] for item in knowledge if item.get("doc_id") is not None})
        with get_db_context() as db:
            learner = db.query(LearnerProfile).filter(LearnerProfile.id == learner_id).first()
            if not learner:
                raise ValueError("学习者不存在")
            for question in questions:
                answer = question.get("correctAnswer", question.get("correct_answer", question.get("correctIndex")))
                issued = IssuedTutoringQuestion(
                    user_id=learner.user_id,
                    learner_id=learner_id,
                    question_type=question.get("type", "single"),
                    topic=question.get("topic", ""),
                    difficulty=question.get("difficulty", 3),
                    content=question["question"],
                    options=question["options"],
                    answer_key=cls._normalize_answer_key(answer),
                    explanation=question.get("explanation", ""),
                    knowledge_points=question.get("knowledgePoints", question.get("knowledge_points", [])),
                    source_slice_ids=source_slice_ids,
                    source_doc_ids=source_doc_ids,
                    generation_method=question.get("generation_method", "deterministic_fallback"),
                )
                db.add(issued)
                db.flush()
                public_questions.append(cls._public_question(issued))
        return public_questions

    @classmethod
    def process_answer(
        cls,
        user_id: int,
        learner_id: int,
        question_id: str,
        user_answer: str,
        time_spent_ms: int,
        hints_used: int = 0,
    ) -> Dict[str, Any]:
        """Server-grade an answer to an issued learner-owned question."""
        if not str(question_id).isdigit():
            return {"success": False, "error": "只能提交服务端下发的题目"}

        with get_db_context() as db:
            issued_question = db.query(IssuedTutoringQuestion).filter(
                IssuedTutoringQuestion.id == int(question_id),
                IssuedTutoringQuestion.user_id == user_id,
                IssuedTutoringQuestion.learner_id == learner_id,
                IssuedTutoringQuestion.status == "issued",
            ).first()
            if not issued_question:
                return {"success": False, "error": "题目不存在、无权限或已提交"}

            normalized_answer = user_answer if isinstance(user_answer, list) else str(user_answer).split(",")
            normalized_answer = sorted(str(value).strip().upper() for value in normalized_answer)
            expected_answer = sorted(str(value) for value in (issued_question.answer_key or []))
            is_correct = normalized_answer == expected_answer
            question_type = issued_question.question_type
            question_topic = issued_question.topic
            question_difficulty = issued_question.difficulty
            question_content = issued_question.content
            correct_answer = issued_question.answer_key
            score = 100.0 if is_correct else 0.0
            issued_question_id = issued_question.id

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

            # Save the record, learner update, and issued-question status atomically.
            with get_db_context() as db:
                claimed = db.query(IssuedTutoringQuestion).filter(
                    IssuedTutoringQuestion.id == issued_question_id,
                    IssuedTutoringQuestion.user_id == user_id,
                    IssuedTutoringQuestion.learner_id == learner_id,
                    IssuedTutoringQuestion.status == "issued",
                ).update({"status": "answering"}, synchronize_session=False)
                if claimed != 1:
                    return {"success": False, "error": "题目已提交或无权限"}
                pending_question = db.query(IssuedTutoringQuestion).filter(
                    IssuedTutoringQuestion.id == issued_question_id,
                ).first()

                answer_record = cls._save_answer_record(
                    user_id=user_id,
                    learner_id=learner_id,
                    question_id=question_id,
                    issued_question_id=issued_question_id,
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
                    db=db,
                )
                cls._update_learner_profile(learner, question_topic, score, is_correct, db=db)
                pending_question.status = "answered"
                pending_question.answered_at = datetime.utcnow()
                db.flush()
            
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
        """生成简化通俗知识点解释（接入知识库检索）"""
        learning_style = learner.learning_style or "visual"

        style_prefixes = {
            "visual": "通过图解方式理解：",
            "auditory": "简单来说：",
            "reading": "核心要点是：",
            "kinesthetic": "动手实践中理解：",
        }

        style_prefix = style_prefixes.get(learning_style, "核心要点是：")

        # 1. 尝试从知识库检索相关内容
        knowledge_explanation = ""
        knowledge_key_points: List[str] = []
        with get_db_context() as db:
            kb_results = KnowledgeService.search(
                db=db,
                query=question_topic,
                industry=learner.target_industry,
                top_k=5,
            )
            if kb_results:
                # 从知识库提取用于解释的内容
                kb_contents = [k.get("content", "").strip() for k in kb_results if k.get("content", "").strip()]
                if kb_contents:
                    # 取最相关的前2段作为解释素材
                    knowledge_explanation = " ".join(kb_contents[:2])[:500]
                    # 提取关键点
                    for k in kb_results[:3]:
                        title = k.get("title", "") or k.get("doc_title", "")
                        if title:
                            knowledge_key_points.append(title)

        # 2. 先从种子JSON取解释，没有则用知识库内容
        explanations = _QUESTION_EXPLANATIONS
        seed_explanation = explanations.get(question_topic)
        if seed_explanation:
            simple_text = f"{style_prefix}{seed_explanation}"
        elif knowledge_explanation:
            simple_text = f"{style_prefix}{knowledge_explanation}"
        else:
            simple_text = f"{style_prefix}{question_topic}是相关领域的重要概念，建议结合实操练习加深理解..."

        # 3. 关键要点：优先知识库提取的，其次种子数据
        if knowledge_key_points:
            key_points = knowledge_key_points
        else:
            key_points = cls._extract_key_points(question_topic)

        # 4. 查找相关资源
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
            "key_points": key_points,
            "practice_tips": f"建议从简单的{question_topic}基础问题开始练习，结合实际案例加深理解。",
            "suggested_resources": suggested_resources,
            "knowledge_source": "knowledge_base" if knowledge_explanation else "seed_data",
        }
    
    @classmethod
    def _generate_advanced_challenge(
        cls,
        learner: LearnerProfile,
        question_topic: str,
        current_difficulty: int,
    ) -> Dict[str, Any]:
        """生成高阶进阶挑战任务（接入知识库检索）"""
        advanced_difficulty = min(MAX_DIFFICULTY, current_difficulty + 1)
        levels = ["基础", "进阶", "高级", "专家", "大师"]
        times = ["2小时", "4小时", "8小时", "12小时", "20小时"]

        # 从知识库检索高阶内容作为挑战素材
        challenge_objectives = [
            "独立完成一个完整项目",
            "优化模型性能",
            "撰写技术文档",
        ]
        challenge_description = f"挑战：在理解{question_topic}基础概念的前提下，完成{levels[advanced_difficulty-1]}级实践任务。"
        kb_results = []  # 初始化避免作用域问题

        with get_db_context() as db:
            kb_results = KnowledgeService.search(
                db=db,
                query=question_topic,
                industry=learner.target_industry,
                top_k=5,
            )
            if kb_results:
                # 用知识库内容构建更具挑战性的目标
                kb_objectives = []
                for k in kb_results[:4]:
                    title = k.get("title", "") or k.get("doc_title", "")
                    content = k.get("content", "").strip()
                    if content:
                        # 从知识库片段中提取可作为挑战任务的内容
                        sentences = [s.strip() for s in content.split("。") if len(s.strip()) > 15]
                        if sentences:
                            kb_objectives.append(f"深入理解并实践：{sentences[0][:100]}")
                        elif title:
                            kb_objectives.append(f"掌握「{title}」的高级应用")
                if kb_objectives:
                    challenge_objectives = kb_objectives[:3]
                    # 用知识库相关内容构建更详细的挑战描述
                    first_content = kb_results[0].get("content", "").strip()[:200]
                    if first_content:
                        challenge_description = (
                            f"挑战：基于知识库中的「{question_topic}」相关内容，"
                            f"完成以下{levels[advanced_difficulty-1]}级实践任务。"
                        )

        challenge = {
            "type": "advance",
            "title": f"{question_topic} - 进阶挑战",
            "current_difficulty": current_difficulty,
            "advanced_difficulty": advanced_difficulty,
            "challenge_description": challenge_description,
            "challenge_objectives": challenge_objectives,
            "estimated_time": times[advanced_difficulty - 1],
            "bonus_points": advanced_difficulty * 20,
            "suggested_resources": [],
            "knowledge_source": "knowledge_base" if kb_results else "template",
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
        issued_question_id: int,
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
        db=None,
    ) -> AnswerRecord:
        """保存答题记录"""
        if db is None:
            with get_db_context() as managed_db:
                return cls._save_answer_record(
                    user_id=user_id,
                    learner_id=learner_id,
                    question_id=question_id,
                    issued_question_id=issued_question_id,
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
                    db=managed_db,
                )

        suggested_res = generated_content.get("suggested_resources", [])
        next_resource_id = suggested_res[0].get("resource_id") if suggested_res else None
        record = AnswerRecord(
            user_id=user_id,
            learner_id=learner_id,
            question_id=int(question_id),
            issued_question_id=issued_question_id,
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
        return record
    
    @classmethod
    def _update_learner_profile(
        cls,
        learner: LearnerProfile,
        topic: str,
        score: float,
        is_correct: bool,
        db=None,
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
        
        if db is None:
            with get_db_context() as managed_db:
                cls._update_learner_profile(learner, topic, score, is_correct, db=managed_db)
            return

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
