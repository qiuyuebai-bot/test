"""Regression coverage for generated-resource content integrity."""
import json
from contextlib import contextmanager
from unittest.mock import patch

import httpx
import pytest

from app.agents import task_repository as task_repository_module
from app.agents.content_corrector import ContentCorrector
from app.agents.generation_agent import GenerationAgent
from app.agents.llm_generator import LLMGenerator
from app.agents.task_repository import TaskRepository
from app.config import settings
from app.domains.resource import service as resource_service_module
from app.domains.resource.service import ResourceGenerationService
from app.domains.knowledge.models import KnowledgePublicationRequest
from app.models import LearningResource
from app.services.ai_content_service import AIContentService
from app.utils.llm import LLMUnavailableError, LLMUtil
from app.utils.resource_content import ResourceContentError, normalize_resource_content


@pytest.fixture
def resource_persistence_context(db_session, monkeypatch):
    @contextmanager
    def override_get_db_context():
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    monkeypatch.setattr(task_repository_module, "get_db_context", override_get_db_context)
    monkeypatch.setattr(resource_service_module, "get_db_context", override_get_db_context)


def test_normalize_resource_content_unwraps_valid_deepseek_envelope():
    markdown = "# Backpropagation guide\n\nUse the chain rule to calculate gradients."
    payload = {
        "resource_title": "Backpropagation guide",
        "content": markdown,
        "_meta": {"model": "deepseek"},
    }

    assert normalize_resource_content(json.dumps(payload)) == markdown


@pytest.mark.parametrize(
    "payload",
    [
        {
            "resource_title": "Fallback guide",
            "content": "# Mock content",
            "_meta": {"model": "mock"},
        },
        {
            "passed": True,
            "score": 88,
            "issues": [],
            "hallucination_detected": False,
            "_meta": {"model": "mock"},
        },
    ],
)
def test_normalize_resource_content_rejects_mock_and_audit_payloads(payload):
    # The first value mirrors the escaped JSON persisted by the broken path.
    escaped_json = json.dumps(json.dumps(payload))

    with pytest.raises(ResourceContentError):
        normalize_resource_content(escaped_json)


def test_content_corrector_uses_rule_fallback_when_llm_returns_mock_audit(monkeypatch):
    mock_audit = {
        "passed": True,
        "score": 88,
        "issues": [],
        "_meta": {"model": "mock"},
    }
    original = "# Original resource\n\nThis resource contains enough detail to require a safe correction."

    monkeypatch.setattr(LLMUtil, "is_available", classmethod(lambda cls: True))
    monkeypatch.setattr(
        AIContentService,
        "sync_call",
        classmethod(lambda cls, **kwargs: (json.dumps(mock_audit), {})),
    )

    result = ContentCorrector().apply_corrections(
        original,
        [{"severity": "high", "issue_type": "unknown", "description": "Check wording"}],
    )

    assert original in result
    assert '"passed"' not in result
    assert '"_meta"' not in result


def test_content_corrector_accepts_valid_markdown_from_llm(monkeypatch):
    revised = "# Revised resource\n\nThis is a complete corrected Markdown resource from DeepSeek."

    monkeypatch.setattr(LLMUtil, "is_available", classmethod(lambda cls: True))
    monkeypatch.setattr(
        AIContentService,
        "sync_call",
        classmethod(lambda cls, **kwargs: (revised, {})),
    )

    result = ContentCorrector().apply_corrections(
        "# Original\n\nThe original resource is long enough to be replaced by a valid revision.",
        [{"severity": "medium", "issue_type": "unknown", "description": "Clarify wording"}],
    )

    assert result == revised


def test_task_repository_rejects_audit_payload_before_persisting(
    db_session,
    sample_agent_task,
    sample_learner_profile,
    resource_persistence_context,
):
    audit_payload = json.dumps(
        {"passed": True, "score": 88, "issues": [], "_meta": {"model": "mock"}}
    )

    with pytest.raises(ResourceContentError):
        TaskRepository().save_resource_and_complete(
            task_id=sample_agent_task.id,
            learner_id=sample_learner_profile.id,
            generation_result={
                "resource_type": "exercise",
                "resource_title": "Invalid exercise",
                "content": audit_payload,
                "content_json": {},
            },
            audit_result={"passed": True, "overall_score": 90},
            debate_rounds=1,
        )

    assert db_session.query(LearningResource).count() == 0


