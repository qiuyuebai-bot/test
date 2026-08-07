"""交互式自适应导学服务：单题二元判定，并同时提供通俗讲解与知识点扩展。"""
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
from app.services.ai_content_service import AIContentService
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
    TOPIC_ALIASES = {
        "bp算法": "反向传播算法",
        "bp 算法": "反向传播算法",
        "bp": "反向传播算法",
        "反向传播": "反向传播算法",
        "backpropagation": "反向传播算法",
        "back propagation": "反向传播算法",
        "python列表": "Python列表",
        "python 列表": "Python列表",
        "python list": "Python列表",
        "python lists": "Python列表",
        "list": "Python列表",
    }

    @classmethod
    def get_questions(cls) -> List[Dict[str, Any]]:
        """获取旧版静态题库，供兼容接口使用。"""
        return _QUESTION_BANK

    @classmethod
    def _normalize_topic(cls, topic: str) -> str:
        normalized = " ".join(str(topic or "").strip().split())
        if not normalized:
            return ""
        return cls.TOPIC_ALIASES.get(normalized.lower(), normalized)

    @classmethod
    def _resolve_topic(cls, learner_id: int, topic: str) -> str:
        normalized = cls._normalize_topic(topic)
        if normalized:
            return normalized

        with get_db_context() as db:
            resource = (
                db.query(LearningResource)
                .filter(
                    LearningResource.learner_id == learner_id,
                    LearningResource.resource_type == "exercise",
                    LearningResource.validation_passed.is_(True),
                    LearningResource.status == "ready",
                    LearningResource.knowledge_topic.is_not(None),
                )
                .order_by(LearningResource.created_at.desc(), LearningResource.id.desc())
                .first()
            )
            if resource and resource.knowledge_topic:
                return cls._normalize_topic(resource.knowledge_topic)
        return ""

    @classmethod
    def _topic_matches(cls, requested_topic: str, candidate_topic: str) -> bool:
        requested = cls._normalize_topic(requested_topic).casefold()
        candidate = cls._normalize_topic(candidate_topic).casefold()
        return bool(requested and candidate and (requested == candidate or requested in candidate or candidate in requested))

    @staticmethod
    def _question_signature(question: Any) -> str:
        """Create a stable comparison key for generated and historical questions."""
        content = question.get("question", "") if isinstance(question, dict) else question
        return " ".join(str(content or "").strip().casefold().split())

    @classmethod
    def _generic_fallback_question(cls, topic: str, difficulty: int, index: int) -> Dict[str, Any]:
        """Return a topic-labelled question when neither the provider nor seed bank can help."""
        focus = ["基础概念与前提", "核心机制", "场景应用", "边界条件", "专业权衡"][index % 5]
        templates = {
            1: (
                f"入门学习“{topic}”时，关于其{focus}首先需要识别哪项基础信息？",
                [
                    f"{topic}的基本定义、主要对象和直接用途",
                    f"{topic}在所有场景中的最终性能上限",
                    f"{topic}尚未解决的全部前沿争议",
                    f"{topic}在复杂系统中的完整形式化证明",
                ],
                "难度 1 只要求识别基本定义、对象与直接用途。",
            ),
            2: (
                f"理解“{topic}”的{focus}时，哪种说明达到了基础理解要求？",
                [
                    "能说明关键概念之间的关系、典型流程以及直接适用场景",
                    "能背出若干术语，但无法解释它们如何关联",
                    "能复述一个结论，但无法说明结论成立的前提",
                    "能记住一个示例答案，并把它直接套用到所有场景",
                ],
                "难度 2 要求理解概念关系、典型流程和直接应用，不能只靠术语记忆。",
            ),
            3: (
                f"把“{topic}”用于条件发生变化的真实场景时，针对{focus}哪种分析最合理？",
                [
                    "先识别输入、约束与目标，再组合相关概念推导并验证结果",
                    "沿用原场景结论，只调整结论中的个别关键词",
                    "只比较最终输出，不检查中间假设是否仍然成立",
                    "只选择最熟悉的方法，不分析它与新约束的匹配程度",
                ],
                "难度 3 要求在新场景中组合多个概念，并根据输入、约束和目标完成推理。",
            ),
            4: (
                f"在“{topic}”的工程评审中，系统约束与数据条件同时变化。对{focus}采用哪种方案最严谨？",
                [
                    "比较候选方案的机制、复杂度与失效边界，并用针对性实验验证关键权衡",
                    "只优化单一指标，其他约束在上线后再根据结果调整",
                    "直接复用公开基线，因为同类方案通常具有相同的边界条件",
                    "先扩大数据或算力规模，以此替代对机制和错误模式的分析",
                ],
                "难度 4 需要分析边界条件、失效模式和多目标权衡，不能依赖单一指标。",
            ),
            5: (
                f"对“{topic}”的{focus}进行专家级审查时，某方案声称在复杂约束下取得突破。哪组证据最足以支持该结论？",
                [
                    "明确形式化假设，给出机制推导与反例，完成消融、稳健性和可复现实验，并说明适用边界",
                    "在单一公开基准上提高平均指标，同时省略失败样本和超参数敏感性分析",
                    "引用多篇相关工作并增加模型规模，以行业常用做法作为主要正确性依据",
                    "展示若干成功案例和可视化结果，用整体趋势代替误差来源与边界条件分析",
                ],
                "难度 5 要求机制推导、反例、系统级权衡与可复现证据共同成立。",
            ),
        }
        question, options, explanation = templates[max(1, min(5, int(difficulty)))]
        is_multiple = (index + 1) % 3 == 0
        correct_indexes = [0]
        if is_multiple:
            second_correct = {
                1: f"能够指出{topic}与相近概念的一个基本区别",
                2: f"能够用典型例子说明{topic}的关键流程与适用条件",
                3: f"能够检查{topic}分析中的关键假设并用结果反证",
                4: f"能够比较{topic}方案对约束变化的敏感性与失效模式",
                5: f"能够报告{topic}实验的负结果、复现条件与结论边界",
            }[max(1, min(5, int(difficulty)))]
            options = [options[0], second_correct, options[1], options[2]]
            correct_indexes = [0, 1]
            question = f"{question.rstrip('？')}（多选）？"
        rotation = index % len(options)
        options = options[rotation:] + options[:rotation]
        rotated_correct_indexes = sorted((answer_index - rotation) % len(options) for answer_index in correct_indexes)
        correct_answer: Any = rotated_correct_indexes if is_multiple else rotated_correct_indexes[0]
        if index >= 3:
            question = f"{question}（变体 {index + 1}）"
        return {
            "id": f"fallback-{uuid.uuid4().hex}",
            "type": "multiple" if is_multiple else "single",
            "topic": topic,
            "question": question,
            "options": options,
            "correctAnswer": correct_answer,
            "correctIndex": correct_answer,
            "difficulty": difficulty,
            "explanation": explanation,
            "knowledgePoints": [topic],
            "generation_method": "deterministic_fallback",
        }

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
        cls,
        user_id: int,
        learner_id: int,
        topic: str,
        difficulty: Optional[int],
        question_count: int,
        replace_pending: bool = False,
    ) -> List[Dict[str, Any]]:
        """Issue server-owned questions; answer keys never leave this service."""
        learner = cls.get_learner(learner_id)
        if not learner:
            raise ValueError("学习者不存在")

        question_count = max(1, min(10, int(question_count)))

        normalized_topic = cls._resolve_topic(learner_id, topic)
        if not normalized_topic:
            raise ValueError("请先指定学习主题或生成分阶测试题资源")

        learner_profile = cls.model_to_dict(learner)
        diagnosis = DiagnosisAgent().execute({"learner_id": learner_id, "learner_profile": learner_profile})
        recommended_difficulty = diagnosis.get("recommended_difficulty", {}).get("recommended_difficulty", 3)
        requested_difficulty = difficulty if difficulty is not None else recommended_difficulty
        # 用户明确选择难度时必须严格遵守；只有留空时才使用画像推荐难度。
        effective_difficulty = max(1, min(5, int(requested_difficulty)))
        with get_db_context() as db:
            knowledge = KnowledgeService.search(
                db=db,
                query=normalized_topic,
                industry=learner.target_industry,
                top_k=6,
            )
            previous_questions = (
                db.query(IssuedTutoringQuestion.content)
                .filter(
                    IssuedTutoringQuestion.learner_id == learner_id,
                    IssuedTutoringQuestion.topic == normalized_topic,
                )
                .order_by(IssuedTutoringQuestion.created_at.desc())
                .limit(20)
                .all()
            )
        excluded_questions = [row[0] for row in previous_questions if row[0]]

        generated: List[Dict[str, Any]] = []
        if LLMUtil.is_available():
            try:
                generated = LLMQuestionGenerator.generate_question_set(
                    normalized_topic,
                    effective_difficulty,
                    question_count,
                    knowledge,
                    variation_seed=f"{learner_id}-{normalized_topic}-{uuid.uuid4().hex}",
                    excluded_questions=excluded_questions,
                )
            except Exception as exc:
                logger.warning(f"[自适应导学] LLM 动态出题失败，使用题库兜底: {exc}")

        excluded_signatures = {
            cls._question_signature(question)
            for question in excluded_questions
            if cls._question_signature(question)
        }
        unique_generated: List[Dict[str, Any]] = []
        seen_signatures = set(excluded_signatures)
        for question in generated:
            if int(question.get("difficulty", effective_difficulty)) != effective_difficulty:
                continue
            signature = cls._question_signature(question)
            if signature and signature not in seen_signatures:
                seen_signatures.add(signature)
                unique_generated.append(question)
        generated = unique_generated[:question_count]
        for question in generated:
            question["difficulty"] = effective_difficulty

        fallback = sorted(
            (
                question for question in _QUESTION_BANK
                if cls._topic_matches(normalized_topic, question.get("topic", ""))
                and int(question.get("difficulty", 3)) == effective_difficulty
            ),
            key=lambda question: abs(int(question.get("difficulty", 3)) - effective_difficulty),
        )
        for question in fallback:
            if len(generated) >= question_count:
                break
            candidate = {
                "id": str(question.get("id", uuid.uuid4().hex)),
                "type": question.get("type", "single"),
                "topic": normalized_topic,
                "question": question["question"],
                "options": question["options"],
                "correctAnswer": question.get("correctAnswer", question.get("correct_answer")),
                "correctIndex": question.get("correctIndex", question.get("correct_answer")),
                "difficulty": effective_difficulty,
                "explanation": question.get("explanation") or _QUESTION_EXPLANATIONS.get(normalized_topic, ""),
                "knowledgePoints": question.get("knowledgePoints") or _QUESTION_KEY_POINTS.get(normalized_topic, [normalized_topic]),
                "generation_method": "deterministic_fallback",
            }
            expected_multiple = (len(generated) + 1) % 3 == 0
            if (candidate["type"] == "multiple") != expected_multiple:
                continue
            signature = cls._question_signature(candidate)
            if signature and signature not in seen_signatures:
                seen_signatures.add(signature)
                generated.append(candidate)

        fallback_variant = 0
        while len(generated) < question_count:
            candidate_index = len(generated) + fallback_variant * 3
            candidate = cls._generic_fallback_question(normalized_topic, effective_difficulty, candidate_index)
            signature = cls._question_signature(candidate)
            if signature not in seen_signatures:
                seen_signatures.add(signature)
                generated.append(candidate)
                fallback_variant = 0
            else:
                fallback_variant += 1

        return cls._persist_issued_questions(
            user_id,
            learner_id,
            generated,
            knowledge,
            topic=normalized_topic,
            replace_pending=replace_pending,
        )

    @classmethod
    def _persist_issued_questions(
        cls,
        user_id: int,
        learner_id: int,
        questions: List[Dict[str, Any]],
        knowledge: List[Dict[str, Any]],
        topic: str = "",
        replace_pending: bool = False,
    ) -> List[Dict[str, Any]]:
        """Persist server-only keys and return only the public question payload."""
        public_questions = []
        source_slice_ids = [item["slice_id"] for item in knowledge if item.get("slice_id") is not None]
        source_doc_ids = list({item["doc_id"] for item in knowledge if item.get("doc_id") is not None})
        with get_db_context() as db:
            learner = db.query(LearnerProfile).filter(LearnerProfile.id == learner_id).first()
            if not learner:
                raise ValueError("学习者不存在")
            normalized_topic = cls._normalize_topic(topic)
            if replace_pending and normalized_topic:
                db.query(IssuedTutoringQuestion).filter(
                    IssuedTutoringQuestion.learner_id == learner_id,
                    IssuedTutoringQuestion.topic == normalized_topic,
                    IssuedTutoringQuestion.status == "issued",
                ).update({"status": "superseded"}, synchronize_session=False)
            for question in questions:
                content = str(question.get("question", "")).strip()
                options = question.get("options") or []
                if not content or not isinstance(options, list) or len(options) < 2:
                    raise ValueError("动态题目格式不完整")
                answer = question.get("correctAnswer", question.get("correct_answer", question.get("correctIndex")))
                question_topic = normalized_topic or cls._normalize_topic(question.get("topic", ""))
                if not question_topic:
                    raise ValueError("动态题目缺少知识主题")
                issued = IssuedTutoringQuestion(
                    user_id=learner.user_id,
                    learner_id=learner_id,
                    question_type=question.get("type", "single"),
                    topic=question_topic,
                    difficulty=max(1, min(5, int(question.get("difficulty", 3)))),
                    content=content,
                    options=options,
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
        session_id: Optional[str] = None,
        sequence_index: Optional[int] = None,
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

            # 无论答对或答错都提供通俗讲解和知识点扩展；决策只影响讲解侧重点与后续难度。
            generated_content = cls._generate_simplified_explanation(
                learner,
                question_topic,
                question_content,
                user_answer,
                correct_answer,
                decision="review" if is_correct else "simplify",
            )
            generated_content["knowledge_expansion"] = cls._generate_knowledge_expansion(
                learner,
                question_topic,
                question_content,
                question_difficulty,
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
                    session_id=session_id,
                    sequence_index=sequence_index,
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
                "next_question_difficulty": max(
                    1,
                    min(
                        MAX_DIFFICULTY,
                        question_difficulty + (1 if next_action == "advance" else -1 if next_action == "simplify" else 0),
                    ),
                ),
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
        
        # 当前题型按单题二元判定：答对为 100，答错为 0，不展示容易误解的单题“正确率”。
        if is_correct:
            decision, reason, confidence = "advance", \
                "本题判定为正确，已掌握当前题目涉及的核心知识点", \
                min(0.95, max(0.8, accuracy_rate))
        else:
            decision, reason, confidence = "simplify", \
                "本题判定为错误，需要复核关键条件并查看通俗讲解", \
                min(0.95, max(0.8, 1 - accuracy_rate))
        
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
                "虽然本题判定正确，但检测到该主题仍存在知识盲区", 0.8
        
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
        decision: str = "simplify",
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
        kb_results = []
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

        try:
            ai_content = AIContentService.generate(
                "tutoring_feedback",
                {
                    "decision": decision,
                    "topic": question_topic,
                    "question": question_content,
                    "user_answer": user_answer,
                    "correct_answer": correct_answer,
                    "difficulty": 3,
                    "learning_style": learning_style,
                    "learner_summary": {
                        "target_industry": learner.target_industry,
                        "preferred_difficulty": learner.preferred_difficulty,
                    },
                    "reference_knowledge": knowledge_explanation or "无可用参考资料",
                },
            )
            ai_content["simple_explanation"] = f"{style_prefix}{ai_content['simple_explanation']}"
            ai_content["suggested_resources"] = suggested_resources
            return ai_content
        except Exception as exc:
            logger.warning(f"[自适应导学] AI 简化反馈失败，使用本地兜底: {exc}")

        return {
            "type": "simplify",
            "title": f"{question_topic} - 简化理解",
            "simple_explanation": simple_text,
            "key_points": key_points,
            "practice_tips": f"建议从简单的{question_topic}基础问题开始练习，结合实际案例加深理解。",
            "recommendation": f"先复习{question_topic}的核心概念，再完成一道基础练习并记录错误原因。",
            "suggested_resources": suggested_resources,
            "knowledge_source": "knowledge_base" if knowledge_explanation else "seed_data",
        }

    @classmethod
    def _generate_knowledge_expansion(
        cls,
        learner: LearnerProfile,
        question_topic: str,
        question_content: str,
        current_difficulty: int,
    ) -> Dict[str, Any]:
        """Generate question-specific knowledge expansion instead of an unrelated challenge task."""
        key_points = cls._extract_key_points(question_topic)
        overview = (
            f"本题围绕“{question_topic}”展开。理解时应同时关注核心机制、成立条件、"
            "典型应用和失效边界，而不只记住选项结论。"
        )
        knowledge_source = "seed_data"

        with get_db_context() as db:
            kb_results = KnowledgeService.search(
                db=db,
                query=f"{question_topic} {question_content}",
                industry=learner.target_industry,
                top_k=5,
            )
            if kb_results:
                contents = [str(item.get("content", "")).strip() for item in kb_results if item.get("content")]
                titles = [
                    str(item.get("title") or item.get("doc_title") or "").strip()
                    for item in kb_results
                    if item.get("title") or item.get("doc_title")
                ]
                if contents:
                    overview = " ".join(contents[:2])[:800]
                if titles:
                    key_points = list(dict.fromkeys([*key_points, *titles]))[:5]
                knowledge_source = "knowledge_base"

            resources = (
                db.query(LearningResource)
                .filter(
                    LearningResource.learner_id == learner.id,
                    LearningResource.difficulty_level >= max(1, current_difficulty - 1),
                )
                .order_by(LearningResource.match_score.desc())
                .limit(3)
                .all()
            )

        return {
            "type": "knowledge_expansion",
            "title": f"{question_topic} - 知识点扩展",
            "overview": overview,
            "key_points": key_points,
            "application": (
                f"回到本题时，可以把“{question_topic}”拆成输入与前提、核心机制、输出结果和边界条件，"
                "再检查选项是否同时满足这些约束。"
            ),
            "pitfalls": [
                "不要用生活常识代替领域内的定义、机制和约束条件。",
                "不要只看结论是否熟悉，还要核对结论成立的前提和适用边界。",
                "面对相近选项时，应比较关键条件，而不是依赖关键词或选项位置。",
            ],
            "suggested_resources": [
                {
                    "resource_id": resource.id,
                    "title": resource.title,
                    "type": resource.resource_type,
                    "difficulty_level": resource.difficulty_level,
                }
                for resource in resources
            ],
            "knowledge_source": knowledge_source,
        }
    
    @classmethod
    def _generate_advanced_challenge(
        cls,
        learner: LearnerProfile,
        question_topic: str,
        current_difficulty: int,
        decision: str = "advance",
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
            "type": decision,
            "title": f"{question_topic} - 进阶挑战",
            "current_difficulty": current_difficulty,
            "advanced_difficulty": advanced_difficulty,
            "challenge_description": challenge_description,
            "challenge_objectives": challenge_objectives,
            "estimated_time": times[advanced_difficulty - 1],
            "bonus_points": advanced_difficulty * 20,
            "recommendation": f"建议围绕{question_topic}完成一次综合实践，并用验收标准检查结果。",
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

        try:
            ai_content = AIContentService.generate(
                "tutoring_feedback",
                {
                    "decision": decision,
                    "topic": question_topic,
                    "question": f"围绕{question_topic}的当前练习",
                    "user_answer": "已完成当前题目",
                    "correct_answer": "当前题目答案已由服务端校验",
                    "difficulty": current_difficulty,
                    "learning_style": learner.learning_style or "visual",
                    "learner_summary": {
                        "target_industry": learner.target_industry,
                        "preferred_difficulty": learner.preferred_difficulty,
                    },
                    "reference_knowledge": "\n".join(
                        str(item.get("content", ""))[:500] for item in kb_results[:3]
                    ) or "无可用参考资料",
                },
            )
            challenge.update({
                "title": ai_content.get("title", challenge["title"]),
                "challenge_description": ai_content.get("challenge_description") or challenge["challenge_description"],
                "challenge_objectives": ai_content.get("challenge_objectives") or challenge["challenge_objectives"],
                "recommendation": ai_content.get("recommendation", ""),
                "practice_tips": ai_content.get("practice_tips", ""),
                "generation_method": "deepseek",
            })
        except Exception as exc:
            logger.warning(f"[自适应导学] AI 进阶反馈失败，使用本地兜底: {exc}")

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
        session_id: Optional[str] = None,
        sequence_index: Optional[int] = None,
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
                    session_id=session_id,
                    sequence_index=sequence_index,
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
            session_id=session_id or f"session_{uuid.uuid4().hex}",
            sequence_index=sequence_index or 1,
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
            "simplify": "提供纠错通俗讲解和知识点扩展",
            "advance": "提供知识点扩展学习，继续深化理解",
            "consolidate": "提供巩固讲解和知识点扩展",
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
                    "question_content": r.question_content,
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
                    "feedback_content": r.feedback_content,
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
