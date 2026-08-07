"""Focused tests for strict LLM parsing and deterministic fallback behavior."""
import json
import httpx
import pytest

from app.agents.diagnosis_agent import DiagnosisAgent
from app.agents.generation_agent import GenerationAgent
from app.agents.llm_generator import LLMGenerator
from app.services.llm_question_generator import LLMQuestionGenerator
from app.utils import llm_response
from app.utils.llm import LLMUtil
from app.utils.llm_response import LLMResponseError, parse_json_object
from app.config import settings


def test_deepseek_request_disables_thinking_mode_by_default(monkeypatch):
    captured = {}

    class FakeClient:
        def post(self, url, json):
            captured["url"] = url
            captured["payload"] = json
            return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(settings, "OPENAI_THINKING_ENABLED", False)
    monkeypatch.setattr(LLMUtil, "_get_sync_client", classmethod(lambda cls: FakeClient()))

    LLMUtil._call_api([{"role": "user", "content": "hello"}], temperature=0)

    assert captured["url"].endswith("/chat/completions")
    assert captured["payload"]["thinking"] == {"type": "disabled"}


def test_empty_final_content_is_rejected():
    response = httpx.Response(
        200,
        json={
            "choices": [
                {"message": {"content": "", "reasoning_content": "internal reasoning"}}
            ]
        },
    )

    with pytest.raises(ValueError, match="final content"):
        LLMUtil._parse_response(response)


def test_parse_json_object_accepts_fenced_json():
    assert parse_json_object("```json\n{\"ok\": true}\n```") == {"ok": True}


def test_parse_json_object_rejects_non_object():
    with pytest.raises(LLMResponseError):
        parse_json_object("[]")


def test_generation_falls_back_without_api_key(monkeypatch):
    monkeypatch.setattr(LLMUtil, "is_available", classmethod(lambda cls: False))
    topic = "反向传播算法"
    result = GenerationAgent().execute({
        "resource_type": "exercise",
        "target_topic": topic,
        "diagnosis_result": {"recommended_difficulty": {"recommended_difficulty": 3}},
        "knowledge_results": [],
        "learner_profile": {},
    })
    assert result["generation_method"] == "deterministic_fallback"
    assert result["content_json"]["total_questions"] == 10
    assert "反向传播算法主要解决什么问题" in result["content"]
    assert "计算损失函数对各层参数的梯度" in result["content"]
    assert "选项A" not in result["content"]
    assert "干扰项" not in result["content"]
    assert "basic题" not in result["content"]
    assert "advanced题" not in result["content"]


def test_generation_guide_and_lecture_are_richer(monkeypatch):
    monkeypatch.setattr(LLMUtil, "is_available", classmethod(lambda cls: False))
    knowledge = [
        {"slice_id": 1, "doc_id": 1, "title": "概念", "content": "第一段知识用于建立概念边界和输入输出。"},
        {"slice_id": 2, "doc_id": 2, "title": "步骤", "content": "第二段知识用于拆解操作步骤和检查方式。"},
        {"slice_id": 3, "doc_id": 3, "title": "误区", "content": "第三段知识用于说明常见误区和修正方法。"},
        {"slice_id": 4, "doc_id": 4, "title": "练习", "content": "第四段知识用于设计变式练习和复盘任务。"},
    ]

    guide = GenerationAgent().execute({
        "resource_type": "guide",
        "target_topic": "资源生成",
        "diagnosis_result": {"recommended_difficulty": {"recommended_difficulty": 3}},
        "knowledge_results": knowledge,
        "learner_profile": {"learning_style": "visual"},
    })
    lecture = GenerationAgent().execute({
        "resource_type": "lecture",
        "target_topic": "资源生成",
        "diagnosis_result": {"recommended_difficulty": {"recommended_difficulty": 3}, "knowledge_blind_areas": [{"name": "步骤迁移", "severity": "中"}]},
        "knowledge_results": knowledge,
        "learner_profile": {"learning_style": "visual"},
    })

    assert len(guide["content"]) > 500
    assert "本节看点" in guide["content"]
    assert "适用场景" in guide["content"]
    assert "检查点" in guide["content"]
    assert len(lecture["content"]) > 500
    assert "这一节解决什么" in lecture["content"]
    assert "如何应用" in lecture["content"]
    assert "常见误区" in lecture["content"]
    assert "自测标准" in lecture["content"]


