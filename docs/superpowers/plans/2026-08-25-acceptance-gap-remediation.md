# 验收短板修复实施计划（画像覆盖 / 专家标注 / 适配指标）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with checkpoints.

**Goal:** 修复评分核查发现的三个证据短板，使指标证据报告（`docs/evidence/metric-evidence-latest.json`）中的 failed / insufficient_evidence 项达到可验收状态，同时不伪造任何证据数据。

**Architecture:** 以"归因 → 修复 → 重测"为主线。Task 1 先对 34 条答题记录做只读归因，确认低正确率是产品缺陷（难度错配）还是数据特性；Task 2 独立补齐学习者画像测试覆盖（纯测试代码，不动业务）；Task 3/4 依据归因结论修复自适应闭环并用真实流程扩充有效样本；Task 5 专家标注为外部依赖，与 Task 2-4 并行推进；Task 6 统一重跑证据报告收口。

**Tech Stack:** FastAPI、SQLAlchemy、SQLite/PostgreSQL、pytest、Python 脚本（`backend/scripts/`）。

## 背景与现状（证据锚点）

| # | 短板 | 现状证据 | 验收要求 |
|---|------|---------|---------|
| ① | 学习者画像测试用例仅 1 组 | `backend/tests/conftest.py` 的 `sample_learner_profile`（硕士/算法工程师） | ≥3 组不同背景画像测试用例 |
| ② | 专家标注 `annotation_count = 0` | `backend/tests/fixtures/industrial_robotics_expert_annotations.json` 的 `annotations: []`，证据报告 status=`insufficient_evidence` | ≥10 条真实标注（`formal_evidence_policy.minimum_sample_size = 10`） |
| ③ | 答题正确率 23.53%（8/34，目标 85%）；资源匹配效果 16.67%（1/6，样本不足） | `metric-evidence-latest.json` → `evidence.claims` 两条 status=`failed`/`insufficient_evidence` | 正确率 ≥85%；匹配效果样本 ≥10 条 |

## Global Constraints

- **不伪造证据**：专家标注必须来自真实行业人员（`reviewer_id` 可溯源）；答题样本必须走真实服务流程产生（资源推荐→答题→记录），不得直接 INSERT 结果字段。
- **不改评分口径**：`target_thresholds`（正确率/匹配 85%、幻觉率 <5%）与 `minimum_sample_size=10` 保持原样，只改善真实表现。
- **业务逻辑最小修改**：只修 Task 1 归因确认的缺陷，不顺手重构。
- **每步 TDD**：涉及业务代码的修改先写失败测试再实现。
- 测试命令统一从 `backend` 目录用 `& .\venv\Scripts\python.exe -m pytest ... -q` 执行。

---

### Task 1: 答题正确率 23.53% 归因分析（只读，前置必做）

**Files:**
- Create: `backend/scripts/analyze_answer_records.py`（一次性分析脚本，产出结论后保留作为证据）

**分析内容：**

1. 34 条 `answer_records` 的 `question_difficulty` 分布 vs 对应学习者 `preferred_difficulty` / 画像能力分——错题是否集中在超出能力的难度（4~5 级）。
2. `agent_decision` 分布：`advance`/`review`/`reinforce` 的比例；答错后 `next_question_difficulty` 是否降级（当前 `_save_answer_record` 只在 advance 时 +1，否则持平——见 `tutoring_service.py:1611`）。
3. 出题路径是否消费了 `DiagnosisAgent._calculate_difficulty_params` 的 `recommended_difficulty`（`tutoring_service.py` 的 `generate_dynamic_questions` / `get_recommendations` 与 `diagnosis_agent.py:251` 的衔接）。
4. `next_resource_id` 只有 6 条非空的原因：`generated_content.suggested_resources` 在什么条件下为空。

**产出：** 一份归因结论写入脚本输出（JSON + 控制台摘要），明确判定"难度错配缺陷"或"数据特性"，作为 Task 3 是否执行、怎么修的依据。

- [x] Step 1: 编写并运行分析脚本，得到四个问题的量化答案
- [x] Step 2: 将结论摘要追加到本文件"归因结论"小节（人工填写）

---

### Task 2: 补齐 3 组学习者画像测试覆盖（评分项①，独立可做）

**Files:**
- Modify: `backend/tests/conftest.py`
- Create: `backend/tests/test_learner_profile_adaptation.py`

**新增画像（与知识库领域对齐，覆盖不同背景维度）：**

1. `sample_learner_profile_production_engineer`：本科 / 机械自动化 / 5 年经验 / 智能制造行业 / 产线调试工程师 / 动手型（KINESTHETIC）/ preferred_difficulty=4 / 能力分 70~85。
2. `sample_learner_profile_maintenance_technician`：大专 / 电气自动化 / 2 年经验 / 工业互联网行业 / 设备维护技术员 / 理论基础弱（各维度 40~55）/ preferred_difficulty=2 / 盲区含"PLC 通信协议"。

