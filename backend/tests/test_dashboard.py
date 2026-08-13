"""角色自适应 Dashboard API 与引导状态测试。"""

from app.models import User, UserRoleEnum
from app.utils.auth import create_access_token


def _headers(user: User) -> dict[str, str]:
    token = create_access_token(
        {
            "user_id": user.id,
            "username": user.username,
            "role": user.role.value if hasattr(user.role, "value") else user.role,
        }
    )
    return {"Authorization": f"Bearer {token}"}


def test_learner_dashboard_is_scoped_to_current_user(
    client,
    sample_user,
    sample_learner_profile,
    sample_learning_resource,
    sample_agent_task,
    auth_headers,
):
    response = client.get("/api/v1/dashboard/learner", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["profile"]["id"] == sample_learner_profile.id
    assert data["profile"]["user_id"] == sample_user.id
    assert "learners" not in data
    assert all(task["learner_id"] == sample_learner_profile.id for task in data["current_tasks"])
    assert data["recent_resources"][0]["id"] == sample_learning_resource.id
    assert data["guidance"]["stage"] == "diagnosis"
    assert sample_agent_task.learner_id == sample_learner_profile.id


def test_learner_dashboard_rejects_non_learner_roles(
    client,
    sample_admin_user,
    admin_auth_headers,
):
    response = client.get("/api/v1/dashboard/learner", headers=admin_auth_headers)

    assert response.status_code == 403
    assert response.json()["code"] == 403


def test_teacher_dashboard_returns_scoped_summary(
    client,
    db_session,
    sample_learner_profile,
):
    teacher = User(
        username="dashboard_teacher",
        password_hash="hash",
        role=UserRoleEnum.TEACHER,
        is_active=True,
    )
    db_session.add(teacher)
    db_session.commit()
    db_session.refresh(teacher)

    response = client.get("/api/v1/dashboard/teacher", headers=_headers(teacher))

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["scope"]["type"] == "teacher_learner_list"
    assert data["summary"]["total_learners"] >= 1
    assert any(item["id"] == sample_learner_profile.id for item in data["learners"])


def test_learner_guidance_state_persists_across_dashboard_reads(
    client,
    auth_headers,
):
    update = client.patch(
        "/api/v1/dashboard/learner/guidance",
        json={"action": "snooze"},
        headers=auth_headers,
    )
    assert update.status_code == 200
    assert update.json()["data"]["dashboard_guidance_dismissed_at"]

    dashboard = client.get("/api/v1/dashboard/learner", headers=auth_headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["data"]["guidance"]["dashboard_guidance_dismissed_at"]
