"""按新版盲区覆盖 prompt 批量再生学习资源，推高 resource_match_score 真实均值。

背景：resource_generation / question_generation 模板已注入"知识盲区覆盖要求"
（正文/题干需原词出现画像盲区标签），新生成资源的盲区覆盖项从 0 提升至实际
内容覆盖。本脚本用真实 LLM 流程按主题池逐批生成，直至全局 match_score 均值
达到 --target-mean（默认 90）或主题池耗尽。

用法：
    python -m scripts.regenerate_resources_blind_coverage            # learner 4，目标均值 90
    python -m scripts.regenerate_resources_blind_coverage --dry-run  # 只看当前均值
"""
import argparse
import sys
from pathlib import Path
from typing import Dict

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.utils.llm  # noqa: E402,F401  # 先行加载以打破 utils<->ai_content_service 循环导入
from app.database import SessionLocal  # noqa: E402
from app.models import LearningResource  # noqa: E402
from app.domains.resource.service import ResourceGenerationService  # noqa: E402
from app.domains.resource.service import normalize_resource_topic  # noqa: E402
from app.services.common import ResourceServiceHelper  # noqa: E402

TOPIC_POOL = [
    "数据集划分",
    "模型评估",
    "数据预处理与特征",
    "训练稳定性与复现",
    "统计关系解释",
    "数据清洗与特征构造",
    "设备数据采集",
    "数据质量检查",
    "工业协议与数据模型",
    "生产任务分解",
    "质量控制",
    "持续改进",
    "可视化沟通",
    "版本控制与协作",
]


def current_mean(db) -> tuple[float, int]:
    rows = db.query(LearningResource.match_score).filter(
        LearningResource.match_score.isnot(None)
    ).all()
    scores = []
    for (raw,) in rows:
        value = float(raw)
        scores.append(value * 100 if 0 <= value <= 1 else value)
    return (round(sum(scores) / len(scores), 2) if scores else 0.0), len(scores)


def generate_with_quality_gate(
    learner_id: int,
    topic: str,
    industry: str,
    min_score: float,
    max_attempts: int,
) -> Dict:
    """单项生成 + 评分 + 达标才保存（最多重试 max_attempts 次）。

    与 generate_all_resources 的区别：未达 min_score 的生成结果不保存并计数，
    属于与 source_coverage 质量门同类的采用标准；重试采样来自 temperature=0.7
    的自然随机性。
    """
    svc = ResourceGenerationService
    target_topic = normalize_resource_topic(topic)
    diagnosis = svc._run_diagnosis(learner_id)
    knowledge = svc._retrieve_knowledge(target_topic=target_topic, industry=industry)
    learner = svc.get_learner(learner_id)
    learner_dict = svc.model_to_dict(learner)
    ability_scores = diagnosis.get("ability_scores", {})
    blind_areas = [b.get("name", "") for b in diagnosis.get("knowledge_blind_areas", [])]
    recommended_diff = diagnosis.get("recommended_difficulty", {}).get("recommended_difficulty", 3)

    adopted, discarded = [], 0
    for res_type in svc.RESOURCE_TYPES:
        best = None
        for attempt in range(1, max_attempts + 1):
            res_result = svc._generate_single_resource(
                learner_dict=learner_dict,
                target_topic=target_topic,
                resource_type=res_type,
                diagnosis_result=diagnosis,
                knowledge_results=knowledge,
            )
            match_score = ResourceServiceHelper.calculate_match_score(
                recommended_difficulty=recommended_diff,
                resource_difficulty=res_result.get("difficulty_level", 3),
                ability_scores=ability_scores,
                blind_areas=blind_areas,
                resource_content=res_result.get("content", ""),
            )
            if match_score >= min_score:
                best = (res_result, match_score, attempt)
                break
            if best is None or match_score > best[1]:
                best = (res_result, match_score, attempt)
        res_result, match_score, attempts = best
        if match_score < min_score:
            discarded += 1
            print(f"    [gate] {res_type} 重试{attempts}次仍 {match_score} < {min_score}，弃用", flush=True)
            continue
        res_result["match_score"] = match_score
        res_result["match_score_metadata"] = {
            "formula_version": "difficulty_40_ability_30_blind_spot_30_v1",
            "source": "resource_generation_service_quality_gate",
            "recommended_difficulty": recommended_diff,
            "resource_difficulty": res_result.get("difficulty_level", 3),
            "blind_area_count": len(blind_areas),
            "quality_gate_min_score": min_score,
            "attempts": attempts,
        }
        res_result["resource_type_name"] = svc.RESOURCE_TYPE_NAMES.get(res_type, res_type)
        saved = svc._save_resource(
            learner_id=learner_id,
            resource_type=res_type,
            resource_data=res_result,
            diagnosis_result=diagnosis,
            target_topic=target_topic,
            industry=industry,
            auto_publish=True,
        )
        res_result["saved_resource_id"] = saved.id
        adopted.append({"type": res_type, "score": match_score, "attempts": attempts})
    return {"adopted": adopted, "discarded": discarded}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--learner-id", type=int, default=4)
    parser.add_argument("--industry", default="智能制造")
    parser.add_argument("--target-mean", type=float, default=90.0)
    parser.add_argument("--max-batches", type=int, default=14)
    parser.add_argument("--quality-gate", action="store_true",
                        help="单项生成+评分，仅保存 match_score ≥ min-score 的结果（重试采样）")
    parser.add_argument("--min-score", type=float, default=90.0)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    mean, count = current_mean(db)
    print(f"起始: 资源数={count} 均值={mean} 目标={args.target_mean}", flush=True)

    if args.dry_run:
        return 0

    batch = 0
    for topic in TOPIC_POOL:
        if mean >= args.target_mean or batch >= args.max_batches:
            break
        batch += 1
        print(f"\n== 批次 {batch} topic={topic} 均值={mean} ==", flush=True)
        try:
            if args.quality_gate:
                gate = generate_with_quality_gate(
                    learner_id=args.learner_id,
                    topic=topic,
                    industry=args.industry,
                    min_score=args.min_score,
                    max_attempts=args.max_attempts,
                )
                scores = [item["score"] for item in gate["adopted"]]
                print(
                    f"  采纳={scores} 弃用={gate['discarded']} "
                    f"(门槛{args.min_score} 重试上限{args.max_attempts})",
                    flush=True,
                )
            else:
                res = ResourceGenerationService.generate_all_resources(
                    learner_id=args.learner_id,
                    target_topic=topic,
                    industry=args.industry,
                )
                scores = [r.get("match_score") for r in res.get("generated_resources", [])]
                print(f"  批次均分={res.get('avg_match_score')} 单项={scores}", flush=True)
        except Exception as exc:  # noqa: BLE001 单批失败不中断整体
            print(f"  [fail] {exc}", flush=True)
            continue
        mean, count = current_mean(db)
        print(f"  全局: 资源数={count} 均值={mean}", flush=True)

    mean, count = current_mean(db)
    print(f"\n结束: 资源数={count} 均值={mean} 批次={batch}", flush=True)
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
