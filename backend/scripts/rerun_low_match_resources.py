"""重跑低匹配分学习资源：质量门生成新版本，达标后归档旧版本。

背景：早期（质量门引入前）生成的资源存在盲区覆盖塌方（分数 70-80）。
本脚本按 match_score < --threshold 选出低分资源，对每条用与
regenerate_resources_blind_coverage 相同的质量门流程重新生成同类型、
同主题资源；达到 --min-score 才保存并归档旧版本（旧版本退出
resource_match_score 统计），未达标则保留旧版本不动。

用法（必须在项目根目录运行，使用 backend venv）：
    python backend/scripts/rerun_low_match_resources.py --dry-run
    python backend/scripts/rerun_low_match_resources.py
"""
import argparse
import sys
from pathlib import Path
from typing import Dict

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.utils.llm  # noqa: E402,F401  # 先行加载以打破 utils<->ai_content_service 循环导入
from app.database import SessionLocal  # noqa: E402
from app.models import LearningResource  # noqa: E402
from app.domains.resource.service import (  # noqa: E402
    ResourceGenerationService,
    normalize_resource_topic,
)
from app.services.common import ResourceServiceHelper  # noqa: E402


def active_mean(db) -> tuple[float, int]:
    rows = db.query(LearningResource.match_score).filter(
        LearningResource.match_score.isnot(None),
        LearningResource.is_enabled.is_(True),
    ).all()
    scores = []
    for (raw,) in rows:
        value = float(raw)
        scores.append(value * 100 if 0 <= value <= 1 else value)
    return (round(sum(scores) / len(scores), 2) if scores else 0.0), len(scores)


def regenerate_one(
    svc,
    learner_dict: Dict,
    learner_id: int,
    topic: str,
    industry: str,
    resource_type: str,
    diagnosis: Dict,
    knowledge,
    min_score: float,
    max_attempts: int,
) -> Dict:
    """单项生成 + 评分 + 达标才返回结果（最多重试 max_attempts 次）。"""
    target_topic = normalize_resource_topic(topic)
    ability_scores = diagnosis.get("ability_scores", {})
    blind_areas = [b.get("name", "") for b in diagnosis.get("knowledge_blind_areas", [])]
    recommended_diff = diagnosis.get("recommended_difficulty", {}).get("recommended_difficulty", 3)

    best = None
    for attempt in range(1, max_attempts + 1):
        res_result = svc._generate_single_resource(
            learner_dict=learner_dict,
            target_topic=target_topic,
            resource_type=resource_type,
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
        return {"adopted": False, "score": match_score, "attempts": attempts}

    res_result["match_score"] = match_score
    res_result["match_score_metadata"] = {
        "formula_version": "difficulty_40_ability_30_blind_spot_30_v1",
        "source": "resource_generation_service_quality_gate",
        "recommended_difficulty": recommended_diff,
        "resource_difficulty": res_result.get("difficulty_level", 3),
        "blind_area_count": len(blind_areas),
        "quality_gate_min_score": min_score,
        "attempts": attempts,
        "regenerated_from": "rerun_low_match_resources",
    }
    res_result["resource_type_name"] = svc.RESOURCE_TYPE_NAMES.get(resource_type, resource_type)
    saved = svc._save_resource(
        learner_id=learner_id,
        resource_type=resource_type,
        resource_data=res_result,
        diagnosis_result=diagnosis,
        target_topic=target_topic,
        industry=industry,
        auto_publish=True,
    )
    return {"adopted": True, "score": match_score, "attempts": attempts, "new_id": saved.id}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=85.0, help="低于该分数的资源参与重跑")
    parser.add_argument("--min-score", type=float, default=90.0, help="质量门分数")
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="最多重跑条数（0=全部）")
    args = parser.parse_args()

    db = SessionLocal()
    mean, count = active_mean(db)
    print(f"起始: 有效资源={count} 均值={mean}", flush=True)

    targets = db.query(LearningResource).filter(
        LearningResource.match_score < args.threshold,
        LearningResource.is_enabled.is_(True),
    ).order_by(LearningResource.match_score).all()
    if args.limit:
        targets = targets[: args.limit]
    print(f"待重跑: {len(targets)} 条 (score < {args.threshold})", flush=True)
    for t in targets:
        print(f"  id={t.id} learner={t.learner_id} {t.resource_type} {t.knowledge_topic} [{t.industry}] score={t.match_score}", flush=True)
    if args.dry_run:
        db.close()
        return 0

    svc = ResourceGenerationService
    diagnosis_cache: Dict[int, Dict] = {}
    knowledge_cache: Dict[tuple, list] = {}
    adopted = failed = 0
    for old in targets:
        print(f"\n== 重跑 id={old.id} {old.resource_type} topic={old.knowledge_topic} ==", flush=True)
        try:
            if old.learner_id not in diagnosis_cache:
                diagnosis_cache[old.learner_id] = svc._run_diagnosis(old.learner_id)
            diagnosis = diagnosis_cache[old.learner_id]
            kkey = (old.knowledge_topic, old.industry)
            if kkey not in knowledge_cache:
                knowledge_cache[kkey] = svc._retrieve_knowledge(
                    target_topic=old.knowledge_topic, industry=old.industry
                )
            learner = svc.get_learner(old.learner_id)
            learner_dict = svc.model_to_dict(learner)
            result = regenerate_one(
                svc,
                learner_dict,
                old.learner_id,
                old.knowledge_topic,
                old.industry,
                old.resource_type,
                diagnosis,
                knowledge_cache[kkey],
                args.min_score,
                args.max_attempts,
            )
        except Exception as exc:  # noqa: BLE001 单条失败不中断整体
            print(f"  [fail] {exc}", flush=True)
            failed += 1
            continue
        if not result["adopted"]:
            print(f"  [gate] 重试{result['attempts']}次仍 {result['score']} < {args.min_score}，保留旧版本", flush=True)
            failed += 1
            continue
        old.is_enabled = False
        old.status = "archived"
        db.commit()
        adopted += 1
        print(f"  [ok] 新id={result['new_id']} score={result['score']} attempts={result['attempts']}，旧 id={old.id} 已归档", flush=True)
        mean, count = active_mean(db)
        print(f"  全局: 有效资源={count} 均值={mean}", flush=True)

    mean, count = active_mean(db)
    print(f"\n结束: 有效资源={count} 均值={mean} 采纳={adopted} 未达标/失败={failed}", flush=True)
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
