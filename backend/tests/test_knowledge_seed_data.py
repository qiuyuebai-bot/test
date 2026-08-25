"""默认知识库种子数据的结构和兼容性回归测试。"""

import hashlib

from sqlalchemy.orm import sessionmaker

from app.domains.knowledge.models import IndustryEnum
from app.domains.knowledge.models import KnowledgeDoc, KnowledgeSlice
from app.utils.seed_loader import load_seed_payload


def test_knowledge_seed_covers_requested_learning_domains():
    payload = load_seed_payload("knowledge.json")
    records = payload["records"]
    supported_industries = {item.value for item in IndustryEnum}

    assert len(records) == payload["_meta"]["expected_documents"]
    assert len({item["code"] for item in records}) == len(records)
    assert len({item["file_name"] for item in records}) == len(records)
    assert all(item["industry"] in supported_industries for item in records)
    assert sum(len(item["slices"]) for item in records) == payload["_meta"]["expected_slices"]
    assert all(
        len(item["slices"]) >= 5
        and all(slice_item["content"].strip() for slice_item in item["slices"])
        for item in records
    )

    titles = " ".join(item["title"] for item in records)
    for topic in (
        "网络安全",
        "电气工程及其自动化",
        "微积分",
        "线性代数",
        "抽象代数",
        "离散数学",
        "模拟电路",
        "数字电路",
        "计算机网络",
        "操作系统",
        "人工智能",
        "大学物理",
    ):
        assert topic in titles


def test_knowledge_seed_backfills_existing_seed_document(db_session, monkeypatch, tmp_path):
    """旧版已有文档时只补缺失切片，重复执行不会重复创建。"""
    from app import seed_data
    from app.config import settings

    payload = load_seed_payload("knowledge.json")
    item = payload["records"][0]
    doc = KnowledgeDoc(
        title=item["title"],
        industry=item["industry"],
        category=item["category"],
        file_name=item["file_name"],
        file_path=str(tmp_path / item["file_name"]),
        slice_count=3,
        status="ready",
        origin_type="seed",
        is_enabled=True,
    )
    db_session.add(doc)
    db_session.flush()
    for index, slice_item in enumerate(item["slices"][:3]):
        content = slice_item["content"]
        db_session.add(KnowledgeSlice(
            doc_id=doc.id,
            slice_index=index,
            content=content,
            content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            title=slice_item["title"],
            slice_metadata={"seed": True, "source_code": item["code"]},
            keywords=slice_item["keywords"],
        ))
    db_session.commit()

    test_session_factory = sessionmaker(bind=db_session.get_bind())
    monkeypatch.setattr(seed_data, "SessionLocal", test_session_factory)
    monkeypatch.setattr(settings, "KNOWLEDGE_DOC_DIR", str(tmp_path))

    seed_data.init_knowledge_seed_data()
    seed_data.init_knowledge_seed_data()

    refreshed = db_session.query(KnowledgeDoc).filter_by(file_name=item["file_name"]).one()
    slices = db_session.query(KnowledgeSlice).filter_by(doc_id=refreshed.id).all()
    assert len(slices) == 5
    assert refreshed.slice_count == 5
    assert {slice_item.title for slice_item in slices} == {
        slice_item["title"] for slice_item in item["slices"]
    }
