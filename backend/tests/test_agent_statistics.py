"""Per-agent statistics derived from durable task stage logs."""

from types import SimpleNamespace

from app.domains.agent.router import _calculate_agent_statistics


def _task(status, logs, task_type="full_pipeline", duration_ms=None):
    return SimpleNamespace(
        status=status,
        execution_logs=logs,
        task_type=task_type,
        duration_ms=duration_ms,
    )


def test_completed_pipeline_counts_each_agent_and_uses_its_stage_latency():
    stats = _calculate_agent_statistics([
        _task("completed", [
            {"stage": "diagnosis"},
            {"stage": "knowledge_retrieval", "previous_stage_duration_ms": 1000},
            {"stage": "generation", "previous_stage_duration_ms": 200},
            {"stage": "judge_first", "previous_stage_duration_ms": 3000},
            {"stage": "debate", "previous_stage_duration_ms": 400},
            {"stage": "final_revision", "previous_stage_duration_ms": 500},
            {"stage": "complete", "previous_stage_duration_ms": 600},
        ]),
    ])

    assert stats["diagnosis"] == {
        "total_tasks_handled": 1,
        "success_count": 1,
        "failure_count": 0,
        "avg_latency_ms": 1000.0,
    }
    assert stats["generation"]["avg_latency_ms"] == 3000.0
    assert stats["judge"]["avg_latency_ms"] == 1500.0


def test_failed_pipeline_attributes_failure_to_the_last_active_agent():
    stats = _calculate_agent_statistics([
        _task("failed", [
            {"stage": "diagnosis"},
            {"stage": "knowledge_retrieval", "previous_stage_duration_ms": 800},
            {"stage": "generation", "previous_stage_duration_ms": 100},
            {"stage": "failed"},
        ]),
    ])

    assert stats["diagnosis"]["success_count"] == 1
    assert stats["knowledge"]["success_count"] == 1
    assert stats["generation"]["failure_count"] == 1