def test_task_repository_persists_valid_deepseek_markdown(
    db_session,
    sample_agent_task,
    sample_learner_profile,
    resource_persistence_context,
):
    markdown = "# Valid guide\n\nThis is valid Markdown generated by DeepSeek."
    result = TaskRepository().save_resource_and_complete(
        task_id=sample_agent_task.id,
        learner_id=sample_learner_profile.id,
        generation_result={
            "resource_type": "guide",
            "resource_title": "Valid guide",
            "content": json.dumps(
                {"content": markdown, "_meta": {"model": "deepseek"}}
            ),
            "content_json": {},
            "generation_method": "deepseek",
        },
        audit_result={"passed": True, "overall_score": 90},
        debate_rounds=1,
    )

    resource = db_session.get(LearningResource, result["resource_id"])
    assert resource.content == markdown
    assert resource.word_count == len(markdown)
    assert resource.generation_method == "deepseek"
    assert resource.review_status == "approved"


def test_task_repository_persists_all_source_slices_and_blocks_incomplete_coverage(
    db_session,
    sample_agent_task,
    sample_learner_profile,
    resource_persistence_context,
):
    result = TaskRepository().save_resource_and_complete(
        task_id=sample_agent_task.id,
        learner_id=sample_learner_profile.id,
        generation_result={
            "resource_type": "guide",
            "resource_title": "来源覆盖指南",
            "content": "# 来源覆盖指南\n\n正文包含 alpha，但没有第二个来源关键词。",
            "content_json": {},
            "source_references": [
                {"slice_id": 10, "doc_id": 2, "title": "来源一", "keywords": ["alpha"]},
                {"slice_id": 11, "doc_id": 2, "title": "来源二", "keywords": ["beta"]},
            ],
            "generation_method": "deepseek",
        },
        audit_result={"passed": True, "overall_score": 95},
        debate_rounds=1,
    )

    resource = db_session.get(LearningResource, result["resource_id"])
    assert resource.source_slice_ids == [10, 11]
    assert resource.source_doc_ids == [2]
    assert resource.status == "failed"
    assert resource.validation_passed is False
    assert resource.content_json["source_coverage"]["coverage_rate"] == 50.0
    assert result["passed"] is False


def test_task_repository_auto_publishes_new_validated_lecture(
    db_session,
    sample_agent_task,
    sample_learner_profile,
    resource_persistence_context,
):
    sample_agent_task.input_data = json.dumps(
        {"target_topic": "测试主题", "industry": "软件开发"},
        ensure_ascii=False,
    )
    db_session.commit()

    with patch(
        "app.domains.knowledge.publication_service.KnowledgeService.process_doc",
        return_value=True,
    ):
        result = TaskRepository().save_resource_and_complete(
            task_id=sample_agent_task.id,
            learner_id=sample_learner_profile.id,
            generation_result={
                "resource_type": "lecture",
                "resource_title": "流水线自动讲义",
                "content": "# 流水线自动讲义\n\n完整内容。",
                "content_json": {},
                "generation_method": "deepseek",
            },
            audit_result={"passed": True, "overall_score": 95},
            debate_rounds=1,
        )

    resource = db_session.get(LearningResource, result["resource_id"])
    request = db_session.query(KnowledgePublicationRequest).filter_by(resource_id=resource.id).one()
    assert resource.industry == "软件开发"
    assert request.status == "published"


def test_task_repository_auto_publishes_reused_lecture(
    db_session,
    sample_agent_task,
    sample_learner_profile,
    resource_persistence_context,
):
    with patch(
        "app.domains.knowledge.publication_service.KnowledgeService.process_doc",
        return_value=True,
    ):
        result = TaskRepository().save_reused_resource_and_complete(
            task_id=sample_agent_task.id,
            learner_id=sample_learner_profile.id,
            reusable_resource={
                "id": None,
                "title": "复用专属讲义",
                "resource_type": "lecture",
                "knowledge_topic": "测试主题",
                "industry": "软件开发",
                "content": "# 复用专属讲义\n\n完整内容。",
                "content_json": {},
                "validation_score": 90,
            },
        )

    request = db_session.query(KnowledgePublicationRequest).filter_by(resource_id=result["resource_id"]).one()
    assert request.status == "published"


