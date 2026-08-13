# 岗位培训场景功能完善 - 会话操作记录

- **日期**：2026-08-12
- **分支**：`feat/career-training-frontend-phase5` → 合并至 `main`
- **主题**：增添岗位培训场景的功能（待完善）
- **最终提交**：`dea9bd4`（已推送至 `origin/main`）

---

## 一、会话目标

在已有"岗位-胜任力-学习-认证"能力平台基础上，完善岗位培训场景的交互与功能闭环，主要解决：
1. 评估模板缺少创建入口
2. Modal 弹窗关闭按钮被内容顶出屏幕
3. 能力评估与学习计划页面因字段命名不匹配导致报错
4. 学习计划缺少培训项目创建入口
5. "生成计划"按钮无响应 / 提示"尚未加入此项目"

---

## 二、任务清单与实现详情

### 任务 1：新增评估模板功能

**问题**：能力评估 Tab 只有"选择已有模板"流程，没有创建模板的 UI 入口。后端 `POST /assessments/templates` 和前端 `trainingApi.createAssessmentTemplate` 已存在，仅缺界面。

**方案**：在 AssessmentTab 步骤 2 卡片右上角，为 admin/teacher 增加"新增模板"按钮，打开创建模态框。

**实现内容**（[AssessmentTab.tsx](file:///c:/Users/69523/test/src/pages/career-training/AssessmentTab.tsx)）：
- 模态框包含：模板名称（必填）、描述、通过分数线（默认 60）、评估时长（可选）
- 胜任力评估配置：自动加载所选岗位的胜任力矩阵，默认全选，每条可配置题数（默认 5）、难度 1-5（默认 3）、评估方式（测验/自评/面试/项目）
- 校验：名称必填、至少选一项胜任力，否则禁用创建按钮
- 创建成功后自动关闭模态框并刷新该岗位的模板列表

**验证**：`npx tsc --noEmit` 零错误，AssessmentTab 测试 2/2 通过。

---

### 任务 2：修复 Modal 关闭按钮被顶出屏幕

**问题**：岗位详情中关联 3 个以上胜任力后雷达图出现，把右上角叉号顶出屏幕可视区，无法关闭弹窗。

**根因**：Modal 容器同时带 `overflow-hidden`（基础类）和 `overflow-y-auto`（各使用处传入），CSS 层叠冲突导致内容超高时无法滚动。

**修复**（[Modal.tsx](file:///c:/Users/69523/test/src/components/Modal.tsx)）：重构为两层结构——
- **外层**：`relative` 定位，承载关闭按钮（`absolute top-5 right-5 z-20`），固定不动
- **内层**：`max-h-[90vh] overflow-y-auto`，承载 children 负责滚动

**澄清**：关联胜任力没有数量限制。"3"是雷达图几何要求（至少 3 个顶点才成形），1-2 个时不画图只显示列表。

---

### 任务 3：Modal 底部增加关闭按钮

**用户反馈**：上面的部分被其他 UI 挡住，底部关闭更方便。

**修复**（[Modal.tsx](file:///c:/Users/69523/test/src/components/Modal.tsx)）：Modal 重构为 flex 列布局——
- **顶部**：右上角 X 按钮（`absolute`，固定不动）
- **中部**：内容区 `flex-1 overflow-y-auto`（独立滚动）
- **底部**：统一的"关闭"按钮栏（`border-t` 分隔，始终可见）

同时删除 CompetencyManagerModal 里原有的重复"关闭"按钮。

---

### 任务 4：修复能力评估字段命名兼容

**问题**：能力评估部分选择岗位和模板时一直显示错误，重新加载也没用。后端日志显示接口都返回 200。

**根因**：http 客户端 `keysToCamel`（[request.ts#L357](file:///c:/Users/69523/test/src/lib/request.ts#L357)）会把响应字段递归转为 camelCase：
- `competency_configs` → `competencyConfigs`
- `pass_threshold` → `passThreshold`
- `overall_score` → `overallScore`
- `is_passed` → `isPassed`
- `gap_count` → `gapCount`

但 `AssessmentTemplate`、`AssessmentRecord`、`GapAnalysis` 等类型定义和访问代码用的是 snake_case，导致 `t.competency_configs` 取到 `undefined`，访问 `.length` 报错。

**修复**（与之前 PositionCompetency 同方案）：
- [training.ts](file:///c:/Users/69523/test/src/types/training.ts)：为 `CompetencyConfig`、`AssessmentTemplate`、`AssessmentRecord`、`GapItem`、`GapAnalysis` 添加可选 camelCase 字段
- [AssessmentTab.tsx](file:///c:/Users/69523/test/src/pages/career-training/AssessmentTab.tsx)：所有字段访问改为 `camelCase ?? snake_case` 兼容，涉及模板列表、开始评估、评估录入、历史记录、差距分析

**验证**：`npx tsc --noEmit` 零错误，AssessmentTab 测试 2/2 通过。

---

### 任务 5：学习计划部分添加创建培训项目功能

**问题**：管理员登录后学习计划部分显示"暂无培训项目 请联系管理员创建培训项目"，没有创建入口。后端 `POST /training-projects` 和前端 `trainingApi.createTrainingProject` 已存在，仅缺 UI。

**方案**：为 admin/teacher 添加"新增培训项目"按钮和创建模态框。

**实现内容**（[LearningPlanTab.tsx](file:///c:/Users/69523/test/src/pages/career-training/LearningPlanTab.tsx)）：
- **入口位置**：空状态时显示按钮 + 有项目时标题栏右侧按钮（仅 admin/teacher 可见）
- **创建模态框**：项目名称（必填）、描述、关联岗位（必填）、关联认证（可选）、项目类型（新人入职/转岗培训/能力提升/认证培训）、企业名称、起止日期
- 创建成功后自动关闭模态框并刷新项目列表

**验证**：`npx tsc --noEmit` 零错误，LearningPlanTab 测试 2/2 通过。

---

### 任务 6：修复"点生成计划没反应"

**问题**：点击"生成计划"按钮什么反应都没有。

**根因**（三点叠加）：
1. `generatePlan` 接口设了 `silent: true`（[training.ts#L196](file:///c:/Users/69523/test/src/api/training.ts#L196)），失败时不会弹 toast，错误被静默吞掉
2. `handleGeneratePlan` 的 catch 只 `console.error`，用户看不到任何反馈
3. 评估记录列表可能为空（没做过评估），按钮一直 disabled，用户不知道为什么

**修复**：
- **错误反馈**：`handleGeneratePlan` 在 enrollment/selectedAssessmentRecord 为空时弹 toast 提示原因；接口失败时弹 toast 显示错误消息
- **评估记录选择 Modal 改进**：空列表时显示"暂无已完成的评估记录。请先到能力评估完成一次评估"；按钮添加 `title` 提示
- **字段兼容**：`TrainingProject`、`TrainingEnrollment`、`PlanStage`、`TrainingPlan` 类型添加 camelCase 可选字段，LearningPlanTab 所有字段访问改为 `camelCase ?? snake_case`

**验证**：`npx tsc --noEmit` 零错误，LearningPlanTab 测试 2/2 通过。

---

### 任务 7：去掉"是否加入项目"的判定

**问题**：点击"生成计划"提示"尚未加入此项目"。

**根因**（后端）：
1. **enroll 接口**（[service.py#L155-L160](file:///c:/Users/69523/test/backend/app/domains/training/service.py#L155-L160)）：用户已报名时返回 `bad_request(400)`，导致前端 `enrollProject` 抛错，`enrollment` 一直为 `null`
2. **generate_plan 接口**（[service.py#L199](file:///c:/Users/69523/test/backend/app/domains/training/service.py#L199)）：校验 `enrollment.user_id != user_id` 时拒绝——管理员无法用别人创建的报名记录生成计划

**修复**：

后端：
- `enroll` 接口改为**幂等**：已报名时返回 `success(200)` + 已有报名记录，而非报错（[service.py#L159-L160](file:///c:/Users/69523/test/backend/app/domains/training/service.py#L159-L160)）
- `generate_plan` 接口：admin/teacher 跳过 `user_id` 校验，可操作任何报名记录（[service.py#L195-L199](file:///c:/Users/69523/test/backend/app/domains/training/service.py#L195-L199)、[router.py#L105-L106](file:///c:/Users/69523/test/backend/app/domains/training/router.py#L105-L106)）
- 更新测试 `test_enroll_duplicate` 以验证幂等行为

前端：
- 去掉"尚未加入培训项目"的提示和阻断
- `handleGeneratePlan` 仅校验是否选了评估记录
- `enrollProject` 失败时静默（不弹 toast），不阻断流程

**验证**：后端 training_service 测试 19/19 通过，前端 tsc 零错误，LearningPlanTab 测试 2/2 通过。

---

### 任务 8：提交代码到 GitHub

- **提交信息**：`增添岗位培训场景的功能（待完善）`
- **提交哈希**：`d5d3706`
- **包含文件**：9 个文件，722 行新增，91 行删除
- **排除**：`backend/.env` 和 `backend/.env.development` 均已被 `.gitignore` 忽略，未进入提交
- **推送**：`feat/career-training-frontend-phase5` 分支推送至远程

---

### 任务 9：合并到 main 并推送

**操作过程**：

1. **切换到 main 并拉取远程更新**：本地 main 与 origin/main 有分歧（本地 33 提交，远程 5 提交），pull 时产生 2 个文件冲突

2. **解决冲突**：
   - [main.py](file:///c:/Users/69523/test/backend/app/main.py)：保留远程新增的 dashboard 路由，去掉重复的 training 路由（第199行已注册）
   - [models/__init__.py](file:///c:/Users/69523/test/backend/app/models/__init__.py)：保留新增的 DashboardGuidanceState，移除已废弃的 EnterpriseTraining（phase5 中已删除）

3. **合并 feature 分支**：`--no-ff` 合并，38 个文件、3864 行新增

4. **验证后端导入**：`backend import OK`

5. **推送到 origin/main**：`da1e9c2..dea9bd4 main -> main`

---

## 三、涉及的文件清单

### 后端（3 个文件）

| 文件 | 修改内容 |
|---|---|
| [backend/app/domains/training/router.py](file:///c:/Users/69523/test/backend/app/domains/training/router.py) | generate_plan 路由传递 is_staff 参数，admin/teacher 放宽权限 |
| [backend/app/domains/training/service.py](file:///c:/Users/69523/test/backend/app/domains/training/service.py) | enroll 幂等化（已报名返回200）；generate_plan 增加 is_staff 参数跳过 user_id 校验 |
| [backend/tests/test_training_service.py](file:///c:/Users/69523/test/backend/tests/test_training_service.py) | test_enroll_duplicate 改为验证幂等行为 |

### 前端（6 个文件）

| 文件 | 修改内容 |
|---|---|
| [src/api/training.ts](file:///c:/Users/69523/test/src/api/training.ts) | 新增 removePositionCompetency、deleteCompetency 方法 |
| [src/components/Modal.tsx](file:///c:/Users/69523/test/src/components/Modal.tsx) | 重构为 flex 列布局，外层固定关闭按钮，内层滚动，底部常驻关闭按钮 |
| [src/pages/career-training/AssessmentTab.tsx](file:///c:/Users/69523/test/src/pages/career-training/AssessmentTab.tsx) | 新增评估模板创建功能；字段访问 camelCase 兼容；错误反馈 |
| [src/pages/career-training/LearningPlanTab.tsx](file:///c:/Users/69523/test/src/pages/career-training/LearningPlanTab.tsx) | 新增培训项目创建功能；生成计划错误反馈；字段访问 camelCase 兼容；去掉 enrollment 阻断 |
| [src/pages/career-training/PositionTab.tsx](file:///c:/Users/69523/test/src/pages/career-training/PositionTab.tsx) | （之前会话）删除岗位/胜任力/关联功能 |
| [src/types/training.ts](file:///c:/Users/69523/test/src/types/training.ts) | 为 AssessmentTemplate、AssessmentRecord、GapAnalysis、TrainingProject、TrainingEnrollment、TrainingPlan 等添加 camelCase 可选字段 |

---

## 四、关键技术决策

### 1. camelCase 字段兼容方案

**背景**：http 客户端 `keysToCamel` 递归转换响应字段为 camelCase，但类型定义和访问代码用 snake_case。

**方案**：在类型接口中添加可选 camelCase 字段，访问处用 `camelCase ?? snake_case` 兼容两种命名。

**优点**：无需修改 http 客户端，对现有代码侵入性小，与之前 PositionCompetency 的处理方式一致。

### 2. 报名接口幂等化

**背景**：用户已报名时返回 400 错误，导致前端 enrollment 为 null，无法继续生成计划。

**方案**：已报名时返回 `success(200)` + 已有报名记录，实现幂等。

**优点**：前端无需特殊处理"已报名"场景，每次点击项目都能拿到 enrollment。

### 3. 管理员权限放宽

**背景**：generate_plan 校验 `enrollment.user_id != user_id`，管理员无法操作别人的报名记录。

**方案**：admin/teacher 跳过 user_id 校验（通过 `is_staff` 参数）。

**优点**：管理员可以为任何培训项目生成学习计划，符合企业管理场景。

---

## 五、验证结果汇总

| 验证项 | 结果 |
|---|---|
| `npx tsc --noEmit` | 零错误 |
| AssessmentTab 测试 | 2/2 通过 |
| LearningPlanTab 测试 | 2/2 通过 |
| 后端 training_service 测试 | 19/19 通过 |
| 后端 app 导入 | `backend import OK` |
| Git 冲突解决 | 无残留冲突标记 |
| 推送到 origin/main | `da1e9c2..dea9bd4` 成功 |

---

## 六、后续待完善事项

1. **认证管理 Tab**：认证申请与审核流程的完整验证
2. **实践练习 Tab**：内嵌资料生成与自适应练习的端到端手动验证
3. **AI 学习计划生成**：LLM 接口配置后的实际生成效果验证
4. **权限模型完善**：目前 admin/teacher 权限较宽，可细化为基于角色的资源级权限
5. **数据库迁移**：合并后需确认 alembic 迁移在生产环境的执行顺序
6. **端到端测试**：各 Tab 的完整业务流程手动验证（创建岗位 → 关联胜任力 → 创建评估模板 → 发起评估 → 生成学习计划 → 完成培训 → 申请认证）
