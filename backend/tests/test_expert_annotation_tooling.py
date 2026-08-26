"""专家标注工具链（导出/校验/交叉验证）纯函数单测。"""
from datetime import datetime

from scripts.export_annotation_package import (
    build_cases,
    normalize_score,
    render_csv,
    render_html,
    tier_of,
)
from scripts.validate_expert_annotations import (
    compute_cross_validation,
    render_rubric_section,
    update_rubric,
    validate_annotations,
)

FIXTURE_BASE = {
    "schema_version": "1.0",
    "domain": "industrial_robotics",
    "required_fields": [
        "case_id", "topic", "generated_content", "reference_slice_ids",
        "expert_label", "reviewer_id", "reviewed_at",
    ],
    "allowed_labels": ["supported", "contradicted", "insufficient_evidence"],
}


def make_annotation(**overrides):
    item = {
        "case_id": "res_1",
        "topic": "机器人坐标系",
        "generated_content": "TCP 校准……",
        "reference_slice_ids": [101],
        "expert_label": "supported",
        "reviewer_id": "EXP-01",
        "reviewed_at": "2026-09-01",
        "notes": "与切片一致",
    }
    item.update(overrides)
    return item


def make_resource(**overrides):
    resource = {
        "source_slice_ids": [101],
        "match_score": 90.0,
        "hallucination_detected": False,
    }
    resource.update(overrides)
    return resource


class TestScoreNormalization:
    def test_percent_stays(self):
        assert normalize_score(87.5) == 87.5

    def test_fraction_scaled(self):
        assert normalize_score(0.9) == 90.0

    def test_none_and_invalid(self):
        assert normalize_score(None) is None
        assert normalize_score("abc") is None

    def test_tier_boundaries(self):
        assert tier_of(80) == "high"
        assert tier_of(79.9) == "mid"
        assert tier_of(60) == "mid"
        assert tier_of(59.9) == "low"
        assert tier_of(None) == "low"


class TestBuildCases:
    def test_assembles_reference_slices_and_blind_score(self):
        resources = [{
            "id": 1, "title": "TCP 指南", "knowledge_topic": "机器人坐标系",
            "resource_type": "guide", "content": "TCP 校准内容",
            "match_score": 90.0, "source_slice_ids": [101, 999],
        }]
        slices = {101: {"title": "TCP", "content": "TCP 校准步骤"}}
        cases = build_cases(resources, slices)

        assert len(cases) == 1
        case = cases[0]
        assert case["case_id"] == "res_1"
        assert case["tier"] == "high"
        assert case["has_reference"] is True
        assert case["references"][0]["slice_id"] == 101
        assert "不存在" in case["references"][1]["content"]

    def test_html_hides_match_score(self):
        resources = [{
            "id": 1, "title": "t", "knowledge_topic": "topic", "resource_type": "guide",
            "content": "内容", "match_score": 95.0, "source_slice_ids": [101],
        }]
        html_text = render_html(build_cases(resources, {101: {"title": "s", "content": "ref"}}), "2026-08-26 10:00")
        assert "res_1" in html_text
        assert "95" not in html_text.replace("95.0", "")  # 分数不外泄
        assert "match_score" not in html_text

    def test_csv_has_blank_label_columns(self):
        resources = [{
            "id": 2, "title": "t", "knowledge_topic": "topic", "resource_type": "guide",
            "content": "内容", "match_score": 70.0, "source_slice_ids": [5],
        }]
        csv_text = render_csv(build_cases(resources, {}))
        lines = csv_text.strip().splitlines()
        assert lines[0] == "case_id,topic,reference_slice_ids,expert_label,reviewer_id,reviewed_at,notes"
        assert lines[1] == "res_2,topic,5,,,,"