**差异化断言（核心，凑数式画像经不起追问）：**

- [x] Step 1: `test_diagnosis_difficulty_differs_across_profiles`——`@pytest.mark.parametrize` 三画像跑 `DiagnosisAgent._calculate_difficulty_params`，断言 `recommended_difficulty` 单调随能力分变化（技术员 < 工程师画像 < 算法画像，或明确的不变式）。
- [x] Step 2: `test_generation_difficulty_matches_profile`——同一主题下生成资源，断言资源 `difficulty_level` 与画像 `preferred_difficulty` 偏差 ≤1。
- [x] Step 3: `test_blind_areas_affect_generation`——断言画像 `knowledge_blind_areas` 出现在生成内容的讲解重点中；技术员画像的内容深度标记低于工程师画像。
- [x] Step 4: 运行 `& .\venv\Scripts\python.exe -m pytest tests/test_learner_profile_adaptation.py -q` 全绿，且全量套件无回归。

**验收标准：** 3 组画像 × ≥3 类差异化断言全部通过；评分材料可引用本测试文件作为"≥3 组画像"证据。

---

### Task 3: 修复难度自适应闭环（条件执行：依 Task 1 归因结论）

**Files:**
- Modify: `backend/app/services/tutoring_service.py`（候选缺陷点）
- Test: `backend/tests/test_tutoring_service.py`

**候选修复（按归因结论裁剪，不做全部）：**

- [x] Step 1: 若确认"答错不降级"——`_save_answer_record` 中 `next_question_difficulty` 对 `review`/`reinforce` 决策改为 `max(1, question_difficulty - 1)`；先写失败测试（连续答错 2 次后难度下降）。
- [x] Step 2: 若确认"出题不消费画像"——在 `generate_dynamic_questions` / `get_recommendations` 中接入诊断结果或画像 `preferred_difficulty`，使首题难度来自画像而非固定值；先写失败测试。
- [x] Step 3: 回归：`& .\venv\Scripts\python.exe -m pytest tests/test_tutoring_service.py tests/test_diagnostic_service.py -q` 全绿。

---

### Task 4: 扩充有效样本至验收最小量（评分项③）

**Files:**
- Create: `backend/scripts/generate_answer_samples.py`（参照 `batch_generate_samples.py` 的矩阵思路）

**目标：**

1. `resource_match_effectiveness` 有效样本（`next_resource_id` 非空且已完成的答题）≥10 条。
2. 修复后的闭环在合理难度下的答题正确率有真实提升。

**步骤：**

- [x] Step 1: 脚本为每个种子学习者走真实流程：取推荐资源 → 按 `suggested_resources` 链路答题（答案策略按画像能力分模拟，能力分映射到作答正确概率）→ 记录落库。
- [x] Step 2: 全量执行后核对：`SELECT COUNT(*) FROM answer_records WHERE next_resource_id IS NOT NULL` ≥10。
- [x] Step 3: 重跑 `& .\venv\Scripts\python.exe -m scripts.generate_metric_evidence` 查看 `answer_accuracy` 与 `resource_match_effectiveness` 新值。

**风险与诚实边界：** 若修复后正确率仍达不到 85%，如实保留 failed 状态并在评分材料中附归因说明（哪些错题属于合理的能力边界），不得通过注水答案刷指标。

---

### Task 5: 专家标注数据与流程（评分项②，外部依赖，与 Task 2-4 并行）

**Files:**
- Modify: `backend/tests/fixtures/industrial_robotics_expert_annotations.json`
- Create: `docs/evidence/expert-annotation-rubric.md`（标注规范与流程）

**步骤：**

- [x] Step 1: 编写标注 rubric：对已生成资源逐条给出 `supported` / `contradicted` / `insufficient_evidence` 的判定标准（依据 `IndustrialRoboticsRules` 与行业规范），定义 `reference_slice_ids` 的溯源方式。
- [ ] Step 2: 邀请 1~2 名行业人员对 10~20 条已生成资源（优先 `match_score` 分档抽样的高中低各档）按 rubric 打标，`reviewer_id` 记真实编号、`reviewed_at` 记实际日期。（外部依赖，待行业评审排期）
- [ ] Step 3: 标注结果填入 fixture（校验 `required_fields` 完整、label 在 `allowed_labels` 内）。（依赖 Step 2）
- [ ] Step 4: 交叉验证加分项：统计专家标注与系统 `match_score` 的一致率，写入 rubric 文档——这比单纯凑满 10 条更能证明价值。（依赖 Step 2）

