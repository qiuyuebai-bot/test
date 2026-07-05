"""
自适应导学服务单元测试
测试范围：决策阈值逻辑、动作描述、要点提取、画像更新、进阶挑战生成
（_run_agent_decision 是性能热点 P4，同步阻塞 Agent 调用，重构前需锁定行为）
"""
import pytest
from contextlib import contextmanager
from unittest.mock import MagicMock
from sqlalchemy.orm import Session

from app.services import tutoring_service as tutoring_service_module
from app.services.tutoring_service import AdaptiveTutoringService
from app.models import LearnerProfile, LearningResource, AnswerRecord


@pytest.fixture(autouse=True)
def patch_tutoring_db_context(db_session: Session, monkeypatch):
    """让 tutoring_service 内的 get_db_context 使用测试 db_session"""

    @contextmanager
    def override_get_db_context():
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    monkeypatch.setattr(
        tutoring_service_module, "get_db_context", override_get_db_context
    )


def _make_fake_agent(blind_areas=None):
    """构造假的 DiagnosisAgent，run 返回可控诊断结果"""
    fake = MagicMock()
    fake.run.return_value = {
        "knowledge_blind_areas": blind_areas or [],
    }
    return fake


class TestGetQuestions:
    """get_questions 返回内置题库"""

    def test_returns_three_questions(self):
        questions = AdaptiveTutoringService.get_questions()
        assert len(questions) == 3

    def test_question_fields_complete(self):
        questions = AdaptiveTutoringService.get_questions()
        for q in questions:
            assert "id" in q
            assert "type" in q
            assert "topic" in q
            assert "question" in q
            assert "options" in q
            assert "difficulty" in q


class TestRunAgentDecision:
    """_run_agent_decision 是性能热点 P4，决策阈值逻辑必须锁定"""

    def test_advance_when_accuracy_above_threshold(
        self, sample_learner_profile, monkeypatch
    ):
        """正确率 >= 0.7 → advance"""
        monkeypatch.setattr(
            tutoring_service_module, "DiagnosisAgent", lambda: _make_fake_agent([])
        )
        decision = AdaptiveTutoringService._run_agent_decision(
            learner=sample_learner_profile,
            question_topic="反向传播算法",
            score=80,
            accuracy_rate=0.8,
            is_correct=True,
        )
        assert decision["next_action"] == "advance"
        assert "70" in decision["reason"]

    def test_simplify_when_accuracy_below_threshold(
        self, sample_learner_profile, monkeypatch
    ):
        """正确率 < 0.7 → simplify"""
        monkeypatch.setattr(
            tutoring_service_module, "DiagnosisAgent", lambda: _make_fake_agent([])
        )
        decision = AdaptiveTutoringService._run_agent_decision(
            learner=sample_learner_profile,
            question_topic="反向传播算法",
            score=50,
            accuracy_rate=0.5,
            is_correct=False,
        )
        assert decision["next_action"] == "simplify"
        assert "<70" in decision["reason"]

    def test_consolidate_when_correct_but_has_blind_area(
        self, sample_learner_profile, monkeypatch
    ):
        """正确率达标但诊断到该主题存在知识盲区 → consolidate"""
        blind_areas = [{"name": "反向传播算法基础"}]
        monkeypatch.setattr(
            tutoring_service_module,
            "DiagnosisAgent",
            lambda: _make_fake_agent(blind_areas),
        )
        decision = AdaptiveTutoringService._run_agent_decision(
            learner=sample_learner_profile,
            question_topic="反向传播算法",
            score=85,
            accuracy_rate=0.85,
            is_correct=True,
        )
        assert decision["next_action"] == "consolidate"
        assert "盲区" in decision["reason"]

    def test_advance_when_correct_and_blind_area_unrelated(
        self, sample_learner_profile, monkeypatch
    ):
        """正确率达标且盲区与当前主题无关 → 仍 advance"""
        blind_areas = [{"name": "强化学习"}]
        monkeypatch.setattr(
            tutoring_service_module,
            "DiagnosisAgent",
            lambda: _make_fake_agent(blind_areas),
        )
        decision = AdaptiveTutoringService._run_agent_decision(
            learner=sample_learner_profile,
            question_topic="反向传播算法",
            score=90,
            accuracy_rate=0.9,
            is_correct=True,
        )
        assert decision["next_action"] == "advance"

    def test_confidence_capped_at_0_95(self, sample_learner_profile, monkeypatch):
        """置信度上限 0.95"""
        monkeypatch.setattr(
            tutoring_service_module, "DiagnosisAgent", lambda: _make_fake_agent([])
        )
        decision = AdaptiveTutoringService._run_agent_decision(
            learner=sample_learner_profile,
            question_topic="测试",
            score=100,
            accuracy_rate=1.0,
            is_correct=True,
        )
        assert decision["confidence"] <= 0.95


class TestGetActionDescription:
    """_get_action_description 纯逻辑"""

    def test_simplify_description(self):
        desc = AdaptiveTutoringService._get_action_description("simplify")
        assert "简化" in desc

    def test_advance_description(self):
        desc = AdaptiveTutoringService._get_action_description("advance")
        assert "进阶" in desc

    def test_consolidate_description(self):
        desc = AdaptiveTutoringService._get_action_description("consolidate")
        assert "巩固" in desc

    def test_none_description(self):
        desc = AdaptiveTutoringService._get_action_description("none")
        assert "暂无" in desc

    def test_unknown_action_fallback(self):
        desc = AdaptiveTutoringService._get_action_description("unknown_xyz")
        assert "未知" in desc