def test_task_repository_persists_calculated_match_score(
    db_session,
    sample_agent_task,
    sample_learner_profile,
    resource_persistence_context,
):
    result = TaskRepository().save_resource_and_complete(
        task_id=sample_agent_task.id,
        learner_id=sample_learner_profile.id,
        generation_result={
            "resource_type": "guide",
            "resource_title": "Scored guide",
            "content": "# Scored guide\n\nThis is valid Markdown generated by DeepSeek.",
            "content_json": {},
            "generation_method": "deepseek",
            "match_score": 73.5,
        },
        audit_result={"passed": True, "overall_score": 90},
        debate_rounds=1,
    )

    resource = db_session.get(LearningResource, result["resource_id"])
    assert resource.match_score == 73.5


def test_task_repository_rejects_placeholder_title_before_persisting(
    db_session,
    sample_agent_task,
    sample_learner_profile,
    resource_persistence_context,
):
    with pytest.raises(ResourceContentError, match="占位符"):
        TaskRepository().save_resource_and_complete(
            task_id=sample_agent_task.id,
            learner_id=sample_learner_profile.id,
            generation_result={
                "resource_type": "guide",
                "resource_title": "None - 精通级实操指南",
                "content": "# Valid guide",
                "content_json": {},
            },
            audit_result={"passed": True, "overall_score": 90},
            debate_rounds=1,
        )

    assert db_session.query(LearningResource).count() == 0


def test_task_repository_marks_missing_match_score_as_pending(
    db_session,
    sample_agent_task,
    sample_learner_profile,
    resource_persistence_context,
):
    result = TaskRepository().save_resource_and_complete(
        task_id=sample_agent_task.id,
        learner_id=sample_learner_profile.id,
        generation_result={
            "resource_type": "guide",
            "resource_title": "Pending score guide",
            "content": "# Pending score guide",
            "content_json": {},
        },
        audit_result={"passed": True, "overall_score": 90},
        debate_rounds=1,
    )

    resource = db_session.get(LearningResource, result["resource_id"])
    assert resource.match_score is None
    assert resource.content_json["match_score_status"] == "pending"


def test_task_repository_keeps_failed_resource_pending(
    db_session,
    sample_agent_task,
    sample_learner_profile,
    resource_persistence_context,
):
    result = TaskRepository().save_resource_and_complete(
        task_id=sample_agent_task.id,
        learner_id=sample_learner_profile.id,
        generation_result={
            "resource_type": "lecture",
            "resource_title": "Failed lecture",
            "content": "# Failed lecture",
            "content_json": {},
        },
        audit_result={"passed": False, "overall_score": 40},
        debate_rounds=1,
    )

    resource = db_session.get(LearningResource, result["resource_id"])
    assert resource.status == "failed"
    assert resource.review_status == "pending"


def test_resource_display_and_export_hide_historical_placeholder_values(
    db_session,
    sample_learner_profile,
    resource_persistence_context,
):
    resource = LearningResource(
        learner_id=sample_learner_profile.id,
        title="None - 精通级实操指南",
        resource_type="guide",
        knowledge_topic="反向传播",
        difficulty_level=4,
        content="# Guide",
        status="ready",
        match_score=None,
    )
    db_session.add(resource)
    db_session.commit()

    exported = ResourceGenerationService.export_resource(resource.id)

    assert "None - 精通级实操指南" not in exported
    assert "反向传播 - 精通级实操指南" in exported
    assert "匹配度: 待计算" in exported


def test_sync_resource_save_rejects_mock_payload_before_persisting(
    db_session,
    sample_learner_profile,
    resource_persistence_context,
):
    with pytest.raises(ResourceContentError):
        ResourceGenerationService._save_resource(
            learner_id=sample_learner_profile.id,
            resource_type="guide",
            resource_data={
                "resource_title": "Invalid guide",
                "content": json.dumps(
                    {"content": "# Mock", "_meta": {"model": "mock"}}
                ),
            },
            diagnosis_result={},
            target_topic="test",
        )

    assert db_session.query(LearningResource).count() == 0


