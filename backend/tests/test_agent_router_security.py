"""Agent 路由安全回归测试：任务列表 IDOR / SSE 归属 / 聚合统计范围。"""
import uuid

from fastapi.testclient import TestClient

from app.models import (
    AgentTask,
    EducationLevelEnum,
    LearnerProfile,
    LearningStyleEnum,
    User,
    UserRoleEnum,
)
from app.utils.auth import create_access_token


# ========== 共享 helpers（Task 5/6 复用） ==========

def _auth_headers(user: User) -> dict:
    token = create_access_token({
        "user_id": user.id,
        "username": user.username,
        "role": user.role.value,
    })
    return {"Authorization": f"Bearer {token}"}


def _seed_user(db, role, enterprise_name=None) -> User:
    user = User(
        username=f"u_{role.value}_{uuid.uuid4().hex[:8]}",
        password_hash="not-a-real-hash",
        role=role,
        enterprise_name=enterprise_name,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _seed_learner(db, user) -> LearnerProfile:
    profile = LearnerProfile(
        user_id=user.id,
        real_name=f"学习者{user.id}",
        display_name=f"Learner{user.id}",
        education_level=EducationLevelEnum.BACHELOR.value,
        major="计算机",
        school="测试大学",
        graduation_year=2021,
        current_position="开发工程师",
        years_of_experience=2,
        learning_style=LearningStyleEnum.VISUAL.value,
        preferred_difficulty=3,
        daily_study_time=60,
        target_industry="人工智能",
        target_position="算法工程师",
        learning_goal="提升",
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def _seed_task(db, learner_id, name) -> AgentTask:
    task = AgentTask(
        task_name=name,
        task_type="learner_diagnosis",
        agent_type="diagnosis",
        status="completed",
        learner_id=learner_id,
        progress=100.0,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


# ========== Task 4: 任务列表 IDOR ==========

def test_task_list_without_learner_id_scopes_to_own_tasks(client, db_session):
    user_a = _seed_user(db_session, UserRoleEnum.LEARNER)
    user_b = _seed_user(db_session, UserRoleEnum.LEARNER)
    learner_a = _seed_learner(db_session, user_a)
    learner_b = _seed_learner(db_session, user_b)
    _seed_task(db_session, learner_a.id, "A的任务")
    _seed_task(db_session, learner_b.id, "B的任务")
    _seed_task(db_session, None, "无归属任务")

    response = client.get("/api/v1/agent/tasks", headers=_auth_headers(user_a))

    assert response.status_code == 200
    items = response.json()["data"]["items"]
    task_names = {item["task_name"] for item in items}
    # 旧代码：不传 learner_id 返回全部任务（含 B 与无归属）→ 失败
    assert task_names == {"A的任务"}


def test_task_list_with_foreign_learner_id_rejected(client, db_session):
    user_a = _seed_user(db_session, UserRoleEnum.LEARNER)
    user_b = _seed_user(db_session, UserRoleEnum.LEARNER)
    learner_b = _seed_learner(db_session, user_b)

    response = client.get(
        f"/api/v1/agent/tasks?learner_id={learner_b.id}",
        headers=_auth_headers(user_a),
    )

    assert response.status_code == 401
    assert response.json()["message"] == "无权限查看该学习者任务"


def test_task_list_admin_sees_all(client, db_session):
    admin = _seed_user(db_session, UserRoleEnum.ADMIN)
    user_a = _seed_user(db_session, UserRoleEnum.LEARNER)
    user_b = _seed_user(db_session, UserRoleEnum.LEARNER)
    learner_a = _seed_learner(db_session, user_a)
    learner_b = _seed_learner(db_session, user_b)
    _seed_task(db_session, learner_a.id, "A的任务")
    _seed_task(db_session, learner_b.id, "B的任务")
    _seed_task(db_session, None, "无归属任务")

    response = client.get("/api/v1/agent/tasks", headers=_auth_headers(admin))

    assert response.status_code == 200
    assert response.json()["data"]["total"] == 3


def test_task_list_enterprise_scoped_to_same_enterprise(client, db_session):
    ent_acme = _seed_user(db_session, UserRoleEnum.ENTERPRISE, enterprise_name="Acme")
    ent_beta = _seed_user(db_session, UserRoleEnum.ENTERPRISE, enterprise_name="Beta")
    member_acme = _seed_user(db_session, UserRoleEnum.LEARNER, enterprise_name="Acme")
    member_beta = _seed_user(db_session, UserRoleEnum.LEARNER, enterprise_name="Beta")
    learner_acme = _seed_learner(db_session, member_acme)
    learner_beta = _seed_learner(db_session, member_beta)
    _seed_task(db_session, learner_acme.id, "Acme任务")
    _seed_task(db_session, learner_beta.id, "Beta任务")

    response = client.get("/api/v1/agent/tasks", headers=_auth_headers(ent_acme))

    assert response.status_code == 200
    items = response.json()["data"]["items"]
    assert {item["task_name"] for item in items} == {"Acme任务"}

    # 跨企业显式指定 learner_id 同样拒绝
    response = client.get(
        f"/api/v1/agent/tasks?learner_id={learner_beta.id}",
        headers=_auth_headers(ent_acme),
    )
    assert response.status_code == 401
    # Beta 企业管理员可访问自己企业学习者的任务
    response = client.get(
        f"/api/v1/agent/tasks?learner_id={learner_beta.id}",
        headers=_auth_headers(ent_beta),
    )
    assert response.status_code == 200


# ========== Task 5: SSE 归属校验 ==========

def test_sse_stream_rejects_unowned_task_for_non_admin(client, db_session):
    user = _seed_user(db_session, UserRoleEnum.LEARNER)
    _seed_learner(db_session, user)
    orphan_task = _seed_task(db_session, None, "无归属任务")

    response = client.get(
        f"/api/v1/agent/tasks/{orphan_task.id}/events",
        headers=_auth_headers(user),
    )

    # 旧代码：learner_id 为 None 时跳过校验直接放流 → 失败
    assert response.status_code == 403
    assert response.json()["message"] == "无权限访问该任务"


def test_sse_stream_allows_owner(client, db_session):
    user = _seed_user(db_session, UserRoleEnum.LEARNER)
    learner = _seed_learner(db_session, user)
    task = _seed_task(db_session, learner.id, "本人任务")

    response = client.get(
        f"/api/v1/agent/tasks/{task.id}/events",
        headers=_auth_headers(user),
    )

    assert response.status_code == 200


def test_sse_stream_rejects_other_learners_task(client, db_session):
    user_a = _seed_user(db_session, UserRoleEnum.LEARNER)
    user_b = _seed_user(db_session, UserRoleEnum.LEARNER)
    learner_b = _seed_learner(db_session, user_b)
    task_b = _seed_task(db_session, learner_b.id, "B的任务")

    response = client.get(
        f"/api/v1/agent/tasks/{task_b.id}/events",
        headers=_auth_headers(user_a),
    )

    assert response.status_code == 403


# ========== Task 6: 聚合统计范围 ==========

def _diagnosis_entry(body):
    for agent in body["data"]["agents"]:
        if agent.get("agent_type") == "diagnosis":
            return agent
    return None


def test_agent_status_statistics_scoped_for_non_admin(client, db_session):
    user_a = _seed_user(db_session, UserRoleEnum.LEARNER)
    user_b = _seed_user(db_session, UserRoleEnum.LEARNER)
    learner_a = _seed_learner(db_session, user_a)
    learner_b = _seed_learner(db_session, user_b)
    _seed_task(db_session, learner_a.id, "A的诊断")
    _seed_task(db_session, learner_b.id, "B的诊断")

    response = client.get("/api/v1/agent/status", headers=_auth_headers(user_a))

    assert response.status_code == 200
    entry = _diagnosis_entry(response.json())
    # 旧代码：统计全量（2）→ 失败
    assert entry["total_tasks_handled"] == 1


def test_agent_status_statistics_full_for_admin(client, db_session):
    admin = _seed_user(db_session, UserRoleEnum.ADMIN)
    user_a = _seed_user(db_session, UserRoleEnum.LEARNER)
    user_b = _seed_user(db_session, UserRoleEnum.LEARNER)
    learner_a = _seed_learner(db_session, user_a)
    learner_b = _seed_learner(db_session, user_b)
    _seed_task(db_session, learner_a.id, "A的诊断")
    _seed_task(db_session, learner_b.id, "B的诊断")

    response = client.get("/api/v1/agent/status", headers=_auth_headers(admin))

    assert response.status_code == 200
    entry = _diagnosis_entry(response.json())
    assert entry["total_tasks_handled"] == 2


def test_single_agent_status_scoped_for_non_admin(client, db_session):
    user_a = _seed_user(db_session, UserRoleEnum.LEARNER)
    user_b = _seed_user(db_session, UserRoleEnum.LEARNER)
    learner_a = _seed_learner(db_session, user_a)
    learner_b = _seed_learner(db_session, user_b)
    _seed_task(db_session, learner_a.id, "A的诊断")
    _seed_task(db_session, learner_b.id, "B的诊断")

    response = client.get(
        "/api/v1/agent/status/diagnosis",
        headers=_auth_headers(user_a),
    )

    assert response.status_code == 200
    assert response.json()["data"]["total_tasks_handled"] == 1