class TestExtractKeyPoints:
    """_extract_key_points 纯逻辑"""

    def test_known_topic_returns_points(self):
        points = AdaptiveTutoringService._extract_key_points("机器学习")
        assert len(points) == 3
        assert any("数据" in p for p in points)

    def test_unknown_topic_returns_fallback(self):
        points = AdaptiveTutoringService._extract_key_points("量子计算")
        assert len(points) == 1
        assert "量子计算" in points[0]


class TestGenerateAdvancedChallenge:
    """_generate_advanced_challenge 难度递进逻辑"""

    def test_difficulty_increments(
        self, sample_learner_profile, sample_learning_resource
    ):
        challenge = AdaptiveTutoringService._generate_advanced_challenge(
            learner=sample_learner_profile,
            question_topic="深度学习",
            current_difficulty=3,
        )
        assert challenge["type"] == "advance"
        assert challenge["advanced_difficulty"] == 4
        assert challenge["current_difficulty"] == 3

    def test_difficulty_capped_at_5(
        self, sample_learner_profile, sample_learning_resource
    ):
        challenge = AdaptiveTutoringService._generate_advanced_challenge(
            learner=sample_learner_profile,
            question_topic="深度学习",
            current_difficulty=5,
        )
        assert challenge["advanced_difficulty"] == 5

    def test_includes_suggested_resources(
        self, sample_learner_profile, sample_learning_resource
    ):
        """sample_learning_resource difficulty=3，应被高阶资源查询命中"""
        challenge = AdaptiveTutoringService._generate_advanced_challenge(
            learner=sample_learner_profile,
            question_topic="深度学习",
            current_difficulty=2,
        )
        assert len(challenge["suggested_resources"]) >= 1
        assert challenge["suggested_resources"][0]["resource_id"] == sample_learning_resource.id

    def test_bonus_points_scale_with_difficulty(
        self, sample_learner_profile, sample_learning_resource
    ):
        challenge = AdaptiveTutoringService._generate_advanced_challenge(
            learner=sample_learner_profile,
            question_topic="深度学习",
            current_difficulty=3,
        )
        assert challenge["bonus_points"] == challenge["advanced_difficulty"] * 20


class TestUpdateLearnerProfile:
    """_update_learner_profile 按 topic 关键词映射能力维度"""

    def test_algorithm_topic_updates_algorithm_design(
        self, sample_learner_profile
    ):
        original = sample_learner_profile.algorithm_design
        AdaptiveTutoringService._update_learner_profile(
            learner=sample_learner_profile,
            topic="算法设计进阶",
            score=80,
            is_correct=True,
        )
        assert sample_learner_profile.algorithm_design == original + 2

    def test_wrong_answer_decrements(
        self, sample_learner_profile
    ):
        original = sample_learner_profile.programming_ability
        AdaptiveTutoringService._update_learner_profile(
            learner=sample_learner_profile,
            topic="编程实战",
            score=40,
            is_correct=False,
        )
        assert sample_learner_profile.programming_ability == original - 1

    def test_unmatched_topic_no_change(self, sample_learner_profile):
        original_theory = sample_learner_profile.theoretical_foundation
        AdaptiveTutoringService._update_learner_profile(
            learner=sample_learner_profile,
            topic="量子纠缠",  # 不命中任何关键词
            score=80,
            is_correct=True,
        )
        assert sample_learner_profile.theoretical_foundation == original_theory


class TestGetInteractionHistory:
    """get_interaction_history 分页查询"""

    def test_returns_existing_records(
        self, sample_learner_profile, sample_answer_record
    ):
        result = AdaptiveTutoringService.get_interaction_history(
            learner_id=sample_learner_profile.id
        )
        assert result["total"] >= 1
        assert len(result["history"]) >= 1
        assert result["history"][0]["record_id"] == sample_answer_record.id

    def test_pagination(
        self, sample_learner_profile, sample_answer_record
    ):
        result = AdaptiveTutoringService.get_interaction_history(
            learner_id=sample_learner_profile.id, page=1, page_size=5
        )
        assert result["page"] == 1
        assert result["page_size"] == 5

    def test_empty_history_for_new_learner(self, db_session, sample_user):
        from app.models import LearnerProfile, EducationLevelEnum, LearningStyleEnum

        learner = LearnerProfile(
            user_id=sample_user.id,
            real_name="无记录学习者",
            display_name="Empty",
            education_level=EducationLevelEnum.BACHELOR.value,
            major="测试",
            school="测试大学",
            graduation_year=2024,
            current_position="学生",
            years_of_experience=0,
            learning_style=LearningStyleEnum.VISUAL.value,
            preferred_difficulty=3,
            daily_study_time=30,
            theoretical_foundation=50.0,
            programming_ability=50.0,
            algorithm_design=50.0,
            system_architecture=50.0,
            data_analysis=50.0,
            engineering_practice=50.0,
        )
        db_session.add(learner)
        db_session.commit()
        db_session.refresh(learner)

        result = AdaptiveTutoringService.get_interaction_history(
            learner_id=learner.id
        )
        assert result["total"] == 0
        assert result["history"] == []
