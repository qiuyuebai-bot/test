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

    PLACEHOLDER_MARKERS = (
        "选项A",
        "正确答案",
        "干扰项",
        "basic题",
        "advanced题",
        "第1道basic",
        "第1道advanced",
    )

    @classmethod
    def generate_guide(
        cls,
        diagnosis: Dict[str, Any],
        knowledge: List[Dict[str, Any]],
        profile: Dict[str, Any],
        topic: str,
        variation_seed: str | int | None = None,
    ) -> Dict[str, Any]:
        return cls._generate_resource(
            "guide", diagnosis, knowledge, profile, topic, variation_seed=variation_seed
        )

    @classmethod
    def generate_lecture(
        cls,
        diagnosis: Dict[str, Any],
        knowledge: List[Dict[str, Any]],
        profile: Dict[str, Any],
        topic: str,
        variation_seed: str | int | None = None,
    ) -> Dict[str, Any]:
        return cls._generate_resource(
            "lecture", diagnosis, knowledge, profile, topic, variation_seed=variation_seed
        )

    @classmethod
    def generate_exercises(
        cls,
        diagnosis: Dict[str, Any],
        knowledge: List[Dict[str, Any]],
        profile: Dict[str, Any],
        topic: str,
        question_count: int | None = None,
        variation_seed: str | int | None = None,
    ) -> Dict[str, Any]:
        difficulty = cls._difficulty(diagnosis)
        question_count = max(1, min(10, question_count or 10))
        response, _ = LLMUtil.call_with_prompt_template(
            "question_generation",
            {
                "knowledge_topic": topic,
                "difficulty_level": difficulty,
                "question_count": question_count,
                "reference_knowledge": cls._reference_text(knowledge),
                "variation_seed": variation_seed or "",
                "variation_hint": cls._variation_hint("exercise", variation_seed),
            },
            temperature=0.7,
            use_cache=False,
        )
        payload = parse_json_object(response)
        if payload.get("_meta", {}).get("model") == "mock":
            raise LLMResponseError("LLM returned fallback mock response")
        questions = [cls._normalize_question(item) for item in bounded_list(payload.get("questions"), "questions", minimum=1, maximum=10)]
        return cls._exercise_result(topic, questions, knowledge)

    @classmethod
    def _generate_resource(
        cls,
        resource_type: str,
        diagnosis: Dict[str, Any],
        knowledge: List[Dict[str, Any]],
        profile: Dict[str, Any],
        topic: str,
        variation_seed: str | int | None = None,
    ) -> Dict[str, Any]:
        difficulty = cls._difficulty(diagnosis)
        response, _ = LLMUtil.call_with_prompt_template(
            "resource_generation",
            {
                "learner_summary": cls._learner_summary(profile, diagnosis),
                "knowledge_topic": topic,
                "difficulty_level": difficulty,
                "resource_type": resource_type,
                "reference_knowledge": cls._reference_text(knowledge),
                "variation_seed": variation_seed or "",
                "variation_hint": cls._variation_hint(resource_type, variation_seed),
            },
            temperature=0.7,
            use_cache=False,
        )
        payload = parse_json_object(response)
        if payload.get("_meta", {}).get("model") == "mock":
            raise LLMResponseError("LLM returned fallback mock response")
        content = bounded_text(payload.get("content") or "", "content", minimum=100, maximum=16000)
        title = bounded_text(payload.get("resource_title") or f"{topic} {resource_type}", "resource_title", maximum=200)
        actual_difficulty = bounded_int(payload.get("difficulty_level", difficulty), "difficulty_level", minimum=1, maximum=5)
        # 容错：LLM 可能返回 null / 空数组 / 非数组，兜底为 [topic]
        raw_topics = payload.get("topics")
        if not isinstance(raw_topics, list) or len(raw_topics) == 0:
            raw_topics = [topic]
        topics = [bounded_text(item, "topic", maximum=100) for item in bounded_list(raw_topics, "topics", minimum=1, maximum=8)]
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

    @classmethod
    def _normalize_question(cls, item: Any) -> Dict[str, Any]:
        if not isinstance(item, dict):
            raise LLMResponseError("question must be an object")
        question = bounded_text(item.get("question"), "question", minimum=5, maximum=2000)
        options = [bounded_text(option, "option", maximum=500) for option in bounded_list(item.get("options"), "options", minimum=2, maximum=6)]
        explanation = bounded_text(item.get("explanation"), "explanation", minimum=5, maximum=3000)
        knowledge_points = [
            bounded_text(point, "knowledge_point", maximum=120)
            for point in bounded_list(item.get("knowledge_points", []), "knowledge_points", maximum=8)
        ]
        cls._reject_placeholder_question(question, options, explanation, knowledge_points)
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
            "question": question,
            "options": options,
            "correct_answer": answer_index,
            "difficulty": bounded_int(item.get("difficulty_level", item.get("difficulty", 3)), "difficulty", minimum=1, maximum=5),
            "explanation": explanation,
            "knowledge_points": knowledge_points,
        }

    @classmethod
    def _reject_placeholder_question(
        cls,
        question: str,
        options: List[str],
        explanation: str,
        knowledge_points: List[str],
    ) -> None:
        combined = "\n".join([question, explanation, *options, *knowledge_points])
        if any(marker in combined for marker in cls.PLACEHOLDER_MARKERS):
            raise LLMResponseError("question contains placeholder text")

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
        if entries:
            return "\n\n".join(entries)
        return (
            "（知识库中暂无相关参考资料，请基于你的训练知识生成高质量、专业的内容。"
            "内容应覆盖该领域核心概念、实操方法和常见问题，确保学习资源有实质价值。"
            "不要使用占位文字或模糊表述，要给出具体的知识点和可操作的指导。）"
        )

    @classmethod
    def _variation_hint(cls, resource_type: str, variation_seed: str | int | None) -> str:
        guide_hints = [
            "从流程拆解切入，重点给出步骤、检查点和复盘动作。",
            "从常见错误切入，重点给出误区、修正路径和实操提示。",
            "从案例驱动切入，先给场景例子，再抽象通用方法。",
            "从任务清单切入，强调执行顺序、验收标准和补充建议。",
        ]
        lecture_hints = [
            "从概念总览切入，先搭框架，再展开关键知识点。",
            "从原理推导切入，先讲机制，再讲应用边界。",
            "从对比辨析切入，先区分相近概念，再说明选择条件。",
            "从应用落地切入，先讲场景，再给实践路径和常见误区。",
        ]
        exercise_hints = [
            "题目覆盖基础概念、步骤理解、错误排查、综合应用，选项顺序随机。",
            "题目以场景判断为主，减少定义背诵，增加解释和反例辨析。",
            "题目从易到难排列，后半部分加入迁移应用和边界条件。",
            "题目围绕常见误区设计干扰项，解析说明每个关键判断依据。",
        ]
        hints = {
            "guide": guide_hints,
            "lecture": lecture_hints,
            "exercise": exercise_hints,
        }.get(resource_type, guide_hints)
        return hints[cls._variation_index(variation_seed, len(hints))]

    @staticmethod
    def _variation_index(variation_seed: str | int | None, size: int) -> int:
        if size <= 0:
            return 0
        seed = str(variation_seed or "")
        if not seed:
            return 0
        try:
            return abs(int(seed)) % size
        except ValueError:
            total = sum(ord(ch) for ch in seed)
            return total % size

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
