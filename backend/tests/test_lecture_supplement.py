"""讲义增量增补与导学讲解落地校验的单元测试。"""
from contextlib import contextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from app.domains.knowledge.service import KnowledgeService
from app.models import LearningResource
from app.services import lecture_supplement_service as lecture_supplement_module
from app.services.ai_content_service import AIContentService
from app.services.lecture_supplement_service import LectureSupplementService
from app.services.tutoring_service import AdaptiveTutoringService


def _fake_learner(blind_areas=None):
    return SimpleNamespace(
        knowledge_blind_areas=blind_areas or [],
        target_industry="人工智能",
        preferred_difficulty=3,
        ability_assessments={},
    )


def _fake_resource(content="# 机器学习讲义\n\n现有基础内容。"):
    return SimpleNamespace(content=content)


KB_SLICE = {
    "slice_id": 5,
    "doc_id": 2,
    "title": "梯度消失",
    "doc_title": "深度学习基础",
    "content": "梯度消失是指深层网络反向传播时梯度逐层衰减的现象，批归一化与残差连接可缓解。",
    "keywords": ["梯度消失", "批归一化"],
    "similarity": 0.92,
}


class TestEvaluateTrigger:
    def test_empty_topic_skipped(self):
        ok, reason = LectureSupplementService.evaluate_trigger(
            _fake_learner(), "  ", _fake_resource(), None, False
        )
        assert not ok and reason == "empty_topic"

    def test_declared_blind_area_skipped(self):
        ok, reason = LectureSupplementService.evaluate_trigger(
            _fake_learner(blind_areas=["模型蒸馏"]), "模型蒸馏", _fake_resource(), None, False
        )
        assert not ok and reason == "already_declared_blind_area"

    def test_no_lecture_skipped(self):
        ok, reason = LectureSupplementService.evaluate_trigger(
            _fake_learner(), "梯度消失", None, None, False
        )
        assert not ok and reason == "no_lecture_to_supplement"

    def test_already_covered_skipped(self):
        resource = _fake_resource(content="本章讨论梯度消失的成因与缓解。")
        ok, reason = LectureSupplementService.evaluate_trigger(
            _fake_learner(), "梯度消失", resource, None, False
        )
        assert not ok and reason == "already_covered_by_lecture"

    def test_cooldown_active_skipped(self):
        ok, reason = LectureSupplementService.evaluate_trigger(
            _fake_learner(), "梯度消失", _fake_resource(),
            datetime.utcnow() - timedelta(hours=1), False,
        )
        assert not ok and reason == "cooldown_active"

    def test_cooldown_expired_triggers(self):
        ok, reason = LectureSupplementService.evaluate_trigger(
            _fake_learner(), "梯度消失", _fake_resource(),
            datetime.utcnow() - timedelta(hours=3), False,
        )
        assert ok and reason == "triggered"

    def test_pipeline_running_skipped(self):
        ok, reason = LectureSupplementService.evaluate_trigger(
            _fake_learner(), "梯度消失", _fake_resource(), None, True
        )
        assert not ok and reason == "pipeline_running"

    def test_happy_path_triggers(self):
        ok, reason = LectureSupplementService.evaluate_trigger(
            _fake_learner(), "梯度消失", _fake_resource(), None, False
        )
        assert ok and reason == "triggered"


class TestBumpVersion:
    def test_minor_version_incremented(self):
        assert LectureSupplementService._bump_version("1.0") == "1.1"
        assert LectureSupplementService._bump_version("2.3") == "2.4"

    def test_invalid_version_falls_back(self):
        assert LectureSupplementService._bump_version(None) == "1.1"
        assert LectureSupplementService._bump_version("dev") == "1.1"


class TestExplanationGrounding:
    def test_grounded_when_keyword_hits(self):
        assert AdaptiveTutoringService._explanation_grounded(
            "梯度消失与批归一化相关。", [KB_SLICE]
        )

    def test_not_grounded_without_keyword(self):
        assert not AdaptiveTutoringService._explanation_grounded(
            "太阳从东边升起，月亮从西边落下。", [KB_SLICE]
        )

    def test_no_references_passes(self):
        assert AdaptiveTutoringService._explanation_grounded("任意内容", [])


class TestExplanationGroundingFallback:
    @pytest.fixture(autouse=True)
    def patch_db_context(self, db_session: Session, monkeypatch):
        @contextmanager
        def override_get_db_context():
            try:
                yield db_session
                db_session.commit()
            except Exception:
                db_session.rollback()
                raise

        monkeypatch.setattr(
            lecture_supplement_module, "get_db_context", override_get_db_context
        )
        import app.services.tutoring_service as ts

        monkeypatch.setattr(ts, "get_db_context", override_get_db_context)
        monkeypatch.setattr(ts.KnowledgeService, "search", staticmethod(lambda **kw: [KB_SLICE]))

    def test_ungrounded_ai_explanation_falls_back_to_deterministic(
        self, sample_learner_profile, monkeypatch
    ):
        ungrounded = {
            "type": "simplify",
            "title": "讲解",
            "simple_explanation": "答错的原因是概念混淆，建议重新梳理知识框架。",
            "key_points": ["梳理框架"],
            "practice_tips": "复习",
            "recommendation": "多练习",
            "generation_method": "deepseek",
        }
        monkeypatch.setattr(
            AIContentService, "generate", classmethod(lambda cls, t, p: ungrounded)
        )

        result = AdaptiveTutoringService._generate_simplified_explanation(
            sample_learner_profile, "梯度消失", "题目内容", "B", "A", decision="simplify"
        )

        # 回退确定性分支：knowledge_source 字段是确定性分支独有的契约
        assert "knowledge_source" in result
        assert result["knowledge_source"] == "knowledge_base"
        assert "梯度消失" in result["simple_explanation"]

    def test_grounded_ai_explanation_is_kept(self, sample_learner_profile, monkeypatch):
        grounded = {
            "type": "simplify",
            "title": "讲解",
            "simple_explanation": "梯度消失是因为反向传播时梯度逐层衰减，可用批归一化缓解。",
            "key_points": ["梯度消失"],
            "practice_tips": "复习",
            "recommendation": "多练习",
            "generation_method": "deepseek",
        }
        monkeypatch.setattr(
            AIContentService, "generate", classmethod(lambda cls, t, p: grounded)
        )

        result = AdaptiveTutoringService._generate_simplified_explanation(
            sample_learner_profile, "梯度消失", "题目内容", "B", "A", decision="simplify"
        )

        assert result.get("generation_method") == "deepseek"
        assert "knowledge_source" not in result


