"""Regression tests for hallucination keyword false positives."""

from app.agents.judge_agent import JudgeAgent


def test_question_explanation_cautious_words_are_not_hallucination():
    content = """
    # 深度学习分阶测试题

    ## 第1题
    更大的学习率可能导致训练不稳定，不一定能改善验证集性能。
    与问题描述相反，梯度爆炸是梯度变得极大。
    """

    result = JudgeAgent().execute({
        "generated_content": content,
        "reference_knowledge": [],
    })

    assert result["hallucination_detected"] is False
    assert all(issue["type"] != "hallucination_keyword" for issue in result["issues"])


def test_unverified_and_absolute_claims_without_evidence_are_reported_as_gap():
    content = "据说这个算法绝对百分百提升准确率。"

    result = JudgeAgent().execute({
        "generated_content": content,
        "reference_knowledge": [],
    })

    assert result["hallucination_detected"] is False
    assert result["credibility"] == "no_evidence"
    assert result["knowledge_gap"]["present"] is True
    assert all(issue["type"] != "hallucination_keyword" for issue in result["issues"])


def test_negated_absolute_words_do_not_trigger_hallucination():
    content = "这两者之间无直接必然联系，通常要结合具体场景判断。"

    result = JudgeAgent().execute({
        "generated_content": content,
        "reference_knowledge": [],
    })

    assert result["hallucination_detected"] is False


def test_keyword_only_language_is_not_a_decisive_issue():
    result = JudgeAgent().execute({
        "generated_content": "这个结论可能需要进一步核实。",
        "reference_knowledge": [{
            "title": "Notes",
            "content": "结论需要核实。",
            "similarity": 0.86,
        }],
    })

    assert result["hallucination_detected"] is False
    assert all(issue["type"] != "hallucination_keyword" for issue in result["issues"])


def test_teaching_context_terms_do_not_trigger_hallucination():
    content = """
    绝对值用于表示数的大小，Transformer 的绝对位置编码和相对位置编码是两种不同方案。
    在一定程度上，批量归一化可以帮助训练稳定，并具有一定的正则化效果，但不一定适用于所有任务。
    """

    result = JudgeAgent().execute({
        "generated_content": content,
        "reference_knowledge": [],
    })

    assert result["hallucination_detected"] is False
    assert all(issue["type"] != "hallucination_keyword" for issue in result["issues"])


def test_multiple_choice_options_do_not_count_as_hallucination_claims():
    content = """
    ## 第1题：迁移学习通常比从零训练更有效，主要原因是？
    - A. 迁移学习不需要数据
    - B. 预训练模型已学习通用低级特征
    - C. 预训练模型一定适用于目标任务

    **答案：B**
    **解析：预训练模型可以复用部分通用特征，但并非一定适用于目标任务。**
    """

    result = JudgeAgent().execute({
        "generated_content": content,
        "reference_knowledge": [],
    })

    assert result["hallucination_detected"] is False
    assert all(issue["type"] != "hallucination_keyword" for issue in result["issues"])
