"""P1-6 回归测试：超长段落/句子切片不应重复"""
from app.utils.text_slice import TextSliceUtil


def test_long_paragraph_not_duplicated():
    """slice_by_paragraph：超长段落只应被分割为子切片，不应再被追加到 current_slice"""
    long_para = "A" * 3000
    text = f"短段落1\n{long_para}\n短段落2"

    slices = TextSliceUtil.slice_by_paragraph(text, max_length=1000)

    total_chars = sum(len(s["content"].replace("\n", "")) for s in slices)
    original_chars = len(text.replace("\n", ""))

    assert total_chars <= original_chars, (
        f"切片内容总长({total_chars})超过原始({original_chars})，存在重复"
    )

    long_para_slice_count = sum(1 for s in slices if s.get("slice_type") == "paragraph_split")
    assert long_para_slice_count >= 1, "超长段落应产生 paragraph_split 类型切片"


def test_long_paragraph_content_not_in_other_slices():
    """超长段落内容不应出现在普通 paragraph 切片中"""
    long_para = "B" * 2500
    text = f"开头\n{long_para}\n结尾"

    slices = TextSliceUtil.slice_by_paragraph(text, max_length=1000)

    for s in slices:
        if s.get("slice_type") != "paragraph_split":
            assert "B" * 100 not in s["content"], (
                "普通切片不应包含超长段落内容（P1-6 重复缺陷）"
            )


def test_normal_paragraph_slicing_still_works():
    """正常段落切片不受影响"""
    text = "段落一\n段落二\n段落三"
    slices = TextSliceUtil.slice_by_paragraph(text, max_length=1000)

    assert len(slices) >= 1
    all_content = "\n".join(s["content"] for s in slices)
    for para in ["段落一", "段落二", "段落三"]:
        assert para in all_content


def test_slice_by_semantic_long_sentence_not_duplicated():
    """slice_by_semantic：超长句子同样不应重复（该路径已有 continue）"""
    long_sentence = "C" * 3000
    text = f"正常句子。{long_sentence}。结束"

    slices = TextSliceUtil.slice_by_semantic(text, max_length=1000)

    total_chars = sum(len(s["content"].replace("。", "")) for s in slices)
    original_chars = len(text.replace("。", ""))

    assert total_chars <= original_chars, (
        f"语义切片内容总长({total_chars})超过原始({original_chars})，存在重复"
    )