def _create_guide_resource(db_session, learner_id, content="# 机器学习讲义\n\n现有基础内容。"):
    resource = LearningResource(
        learner_id=learner_id,
        title="机器学习讲义",
        resource_type="guide",
        content=content,
        status="ready",
        is_latest=True,
        is_enabled=True,
        version="1.0",
        section_count=1,
        word_count=len(content),
        source_slice_ids=[],
        source_doc_ids=[],
    )
    db_session.add(resource)
    db_session.commit()
    return resource


class TestSupplementRun:
    @pytest.fixture(autouse=True)
    def patch_db_context(self, db_session: Session, monkeypatch):
        @contextmanager
        def override_get_db_context():
            try:
                yield db_session
                db_session.commit()
            except Exception:
                db_session.rollback()
                raise

        monkeypatch.setattr(
            lecture_supplement_module, "get_db_context", override_get_db_context
        )

    def test_run_appends_grounded_section(
        self, db_session, sample_learner_profile, monkeypatch
    ):
        resource = _create_guide_resource(db_session, sample_learner_profile.id)
        monkeypatch.setattr(
            KnowledgeService, "search", staticmethod(lambda **kw: [KB_SLICE])
        )
        section = {
            "section_title": "梯度消失与缓解",
            "section_content": "梯度消失指反向传播中梯度逐层衰减，批归一化与残差连接可缓解。",
            "key_points": ["梯度消失"],
            "generation_method": "deepseek",
        }
        monkeypatch.setattr(
            AIContentService, "generate", classmethod(lambda cls, t, p: section)
        )

        result = LectureSupplementService.run(
            learner_id=sample_learner_profile.id,
            topic="梯度消失",
            question_summary="题目：…",
            difficulty_level=3,
        )

        assert result["status"] == "supplemented"
        db_session.refresh(resource)
        assert "## 梯度消失与缓解" in resource.content
        assert resource.version == "1.1"
        assert resource.section_count == 2
        supplements = resource.content_json["supplements"]
        assert supplements[0]["topic"] == "梯度消失"
        assert supplements[0]["source_slice_ids"] == [5]
        assert 5 in resource.source_slice_ids

    def test_run_rejects_ungrounded_section(
        self, db_session, sample_learner_profile, monkeypatch
    ):
        resource = _create_guide_resource(db_session, sample_learner_profile.id)
        original_content = resource.content
        monkeypatch.setattr(
            KnowledgeService, "search", staticmethod(lambda **kw: [KB_SLICE])
        )
        ungrounded = {
            "section_title": "无关章节",
            "section_content": "今天天气不错，适合外出散步和思考人生。",
            "key_points": ["天气"],
            "generation_method": "deepseek",
        }
        monkeypatch.setattr(
            AIContentService, "generate", classmethod(lambda cls, t, p: ungrounded)
        )

        result = LectureSupplementService.run(
            learner_id=sample_learner_profile.id, topic="梯度消失"
        )

        assert result["status"] == "failed"
        assert result["reason"] == "section_not_grounded"
        db_session.refresh(resource)
        assert resource.content == original_content
        assert resource.version == "1.0"

    def test_run_skips_without_knowledge_results(
        self, db_session, sample_learner_profile, monkeypatch
    ):
        _create_guide_resource(db_session, sample_learner_profile.id)
        monkeypatch.setattr(KnowledgeService, "search", staticmethod(lambda **kw: []))

        result = LectureSupplementService.run(
            learner_id=sample_learner_profile.id, topic="梯度消失"
        )

        assert result["status"] == "skipped"
        assert result["reason"] == "no_knowledge_results"

    def test_run_skips_when_topic_already_covered(
        self, db_session, sample_learner_profile, monkeypatch
    ):
        _create_guide_resource(
            db_session,
            sample_learner_profile.id,
            content="# 机器学习讲义\n\n本章讲解梯度消失的成因。",
        )
        monkeypatch.setattr(
            KnowledgeService, "search", staticmethod(lambda **kw: [KB_SLICE])
        )

        result = LectureSupplementService.run(
            learner_id=sample_learner_profile.id, topic="梯度消失"
        )

        assert result["status"] == "skipped"
        assert result["reason"] == "already_covered_by_lecture"
