"""只读验证：重跑后资源匹配分数分布与指标口径一致性。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func

from app.database import SessionLocal
from app.models import LearningResource
from app.services.metric_service import MetricService


def main():
    db = SessionLocal()
    try:
        enabled = db.query(LearningResource).filter(LearningResource.is_enabled.is_(True))
        archived = db.query(LearningResource).filter(
            LearningResource.status == "archived", LearningResource.is_enabled.is_(False)
        )

        total = enabled.count()
        scored = enabled.filter(LearningResource.match_score.isnot(None))
        n = scored.count()
        avg = scored.with_entities(func.avg(LearningResource.match_score)).scalar()
        below_85 = (
            scored.filter(LearningResource.match_score < 85)
            .with_entities(LearningResource.id, LearningResource.title, LearningResource.match_score)
            .all()
        )

        print(f"有效资源={total} 有分数={n} 均值={round(avg or 0, 2)}")
        print(f"归档资源={archived.count()}")
        print(f"低于 85 分的有效资源={len(below_85)}")
        for row in below_85:
            print(f"  id={row.id} {row.title} score={row.match_score}")

        metrics = {m["metric_id"]: m for m in MetricService.calculate_metrics(db, scope="global")}
        rms = metrics["resource_match_score"]
        print(f"指标口径 resource_match_score: value={rms['value']} n={rms['numerator']}/{rms['denominator']} status={rms['status']}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
