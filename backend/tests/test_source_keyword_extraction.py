"""Keyword-extraction and disclosure-stripping regressions for source slices."""

from app.utils.resource_content import (
    _fallback_source_keywords,
    normalize_source_keywords,
    strip_fallback_disclosure,
)

LECTURE_SLICE = (
    "特征工程是从原始数据中构造更有预测力的特征的过程。\n"
    "**特征选择**的机制是识别并保留对目标变量有显著影响的特征，"
    "常用的方法有过滤法（如方差阈值、相关系数）和递归特征消除。\n"
    "**特征提取**与**特征构造**分别对应降维与组合变换，"
    "在 Python 的 `scikit-learn` 中可用 `Pipeline` 串接。"
)


def test_fallback_prefers_markdown_emphasis_terms_over_sliding_windows():
    keywords = _fallback_source_keywords(LECTURE_SLICE)
    assert "特征选择" in keywords
    assert "特征提取" in keywords
    # 旧实现的 8 字滑窗碎片不再是关键词
    assert not any(k.startswith("特征工程是从原") for k in keywords)


def test_fallback_extracts_english_technical_terms():
    keywords = _fallback_source_keywords(
        "在 Python 的 scikit-learn 中可用 train_test_split 完成分层采样。"
    )
    assert "scikit" in keywords or "scikit-learn" in keywords
    assert "train_test_split" in keywords


def test_fallback_ngram_terms_are_short_and_deterministic():
    text = (
        "分层采样确保划分后的每个子集保持原始类别比例。"
        "当故障样本仅占少数时，分层采样可以避免评估偏移。"
    )
    first = _fallback_source_keywords(text)
    second = _fallback_source_keywords(text)
    assert first == second
    assert "分层采样" in first
    assert all(len(k) <= 4 or k.isascii() for k in first)


def test_fallback_skips_stopword_windows():
    keywords = _fallback_source_keywords("这个方法可以用于过程，以及一个步骤。")
    assert "这个" not in keywords
    assert "可以" not in keywords


def test_normalize_source_keywords_prefers_explicit_metadata():
    assert normalize_source_keywords(
        ["分层采样"], title="任意标题", content=LECTURE_SLICE
    ) == ["分层采样"]


def test_normalize_source_keywords_falls_back_title_then_content():
    title_keywords = normalize_source_keywords(
        [], title="数据集划分指南", content=LECTURE_SLICE
    )
    # 短标题：整体 + 前缀窗口（去掉“指南”后缀仍可命中正文）
    assert "数据集划分指南" in title_keywords
    assert "数据集划分" in title_keywords
    content_only = normalize_source_keywords([], title="", content=LECTURE_SLICE)
    assert content_only
    assert "特征选择" in content_only


def test_strip_fallback_disclosure_removes_notice_lines():
    content = (
        "参考知识库资料不足，以下为模型生成的通用学习建议。\n"
        "## 一、设备数据采集\n\n设备数据采集是连接物理车间与数字世界的桥梁。"
    )
    stripped = strip_fallback_disclosure(content)
    assert "参考知识库资料不足" not in stripped
    assert stripped.startswith("## 一、设备数据采集")
    assert "物理车间" in stripped


def test_strip_fallback_disclosure_removes_sentence_merged_into_first_line():
    content = (
        "参考知识库资料不足，以下为模型生成的通用学习建议。"
        "本次讲解从原理推导切入，先讲机制，再讲应用边界。"
    )
    stripped = strip_fallback_disclosure(content)
    assert "参考知识库资料不足" not in stripped
    assert stripped.startswith("本次讲解从原理推导切入")
    assert "应用边界" in stripped


def test_strip_fallback_disclosure_removes_mid_line_sentence_keeping_rest():
    content = "分层采样保持类别比例。参考知识库资料不足，以下为模型生成的通用学习建议：请结合产线数据练习。"
    stripped = strip_fallback_disclosure(content)
    assert "参考知识库资料不足" not in stripped
    assert stripped == "分层采样保持类别比例。请结合产线数据练习。"


def test_strip_fallback_disclosure_removes_list_item_notice_line():
    content = "- 参考知识库资料不足，以下为模型生成的通用学习建议。\n- 正常列表项"
    stripped = strip_fallback_disclosure(content)
    assert "参考知识库资料不足" not in stripped
    assert stripped == "- 正常列表项"


def test_strip_fallback_disclosure_keeps_normal_content():
    content = "# 标题\n\n正文讲到：参考知识库资料充足时应当优先引用切片原文，"
    "并说明该流程覆盖了从检索到生成的完整链路。"
    assert strip_fallback_disclosure(content) == content


def test_strip_fallback_disclosure_handles_empty():
    assert strip_fallback_disclosure(None) == ""
    assert strip_fallback_disclosure("") == ""
