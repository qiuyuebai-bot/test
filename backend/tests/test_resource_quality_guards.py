import pytest
from pydantic import ValidationError

from app.agents.generation_agent import GenerationAgent
from app.domains.agent.schemas import CreateAgentTaskRequest, GenerationRequest
from app.schemas.core import GenerateResourcesRequest
from app.services.common import ResourceServiceHelper
from app.middleware.prometheus import resource_quality_events_total
from app.utils.resource_content import (
    ResourceContentError,
    build_resource_title,
    validate_match_score,
    validate_resource_title,
)
from scripts.backfill_match_scores import _build_repaired_title


def test_generation_task_requires_a_non_blank_topic():
    with pytest.raises(ValidationError):
        CreateAgentTaskRequest(
            learner_id=1,
            task_name="生成资源",
            task_type="full_pipeline",
            target_topic="  ",
        )


def test_diagnosis_task_can_omit_topic():
    request = CreateAgentTaskRequest(
        learner_id=1,
        task_name="学情诊断",
        task_type="learner_diagnosis",
    )
    assert request.target_topic is None


@pytest.mark.parametrize("request_type", [GenerationRequest, GenerateResourcesRequest])
def test_resource_generation_requests_trim_and_require_topic(request_type):
    request = request_type(learner_id=1, target_topic="  反向传播  ")
    assert request.target_topic == "反向传播"

    with pytest.raises(ValidationError):
        request_type(learner_id=1, target_topic="   ")


@pytest.mark.parametrize("title", ["None - 精通级实操指南", "null - 指南", "undefined - 指南", "  "])
def test_placeholder_resource_titles_are_rejected(title):
    before = resource_quality_events_total.get(event="title_rejected", reason="placeholder")
    with pytest.raises(ResourceContentError):
        validate_resource_title(title)
    if "None" in title or "null" in title or "undefined" in title:
        assert resource_quality_events_total.get(
            event="title_rejected", reason="placeholder"
        ) == before + 1


def test_resource_title_builder_produces_a_valid_fallback():
    assert build_resource_title("反向传播", "guide", 4) == "反向传播 - 精通级实操指南"


def test_safe_resource_title_does_not_count_read_time_fallbacks():
    resource = type(
        "Resource",
        (),
        {
            "title": "None - 精通级实操指南",
            "knowledge_topic": "反向传播",
            "resource_type": "guide",
            "difficulty_level": 4,
        },
    )()
    before = resource_quality_events_total.get(event="title_rejected", reason="placeholder")

    assert ResourceServiceHelper.safe_resource_title(resource) == "反向传播 - 精通级实操指南"
    assert resource_quality_events_total.get(
        event="title_rejected", reason="placeholder"
    ) == before


@pytest.mark.parametrize("topic", ["None", "null", "undefined", "  ", None])
def test_title_repair_skips_unreliable_topics(topic):
    resource = type(
        "Resource",
        (),
        {
            "knowledge_topic": topic,
            "resource_type": "guide",
            "difficulty_level": 4,
        },
    )()

    assert _build_repaired_title(resource, None) is None


def test_missing_match_score_is_not_coerced_to_zero():
    assert validate_match_score(None) is None
    assert validate_match_score(73.5) == 73.5


def test_generation_agent_rejects_missing_topic_before_generation():
    with pytest.raises(ValueError, match="目标主题不能为空"):
        GenerationAgent().execute({"resource_type": "guide", "target_topic": None})