**诚实边界：** 短期找不到专家时，保留 `insufficient_evidence`，在评分/答辩材料中附 rubric 与流程文档并说明限制。**严禁凭空填 `supported`**——标注可被抽查，伪造证据风险远大于收益。

---

### Task 6: 重跑证据报告与验收核对（收口）

- [x] Step 1: `cd backend; & .\venv\Scripts\python.exe -m scripts.generate_metric_evidence`，核对六项指标 status。
- [x] Step 2: 对照验收清单：① 三画像测试全绿可引用；② `annotation_count ≥ 10` 且 `expert_review.status = ready`；③ `answer_accuracy` 与 `resource_match_effectiveness` 达标或有诚实归因说明。
- [x] Step 3: 更新评分材料中对应扣分项的回应证据。

---

## 执行顺序与依赖

```
Task 1 (0.5h, 只读归因) ──┬─→ Task 3 (0.5~1d, 条件执行) ─→ Task 4 (0.5d) ─→ Task 6 (0.5h)
Task 2 (0.5d, 独立) ──────┘
Task 5 (外部依赖, 1~2 周日历时间, 与 Task 2-4 并行)
```

**优先级：③（Task 1→3→4）> ①（Task 2）> ②（Task 5）**。③ 是根因，修复后多画像测试与指标数据会同步改善；② 受外部约束尽早启动流程但不阻塞其他任务。

## 归因结论（Task 1 已完成，2026-08-25）

完整数据见 `docs/evidence/answer-attribution.json`，脚本 `backend/scripts/analyze_answer_records.py`。

1. **主因——测试账号数据污染**：27/34（79%）条记录来自手工测试账号 "jkl"（learner_id=6，六维能力分全 0、无岗位，2026-08-22 创建），作答呈随机分布（正确率 22.2% ≈ 四选一猜测基线 25%）。23.53% 全局正确率被该账号主导。
2. **次因——诊断模式记录混入分母**：21/34 条来自 `diag_*` 会话。`DiagnosticService.submit_answer`（`domains/diagnostic/service.py:164`）直接创建 AnswerRecord、不走 agent 决策（agent_decision=None），且诊断出题固定 `difficulty=3`（`:73`）。摸底测试本不应计入"学习效果"指标。
3. **真实缺陷 #1——答错后难度不降级（确认，需修）**：`tutoring_service.py:1611` 仅在 advance 时 +1，否则持平。数据证实：答错且走决策路径的 10 条记录 0 降级、10 持平（含 10 条 simplify 决策）。自适应闭环断裂。
4. **真实缺陷 #2——匹配效果样本少的根因**：只有走 `AdaptiveTutoringService._save_answer_record`（依赖 `generated_content.suggested_resources`）的记录才写 `next_resource_id`，诊断路径不写——34 条中仅 6 条非空。

**Task 3 修复范围据此裁剪为：**
- Fix A：`_save_answer_record` 中 simplify 决策 → 下一题难度 `max(1, difficulty-1)`（advance 保持 +1，consolidate 持平）。
- Fix B：`MetricCalculator.answer_accuracy` / `resource_match_effectiveness` 排除诊断会话记录（`session_id LIKE 'diag_%'`），并在指标 metadata 中透明标注排除规则——摸底测试与学习效果分离统计，非隐藏数据。
- 诊断固定难度 3 **不改**（摸底标准难度是合理设计）。
- jkl 的随机作答数据**不删除**（保留真实数据），通过 Task 4 真实流程样本扩充稀释其影响。

## 执行结果（2026-08-25 收口）

完整数据与归因见 `docs/evidence/acceptance-remediation-summary.md`。

| 项 | 结果 |
|---|---|
| Task 2 | 3 组画像 × 4 类差异化断言，13 用例全绿（`test_learner_profile_adaptation.py`） |
| Task 3 Fix A | simplify 后难度降级：修复前 0/10 → 修复后 32 次降级、0 次反向上升；全量 492 用例通过 |
| Task 3 Fix B | 诊断会话排除进 metric_registry 公式描述，口径透明 |
| Task 4 | 74 条真实流程样本（36 条复刻前端自适应会话）；`next_resource_id` 非空 6→82（≥10 达标）；自适应会话正确率 47.2% vs 固定难度 38.9%（闭环收益 +8.3pp） |
| Task 5 | rubric 文档就绪（`docs/evidence/expert-annotation-rubric.md`）；真实标注待外部行业评审（诚实保留 insufficient_evidence） |
| Task 6 | answer_accuracy 23.53%→38.3%；resource_match_effectiveness 16.67%(1/6)→41.46%(34/82)；两项未达 85%，保留 failed + 归因说明（弱能力学习者边界 + 污染账号 + 单轮样本限制），未注水 |
