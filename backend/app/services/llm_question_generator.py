"""Validated dynamic tutoring questions backed by the shared LLM generator."""
import logging
import uuid
from typing import Any, Dict, List

from app.agents.llm_generator import LLMGenerator
from app.utils.llm import LLMUtil


logger = logging.getLogger(__name__)


class LLMQuestionGenerator:
    """Generate practice content while keeping answer data server controlled."""

    DIFFICULTY_STANDARDS = {
        1: "入门识别：只考查术语、基本事实和直接定义，初学者可凭基础常识或单步回忆作答。",
        2: "基础理解：考查概念关系、典型流程和直接应用，需要理解而非只靠常识排除。",
        3: "综合应用：给出真实场景或条件组合，要求运用多个相关概念完成分析与判断。",
        4: "高级分析：考查边界条件、失效模式、方案权衡和跨知识点推理，干扰项必须专业且合理。",
        5: "专家前沿：面向资深从业者或研究者，考查复杂约束下的机制推导、前沿方法、反例和系统级权衡；不得仅凭常识或关键词排除作答。",
    }

    @classmethod
    def difficulty_standard(cls, difficulty: int) -> str:
        return cls.DIFFICULTY_STANDARDS[max(1, min(5, int(difficulty)))]

    @classmethod
    def generate_question_set(
        cls,
        topic: str,
        difficulty: int,
        count: int,
        knowledge: List[Dict[str, Any]] | None = None,
        *,
        variation_seed: str | None = None,
        excluded_questions: List[str] | None = None,
    ) -> List[Dict[str, Any]]:
        if not LLMUtil.is_available():
            raise RuntimeError("LLM is unavailable")
        generated = None
        for attempt in range(2):
            attempt_seed = variation_seed
            if attempt:
                attempt_seed = f"{variation_seed or topic}-retry-{uuid.uuid4().hex[:8]}"
            try:
                generated = LLMGenerator.generate_exercises(
                    {"recommended_difficulty": {"recommended_difficulty": difficulty}},
                    knowledge or [],
                    {},
                    topic,
                    question_count=count,
                    variation_seed=attempt_seed,
                    excluded_questions=excluded_questions or [],
                    difficulty_standard=cls.difficulty_standard(difficulty),
                    multiple_choice_count=count // 3,
                )
                break
            except Exception as exc:
                logger.warning(
                    "[自适应导学] LLM 动态出题第 %d/2 次失败（主题=%s）：%s",
                    attempt + 1,
                    topic,
                    exc,
                )
                if attempt == 1:
                    raise
        if generated is None:  # pragma: no cover - loop either returns or raises
            raise RuntimeError("LLM question generation failed")
        questions = generated["content_json"].get("basic_questions", []) + generated["content_json"].get("advanced_questions", [])
        expected_multiple = count // 3
        actual_multiple = sum(question.get("type") == "multiple" for question in questions[:count])
        if len(questions) < count or actual_multiple != expected_multiple:
            raise ValueError("LLM question set does not match the requested count or type distribution")
        result = []
        for question in questions[:count]:
            answer_indexes = question.get("correct_answers") or [question["correct_answer"]]
            is_multiple = question.get("type") == "multiple"
            result.append({
                "id": f"llm-{uuid.uuid4().hex}",
                "type": "multiple" if is_multiple else "single",
                "topic": topic,
                "question": question["question"],
                "options": question["options"],
                "correctAnswer": answer_indexes if is_multiple else answer_indexes[0],
                "correctIndex": answer_indexes if is_multiple else answer_indexes[0],
                "difficulty": question["difficulty"],
                "explanation": question["explanation"],
                "knowledgePoints": question.get("knowledge_points", []),
                "generation_method": "deepseek",
            })
        return result

    @classmethod
    def generate_explanation(cls, topic: str, question: str, correct_answer: str) -> str:
        questions = cls.generate_question_set(topic, 1, 1)
        return questions[0].get("explanation", f"请回顾 {topic} 的基础概念，再检查答案 {correct_answer}。")
