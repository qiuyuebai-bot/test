"""默认知识库种子数据的结构回归测试。"""

from app.domains.knowledge.models import IndustryEnum
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