def test_generation_steps_vary_by_chapter():
    agent = GenerationAgent()
    steps_one = agent._generate_steps("资源生成", "概念框架", "第一段内容", 3, 0)
    steps_two = agent._generate_steps("资源生成", "实践步骤", "第二段内容", 3, 1)

    assert len(steps_one) >= 3
    assert len(steps_two) >= 3
    assert steps_one != steps_two


def test_generation_rejects_llm_placeholder_questions(monkeypatch):
    monkeypatch.setattr(LLMUtil, "is_available", classmethod(lambda cls: True))

    def fake_call(cls, template_name, variables=None, temperature=None, model=None, use_cache=True):
        return (
            json.dumps({"questions": [{
                "question": "关于深度学习的第1道basic题",
                "options": ["选项A（正确答案）", "选项B（干扰项）", "选项C（干扰项）", "选项D（干扰项）"],
                "correct_answer": 0,
                "difficulty_level": 1,
                "explanation": "这是一段足够长的模板解析文本",
                "knowledge_points": ["深度学习"],
            }]}, ensure_ascii=False),
            {},
        )

    monkeypatch.setattr(LLMUtil, "call_with_prompt_template", classmethod(fake_call))
    result = GenerationAgent().execute({
        "resource_type": "exercise",
        "target_topic": "反向传播算法",
        "diagnosis_result": {"recommended_difficulty": {"recommended_difficulty": 3}},
        "knowledge_results": [{"slice_id": 1, "doc_id": 1, "title": "基础", "content": "反向传播使用链式法则计算梯度。"}],
        "learner_profile": {},
    })
    assert result["generation_method"] == "deterministic_fallback"
    assert result["content_json"]["total_questions"] == 10
    assert "反向传播算法主要解决什么问题" in result["content"]
    assert "选项A" not in result["content"]
    assert "干扰项" not in result["content"]
    assert "basic题" not in result["content"]


def test_diagnosis_preserves_rule_scores_without_api_key(monkeypatch):
    monkeypatch.setattr(LLMUtil, "is_available", classmethod(lambda cls: False))
    result = DiagnosisAgent().execute({"learner_profile": {"theoretical_foundation": 80}})
    assert result["ability_scores"]["theoretical_foundation"] == 80
    assert result["diagnosis_method"] == "deterministic_fallback"


def test_llm_question_generation_allows_ten_questions(monkeypatch):
    captured = {}
    monkeypatch.setattr(LLMUtil, "is_available", classmethod(lambda cls: True))

    def fake_call(cls, template_name, variables=None, temperature=None, model=None, use_cache=True):
        captured["template_name"] = template_name
        captured["question_count"] = variables["question_count"]
        captured["multiple_choice_count"] = variables["multiple_choice_count"]
        captured["difficulty_standard"] = variables["difficulty_standard"]
        questions = []
        for index in range(10):
            is_multiple = index in {2, 5, 8}
            questions.append({
                "type": "multiple" if is_multiple else "single",
                "question": f"Question {index + 1}",
                "options": ["Option A", "Option B", "Option C", "Option D"],
                "correct_answers": ["A", "C"] if is_multiple else ["A"],
                "difficulty_level": 2 if index < 5 else 4,
                "explanation": "Detailed explanation",
                "knowledge_points": ["knowledge point"],
            })
        return json.dumps({"questions": questions}, ensure_ascii=False), {}

    monkeypatch.setattr(LLMUtil, "call_with_prompt_template", classmethod(fake_call))

    result = LLMQuestionGenerator.generate_question_set(
        topic="topic",
        difficulty=3,
        count=10,
        knowledge=[{"slice_id": 1, "doc_id": 1, "title": "base", "content": "content"}],
    )

    assert captured["template_name"] == "question_generation"
    assert captured["question_count"] == 10
    assert captured["multiple_choice_count"] == 3
    assert "综合应用" in captured["difficulty_standard"]
    assert len(result) == 10
    assert sum(question["type"] == "multiple" for question in result) == 3
    assert result[2]["correctIndex"] == [0, 2]
    assert result[0]["generation_method"] == "deepseek"


