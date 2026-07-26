"""Validated dynamic tutoring questions backed by the shared LLM generator."""
import uuid
from typing import Any, Dict, List

from app.agents.llm_generator import LLMGenerator
from app.utils.llm import LLMUtil


class LLMQuestionGenerator:
    """Generate practice content while keeping answer data server controlled."""

    @classmethod
    def generate_question_set(
        cls, topic: str, difficulty: int, count: int, knowledge: List[Dict[str, Any]] | None = None
    ) -> List[Dict[str, Any]]:
        if not LLMUtil.is_available():
            raise RuntimeError("LLM is unavailable")
        generated = LLMGenerator.generate_exercises(
            {"recommended_difficulty": {"recommended_difficulty": difficulty}},
            knowledge or [],
            {},
            topic,
            question_count=count,
        )
        questions = generated["content_json"].get("basic_questions", []) + generated["content_json"].get("advanced_questions", [])
        result = []
        for question in questions[:count]:
            result.append({
                "id": f"llm-{uuid.uuid4().hex}",
                "type": "single",
                "topic": topic,
                "question": question["question"],
                "options": question["options"],
                "correctAnswer": chr(65 + question["correct_answer"]),
                "correctIndex": question["correct_answer"],
                "difficulty": question["difficulty"],
                "explanation": question["explanation"],
                "knowledgePoints": question.get("knowledge_points", []),
                "generation_method": "llm",
            })
        return result

    @classmethod
    def generate_explanation(cls, topic: str, question: str, correct_answer: str) -> str:
        questions = cls.generate_question_set(topic, 1, 1)
        return questions[0].get("explanation", f"请回顾 {topic} 的基础概念，再检查答案 {correct_answer}。")
