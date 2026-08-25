"""generate_learning_gain_curve 纯函数单测。"""
from types import SimpleNamespace

import pytest

from scripts.generate_learning_gain_curve import (
    build_session_ids,
    effective_ability,
    phase_stats,
    summarize_rounds,
)


def _learner(assessments=None, **columns):
    defaults = {
        "theoretical_foundation": 50.0,
        "programming_ability": 50.0,
        "algorithm_design": 50.0,
        "system_architecture": 50.0,
        "data_analysis": 50.0,
        "engineering_practice": 50.0,
    }
    defaults.update(columns)
    return SimpleNamespace(ability_assessments=assessments or {}, **defaults)


def test_effective_ability_prefers_estimated_score():
    learner = _learner({"data_analysis": {"estimatedScore": 66}}, data_analysis=60)
    assert effective_ability(learner, "数据分析") == 66


def test_effective_ability_falls_back_to_base_column():
    learner = _learner({}, data_analysis=44)
    assert effective_ability(learner, "数据分析") == 44


def test_effective_ability_defaults_to_dimension_mean():
    learner = _learner({}, data_analysis=70)
    # 陌生主题不匹配任何维度关键词 -> 回退六维均值 (50*5+70)/6
    assert effective_ability(learner, "陌生主题") == pytest.approx((50.0 * 5 + 70) / 6)


def test_phase_stats():
    assert phase_stats(3, 6) == {"correct": 3, "total": 6, "accuracy": 50.0}
    assert phase_stats(0, 0) == {"correct": 0, "total": 0, "accuracy": None}


def test_build_session_ids_uses_diagnostic_prefix_for_tests_only():
    ids = build_session_ids(learner_id=5, round_no=1)
    assert ids["pre"] == "diag_gain_l5_r1_pre"
    assert ids["post"] == "diag_gain_l5_r1_post"
    assert ids["learn"] == "gain_l5_r1_learn"  # 学习阶段计入练习口径


def test_summarize_rounds():
    rounds = [
        {"pre": {"accuracy": 30.0}, "post": {"accuracy": 40.0},
         "within_round_gain_pp": 10.0},
        {"pre": {"accuracy": 45.0}, "post": {"accuracy": 55.0},
         "within_round_gain_pp": 10.0},
    ]
    summary = summarize_rounds(rounds)
    assert summary["pre_round1_accuracy"] == 30.0
    assert summary["post_roundN_accuracy"] == 55.0
    assert summary["cross_round_gain_pp"] == 25.0
    assert summary["mean_within_round_gain_pp"] == 10.0
