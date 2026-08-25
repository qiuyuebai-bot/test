# 工业机器人领域专家标注规范与流程（Expert Annotation Rubric）

> 版本 1.0 · 2026-08-25 · 对应 fixture：`backend/tests/fixtures/industrial_robotics_expert_annotations.json`
>
> 目的：以可溯源、可抽查的方式证明系统生成的学习内容"贴合行业实际规范"，为证据报告
> `metric-evidence-latest.json` 中 `expert_review` 项提供真实标注支撑。

## 1. 范围与标注对象

- **领域**：工业机器人 / 智能制造（`domain: industrial_robotics`）。
- **标注对象**：已生成并通过校验的学习资源（`learning_resources` 表，`status` 为可用态）。
- **抽样策略**：按系统 `match_score` 分档抽样，高/中/低三档各取 3~7 条，合计 10~20 条，避免只标高分资源造成偏差。抽样 SQL：

```sql
-- 高档：match_score >= 80
SELECT id, title, knowledge_topic, match_score FROM learning_resources
 WHERE match_score >= 80 AND is_enabled = 1 ORDER BY match_score DESC LIMIT 5;
-- 中档：60 <= match_score < 80
SELECT id, title, knowledge_topic, match_score FROM learning_resources
 WHERE match_score >= 60 AND match_score < 80 AND is_enabled = 1 LIMIT 5;
-- 低档：match_score < 60（含 NULL，需回填后标）
SELECT id, title, knowledge_topic, match_score FROM learning_resources
 WHERE match_score < 60 AND is_enabled = 1 LIMIT 5;
```

## 2. 标签定义（allowed_labels）

判定依据：生成内容 vs 参考知识切片（`source_slice_ids` 指向的 `knowledge_slices`），
并结合 `IndustrialRoboticsRules`（`backend/app/utils/industry_rules.py`）的行业规则与
通用行业规范（安全类参照 ISO 10218 / ISO/TS 15066 表述习惯）。

### 2.1 `supported`（内容有据、合规）

同时满足以下全部条件：

1. **论断有源**：内容中的核心技术论断（定义、参数、步骤、结论）能在参考切片中找到直接支持，或属于该岗位公认常识（如"急停回路属于安全功能"）。
2. **数值与单位合规**：负载/载荷表述带 kg（或 N）单位；重复定位精度带 mm/μm 单位；出现具体数值时可溯源或与行业标准一致。
3. **无主题混淆**：内容主题与参考资料主题一致（不出现"参考资料只讲维护、内容却大篇幅讲坐标系"这类错位）。
4. **无安全违规表述**：不含"无需急停/可以跳过安全/不必设置围栏/绝对安全"等可能导致跳过安全控制的表述。

### 2.2 `contradicted`（内容与证据或规范冲突）

出现任一情形即判：

1. 核心论断与参考切片内容直接矛盾（如参数、方向、步骤颠倒）。
2. 触发行业规则中的高危问题：主题混淆（`industry_topic_confusion`）、安全违规表述（`industry_safety_violation`）。
3. 数值/单位错误且超出合理工程误差（如把 0.02 mm 重复定位精度写成 0.02 cm）。

### 2.3 `insufficient_evidence`（证据不足，无法判定）

既不能确认也不能证伪时使用——**这是诚实标签，不是"错误"**：

1. 参考切片未覆盖内容的论断范围（内容讲了切片没讲的东西，且非公认常识）。
2. 缺少可核查的数值/单位（如谈负载但无 kg/N 单位），无法核实是否正确。
3. 参考切片本身互相矛盾，无法仲裁。

## 3. reference_slice_ids 溯源方式

每条标注必须携带 `reference_slice_ids`，按以下方式取得，保证评审员看到的内容与系统判分用到的证据一致：

1. 从 `learning_resources.source_slice_ids` 读取该资源生成时引用的切片 ID 列表。
2. 按 ID 回查 `knowledge_slices` 表（`id`、`title`、`content`），作为参考资料原文。
3. 标注表单**并排展示**：左列 = 生成内容全文（`learning_resources.content`），右列 = 全部参考切片原文。评审员逐条对照打标。
4. 若 `source_slice_ids` 为空，该条资源仍可标注，但默认倾向 `insufficient_evidence`（无源可溯）。

## 4. 标注流程

| 步骤 | 内容 | 产出 |
|------|------|------|
| 1. 导出标注包 | 按 §1 抽样，导出 CSV（资源 ID、标题、生成内容、参考切片全文、系统 match_score 隐藏列） | 标注包 + 空白标注表 |
| 2. 评审员培训 | 30 分钟讲解 rubric 与 3 个校准样例（每类标签 1 个） | 评审员理解一致性确认 |
| 3. 独立标注 | 1~2 名行业人员**独立**逐条打标，不互相讨论、不看系统分数 | 标注表（含标签 + 备注） |
| 4. 仲裁 | 两人标签不一致的条目由第三人或讨论仲裁，保留仲裁记录 | 最终标签 |
| 5. 回填 fixture | 按 §5 格式填入 JSON，`reviewer_id` 记真实编号（如工号/姓名缩写+序号），`reviewed_at` 记实际日期 | fixture 更新 |
| 6. 校验 | 脚本校验 `required_fields` 完整、`expert_label` 在 `allowed_labels` 内 | 校验通过 |

**评审员要求**：工业机器人/自动化相关岗位在职人员，≥2 年现场经验（调试、维护、集成或培训岗均可）。

## 5. fixture 记录格式

```json
{
  "case_id": "res_0001",
  "topic": "机器人坐标系",
  "generated_content": "……资源内容摘录（保留核心论断句）……",
  "reference_slice_ids": [101, 102],
  "expert_label": "supported",
  "reviewer_id": "EXP-01",
  "reviewed_at": "2026-09-01",
  "notes": "坐标变换描述与切片101一致；TCP 定义正确"
}
```

- `case_id`：`res_` + 资源 ID，可直接回查 `learning_resources`。
- `notes` 可选，记录判定依据（哪条切片、哪个规则）。
- 其余字段为 `required_fields`，缺失即校验失败。

## 6. 交叉验证（系统分数 vs 专家标注）

标注完成后计算两项指标写入本节（模板如下）：

1. **分档一致率**：高档（match_score≥80）中 `supported` 占比 + 低档（<60）中非 `supported` 占比，二者的均值。越接近 1 说明系统打分与专家判断越一致。
2. **矛盾检出率**：`contradicted` 条目中系统 `hallucination_detected=0` 的占比，反映专家能发现系统漏检的问题。

```
（待标注完成后填写）
- 标注条数：N（高档 x / 中档 y / 低档 z）
- 分档一致率：0.xx
- 矛盾检出率：0.xx
- 结论一句话：……
```

## 7. 诚实边界（红线）

1. **严禁凭空填 `supported`**：标注必须由真实评审员对照参考切片作出，可被抽查复核；伪造证据的风险远大于短期收益。
2. 标注未完成前，fixture 保持 `annotations: []`，证据报告 `expert_review.status` 维持 `insufficient_evidence`，并在评分/答辩材料中附本文档说明"流程已就绪、等待外部评审"。
3. `insufficient_evidence` 是合法结果：它说明该条内容需要补充知识库证据，而不是系统失败；对应改进动作是扩充知识切片而非改标签。
4. 系统已有的 `IndustrialRoboticsRules` 自动检查结果（主题混淆/单位缺失/安全违规）可作为评审员的**辅助线索**，但最终标签以人工判断为准，不得直接抄机器结果。
