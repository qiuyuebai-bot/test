"""Regression tests for the canonical metric contract."""

from datetime import timedelta

from app.models import DebateRecord
from app.services.metric_service import MetricService
from app.utils.datetime import utcnow_naive


def _by_id(results):
    return {result["metric_id"]: result for result in results}


def test_empty_database_reports_no_data_instead_of_zero(db_session):
    metrics = _by_id(MetricService.calculate_metrics(db_session, scope="global"))

    assert metrics["resource_match_score"]["value"] is None
    assert metrics["resource_match_score"]["status"] == "no_data"
    assert metrics["knowledge_index_coverage"]["value"] is None
    assert metrics["knowledge_index_coverage"]["status"] == "no_data"
    assert metrics["answer_accuracy"]["value"] is None
    assert metrics["answer_accuracy"]["status"] == "no_data"
    assert metrics["generated_content_coverage"]["value"] is None
    assert metrics["generated_content_coverage"]["status"] == "no_data"


def test_zero_is_a_ready_metric_value(db_session, sample_learning_resource):
    sample_learning_resource.match_score = 0
    db_session.commit()

    result = _by_id(
        MetricService.calculate_metrics(db_session, scope="learner", scope_id=sample_learning_resource.learner_id)
    )["resource_match_score"]

    assert result["value"] == 0
    assert result["status"] == "ready"
    assert result["numerator"] == 0
    assert result["denominator"] == 1


def _add_answer_record(db, user_id, learner_id, *, result, session_id, next_resource_id=None):
    from app.models import AnswerRecord

    record = AnswerRecord(
        user_id=user_id,
        learner_id=learner_id,
        question_id=1,
        question_type="single",
        question_topic="测试主题",
        question_difficulty=3,
        question_content="测试问题",
        user_answer=["A"],
        correct_answer=["A"],
        result=result,
        score=100.0 if result == "correct" else 0.0,
        time_spent_ms=1000,
        session_id=session_id,
        next_resource_id=next_resource_id,
        sequence_index=1,
    )
    db.add(record)
    db.commit()
    return record


def test_answer_accuracy_excludes_diagnostic_sessions(db_session, sample_user, sample_learner_profile):
    """诊断会话（diag_ 前缀）是能力摸底，不计入学习效果指标（Fix B）"""
    _add_answer_record(db_session, sample_user.id, sample_learner_profile.id, result="correct", session_id="diag_abc")
    _add_answer_record(db_session, sample_user.id, sample_learner_profile.id, result="wrong", session_id="diag_abc")
    _add_answer_record(db_session, sample_user.id, sample_learner_profile.id, result="correct", session_id="session_practice")
    _add_answer_record(db_session, sample_user.id, sample_learner_profile.id, result="correct", session_id="session_practice")

    result = _by_id(
        MetricService.calculate_metrics(db_session, scope="global", metric_ids=["answer_accuracy"])
    )["answer_accuracy"]

    assert result["value"] == 100.0
    assert result["numerator"] == 2
    assert result["denominator"] == 2


def test_answer_accuracy_counts_practice_records_only(db_session, sample_user, sample_learner_profile):
    """只有诊断记录时指标应为 no_data，而非用摸底正确率充当学习效果"""
    _add_answer_record(db_session, sample_user.id, sample_learner_profile.id, result="wrong", session_id="diag_abc")

    result = _by_id(
        MetricService.calculate_metrics(db_session, scope="global", metric_ids=["answer_accuracy"])
    )["answer_accuracy"]

    assert result["value"] is None
    assert result["status"] == "no_data"


def test_resource_match_effectiveness_measures_next_answer(db_session, sample_user, sample_learner_profile):
    """口径：带资源推荐的练习题触发，统计其"下一次答题"的判分结果。

    - 触发集排除诊断会话（diag_pre 不触发，其后续记录不计入）
    - 下一次答题可以是练习下一题，也可以是随后再测的首题（diag_gain_post）
    - 触发后无下一次答题（最后一条）不计入分母
    """
    _add_answer_record(
        db_session, sample_user.id, sample_learner_profile.id,
        result="wrong", session_id="diag_pre", next_resource_id=101,      # 诊断触发：不计
    )
    _add_answer_record(
        db_session, sample_user.id, sample_learner_profile.id,
        result="wrong", session_id="session_p0", next_resource_id=102,    # 触发1
    )
    _add_answer_record(
        db_session, sample_user.id, sample_learner_profile.id,
        result="correct", session_id="session_p1",                        # 触发1的下一次→对
    )
    _add_answer_record(
        db_session, sample_user.id, sample_learner_profile.id,
        result="wrong", session_id="session_p2", next_resource_id=103,    # 触发2
    )
    _add_answer_record(
        db_session, sample_user.id, sample_learner_profile.id,
        result="wrong", session_id="diag_gain_post",                      # 触发2的下一次（再测首题）→错
    )
    _add_answer_record(
        db_session, sample_user.id, sample_learner_profile.id,
        result="wrong", session_id="session_p4", next_resource_id=105,    # 触发4
    )
    _add_answer_record(
        db_session, sample_user.id, sample_learner_profile.id,
        result="correct", session_id="session_p5",                        # 触发4的下一次→对
    )
    _add_answer_record(
        db_session, sample_user.id, sample_learner_profile.id,
        result="correct", session_id="session_p3", next_resource_id=104,  # 触发3：排在最后，无下一次，不计
    )

    result = _by_id(
        MetricService.calculate_metrics(db_session, scope="global", metric_ids=["resource_match_effectiveness"])
    )["resource_match_effectiveness"]

    assert result["value"] == 66.67
    assert result["numerator"] == 2
    assert result["denominator"] == 3


