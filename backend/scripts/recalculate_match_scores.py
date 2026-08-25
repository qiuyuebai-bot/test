"""用当前公式重算已有资源的 match_score（含带旧元数据的历史行）。

用法:
  cd backend
  python -m scripts.recalculate_match_scores            # 预览
  python -m scripts.recalculate_match_scores --apply    # 落库

仅重算 content_json.match_score_metadata.formula_version 为 v1（或缺失）的行，
重算后更新 formula_version 为 v2，可安全重复执行。
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal  # noqa: E402
from app.models import LearnerProfile, LearningResource  # noqa: E402
from app.services.common import ResourceServiceHelper  # noqa: E402

FORMULA_VERSION = "difficulty_40_ability_30_blind_spot_30_v2"


def _content_json(resource):
    value = resource.content_json or {}
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
    return dict(value) if isinstance(value, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="persist recalculated scores")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        profiles = {p.id: p for p in db.query(LearnerProfile).all()}
        changes = []
        for resource in db.query(LearningResource).all():
            content_json = _content_json(resource)
            meta = content_json.get("match_score_metadata") or {}
            if meta.get("formula_version") == FORMULA_VERSION:
                continue

            profile = profiles.get(resource.learner_id)
            if not profile:
                continue

            recommended = meta.get("recommended_difficulty") or profile.preferred_difficulty or 3
            resource_difficulty = meta.get("resource_difficulty") or resource.difficulty_level or 3
            blind_areas = [
                item.get("name", "") if isinstance(item, dict) else str(item)
                for item in (profile.knowledge_blind_areas or [])
            ]
            new_score = ResourceServiceHelper.calculate_match_score(
                recommended_difficulty=recommended,
                resource_difficulty=resource_difficulty,
                ability_scores={},  # v2 公式能力项已统一难度基准，不再使用
                blind_areas=blind_areas,
                resource_content=resource.content or "",
            )
            changes.append({
                "resource_id": resource.id,
                "old": resource.match_score,
                "new": new_score,
            })
            if args.apply:
                meta.update({
                    "formula_version": FORMULA_VERSION,
                    "recommended_difficulty": recommended,
                    "resource_difficulty": resource_difficulty,
                })
                content_json["match_score_metadata"] = meta
                resource.match_score = new_score
                resource.content_json = content_json

        if args.apply and changes:
            db.commit()

        old_avg = sum(c["old"] or 0 for c in changes) / len(changes) if changes else 0
        new_avg = sum(c["new"] for c in changes) / len(changes) if changes else 0
        print(json.dumps({
            "apply": args.apply,
            "recalculated": len(changes),
            "old_average": round(old_avg, 2),
            "new_average": round(new_avg, 2),
        }, ensure_ascii=False))
        if not args.apply:
            print(json.dumps(changes[:10], ensure_ascii=False, indent=2))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
