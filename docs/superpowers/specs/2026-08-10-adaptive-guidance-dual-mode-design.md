# 自适应导学双答题模式设计

## 1. 背景

当前自适应导学只有逐题模式：学习者提交一道题后立即获得判分和解析，系统根据结果调整下一题难度。这适合即时反馈与动态适应，但不适合希望连续完成一组题目、最后集中复盘的学习者。

本次新增“整卷练习”，并保留现有“逐题自适应”。两种模式共享学习者选择、主题推荐、题目生成、服务端答案保护、答题记录和能力画像，使用不同的答题与提交状态流。

## 2. 目标与成功标准

### 目标

- 在导学开始前提供 `逐题自适应` 和 `整卷练习` 两种明确选择。
- 逐题模式保持现有行为：每题提交、立即解析、动态生成或调整下一题。
- 整卷模式开始时一次生成全部题目，本轮题目和难度固定。
- 整卷交卷前允许自由切题和修改答案，不返回正确答案或解析。
- 整卷必须全部作答后才能提交；存在未答题时定位到第一道未答题。
- 整卷成功后统一展示总成绩、维度汇总和逐题解析，并一次性更新能力画像。
- 整卷提交具备事务性和幂等性，不产生部分成绩或重复画像更新。
- 未完成整卷可在刷新后从本地草稿恢复。

### 非目标

- 不修改现有逐题自适应难度算法。
- 不增加考试倒计时、暂停次数、监考、乱序或题目版本管理。
- 不建设通用考试平台或服务端草稿会话。
- 不允许模式在会话开始后切换；切换模式必须退出当前会话并重新开始。
- 不在整卷交卷前生成逐题个性化讲解。

## 3. 产品交互

### 3.1 模式选择

`GuidanceLauncher` 在主题和高级设置之前增加分段选择：

- `逐题自适应`：说明“每题提交后立即反馈，下一题会随表现调整”。
- `整卷练习`：说明“一次生成整套题，完成后统一评分与解析”。

默认选择逐题自适应，确保已有用户和旧链接行为不变。选择结果随会话配置保存，但不作为用户永久偏好。

### 3.2 逐题自适应

完全保留现有流程：

```text
生成首题 -> 作答 -> 提交 -> 判分与解析 -> 决定下一题难度 -> 下一题
```

固定难度会话仍可一次生成多题，但继续逐题提交和逐题展示反馈；本次不改变其行为。

### 3.3 整卷练习

开始时按用户选择的主题、题量和难度一次生成完整题集。未显式选择难度时，以当前能力画像或推荐难度确定本卷基准难度；服务端可在生成时形成有限难度分布，但题集生成完成后不再根据本卷答案变化。

答题页包含：

- 顶部会话摘要：模式、主题、进度、已答数量、退出。
- 主答题区：当前题目、选项、上一题、下一题。
- 题号导航：当前题、已答题、未答题三种状态，可直接跳转。
- 底部交卷操作：全部作答前禁用；若通过其他入口触发校验，则提示未完成并跳到第一道未答题。

交卷前答案可反复修改。交卷确认显示“共 N 题，已全部作答”；确认后进入提交状态并暂时锁定操作。提交失败则解除锁定并保留全部答案，不展示解析。

交卷成功进入整卷结果页：

- 总分、正确数、错误数和正确率。
- 按能力维度聚合的正确率及薄弱维度。
- 每道题的题干、用户答案、正确答案、正误、知识点和解析。
- 返回导学首页、重新练习和进入薄弱维度练习的操作。

## 4. 前端状态设计

### 4.1 类型

会话配置增加：

```ts
type GuidanceMode = 'adaptive' | 'batch'

interface SessionConfig {
  mode: GuidanceMode
  topic: string
  difficulty?: number
  questionCount: number
  sessionId: string
}
```

整卷状态增加：

```ts
answersByQuestionId: Record<string, number[]>
batchResult: BatchSubmitResult | null
```

