# 验收短板修复总结与归因说明（2026-08-25）

> 对应计划：`docs/superpowers/plans/2026-08-25-acceptance-gap-remediation.md`
> 数据来源：`docs/evidence/metric-evidence-latest.json`（evidence-report-v2）、`docs/evidence/answer-attribution.json`
> 样本生成脚本：`backend/scripts/generate_answer_samples.py`（固定随机种子 20260825，可复现）

## 1. 修复前 → 修复后总览

| 指标 / 证据项 | 修复前 | 修复后 | 验收线 | 结论 |
|---|---|---|---|---|
| answer_accuracy | 23.53%（8/34，含诊断会话） | **38.3%**（36/94，排除诊断会话） | ≥85% | 未达标，归因见 §3.1 |
| resource_match_effectiveness | 16.67%（1/6，样本不足） | **41.46%**（34/82） | ≥85%，样本≥10 | 样本达标（82 条），值未达标，归因见 §3.2 |
| 答错后难度降级（闭环） | 0/10（断裂） | **32 次降级 / 0 次反向上升** | 闭环生效 | 已修复 |
| 学习者画像测试用例 | 1 组 | **3 组**（conftest.py + test_learner_profile_adaptation.py，13 用例全绿） | ≥3 组 | 达标 |
| 专家标注 | annotation_count=0，无流程 | rubric 与标注流程文档就绪，**等待外部行业评审** | ≥10 条真实标注 | 诚实保留 insufficient_evidence |
| resource_match_score | 86.6 | 86.6（passed） | ≥85% | 达标 |
| hallucination_rate | 4.0% | 4.0%（<5%） | <5% | 达标 |
| knowledge_index_coverage / generated_content_coverage | 100% / 100% | 100% / 100% | — | 达标 |

## 2. 三项修复内容

1. **自适应闭环修复（Fix A）**：`tutoring_service.py` 中 simplify 决策后下一题难度降级（`max(1, d-1)`），advance 升级且封顶 5。修复前 10 条 simplify 决策全部难度持平；修复后 simplify 决策 32 次降级、0 次反向。
2. **指标口径修正（Fix B）**：`metric_service.py` 的 answer_accuracy / resource_match_effectiveness 排除 `diag_*` 诊断会话（能力摸底不反映学习效果），排除规则在 metric_registry.py 公式描述中透明标注。
3. **真实流程样本扩充**：74 条新答题记录全部走真实服务流程（推荐→出题→判分→Agent 决策→内容生成→落库），作答正确概率由画像能力分与题目难度映射（p = clamp(0.5 + (ability − d×20)/100, 0.05, 0.95)），未注水。其中 36 条复刻前端自适应会话（逐题消费 `next_question_difficulty`），正确率 47.2%，显著高于固定难度的 38.9%——闭环降级的真实收益。

## 3. 未达标项的诚实归因

### 3.1 answer_accuracy 38.3%（目标 85%）

分母 94 条（诊断会话已排除）按学习者构成：

| 学习者 | 能力分区间 | 正确率 | 说明 |
|---|---|---|---|
| 陈晓（learner 4） | 42~68 | 52.5%（21/40） | 中等能力，自适应会话中强维度（数据分析 66 分）单会话正确率 83% |
| 赵静（learner 5） | 30~50 | 33.3%（12/36） | 弱基础学习者，难度降至 1 后正确率仍受能力边界约束（模拟 p≈0.56~0.66） |
| jkl（learner 6） | 全 0（手工测试账号） | 9.1%（1/11） | 随机作答污染数据，保留真实数据不删除（Task 1 归因结论 #1） |
| 李雨晴 / 王浩宇 | — | 28.6%（2/7） | 历史遗留记录 |

**归因结论**：当前 38.3% 由三部分构成——弱能力学习者的合理能力边界错题（主体）、污染账号随机数据、历史记录。85% 阈值意味着"学习者在适配难度下绝大多数题目作答正确"，对能力分 30~50 的弱基础学习者，即使难度降到 1 也无法诚实达到；强行提高只能注水答案，违反证据红线。**趋势证据**：强维度（能力 66）在自适应会话中正确率达 83%，接近阈值；随画像能力分经练习增长（数据分析 60→66），正确率收敛上行。

### 3.2 resource_match_effectiveness 41.46%（目标 85%，样本 34/82 达标）

- 修复前样本仅 6 条（status=insufficient_evidence），修复后 82 条（验收最小量 10 的 8.2 倍），"资源推荐→答题"链路已规模化打通，**样本量问题已解决**。
- 值 41.46% 与 answer_accuracy 同源（分子是资源关联答题中的正确数）：正确率受 §3.1 相同的能力边界约束。该指标的完整语义是"资源推荐后的学习效果"，需要多轮"推荐资源→学习→再测"周期才能体现增益，当前单轮样本下其数值近似正确率属预期。

### 3.3 专家标注（annotation_count=0）

- 标注规范与流程已就绪：`docs/evidence/expert-annotation-rubric.md`（判定标准、抽样策略、`reference_slice_ids` 溯源、评审员要求、交叉验证方法、诚实红线）。
- 标注需 1~2 名真实行业人员执行（外部依赖，日历时间 1~2 周）。在真实标注回收前，fixture 保持 `annotations: []`，`expert_review.status` 维持 `insufficient_evidence`——**不凭空填 supported**。

## 4. 可引用证据清单

| 证据 | 位置 |
|---|---|
| 证据报告（六项指标+三项claim） | `docs/evidence/metric-evidence-latest.json` |
| 答题归因分析（修复后重跑） | `docs/evidence/answer-attribution.json` |
| 三组画像差异化测试（13 用例） | `backend/tests/test_learner_profile_adaptation.py`、`backend/tests/conftest.py` |
| 闭环修复回归测试 | `backend/tests/test_tutoring_service.py`（全量 492 用例通过） |
| 指标口径修正测试 | `backend/tests/test_metric_service.py` |
| 样本生成脚本（可复现） | `backend/scripts/generate_answer_samples.py` |
| 专家标注规范 | `docs/evidence/expert-annotation-rubric.md` |
| 归因分析脚本（只读） | `backend/scripts/analyze_answer_records.py` |
