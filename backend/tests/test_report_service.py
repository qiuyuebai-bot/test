"""
学情报告服务单元测试
测试范围：核心指标计算、统计信息、盲区描述阈值
（这些是性能热点 P1/P2 所在方法，重构前需锁定行为）
"""
import pytest
from contextlib import contextmanager
from sqlalchemy.orm import Session

from app.services import report_service as report_service_module
from app.services.report_service import ReportService
from app.models import LearnerProfile, LearningResource, AnswerRecord


@pytest.fixture(autouse=True)
def patch_report_db_context(db_session: Session, monkeypatch):
    """让 report_service 内的 get_db_context 使用测试 db_session，与 conftest 的 client fixture 行为一致"""

    @contextmanager
    def override_get_db_context():
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    monkeypatch.setattr(report_service_module, "get_db_context", override_get_db_context)


class TestCalculateCoreMetrics:
    """_calculate_core_metrics 是性能热点 P2，内存聚合逻辑，重构前必须锁定行为"""

    def test_metrics_with_resource_and_answer(
        self,
        db_session: Session,
        sample_learning_resource: LearningResource,
        sample_answer_record: AnswerRecord,
        sample_learner_profile: LearnerProfile,
    ):
        metrics = ReportService._calculate_core_metrics(
            sample_learner_profile.id,
            blind_areas=["卷积"],
        )
        # 资源 match_score=0.88 → 0.88
        assert metrics["resource_match_accuracy"] == 0.88
        # 资源 content 含"卷积" → 1/1*100 = 100
        assert metrics["knowledge_coverage_rate"] == 100.0
        # 1 条答题记录 result=correct → 1/1*100 = 100
        assert metrics["answer_accuracy"] == 100.0

    def test_knowledge_coverage_zero_when_blind_area_not_in_content(
        self,
        db_session: Session,
        sample_learning_resource: LearningResource,
        sample_learner_profile: LearnerProfile,
    ):
        metrics = ReportService._calculate_core_metrics(
            sample_learner_profile.id,
            blind_areas=["不存在的盲区关键词"],
        )
        assert metrics["knowledge_coverage_rate"] == 0.0

    def test_knowledge_coverage_full_when_no_blind_areas(
        self,
        db_session: Session,
        sample_learning_resource: LearningResource,
        sample_learner_profile: LearnerProfile,
    ):
        # 无盲区时覆盖率定义为 100
        metrics = ReportService._calculate_core_metrics(
            sample_learner_profile.id,
            blind_areas=[],
        )
        assert metrics["knowledge_coverage_rate"] == 100.0

    def test_metrics_zero_when_no_data(
        self,
        db_session: Session,
        sample_learner_profile: LearnerProfile,
    ):
        # 无资源、无答题记录
        metrics = ReportService._calculate_core_metrics(
            sample_learner_profile.id,
            blind_areas=["任意"],
        )
        assert metrics["resource_match_accuracy"] == 0
        assert metrics["knowledge_coverage_rate"] == 0.0
        assert metrics["answer_accuracy"] == 0

    def test_coverage_counts_each_blind_area_at_most_once_per_resource(
        self,
        db_session: Session,
        sample_learner_profile: LearnerProfile,
    ):
        # 资源 content 同时包含两个盲区关键词，但每个资源只算 1 次覆盖
        r = LearningResource(
            learner_id=sample_learner_profile.id,
            title="T",
            resource_type="guide",
            industry="AI",
            difficulty_level=3,
            content="卷积 池化 都在这里",
            match_score=0.5,
            status="ready",
        )
        db_session.add(r)
        db_session.commit()

        metrics = ReportService._calculate_core_metrics(
            sample_learner_profile.id,
            blind_areas=["卷积", "池化", "不存在"],
        )
        # covered_blind 是按资源计数：1 个资源命中任一盲区记 1 次 → 1/3*100
        assert metrics["knowledge_coverage_rate"] == round(1 / 3 * 100, 2)


class TestGetStatistics:
    def test_statistics_counts_and_avg_score(
        self,
        db_session: Session,
        sample_learning_resource: LearningResource,
        sample_answer_record: AnswerRecord,
        sample_learner_profile: LearnerProfile,
    ):
        stats = ReportService._get_statistics(sample_learner_profile.id)
        assert stats["total_resources"] == 1
        assert stats["total_answers"] == 1
        # score=10.0 → avg 10.0
        assert stats["avg_answer_score"] == 10.0

    def test_statistics_empty_for_learner(
        self,
        db_session: Session,
        sample_learner_profile: LearnerProfile,
    ):
        stats = ReportService._get_statistics(sample_learner_profile.id)
        assert stats["total_resources"] == 0
        assert stats["total_answers"] == 0
        assert stats["avg_answer_score"] == 0


class TestGetBlindDescription:
    """_get_blind_description 阈值逻辑，纯函数"""

    def test_weak_below_40(self):
        desc = ReportService._get_blind_description("算法", 35.0)
        assert "薄弱" in desc
        assert "算法" in desc

    def test_average_between_40_and_60(self):
        desc = ReportService._get_blind_description("算法", 50.0)
        assert "一般" in desc

    def test_good_at_or_above_60(self):
        desc = ReportService._get_blind_description("算法", 75.0)
        assert "良好" in desc

    def test_boundary_40_is_average(self):
        # 40 不算 < 40，落入 40-60 分支
        desc = ReportService._get_blind_description("算法", 40.0)
        assert "一般" in desc

    def test_boundary_60_is_good(self):
        # 60 不算 < 60，落入 >=60 分支
        desc = ReportService._get_blind_description("算法", 60.0)
        assert "良好" in desc
