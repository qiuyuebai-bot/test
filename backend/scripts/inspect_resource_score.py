"""只读诊断：单个资源的匹配分丢分维度。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models import LearningResource


def main(rid: int):
    db = SessionLocal()
    try:
        r = db.query(LearningResource).filter(LearningResource.id == rid).first()
        if not r:
            print(f"id={rid} 不存在")
            return
        print(f"id={r.id} title={r.title}")
        print(f"resource_type={r.resource_type} difficulty={r.difficulty_level} industry={r.industry}")
        print(f"match_score={r.match_score}")
        cj = r.content_json or {}
        print(f"metadata={cj.get('match_score_metadata')}")
        content = r.content or ""
        print(f"content_len={len(content)}")
    finally:
        db.close()


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 118)
