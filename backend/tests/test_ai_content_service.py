import json

from app.services.ai_content_service import AIContentService
from app.utils.llm import LLMUtil


def test_tutoring_feedback_uses_structured_provider_response(monkeypatch):
    monkeypatch.setattr(LLMUtil, "is_available", classmethod(lambda cls: True))

    def fake_call(cls, template_name, variables=None, temperature=None, model=None, use_cache=True):
        assert template_name == "tutoring_feedback"
        assert variables["knowledge_topic"] == "反向传播算法"
        return json.dumps({
            "type": "simplify",
            "title": "反向传播算法 - 错题讲解",
            "simple_explanation": "先从输出误差沿网络反向计算梯度。",
            "key_points": ["链式法则", "梯度传播"],
            "practice_tips": "先完成一题基础梯度计算题。",
            "recommendation": "复习链式法则后再练习。",
            "challenge_description": "",
            "challenge_objectives": [],
        }, ensure_ascii=False), {}

    monkeypatch.setattr(LLMUtil, "call_with_prompt_template", classmethod(fake_call))

    result = AIContentService.generate(
        "tutoring_feedback",
        {
            "decision": "simplify",
            "topic": "反向传播算法",
            "question": "梯度如何传播？",
            "user_answer": "B",
            "correct_answer": "A",
            "difficulty": 3,
        },
    )

    assert result["generation_method"] == "deepseek"
    assert result["recommendation"] == "复习链式法则后再练习。"
    assert result["key_points"] == ["链式法则", "梯度传播"]


def test_tutoring_feedback_requires_available_provider(monkeypatch):
    monkeypatch.setattr(LLMUtil, "is_available", classmethod(lambda cls: False))

    try:
        AIContentService.generate("tutoring_feedback", {"topic": "测试"})
    except ValueError as exc:
        assert "unavailable" in str(exc)
    else:
        raise AssertionError("unavailable provider should fail the AI contract")
