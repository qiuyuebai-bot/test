"""Focused tests for strict LLM parsing and deterministic fallback behavior."""
import pytest

from app.agents.diagnosis_agent import DiagnosisAgent
from app.agents.generation_agent import GenerationAgent
from app.utils import llm_response
from app.utils.llm import LLMUtil
from app.utils.llm_response import LLMResponseError, parse_json_object


def test_parse_json_object_accepts_fenced_json():
    assert parse_json_object("```json\n{\"ok\": true}\n```") == {"ok": True}


def test_parse_json_object_rejects_non_object():
    with pytest.raises(LLMResponseError):
        parse_json_object("[]")


def test_generation_falls_back_without_api_key(monkeypatch):
    monkeypatch.setattr(LLMUtil, "is_available", classmethod(lambda cls: False))
    result = GenerationAgent().execute({
        "resource_type": "exercise",
        "target_topic": "机器学习",
        "diagnosis_result": {"recommended_difficulty": {"recommended_difficulty": 3}},
        "knowledge_results": [{"slice_id": 1, "doc_id": 1, "title": "基础", "content": "机器学习基础知识"}],
        "learner_profile": {},
    })
    assert result["generation_method"] == "deterministic_fallback"
    assert "选项A（正确答案）" in result["content"]


def test_diagnosis_preserves_rule_scores_without_api_key(monkeypatch):
    monkeypatch.setattr(LLMUtil, "is_available", classmethod(lambda cls: False))
    result = DiagnosisAgent().execute({"learner_profile": {"theoretical_foundation": 80}})
    assert result["ability_scores"]["theoretical_foundation"] == 80
    assert result["diagnosis_method"] == "deterministic_fallback"