def test_resource_match_effectiveness_diagnostic_trigger_excluded(db_session, sample_user, sample_learner_profile):
    """诊断会话记录即使带资源推荐也不构成触发；其后的练习记录结果不因此计入。"""
    _add_answer_record(
        db_session, sample_user.id, sample_learner_profile.id,
        result="wrong", session_id="diag_abc", next_resource_id=201,      # 诊断触发：不计
    )
    for i in range(3):
        _add_answer_record(
            db_session, sample_user.id, sample_learner_profile.id,
            result="wrong", session_id=f"session_rec_{i}", next_resource_id=202 + i,  # 触发
        )
        _add_answer_record(
            db_session, sample_user.id, sample_learner_profile.id,
            result="correct", session_id=f"session_follow_{i}",           # 每次触发的下一次→对
        )

    result = _by_id(
        MetricService.calculate_metrics(db_session, scope="global", metric_ids=["resource_match_effectiveness"])
    )["resource_match_effectiveness"]

    assert result["value"] == 100.0
    assert result["numerator"] == 3
    assert result["denominator"] == 3


def test_snapshot_policy_marks_old_results_stale(db_session, sample_learning_resource):
    calculated_at = utcnow_naive() - timedelta(days=2)
    result = _by_id(
        MetricService.calculate_metrics(
            db_session,
            scope="global",
            calculated_at=calculated_at,
            now=utcnow_naive(),
            metric_ids=["resource_match_score"],
        )
    )["resource_match_score"]
    assert result["value"] is None
    assert result["status"] == "stale"


def test_blind_spot_policy_distinguishes_not_applicable_and_collecting(
    db_session, sample_learner_profile
):
    sample_learner_profile.knowledge_blind_areas = []
    db_session.commit()
    not_applicable = _by_id(
        MetricService.calculate_metrics(db_session, scope="learner", scope_id=sample_learner_profile.id)
    )["blind_spot_resource_coverage"]
    assert not_applicable["value"] is None
    assert not_applicable["status"] == "not_applicable"

    sample_learner_profile.knowledge_blind_areas = ["API"]
    db_session.commit()
    collecting = _by_id(
        MetricService.calculate_metrics(db_session, scope="learner", scope_id=sample_learner_profile.id)
    )["blind_spot_resource_coverage"]
    assert collecting["value"] is None
    assert collecting["status"] == "collecting"
    assert collecting["numerator"] == 0
    assert collecting["denominator"] == 1


def test_hallucination_rate_waits_for_five_reviewed_records(
    db_session, sample_agent_task
):
    for index in range(4):
        db_session.add(
            DebateRecord(
                task_id=sample_agent_task.id,
                debate_round=index + 1,
                original_content="content",
                is_hallucination=index == 0,
                resolution_status="resolved",
                judge_decision="rejected" if index == 0 else "approved",
                conflict_description="[]",
            )
        )
    db_session.commit()
    result = _by_id(MetricService.calculate_metrics(db_session, scope="global"))["hallucination_rate"]

    assert result["value"] is None
    assert result["status"] == "collecting"
    assert result["sample_count"] == 4
    assert result["minimum_sample_size"] == 5


def test_metrics_api_exposes_registry_and_standard_results(client):
    response = client.get("/api/v1/report/metrics")
    assert response.status_code == 200
    data = response.json()["data"]
    assert {metric["metric_id"] for metric in data["metrics"]} == {
        "resource_match_score",
        "resource_match_effectiveness",
        "knowledge_index_coverage",
        "generated_content_coverage",
        "blind_spot_resource_coverage",
        "answer_accuracy",
        "hallucination_rate",
    }
    assert data["metrics"][0]["status"] in {
        "ready",
        "collecting",
        "no_data",
        "not_applicable",
        "stale",
        "error",
    }
    definitions = client.get("/api/v1/report/metrics/definitions")
    assert definitions.status_code == 200
    assert len(definitions.json()["data"]) == 7
