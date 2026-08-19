"""Regression tests for explicit agent-to-agent communication contracts."""

from contextlib import contextmanager

from app.agents.generation_agent import GenerationAgent
from app.agents.judge_agent import JudgeAgent
from app.agents.knowledge_agent import KnowledgeAgent
from app.agents import knowledge_agent as knowledge_agent_module
from app.agents import llm_debater as llm_debater_module
from app.services.ai_content_service import AIContentService
from app.utils.hallucination import HallucinationUtil
from app.utils.llm import LLMUtil


def test_generation_agent_does_not_fabricate_a_review_when_llm_is_unavailable(monkeypatch):
    monkeypatch.setattr(LLMUtil, "_available", False)

    result = GenerationAgent().respond_to_review(
        "机器人坐标系说明", [], {"issues": [{"type": "grounding"}]}
    )

    assert result["status"] == "unavailable"
    assert result["method"] == "unavailable"
    assert result["requires_human_review"] is True
    assert result["accepts"] is None


def test_judge_marks_deterministic_review_as_human_review(monkeypatch):
    monkeypatch.setattr(LLMUtil, "_available", False)

    result = JudgeAgent().debate_with_generation(
        "机器人坐标系说明", [], max_rounds=1
    )

    assert result["debate_method"] == "deterministic_review"
    assert result["agent_response_status"] == "unavailable"
    assert result["requires_human_review"] is True
    assert result["generation_counterargument"]["response"]


def test_llm_debate_uses_separate_generation_and_judge_turns(monkeypatch):
    monkeypatch.setattr(LLMUtil, "_available", True)

    def fake_generation_call(cls, template_name, variables=None, **kwargs):
        assert template_name == "generation_review"
        return (
            '{"stance":"defend","accepts":false,"response":"依据TCP资料保留该表述。",'
            '"revisions_made":1,"disputed_issues":["单位需要复核"],"evidence_citations":["slice-1"]}',
            None,
        )

    monkeypatch.setattr(AIContentService, "call_with_prompt_template", classmethod(fake_generation_call))
    generation_response = GenerationAgent().respond_to_review(
        "TCP 校准说明",
        [{"title": "TCP", "content": "TCP 校准", "similarity": 0.9}],
        {"issues": []},
    )

    def fake_judge_round(cls, *args, **kwargs):
        assert args[3]["stance"] == "defend"
        return {
            "judge_rebuttal": "单位需要补充。",
            "final_decision": "needs_revision",
            "issues": [],
            "confidence": 0.8,
        }

    monkeypatch.setattr(llm_debater_module.LLMDebater, "run_judge_round", classmethod(fake_judge_round))
    result = JudgeAgent().debate_with_generation(
        "TCP 校准说明",
        [{"title": "TCP", "content": "TCP 校准", "similarity": 0.9}],
        generation_response=generation_response,
    )

    assert result["debate_method"] == "llm_dual_agent"
    assert result["generation_counterargument"]["stance"] == "defend"
    assert result["agent_response_status"] == "available"


def test_knowledge_agent_returns_retrieval_evidence_metadata(monkeypatch):
    @contextmanager
    def fake_context():
        yield object()

    monkeypatch.setattr(knowledge_agent_module.database, "get_db_context", fake_context)
    monkeypatch.setattr(
        knowledge_agent_module.KnowledgeService,
        "search",
        staticmethod(lambda **kwargs: [{"title": "TCP", "content": "TCP 校准", "similarity": 0.81}]),
    )

    result = KnowledgeAgent().run(
        1, {"query": "工具坐标 TCP", "top_k": 4}
    )

    assert result["_meta"]["success"] is True
    assert result["evidence_status"] == "sufficient"
    assert result["result_count"] == 1
    assert result["knowledge_results"] == result["results"]


def test_industrial_robotics_rules_detect_coordinate_maintenance_confusion():
    detected, info = HallucinationUtil.detect_hallucination(
        "机器人坐标系需要进行 TCP 校准。",
        reference_knowledge=[{
            "title": "维护手册",
            "content": "减速机保养和润滑周期。",
            "similarity": 0.82,
        }],
    )

    assert detected is True
    assert any(
        issue["type"] == "industry_topic_confusion"
        for issue in info["industry_rules"]["issues"]
    )
