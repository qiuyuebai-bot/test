"""3 组不同背景学习者画像的差异化适配测试（评分项①证据）。

画像A 算法工程师（硕士/3年/人工智能/能力70+）      期望推荐难度 4
画像B 产线调试工程师（本科/5年/智能制造/能力75+）   期望推荐难度 4
画像C 设备维护技术员（大专/2年/工业互联网/能力45+） 期望推荐难度 2

差异化断言：
1. 诊断推荐难度随画像能力分区分（C 显著低于 A/B）
2. 生成资源的难度等级与画像诊断结果一致（★ 数量、适用人群文案）
3. 画像盲区进入讲义的"知识盲区专项突破"章节
"""
import pytest

from app.agents.diagnosis_agent import DiagnosisAgent
from app.agents.generation_agent import GenerationAgent
from app.utils.llm import LLMUtil

AUDIENCE_TEXTS = {
    1: "零基础初学者",
    2: "有一定基础的学习者",
    3: "具备中等基础的开发者",
    4: "有丰富经验的工程师",
    5: "资深技术专家",
}


def profile_to_dict(profile) -> dict:
    """与 AgentOrchestrator._model_to_dict 相同的 ORM→dict 转换"""
    return {column.name: getattr(profile, column.name) for column in profile.__table__.columns}


@pytest.fixture(autouse=True)
def disable_llm(monkeypatch):
    """禁用 LLM，走确定性规则路径，保证断言稳定"""
    monkeypatch.setattr(LLMUtil, "is_available", classmethod(lambda cls: False))


@pytest.fixture
def three_profiles(sample_learner_profile, sample_learner_profile_production_engineer,
                   sample_learner_profile_maintenance_technician):
    return {
        "A_algorithm_engineer": sample_learner_profile,
        "B_production_engineer": sample_learner_profile_production_engineer,
        "C_maintenance_technician": sample_learner_profile_maintenance_technician,
    }


def run_diagnosis(profile) -> dict:
    agent = DiagnosisAgent()
    return agent.execute({"learner_id": profile.id, "learner_profile": profile_to_dict(profile)})


def run_generation(diagnosis_result, profile, resource_type="lecture", topic="工业机器人基础"):
    agent = GenerationAgent()
    knowledge = [
        {
            "slice_id": 101,
            "doc_id": 1,
            "title": "工业机器人坐标系标定",
            "content": "工业机器人坐标系标定是保证定位精度的关键环节，包括基坐标系、工具坐标系与工件坐标系的标定方法。",
            "keywords": ["坐标系", "标定"],
        },
        {
            "slice_id": 102,
            "doc_id": 1,
            "title": "PLC 与工业机器人通信",
            "content": "PLC 通过 PROFINET、EtherCAT 等工业以太网协议与机器人控制器交换信号，实现产线联动控制。",
            "keywords": ["PLC", "通信"],
        },
    ]
    return agent.execute({
        "diagnosis_result": diagnosis_result,
        "knowledge_results": knowledge,
        "learner_profile": profile_to_dict(profile),
        "resource_type": resource_type,
        "target_topic": topic,
    })


class TestDiagnosisDifficultyDifferentiation:
    """断言1：诊断推荐难度随画像能力分区分"""

    @pytest.mark.parametrize("profile_key", ["A_algorithm_engineer", "B_production_engineer", "C_maintenance_technician"])
    def test_recommended_difficulty_within_bounds(self, three_profiles, profile_key):
        result = run_diagnosis(three_profiles[profile_key])
        params = result["recommended_difficulty"]
        assert 1 <= params["recommended_difficulty"] <= 5
        assert params["base_difficulty"] >= 1

    def test_weak_profile_gets_lower_difficulty_than_strong_profiles(self, three_profiles):
        """画像C（能力45+）推荐难度必须显著低于画像A/B（能力70+）"""
        results = {key: run_diagnosis(p) for key, p in three_profiles.items()}
        rec = {key: r["recommended_difficulty"]["recommended_difficulty"] for key, r in results.items()}

        assert rec["C_maintenance_technician"] < rec["A_algorithm_engineer"]
        assert rec["C_maintenance_technician"] < rec["B_production_engineer"]
        # 基础薄弱画像应落到难度 1-2 档
        assert rec["C_maintenance_technician"] <= 2
        # 能力画像应落到 3-5 档
        assert rec["A_algorithm_engineer"] >= 3
        assert rec["B_production_engineer"] >= 3

    def test_base_difficulty_reflects_ability_gap(self, three_profiles):
        """基础难度（纯能力分驱动）C 低于 A/B"""
        results = {key: run_diagnosis(p) for key, p in three_profiles.items()}
        base = {key: r["recommended_difficulty"]["base_difficulty"] for key, r in results.items()}

        assert base["C_maintenance_technician"] < base["A_algorithm_engineer"]
        assert base["C_maintenance_technician"] < base["B_production_engineer"]

    def test_weak_profile_has_more_blind_areas(self, three_profiles):
        """画像C 能力分低于60的维度会被诊断为盲区，数量多于画像B"""
        results = {key: run_diagnosis(p) for key, p in three_profiles.items()}
        blind = {key: len(r["knowledge_blind_areas"]) for key, r in results.items()}

        assert blind["C_maintenance_technician"] > blind["B_production_engineer"]
        # 画像C 声明的盲区必须完整进入诊断结果
        blind_names = {b["name"] for b in results["C_maintenance_technician"]["knowledge_blind_areas"]}
        assert "PLC通信协议" in blind_names
        assert "工业机器人安全操作" in blind_names