提交状态复用 `phase`，明确增加 `batchReview` 整卷结果阶段。逐题模式继续使用当前 `selectedAnswers`、`showResult` 和 `submitResult`。

### 4.2 状态边界

`useGuidanceSession` 根据 `sessionConfig.mode` 分派行为：

- `adaptive`：复用 `submitAnswer`、`prepareNextQuestion` 和现有反馈状态。
- `batch`：选择答案时写入 `answersByQuestionId`；切题不提交；`submitBatch` 一次调用整卷接口。

模式专属组件保持清晰边界：

- 复用 `GuidanceQuestion` 的题目和选项展示。
- 新增 `BatchQuestionNavigator` 管理题号状态与跳转。
- 新增 `BatchGuidanceResult` 展示整卷汇总和逐题解析。
- `AdaptiveGuidance` 只负责按模式组合组件，不承载评分逻辑。

### 4.3 本地恢复

现有持久化结构升级并兼容旧数据：

```ts
interface PersistedSession {
  config: SessionConfig
  questions: TutoringQuestion[]
  currentQuestion: number
  answersByQuestionId?: Record<string, number[]>
  // 保留已有逐题字段
}
```

旧会话缺少 `mode` 时按 `adaptive` 处理。整卷每次选题、改答和切题后保存草稿；交卷成功或主动退出后清除草稿。服务端题目仍是答案真源，本地数据不包含正确答案和解析。

## 5. 后端设计

### 5.1 题目生成

复用 `POST /api/v1/tutoring/questions/generate`，请求增加可选字段：

```json
{
  "learner_id": 1,
  "topic": "algorithm design",
  "difficulty": 3,
  "question_count": 5,
  "assessment_mode": "batch_practice",
  "session_id": "guidance-..."
}
```

服务端为整卷题目写入 `assessment_mode=batch_practice` 和 `session_id`。公开题目响应继续排除答案键与解析。`session_id` 必须属于当前用户和学习者。

### 5.2 整卷提交接口

新增：

```http
POST /api/v1/tutoring/answers/batch
```

请求：

```json
{
  "learner_id": 1,
  "session_id": "guidance-...",
  "answers": [
    { "question_id": "101", "user_answer": "A", "sequence_index": 1 },
    { "question_id": "102", "user_answer": "B,C", "sequence_index": 2 }
  ]
}
```

服务端在单个数据库事务中：

1. 锁定或条件认领本会话所有 `issued` 的 `batch_practice` 题目。
2. 校验当前用户、学习者、会话归属和题目集合完全一致。
3. 校验答案非空、题目不重复、序号唯一且连续。
4. 使用服务端答案键完成全部评分。
5. 写入所有 `AnswerRecord`，统一关联 `session_id` 和 `sequence_index`。
6. 按 `ability_dimension` 聚合本卷证据，并在本事务内更新一次能力画像。
7. 将本卷题目标记为 `answered`，保存可重复读取的结果摘要。
8. 提交事务后返回整卷结果和逐题解析。

任一步失败时回滚全部记录、题目状态和画像更新。

### 5.3 幂等与结果恢复

以当前用户、学习者和 `session_id` 作为整卷提交幂等键。第一次成功提交后保存结果摘要或通过答题记录稳定重建相同响应。相同答案重复提交返回原结果，不重复更新画像；同一已完成会话提交不同答案返回冲突错误。

若客户端提交成功但丢失响应，再次提交相同载荷可取回结果。前端也可通过结果查询接口或重复提交恢复：

```http
GET /api/v1/tutoring/answers/batch/{session_id}?learner_id=1
```

未完成会话返回 404；越权访问返回 403。

### 5.4 画像更新

整卷不逐题调用现有 `_update_learner_profile`。服务端先按能力维度聚合题数、正确数和难度证据，再调用批量画像更新函数一次。无 `ability_dimension` 的题目计入总成绩，但不改变六维画像。

结果响应至少包含：