class TestValidateAnnotations:
    def test_empty_annotations_is_error(self):
        errors, warnings = validate_annotations({**FIXTURE_BASE, "annotations": []}, {}, {})
        assert errors == ["annotations 为空：尚未回收真实专家标注"]

    def test_valid_annotation_passes(self):
        errors, warnings = validate_annotations(
            {**FIXTURE_BASE, "annotations": [make_annotation()]},
            {1: make_resource()},
            {101: {"title": "TCP"}},
        )
        assert errors == [] and warnings == []

    def test_missing_field_and_bad_label(self):
        errors, _ = validate_annotations(
            {**FIXTURE_BASE, "annotations": [make_annotation(expert_label="great", reviewer_id="")]},
            {1: make_resource()},
            {101: {"title": "TCP"}},
        )
        assert any("reviewer_id" in e for e in errors)
        assert any("allowed_labels" in e for e in errors)

    def test_missing_resource_and_slice(self):
        errors, _ = validate_annotations(
            {**FIXTURE_BASE, "annotations": [make_annotation()]},
            {},
            {},
        )
        assert any("不存在于 learning_resources" in e for e in errors)

        errors, _ = validate_annotations(
            {**FIXTURE_BASE, "annotations": [make_annotation(reference_slice_ids=[404])]},
            {1: make_resource()},
            {},
        )
        assert any("不存在的切片 [404]" in e for e in errors)

    def test_bad_date_format(self):
        errors, _ = validate_annotations(
            {**FIXTURE_BASE, "annotations": [make_annotation(reviewed_at="2026/09/01")]},
            {1: make_resource()},
            {101: {"title": "TCP"}},
        )
        assert any("reviewed_at" in e for e in errors)

    def test_supported_with_system_hallucination_warns(self):
        _, warnings = validate_annotations(
            {**FIXTURE_BASE, "annotations": [make_annotation()]},
            {1: make_resource(hallucination_detected=True)},
            {101: {"title": "TCP"}},
        )
        assert any("已检出幻觉但专家判 supported" in w for w in warnings)


class TestCrossValidation:
    def test_tier_agreement_and_contradiction_detection(self):
        annotations = [
            make_annotation(case_id="res_1", expert_label="supported"),        # 高档 supported
            make_annotation(case_id="res_2", expert_label="supported"),        # 高档 supported
            make_annotation(case_id="res_3", expert_label="contradicted"),     # 低档 非 supported
            make_annotation(case_id="res_4", expert_label="insufficient_evidence"),  # 低档 非 supported
        ]
        resources = {
            1: make_resource(match_score=90.0),
            2: make_resource(match_score=85.0),
            3: make_resource(match_score=50.0, hallucination_detected=False),
            4: make_resource(match_score=30.0, hallucination_detected=False),
        }
        metrics = compute_cross_validation(annotations, resources)

        assert metrics["annotation_count"] == 4
        assert metrics["tier_counts"] == {"high": 2, "mid": 0, "low": 2}
        assert metrics["tier_agreement"] == 1.0  # 高档 2/2 + 低档 2/2
        assert metrics["contradiction_detection"] == 1.0  # 1 条 contradicted 且系统漏检

    def test_partial_agreement(self):
        annotations = [
            make_annotation(case_id="res_1", expert_label="supported"),
            make_annotation(case_id="res_2", expert_label="contradicted"),
        ]
        resources = {
            1: make_resource(match_score=90.0),
            2: make_resource(match_score=40.0, hallucination_detected=True),
        }
        metrics = compute_cross_validation(annotations, resources)
        # 高档 supported 1/1；低档非 supported 1/1；但 contradicted 被系统检出 → 漏检 0/1
        assert metrics["tier_agreement"] == 1.0
        assert metrics["contradiction_detection"] == 0.0

    def test_insufficient_tiers_yield_none(self):
        annotations = [make_annotation(case_id="res_1", expert_label="supported")]
        metrics = compute_cross_validation(annotations, {1: make_resource(match_score=90.0)})
        assert metrics["tier_agreement"] is None
        assert metrics["contradiction_detection"] is None

    def test_rubric_section_rendering(self):
        metrics = compute_cross_validation(
            [make_annotation(case_id="res_1", expert_label="supported")],
            {1: make_resource(match_score=90.0)},
        )
        section = render_rubric_section(metrics)
        assert "标注条数：1" in section
        assert "高档 1 / 中档 0 / 低档 0" in section
        assert "无法计算" in section

    def test_update_rubric_replaces_template(self, tmp_path):
        rubric = tmp_path / "rubric.md"
        rubric.write_text(
            "## 6. 交叉验证\n\n```\n（待标注完成后填写）\n- 标注条数：N（高档 x / 中档 y / 低档 z）\n"
            "- 分档一致率：0.xx\n- 矛盾检出率：0.xx\n- 结论一句话：……\n```\n",
            encoding="utf-8",
        )
        import scripts.validate_expert_annotations as mod
        original_path = mod.RUBRIC_PATH
        mod.RUBRIC_PATH = rubric
        try:
            metrics = compute_cross_validation(
                [make_annotation(case_id="res_1", expert_label="supported")],
                {1: make_resource(match_score=90.0)},
            )
            assert update_rubric(metrics) is True
            updated = rubric.read_text(encoding="utf-8")
            assert "待标注完成后填写" not in updated
            assert "标注条数：1" in updated
            assert update_rubric(metrics) is False  # 模板已替换，二次调用不再生效
        finally:
            mod.RUBRIC_PATH = original_path
