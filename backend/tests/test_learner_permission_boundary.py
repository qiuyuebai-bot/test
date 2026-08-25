"""LearnerService 数据权限边界回归测试（ENTERPRISE 收紧 + 统一可访问集合）。"""
import uuid

from app.models import (
    EducationLevelEnum,
    LearnerProfile,
    LearningStyleEnum,
    User,
    UserRoleEnum,
)
from app.domains.learner.service import LearnerService


def _make_user(db_session, role, enterprise_name=None):
    user = User(
        username=f"u_{role.value}_{uuid.uuid4().hex[:8]}",
        password_hash="not-a-real-hash",
        role=role,
        enterprise_name=enterprise_name,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_learner(db_session, user):
    profile = LearnerProfile(
        user_id=user.id,
        real_name=f"学习者{user.id}",
        display_name=f"Learner{user.id}",
        education_level=EducationLevelEnum.MASTER.value,
        major="计算机科学与技术",
        school="测试大学",
        graduation_year=2020,
        current_position="算法工程师",
        years_of_experience=3,
        learning_style=LearningStyleEnum.VISUAL.value,
        preferred_difficulty=3,
        daily_study_time=60,
        theoretical_foundation=75.0,
        programming_ability=80.0,
        algorithm_design=70.0,
        system_architecture=60.0,
        data_analysis=65.0,
        engineering_practice=72.0,
        knowledge_blind_areas=["模型蒸馏"],
        knowledge_strengths=["Python编程"],
        learning_goal="掌握深度学习核心算法",
        target_industry="人工智能",
        target_position="高级算法工程师",
        learning_phase="growth",
        total_questions_answered=50,
        total_correct_rate=0.78,
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)
    return profile


def test_learner_role_only_sees_own_profile(db_session):
    user_a = _make_user(db_session, UserRoleEnum.LEARNER)
    user_b = _make_user(db_session, UserRoleEnum.LEARNER)
    learner_a = _make_learner(db_session, user_a)
    learner_b = _make_learner(db_session, user_b)

    assert LearnerService.check_data_permission(db_session, user_a.id, learner_a.id) is True
    assert LearnerService.check_data_permission(db_session, user_a.id, learner_b.id) is False


def test_enterprise_role_scoped_to_same_enterprise(db_session):
    ent_acme = _make_user(db_session, UserRoleEnum.ENTERPRISE, enterprise_name="Acme")
    ent_beta = _make_user(db_session, UserRoleEnum.ENTERPRISE, enterprise_name="Beta")
    ent_blank = _make_user(db_session, UserRoleEnum.ENTERPRISE, enterprise_name=None)

    acme_member = _make_user(db_session, UserRoleEnum.LEARNER, enterprise_name="Acme")
    beta_member = _make_user(db_session, UserRoleEnum.LEARNER, enterprise_name="Beta")
    no_ent_member = _make_user(db_session, UserRoleEnum.LEARNER, enterprise_name=None)

    acme_learner = _make_learner(db_session, acme_member)
    beta_learner = _make_learner(db_session, beta_member)
    no_ent_learner = _make_learner(db_session, no_ent_member)

    # 同企业放行
    assert LearnerService.check_data_permission(db_session, ent_acme.id, acme_learner.id) is True
    # 跨企业拒绝（旧代码：学习者存在即 True → 失败）
    assert LearnerService.check_data_permission(db_session, ent_acme.id, beta_learner.id) is False
    assert LearnerService.check_data_permission(db_session, ent_beta.id, acme_learner.id) is False
    # 企业归属缺失 fail-closed
    assert LearnerService.check_data_permission(db_session, ent_acme.id, no_ent_learner.id) is False
    assert LearnerService.check_data_permission(db_session, ent_blank.id, acme_learner.id) is False


def test_teacher_and_admin_policies_unchanged(db_session):
    teacher = _make_user(db_session, UserRoleEnum.TEACHER)
    admin = _make_user(db_session, UserRoleEnum.ADMIN)
    member = _make_user(db_session, UserRoleEnum.LEARNER)
    learner = _make_learner(db_session, member)

    assert LearnerService.check_data_permission(db_session, teacher.id, learner.id) is True
    assert LearnerService.check_data_permission(db_session, admin.id, learner.id) is True


def test_get_accessible_learner_ids_matches_boundary(db_session):
    ent_acme = _make_user(db_session, UserRoleEnum.ENTERPRISE, enterprise_name="Acme")
    member_a = _make_user(db_session, UserRoleEnum.LEARNER, enterprise_name="Acme")
    member_b = _make_user(db_session, UserRoleEnum.LEARNER, enterprise_name=None)
    learner_a = _make_learner(db_session, member_a)
    _make_learner(db_session, member_b)

    assert LearnerService.get_accessible_learner_ids(db_session, ent_acme.id) == [learner_a.id]
    assert LearnerService.get_accessible_learner_ids(db_session, 999999) == []