def test_sync_resource_save_marks_validated_resource_approved(
    db_session,
    sample_learner_profile,
    resource_persistence_context,
):
    resource = ResourceGenerationService._save_resource(
        learner_id=sample_learner_profile.id,
        resource_type="lecture",
        resource_data={
            "resource_title": "Validated lecture",
            "content": "# Validated lecture\n\nThis is complete content.",
            "_meta": {"score": 95},
        },
        diagnosis_result={},
        target_topic="test",
    )

    assert resource.status == "ready"
    assert resource.validation_passed is True
    assert resource.review_status == "approved"


def test_sync_resource_save_preserves_complete_source_slice_snapshot(
    db_session,
    sample_learner_profile,
    resource_persistence_context,
):
    resource = ResourceGenerationService._save_resource(
        learner_id=sample_learner_profile.id,
        resource_type="guide",
        resource_data={
            "resource_title": "来源快照指南",
            "content": "# 来源快照指南\n\n正文包含 alpha 和 beta。",
            "source_references": [
                {"slice_id": 21, "doc_id": 4, "title": "来源一", "keywords": ["alpha"]},
                {"slice_id": 22, "doc_id": 4, "title": "来源二", "keywords": ["beta"]},
            ],
        },
        diagnosis_result={},
        target_topic="test",
    )

    assert resource.source_slice_ids == [21, 22]
    assert resource.source_doc_ids == [4]
    assert resource.validation_passed is True


def test_sync_resource_save_auto_publishes_new_lecture(
    db_session,
    sample_learner_profile,
    resource_persistence_context,
):
    with patch(
        "app.domains.knowledge.publication_service.KnowledgeService.process_doc",
        return_value=True,
    ):
        resource = ResourceGenerationService._save_resource(
            learner_id=sample_learner_profile.id,
            resource_type="lecture",
            resource_data={
                "resource_title": "自动入库讲义",
                "content": "# 自动入库讲义\n\nThis is complete content.",
                "_meta": {"score": 95},
            },
            diagnosis_result={},
            target_topic="test",
            industry="软件开发",
            auto_publish=True,
        )

    request = db_session.query(KnowledgePublicationRequest).filter_by(resource_id=resource.id).one()
    assert request.status == "published"
    assert request.review_note == "系统自动入库"


def test_strict_llm_call_never_returns_a_mock_when_provider_is_missing(monkeypatch):
    monkeypatch.setattr(LLMUtil, "is_available", classmethod(lambda cls: False))

    with pytest.raises(LLMUnavailableError, match="unauthorized"):
        LLMUtil.sync_call("generate a guide", allow_mock=False)


def test_llm_health_check_reports_network_error_without_credentials(monkeypatch):
    class FailingClient:
        def get(self, _url):
            raise httpx.ConnectError("blocked")

    monkeypatch.setattr(LLMUtil, "is_available", classmethod(lambda cls: True))
    monkeypatch.setattr(LLMUtil, "_get_sync_client", classmethod(lambda cls, timeout=10.0: FailingClient()))

    assert LLMUtil.health_check() == {"available": False, "reason": "network_error"}


def test_resource_generation_stops_when_strict_provider_is_unavailable(monkeypatch):
    monkeypatch.setattr(settings, "REQUIRE_RESOURCE_LLM", True)
    monkeypatch.setattr(LLMUtil, "is_available", classmethod(lambda cls: True))
    monkeypatch.setattr(
        LLMGenerator,
        "generate_guide",
        classmethod(lambda cls, *args, **kwargs: (_ for _ in ()).throw(LLMUnavailableError("network_error"))),
    )

    with pytest.raises(LLMUnavailableError, match="network_error"):
        GenerationAgent().execute(
            {
                "resource_type": "guide",
                "target_topic": "backpropagation",
                "diagnosis_result": {"recommended_difficulty": {"recommended_difficulty": 3}},
                "knowledge_results": [],
                "learner_profile": {},
            }
        )
