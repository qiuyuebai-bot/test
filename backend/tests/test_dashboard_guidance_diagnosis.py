"""仪表盘引导阶段的诊断完成信号测试。

向导的六维能力诊断走 DiagnosticSession 答题路径，不产生 AgentTask；
dashboard 只认 AgentTask 会把完成答题诊断的学习者永远卡在
"开始首次诊断"（回归见 2026-08-29 用户报告：答了两套题仍在首建画像阶段）。
"""
from datetime import datetime

from app.models import DiagnosticSession, UserRoleEnum, User
from app.utils.auth import create_access_token


def _create_independent_learner(db_session, diagnostic_status="not_started"):
    """创建独立学习者（避开共享 fixture 的诊断状态），确保互不污染。"""
    import uuid

    unique = uuid.uuid4().hex[:8]
    user = User(
        username=f"diag_learner_{unique}",
        password_hash="x",
        email=f"diag_{unique}@example.com",
        role=UserRoleEnum.LEARNER,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.flush()

    from app.models import LearnerProfile

    profile = LearnerProfile(
        user_id=user.id,
        real_name=f"诊断学习者{unique[:4]}",
        education_level="master",
        major="计算机科学与技术",
        diagnostic_status=diagnostic_status,
        learning_style="visual",
        preferred_difficulty=3,
    )
    db_session.add(profile)
    db_session.commit()
    return user, profile


def _headers(user: User) -> dict[str, str]:
    token = create_access_token(
        {"user_id": user.id, "username": user.username, "role": "learner"}
    )
    return {"Authorization": f"Bearer {token}"}


def test_wizard_diagnostic_status_completes_guidance_stage(db_session, client):
    """答完向导诊断（diagnostic_status=completed）后 stage 必须离开 diagnosis。"""
    user, profile = _create_independent_learner(db_session, diagnostic_status="completed")

    response = client.get("/api/v1/dashboard/learner", headers=_headers(user))

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["facts"]["has_diagnosis"] is True
    assert data["guidance"]["stage"] != "diagnosis"


def test_completed_diagnostic_session_completes_guidance_stage(db_session, client):
    """有已完成诊断会话（即使画像字段滞后）也必须离开 diagnosis。"""
    user, profile = _create_independent_learner(db_session, diagnostic_status="in_progress")
    session = DiagnosticSession(
        id=f"diag-test-completed-{profile.id}",
        user_id=user.id,
        learner_id=profile.id,
        total_questions=12,
        answered_questions=12,
        status="completed",
        completed_at=datetime.utcnow(),
    )
    db_session.add(session)
    db_session.commit()

    response = client.get("/api/v1/dashboard/learner", headers=_headers(user))

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["facts"]["has_diagnosis"] is True
    assert data["guidance"]["stage"] != "diagnosis"


def test_active_diagnostic_session_keeps_diagnosis_stage(db_session, client):
    """未完成的诊断（in_progress 会话）仍停留在 diagnosis——诊断未做完不该跳步。"""
    user, profile = _create_independent_learner(db_session, diagnostic_status="in_progress")
    session = DiagnosticSession(
        id=f"diag-test-active-{profile.id}",
        user_id=user.id,
        learner_id=profile.id,
        total_questions=12,
        answered_questions=5,
        status="active",
    )
    db_session.add(session)
    db_session.commit()

    response = client.get("/api/v1/dashboard/learner", headers=_headers(user))

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["facts"]["has_diagnosis"] is False
    assert data["guidance"]["stage"] == "diagnosis"