def test_llm_exercise_generation_uses_variation_and_no_cache(monkeypatch):
    captured = {}

    def fake_call(cls, template_name, variables=None, temperature=None, model=None, use_cache=True):
        captured["temperature"] = temperature
        captured["use_cache"] = use_cache
        captured["variation_seed"] = variables["variation_seed"]
        captured["variation_hint"] = variables["variation_hint"]
        questions = [{
            "question": "What does backpropagation compute?",
            "options": ["Gradients", "File paths", "Window sizes", "CSS colors"],
            "correct_answer": 0,
            "difficulty_level": 2,
            "explanation": "Backpropagation computes gradients for model parameters.",
            "knowledge_points": ["backpropagation"],
        }]
        return json.dumps({"questions": questions}, ensure_ascii=False), {}

    monkeypatch.setattr(LLMUtil, "call_with_prompt_template", classmethod(fake_call))
    LLMGenerator.generate_exercises(
        {"recommended_difficulty": {"recommended_difficulty": 3}},
        [{"slice_id": 1, "doc_id": 1, "title": "base", "content": "Backpropagation computes gradients."}],
        {},
        "backpropagation",
        variation_seed="seed-42",
    )

    assert captured["temperature"] == 0.7
    assert captured["use_cache"] is False
    assert captured["variation_seed"] == "seed-42"
    assert captured["variation_hint"]


def test_generation_agent_passes_unique_variation_seed(monkeypatch):
    monkeypatch.setattr(LLMUtil, "is_available", classmethod(lambda cls: True))

    captured = {"guide": [], "exercise": [], "lecture": []}

    def fake_guide(cls, diagnosis, knowledge, profile, topic, variation_seed=None):
        captured["guide"].append(variation_seed)
        return {
            "content": "guide content",
            "resource_title": "guide",
            "difficulty_level": 3,
            "content_json": {},
            "source_slice_ids": [1],
            "source_doc_ids": [1],
        }

    def fake_exercises(cls, diagnosis, knowledge, profile, topic, question_count=None, variation_seed=None):
        captured["exercise"].append(variation_seed)
        return {
            "content": "exercise content",
            "resource_title": "exercise",
            "difficulty_level": 3,
            "content_json": {},
            "source_slice_ids": [1],
            "source_doc_ids": [1],
        }

    def fake_lecture(cls, diagnosis, knowledge, profile, topic, variation_seed=None):
        captured["lecture"].append(variation_seed)
        return {
            "content": "lecture content",
            "resource_title": "lecture",
            "difficulty_level": 3,
            "content_json": {},
            "source_slice_ids": [1],
            "source_doc_ids": [1],
        }

    monkeypatch.setattr(LLMGenerator, "generate_guide", classmethod(fake_guide))
    monkeypatch.setattr(LLMGenerator, "generate_exercises", classmethod(fake_exercises))
    monkeypatch.setattr(LLMGenerator, "generate_lecture", classmethod(fake_lecture))

    agent = GenerationAgent()
    base_input = {
        "diagnosis_result": {"recommended_difficulty": {"recommended_difficulty": 3}},
        "knowledge_results": [{"slice_id": 1, "doc_id": 1, "title": "base", "content": "content"}],
        "learner_profile": {},
        "target_topic": "topic",
    }

    for resource_type in ("guide", "exercise", "lecture"):
        agent.execute({**base_input, "resource_type": resource_type})

    assert all(captured[name] and captured[name][0] for name in captured)
    assert len({captured["guide"][0], captured["exercise"][0], captured["lecture"][0]}) == 3
