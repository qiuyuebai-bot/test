"""LLM-backed learning-resource generation with strict response validation."""
import json
from typing import Any, Dict, List

from app.utils.llm import LLMUtil
from app.utils.llm_response import (
    LLMResponseError,
    bounded_int,
    bounded_list,
    bounded_text,
    parse_json_object,
)


class LLMGenerator:
    """Generate resources from approved prompt templates and retrieved context."""

    @classmethod
    def generate_guide(
        cls, diagnosis: Dict[str, Any], knowledge: List[Dict[str, Any]], profile: Dict[str, Any], topic: str
    ) -> Dict[str, Any]:
        return cls._generate_resource("guide", diagnosis, knowledge, profile, topic)

    @classmethod
    def generate_lecture(
        cls, diagnosis: Dict[str, Any], knowledge: List[Dict[str, Any]], profile: Dict[str, Any], topic: str
    ) -> Dict[str, Any]:
        return cls._generate_resource("lecture", diagnosis, knowledge, profile, topic)

    @classmethod
    def generate_exercises(
        cls,
        diagnosis: Dict[str, Any],
        knowledge: List[Dict[str, Any]],
        profile: Dict[str, Any],
        topic: str,
        question_count: int | None = None,
    ) -> Dict[str, Any]:
        if not knowledge:
            raise LLMResponseError("retrieved knowledge is required for LLM question generation")
        difficulty = cls._difficulty(diagnosis)
        question_count = max(1, min(6, question_count or max(3, difficulty + 1)))
        response, _ = LLMUtil.call_with_prompt_template(
            "question_generation",
            {
                "knowledge_topic": topic,
                "difficulty_level": difficulty,
                "question_count": question_count,
                "reference_knowledge": cls._reference_text(knowledge),
            },
            temperature=0.4,
            use_cache=False,
        )
        payload = parse_json_object(response)
        if payload.get("_meta", {}).get("model") == "mock":
            raise LLMResponseError("LLM returned fallback mock response")
        questions = [cls._normalize_question(item) for item in bounded_list(payload.get("questions"), "questions", minimum=1, maximum=10)]
        return cls._exercise_result(topic, questions, knowledge)

    @classmethod
    def _generate_resource(
        cls, resource_type: str, diagnosis: Dict[str, Any], knowledge: List[Dict[str, Any]], profile: Dict[str, Any], topic: str
    ) -> Dict[str, Any]:
        if not knowledge:
            raise LLMResponseError("retrieved knowledge is required for LLM resource generation")
        difficulty = cls._difficulty(diagnosis)
        response, _ = LLMUtil.call_with_prompt_template(
            "resource_generation",
            {
                "learner_summary": cls._learner_summary(profile, diagnosis),
                "knowledge_topic": topic,
                "difficulty_level": difficulty,
                "resource_type": resource_type,
                "reference_knowledge": cls._reference_text(knowledge),
            },
            temperature=0.5,
            use_cache=False,
        )
        payload = parse_json_object(response)
        if payload.get("_meta", {}).get("model") == "mock":
            raise LLMResponseError("LLM returned fallback mock response")
        content = bounded_text(payload.get("content"), "content", minimum=100, maximum=16000)
        title = bounded_text(payload.get("resource_title", f"{topic} {resource_type}"), "resource_title", maximum=200)
        actual_difficulty = bounded_int(payload.get("difficulty_level", difficulty), "difficulty_level", minimum=1, maximum=5)
        topics = [bounded_text(item, "topic", maximum=100) for item in bounded_list(payload.get("topics", [topic]), "topics", minimum=1, maximum=8)]
        return {
            "content": content,
            "content_json": {
                "resource_type": resource_type,
                "title": title,
                "topics": topics,
                "difficulty": actual_difficulty,
            },
            "resource_title": title,
            "difficulty_level": actual_difficulty,
            **cls._provenance(knowledge),
        }

    @staticmethod
    def _normalize_question(item: Any) -> Dict[str, Any]:
        if not isinstance(item, dict):
            raise LLMResponseError("question must be an object")
        options = [bounded_text(option, "option", maximum=500) for option in bounded_list(item.get("options"), "options", minimum=2, maximum=6)]
        answer = item.get("correct_answer")
        if isinstance(answer, int):
            answer_index = bounded_int(answer, "correct_answer", minimum=0, maximum=len(options) - 1)
        elif isinstance(answer, str):
            normalized = answer.strip().upper()
            answer_index = ord(normalized[0]) - ord("A") if normalized else -1
            if not 0 <= answer_index < len(options):
                try:
                    answer_index = options.index(answer)
                except ValueError as exc:
                    raise LLMResponseError("correct_answer does not match an option") from exc
        else:
            raise LLMResponseError("correct_answer is required")
        return {
            "question": bounded_text(item.get("question"), "question", minimum=5, maximum=2000),
            "options": options,
            "correct_answer": answer_index,
            "difficulty": bounded_int(item.get("difficulty_level", item.get("difficulty", 3)), "difficulty", minimum=1, maximum=5),
            "explanation": bounded_text(item.get("explanation"), "explanation", minimum=5, maximum=3000),
            "knowledge_points": [
                bounded_text(point, "knowledge_point", maximum=120)
                for point in bounded_list(item.get("knowledge_points", []), "knowledge_points", maximum=8)
            ],
        }

    @classmethod
    def _exercise_result(cls, topic: str, questions: List[Dict[str, Any]], knowledge: List[Dict[str, Any]]) -> Dict[str, Any]:
        basic = [question for question in questions if question["difficulty"] <= 3]
        advanced = [question for question in questions if question["difficulty"] > 3]
        lines = [f"# {topic} 分阶测试题", ""]
        for index, question in enumerate(questions, 1):
            lines.extend([f"## 第{index}题：{question['question']}"])
            lines.extend(f"- {chr(65 + opt_index)}. {option}" for opt_index, option in enumerate(question["options"]))
            lines.extend([f"\n**答案：{chr(65 + question['correct_answer'])}**", f"**解析：{question['explanation']}**", ""])
        return {
            "content": "\n".join(lines),
            "content_json": {"basic_questions": basic, "advanced_questions": advanced, "total_questions": len(questions)},
            **cls._provenance(knowledge),
        }

    @staticmethod
    def _difficulty(diagnosis: Dict[str, Any]) -> int:
        return max(1, min(5, int(diagnosis.get("recommended_difficulty", {}).get("recommended_difficulty", 3))))

    @staticmethod
    def _reference_text(knowledge: List[Dict[str, Any]]) -> str:
        entries = []
        for item in knowledge[:6]:
            content = str(item.get("content", "")).strip()[:2500]
            if content:
                entries.append(f"[{item.get('slice_id', 'unknown')}] {item.get('title', '知识片段')}: {content}")
        return "\n\n".join(entries) or "未检索到参考资料；请明确说明信息不足。"

    @staticmethod
    def _learner_summary(profile: Dict[str, Any], diagnosis: Dict[str, Any]) -> str:
        return json.dumps(
            {
                "learning_style": profile.get("learning_style", "visual"),
                "target_industry": profile.get("target_industry"),
                "blind_areas": [item.get("name") for item in diagnosis.get("knowledge_blind_areas", [])[:4]],
            },
            ensure_ascii=False,
        )

    @staticmethod
    def _provenance(knowledge: List[Dict[str, Any]]) -> Dict[str, List[Any]]:
        return {
            "source_slice_ids": [item["slice_id"] for item in knowledge if item.get("slice_id") is not None],
            "source_doc_ids": list({item["doc_id"] for item in knowledge if item.get("doc_id") is not None}),
        }
