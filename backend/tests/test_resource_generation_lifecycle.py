"""Regression coverage for durable, de-duplicated resource generation."""

from app.models import AgentTask


def test_repeated_full_pipeline_requests_reuse_the_same_active_task(
    client,
    db_session,
    sample_learner_profile,
    auth_headers,
    monkeypatch,
):
    import app.domains.agent.router as agent_router

    scheduled = []

    class DeferredThread:
        def __init__(self, *, target, **_kwargs):
            scheduled.append(target)

        def start(self):
            return None

    # Do not execute the real LLM pipeline; the test only verifies the
    # transactional task claim and the returned task identity.
    monkeypatch.setattr(
        agent_router,
        "threading",
        type("ThreadingStub", (), {"Thread": DeferredThread}),
    )
    payload = {
        "learner_id": sample_learner_profile.id,
        "target_topic": "算法设计",
        "resource_type": "guide",
    }

    first = client.post("/api/v1/agent/run/full-pipeline", headers=auth_headers, json=payload)
    second = client.post("/api/v1/agent/run/full-pipeline", headers=auth_headers, json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    first_data = first.json()["data"]
    second_data = second.json()["data"]
    assert second_data["task_id"] == first_data["task_id"]
    assert second_data["reused"] is True
    assert len(scheduled) == 1

    tasks = db_session.query(AgentTask).filter(
        AgentTask.learner_id == sample_learner_profile.id,
        AgentTask.task_type == "full_pipeline",
    ).all()
    assert len(tasks) == 1
    assert tasks[0].status == "running"
