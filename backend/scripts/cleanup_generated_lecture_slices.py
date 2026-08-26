"""Clean legacy generated-lecture slices in place (no re-slicing).

两件事：
1. 剥离切片 content 中由生成 prompt 注入的“参考知识库资料不足…”声明行
   （存量数据；新发布路径已在 publication_service 剥离）。
2. 为 keywords 为空的切片回填共享提取器产出的术语，供 DB 关键词降级检索、
   Chroma metadata 与覆盖率判分使用。

约束：必须原地更新，不能重建切片——重建会产生新 slice ID，破坏
learning_resources.source_slice_ids 引用与专家标注包溯源。
Chroma 向量按确定性 vector_id（doc_{doc_id}_slice_{index}）upsert 同步。

用法（backend/ 目录下）：
    python -m scripts.cleanup_generated_lecture_slices           # dry-run
    python -m scripts.cleanup_generated_lecture_slices --apply
"""

import argparse
import hashlib
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal  # noqa: E402
from app.domains.knowledge.models import KnowledgeDoc, KnowledgeSlice  # noqa: E402
from app.domains.knowledge.service import (  # noqa: E402
    _CHROMA_AVAILABLE,
    _get_chroma_collection,
)
from app.utils.resource_content import (  # noqa: E402
    normalize_source_keywords,
    strip_fallback_disclosure,
)


def load_docs(db):
    return (
        db.query(KnowledgeDoc)
        .filter(KnowledgeDoc.origin_type == "generated_lecture")
        .order_by(KnowledgeDoc.id)
        .all()
    )


def sync_chroma(doc, slices, changed_ids):
    """Upsert changed slices into Chroma with rebuilt document/metadata."""
    if not changed_ids or not _CHROMA_AVAILABLE:
        if changed_ids:
            print("  [warn] Chroma 不可用，向量文本未同步（下次重建索引时刷新）")
        return 0
    collection = _get_chroma_collection()
    if collection is None:
        print("  [warn] Chroma 集合不可用，向量文本未同步")
        return 0
    ids, documents, metadatas = [], [], []
    for slice_obj in slices:
        if slice_obj.id not in changed_ids:
            continue
        ids.append(f"doc_{doc.id}_slice_{slice_obj.slice_index}")
        documents.append(slice_obj.content)
        metadatas.append(
            {
                "doc_id": str(doc.id),
                "slice_index": str(slice_obj.slice_index),
                "industry": doc.industry or "",
                "slice_type": slice_obj.slice_type or "paragraph",
                "keywords": ",".join(slice_obj.keywords or []),
                "title": slice_obj.title or "",
            }
        )
    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    return len(ids)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="实际写库（默认 dry-run）")
    args = parser.parse_args()

    db = SessionLocal()
    stats = {"docs": 0, "disclosure_stripped": 0, "keywords_backfilled": 0, "chroma_synced": 0}
    try:
        docs = load_docs(db)
        for doc in docs:
            slices = (
                db.query(KnowledgeSlice)
                .filter(KnowledgeSlice.doc_id == doc.id)
                .order_by(KnowledgeSlice.slice_index)
                .all()
            )
            changed_ids: set[int] = set()
            doc_dirty = False
            print(f"doc {doc.id} {doc.title[:30]!r}: {len(slices)} slices")

            for slice_obj in slices:
                stripped = strip_fallback_disclosure(slice_obj.content)
                content_changed = stripped != (slice_obj.content or "")
                if content_changed:
                    stats["disclosure_stripped"] += 1
                    slice_obj.content = stripped
                    slice_obj.content_hash = hashlib.sha256(
                        stripped.encode("utf-8")
                    ).hexdigest()
                    slice_obj.word_count = len(stripped)

                existing_keywords = list(slice_obj.keywords or [])
                if not existing_keywords:
                    backfilled = normalize_source_keywords(
                        [], title=slice_obj.title or "", content=stripped
                    )
                    if backfilled:
                        slice_obj.keywords = backfilled
                        stats["keywords_backfilled"] += 1

                if content_changed or (slice_obj.keywords or []) != existing_keywords:
                    changed_ids.add(slice_obj.id)

            # 文档正文与预览同步剥离，防止未来重建索引时话术回流
            if args.apply and doc.file_path and Path(doc.file_path).exists():
                raw = Path(doc.file_path).read_text(encoding="utf-8")
                stripped_file = strip_fallback_disclosure(raw)
                if stripped_file != raw:
                    Path(doc.file_path).write_text(stripped_file, encoding="utf-8")
                    doc_dirty = True
                    print(f"  doc file stripped: {doc.file_path}")
            if doc.content_preview and strip_fallback_disclosure(doc.content_preview) != doc.content_preview:
                doc.content_preview = strip_fallback_disclosure(doc.content_preview)
                doc_dirty = True

            if changed_ids or doc_dirty:
                stats["docs"] += 1
                if args.apply:
                    stats["chroma_synced"] += sync_chroma(doc, slices, changed_ids)
                    db.commit()
                else:
                    db.rollback()
                mode = "applied" if args.apply else "would apply"
                print(f"  {mode}: {len(changed_ids)} slices updated")

        print(
            f"\n汇总({'APPLY' if args.apply else 'DRY-RUN'}): "
            f"docs={stats['docs']}, 声明剥离={stats['disclosure_stripped']}, "
            f"keywords回填={stats['keywords_backfilled']}, chroma同步={stats['chroma_synced']}"
        )
        if not args.apply:
            print("dry-run 未写库；加 --apply 执行")
    finally:
        db.close()


if __name__ == "__main__":
    main()
