from app.services.common import ResourceServiceHelper


def test_match_score_uses_recommended_difficulty_for_ability_adaptation():
    score = ResourceServiceHelper.calculate_match_score(
        recommended_difficulty=4,
        resource_difficulty=4,
        ability_scores={"theoretical_foundation": 10, "programming_ability": 10},
        blind_areas=["反向传播"],
        resource_content="本节讲解反向传播。",
    )

    assert score == 100.0


def test_match_score_accepts_common_blind_area_wording_variation():
    score = ResourceServiceHelper.calculate_match_score(
        recommended_difficulty=3,
        resource_difficulty=3,
        ability_scores={},
        blind_areas=["梯度消失问题"],
        resource_content="本节重点分析梯度消失，并给出改进方法。",
    )

    assert score == 100.0


def test_match_score_keeps_empty_blind_area_default():
    score = ResourceServiceHelper.calculate_match_score(
        recommended_difficulty=3,
        resource_difficulty=3,
        ability_scores={},
        blind_areas=[],
        resource_content="正文",
    )

    assert score == 85.0
