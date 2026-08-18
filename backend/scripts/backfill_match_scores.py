"""Backfill match scores for resources created before the Agent pipeline fix.

Run without ``--apply`` to inspect the proposed values.  The script only
updates rows that have no persisted match-score metadata, so it is safe to run
again after a deployment.
"""

import argparse
import json

from app.database import SessionLocal
from app.models import LearnerProfile, LearningResource
from app.services.common import ResourceServiceHelper


FORMULA_VERSION = "difficulty_40_ability_30_blind_spot_30_v1"


def _model_dict(model):
    return {column.name: getattr(model, column.name) for column in model.__table__.columns}


def _content_json(resource):
    value = resource.content_json or {}
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            value = {}
    return dict(value) if isinstance(value, dict) else {}


def _profile_inputs(profile):
    ability_fields = (
        "theoretical_foundation",
        "programming_ability",
        "algorithm_design",
        "system_architecture",
        "data_analysis",
        "engineering_practice",
    )
    ability_scores = {
        field: float(getattr(profile, field, 0) or 0)
        for field in ability_fields
    }
    average = sum(ability_scores.values()) / len(ability_scores) if ability_scores else 0
    return {
        "recommended_difficulty": getattr(profile, "preferred_difficulty", 3) or 3,
        "ability_scores": ability_scores,
        "blind_names": [
            item.get("name", "") if isinstance(item, dict) else str(item)
            for item in (profile.knowledge_blind_areas or [])
        ],
        "ability_average": average,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="persist the calculated scores")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        profiles = {
            profile.id: profile
            for profile in db.query(LearnerProfile).all()
        }
        updates = []
        for resource in db.query(LearningResource).all():
            metadata = _content_json(resource).get("match_score_metadata")
            if metadata or resource.match_score not in (None, 0):
                continue
            profile = profiles.get(resource.learner_id)
            if not profile:
                continue
            inputs = _profile_inputs(profile)
            score = ResourceServiceHelper.calculate_match_score(
                recommended_difficulty=inputs["recommended_difficulty"],
                resource_difficulty=resource.difficulty_level or 3,
                ability_scores=inputs["ability_scores"],
                blind_areas=inputs["blind_names"],
                resource_content=resource.content or "",
            )
            updates.append({"resource_id": resource.id, "match_score": score})
            if args.apply:
                content_json = _content_json(resource)
                content_json["match_score_metadata"] = {
                    "formula_version": FORMULA_VERSION,
                    "source": "backfill_match_scores",
                    "recommended_difficulty": inputs["recommended_difficulty"],
                    "resource_difficulty": resource.difficulty_level or 3,
                    "blind_area_count": len(inputs["blind_names"]),
                }
                resource.match_score = score
                resource.content_json = content_json
        if args.apply:
            db.commit()
        print(json.dumps({"apply": args.apply, "updates": updates}, ensure_ascii=False))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