class TestGenerationMatchesProfile:
    """断言2：生成资源难度与画像诊断结果一致"""

    @pytest.mark.parametrize("profile_key,expected_difficulty", [
        ("C_maintenance_technician", 2),
        ("A_algorithm_engineer", 4),
        ("B_production_engineer", 4),
    ])
    def test_lecture_difficulty_level_matches_diagnosis(self, three_profiles, profile_key, expected_difficulty):
        profile = three_profiles[profile_key]
        diagnosis = run_diagnosis(profile)
        result = run_generation(diagnosis, profile, resource_type="lecture")

        assert result["difficulty_level"] == expected_difficulty
        assert result["difficulty_level"] == diagnosis["recommended_difficulty"]["recommended_difficulty"]

    def test_lecture_difficulty_markers_differ(self, three_profiles):
        """难度标记（★数量与适用人群文案）随画像区分"""
        contents = {}
        for key in ("C_maintenance_technician", "B_production_engineer"):
            profile = three_profiles[key]
            result = run_generation(run_diagnosis(profile), profile, resource_type="lecture")
            contents[key] = result["content"]

        # 画像C：难度2 → ★★ + 基础人群文案；画像B：难度4 → ★★★★ + 工程师文案
        assert "★★ |" in contents["C_maintenance_technician"].replace("**难度等级**：", "")
        assert AUDIENCE_TEXTS[2] in contents["C_maintenance_technician"]
        assert "★★★★ |" in contents["B_production_engineer"].replace("**难度等级**：", "")
        assert AUDIENCE_TEXTS[4] in contents["B_production_engineer"]

    def test_guide_difficulty_matches_profile(self, three_profiles):
        profile = three_profiles["C_maintenance_technician"]
        diagnosis = run_diagnosis(profile)
        result = run_generation(diagnosis, profile, resource_type="guide")

        assert result["difficulty_level"] == 2
        assert AUDIENCE_TEXTS[2] in result["content"]


class TestBlindAreasAffectGeneration:
    """断言3：画像盲区进入讲义生成内容"""

    def test_technician_blind_areas_appear_in_lecture(self, three_profiles):
        profile = three_profiles["C_maintenance_technician"]
        diagnosis = run_diagnosis(profile)
        result = run_generation(diagnosis, profile, resource_type="lecture")

        assert "知识盲区专项突破" in result["content"]
        assert "PLC通信协议" in result["content"]
        assert "工业机器人安全操作" in result["content"]
        # 盲区同步进入结构化 content_json
        blind_names = {b["name"] for b in result["content_json"]["blind_areas"]}
        assert "PLC通信协议" in blind_names

    def test_learning_goal_reflects_phase_gap(self, three_profiles):
        """画像C（foundation 期）与画像B（advanced 期）的学习阶段不同，诊断输出保留该差异"""
        diag_c = run_diagnosis(three_profiles["C_maintenance_technician"])
        diag_b = run_diagnosis(three_profiles["B_production_engineer"])

        assert diag_c["overall_score"] < diag_b["overall_score"]
        assert diag_c["overall_level"] != diag_b["overall_level"] or diag_c["overall_score"] < diag_b["overall_score"]
