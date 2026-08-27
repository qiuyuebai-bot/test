"""Regression tests for fresh resource generation."""

from app.agents.orchestrator import AgentOrchestrator


def test_full_pipeline_does_not_reuse_existing_exercise_resource(monkeypatch):
    orch = AgentOrchestrator()
    saved_resources = []

    def fail_if_reuse_called(*args, **kwargs):
        raise AssertionError("resource generation should not reuse existing resources")

    monkeypatch.setattr(orch.task_repo, "find_reusable_resource", fail_if_reuse_called)
    monkeypatch.setattr(orch.task_repo, "update_stage", lambda *args, **kwargs: None)
    monkeypatch.setattr(orch.task_repo, "update_output_data", lambda *args, **kwargs: None)
    monkeypatch.setattr(orch.task_repo, "save_metrics", lambda *args, **kwargs: None)
    monkeypatch.setattr(orch.event_bus, "broadcast", lambda *args, **kwargs: None)
    monkeypatch.setattr(orch, "_schedule_cache_cleanup", lambda *args, **kwargs: None)

    monkeypatch.setattr(
        orch,
        "_run_diagnosis",
        lambda *args, **kwargs: {"recommended_difficulty": {"recommended_difficulty": 3}},
    )
    monkeypatch.setattr(orch, "_retrieve_knowledge", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        orch,
        "_run_generation",
        lambda *args, **kwargs: {
            "resource_type": "exercise",
            "resource_title": "fresh exercise",
            "difficulty_level": 3,
            "content": "fresh exercise content",
            "content_json": {},
            "word_count": 22,
            "source_slice_ids": [],
            "source_doc_ids": [],
            "generation_method": "llm",
        },
    )
    monkeypatch.setattr(
        orch,
        "_run_audit",
        lambda *args, **kwargs: {
            "passed": True,
            "overall_score": 90,
            "hallucination_detected": False,
            "_meta": {},
        },
    )
    monkeypatch.setattr(orch, "_run_debate_process", lambda *args, **kwargs: ([], "fresh exercise content"))
    def save_one_resource(*args, **kwargs):
        saved_resources.append((args, kwargs))
        return {
            "task_id": 101,
            "resource_id": 202,
            "generation_result": {"word_count": 22},
            "final_score": 90,
            "passed": True,
        }

    monkeypatch.setattr(orch.task_repo, "save_resource_and_complete", save_one_resource)

    result = orch.run_full_pipeline(
        task_id=101,
        learner_id=1,
        target_topic="backpropagation",
        resource_type="exercise",
    )

    assert result["resource_id"] == 202
    assert len(saved_resources) == 1