```ts
interface BatchSubmitResult {
  sessionId: string
  total: number
  correctCount: number
  score: number
  dimensionSummary: Array<{
    dimension: string
    answeredCount: number
    correctCount: number
    score: number
  }>
  questions: Array<{
    questionId: string
    isCorrect: boolean
    score: number
    userAnswer: string[]
    correctAnswer: string[]
    explanation: string
    knowledgePoints: string[]
  }>
}
```

## 6. 数据模型与迁移

优先扩展现有 `IssuedTutoringQuestion`：

- `assessment_mode` 增加 `batch_practice` 取值。
- 增加可空 `session_id` 并建立用户、学习者、会话复合索引。

为可靠幂等和结果恢复增加轻量整卷提交记录，字段至少包括：

- `user_id`
- `learner_id`
- `session_id`（复合唯一约束）
- `answer_fingerprint`
- `result_summary`
- `submitted_at`

不保存前端草稿。逐题模式和诊断模式的现有数据不迁移、不改语义。

## 7. 错误处理与安全

- 未全部作答：前端阻止；后端仍执行完整性校验并返回 422。
- 题目集合不匹配或重复：返回 409，不写入任何结果。
- 已交卷且答案不同：返回 409，提示刷新查看已提交结果。
- 越权学习者或题目：返回 403，不泄露题目是否存在。
- 题目已被其他流程消费：返回 409，整卷保持本地草稿并允许查看服务端状态。
- 事务或画像更新失败：返回 500，全部回滚，可安全重试。
- 正确答案和解析只出现在成功交卷结果或已完成结果查询中。
- 日志记录用户、学习者、会话和题目数量，不记录明文答案、答案键或令牌。

## 8. 测试与验收

### 前端单元与组件测试

- 启动页默认逐题模式，可切换整卷模式。
- 旧持久化数据恢复为逐题模式。
- 整卷一次生成配置题量，不触发逐题预取。
- 切题和刷新保留每题答案，修改答案覆盖旧值。
- 存在未答题时不能交卷并定位第一道未答题。
- 提交失败保留答案且不显示解析。
- 提交成功锁定答案并展示汇总和全部逐题解析。
- 逐题模式现有 reducer 和页面测试不回归。

### 后端测试

- 整卷生成不泄露答案或解析。
- 完整答案可原子写入答题记录和画像。
- 缺题、额外题、重复题、空答案、错误归属均被拒绝。
- 中途异常回滚所有记录、题目状态和画像变更。
- 相同载荷重复提交返回相同结果，不重复更新画像。
- 不同载荷重复提交返回冲突。
- 结果查询具备用户和学习者权限隔离。
- 无维度题目不改变六维画像。

### E2E

- 逐题模式：提交一题后立即显示解析，并可进入自适应下一题。
- 整卷模式：一次生成完整题集、自由切题、未答阻止交卷、统一展示解析。
- 整卷作答中刷新后恢复草稿。
- 模拟交卷响应丢失后重试，成绩与画像只更新一次。

验证命令包括 `npm run typecheck`、相关 Vitest、后端 tutoring 测试、`npm run build` 和 Playwright 双模式流程。

## 9. 实施顺序

1. 扩展会话类型、请求响应契约和数据库迁移。
2. 实现后端整卷生成标记、事务提交、幂等记录和结果查询。
3. 扩展前端持久化与 reducer，保证旧会话兼容。
4. 在启动页增加模式选择并保持逐题默认行为。
5. 实现整卷题号导航、完整性校验、提交和结果页。
6. 补齐前后端测试和两套 Playwright 流程。

## 10. 风险与假设

- 当前题目生成器最多支持 10 题，整卷首版沿用 1-10 题限制。
- 一次生成全部题目可能比首题生成耗时更长；沿用现有生成中状态和超时，不增加异步任务系统。
- SQLite 开发环境不提供行级锁，使用条件更新、唯一约束和事务保证单进程幂等；生产数据库使用事务与唯一约束处理并发。
- 本地草稿用于体验恢复，不作为可信提交数据；服务端始终重新校验题目归属和答案完整性。
- 逐题模式与整卷模式共享题目生成质量，模式本身不改变知识检索和出题算法。
