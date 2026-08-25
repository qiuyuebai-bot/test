"""一次性脚本：把数据库中已有切片（保留种子标题/关键词）索引到 Chroma。

用法: cd backend && python -m scripts.reindex_existing_slices
仅补齐 is_indexed=0 的切片，不重新切片，不改动切片内容。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal  # noqa: E402
from app.domains.knowledge.models import KnowledgeDoc, KnowledgeSlice  # noqa: E402
from app.domains.knowledge.service import KnowledgeService  # noqa: E402
from loguru import logger  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        docs = db.query(KnowledgeDoc).filter(KnowledgeDoc.is_enabled == True).all()  # noqa: E712
        total_indexed = 0
        failed_docs = 0

        for doc in docs:
            slices = (
                db.query(KnowledgeSlice)
                .filter(
                    KnowledgeSlice.doc_id == doc.id,
                    KnowledgeSlice.is_indexed == False,  # noqa: E712
                )
                .order_by(KnowledgeSlice.slice_index)
                .all()
            )
            if not slices:
                continue

            payload = [
                {
                    "slice_index": s.slice_index,
                    "content": s.content,
                    "slice_type": s.slice_type or "paragraph",
                    "keywords": s.keywords or [],
                    "title": s.title or "",
                }
                for s in slices
                if (s.content or "").strip()
            ]
            if not payload:
                continue

            try:
                vector_ids = KnowledgeService._index_slices_to_chroma(
                    doc.id, doc.industry, payload
                )
            except Exception as exc:
                failed_docs += 1
                logger.error(f"doc_id={doc.id} ({doc.title}) 索引失败: {exc}")
                continue

            by_index = {p["slice_index"]: vid for p, vid in zip(payload, vector_ids)}
            for s in slices:
                vid = by_index.get(s.slice_index)
                if vid:
                    s.vector_id = vid
                    s.is_indexed = True
            db.flush()  # SessionLocal 为 autoflush=False，必须先 flush 再统计

            doc.indexed_slice_count = (
                db.query(KnowledgeSlice)
                .filter(
                    KnowledgeSlice.doc_id == doc.id,
                    KnowledgeSlice.is_indexed == True,  # noqa: E712
                )
                .count()
            )
            total_indexed += len(vector_ids)
            db.commit()
            print(f"[OK] doc_id={doc.id} {doc.title}: +{len(vector_ids)} slices")

        print(f"\n完成: 新索引 {total_indexed} 个切片, 失败文档 {failed_docs} 个")
    finally:
        db.close()


if __name__ == "__main__":
    main()
