# 岗位-胜任力-学习-认证 能力平台设计文档

> **日期**: 2026-08-09
> **状态**: 待审阅
> **范围**: 删除旧 training 域，新建岗位/胜任力/评估/认证/培训项目体系，前端新增"就业培训"聚合页面，与现有 AI 多智能体深度融合

---

## 1. 背景与目标

### 1.1 现状

项目当前是一个面向在校学生的 AI 学习平台，核心能力包括：学情诊断、知识库 RAG 检索、多智能体资源生成（含审核+辩论纠偏）、自适应导学、学情报告。

后端有一个旧的 `training` 域（`EnterpriseTraining` 表），但数据模型过于扁平（培训信息全塞在一张表里），缺乏岗位模型、胜任力矩阵、认证体系等结构化支撑，前端页面也完全缺失（`/enterprise` 路由直接重定向到 dashboard）。

### 1.2 目标

将平台能力从"在校学生学术培养"拓展为通用的"岗位-胜任力-学习-认证"能力平台，支持企业标准化内训、转岗培训等高要求场景。核心业务闭环：

```
岗位定义 → 胜任力拆解 → 学员能力评估 → 差距分析 → AI生成个性化学习计划
→ 学习+练习（复用现有资源生成+自适应导学+多智能体审核）→ 再评估 → 达标发证
```

### 1.3 设计原则

- **删除旧 training 域**，从零设计逻辑自洽的模型体系
- **深度融合 AI**：在闭环 6 个节点调用 LLM/多智能体，复用现有 AgentOrchestrator
- **前端不铺页面**：仅新增一个"就业培训"菜单入口，内部按环节分步导航
- **不影响现有功能**：新增域独立运作，通过 Service 层调用现有 resource/agent/tutoring/knowledge 域

---

## 2. 数据模型

### 2.1 新域划分

删除 `backend/app/domains/training/` 全部内容，新建 4 个域：

| 域 | 路径 | 核心模型 |
|---|---|---|
| `position` | `backend/app/domains/position/` | `Position`, `Competency`, `PositionCompetency` |
| `assessment` | `backend/app/domains/assessment/` | `AssessmentTemplate`, `AssessmentRecord`, `CompetencyScore` |
| `certification` | `backend/app/domains/certification/` | `Certification`, `CertificationRule`, `CertificationRecord` |
| `training`（重建） | `backend/app/domains/training/` | `TrainingProject`, `TrainingPlan`, `TrainingEnrollment` |

### 2.2 Position 域

#### Position（岗位定义）

```
positions
├── id: int PK
├── code: varchar(50) unique      -- 岗位编码，如 "FE-001"
├── name: varchar(100)            -- 岗位名称，如 "前端工程师"
├── category: varchar(50)         -- 岗位类别，如 "技术"/"管理"/"运营"
├── industry: varchar(50)         -- 所属行业
├── level: varchar(20)            -- 岗位层级 junior/mid/senior/expert
├── description: text             -- 岗位描述
├── responsibilities: json        -- 岗位职责列表
├── prerequisites: json           -- 前置要求（学历/经验等）
├── career_path: json             -- 职业发展路径（晋升方向）
├── is_active: bool default true
├── created_at: datetime
├── updated_at: datetime
```

#### Competency（胜任力项）

```
competencies
├── id: int PK
├── code: varchar(50) unique      -- 胜任力编码，如 "PROG-PY"
├── name: varchar(100)            -- 胜任力名称，如 "Python编程"
├── category: varchar(50)         -- 类别：技术/软技能/领域知识/工程实践
├── description: text             -- 胜任力描述
├── level_descriptions: json      -- 5个等级的描述 {1: "了解", 2: "能使用", 3: "熟练", 4: "精通", 5: "专家"}
├── is_active: bool default true
├── created_at: datetime
├── updated_at: datetime
```

#### PositionCompetency（岗位-胜任力关联）

```
position_competencies
├── id: int PK
├── position_id: int FK -> positions.id
├── competency_id: int FK -> competencies.id
├── required_level: int (1-5)     -- 该岗位对此胜任力的要求等级
├── weight: float default 1.0     -- 权重（用于综合达标率计算）
├── is_mandatory: bool default true -- 是否必修（vs 加分项）
├── UNIQUE(position_id, competency_id)
```

### 2.3 Assessment 域

#### AssessmentTemplate（评估模板）

```
assessment_templates
├── id: int PK
├── position_id: int FK -> positions.id   -- 关联岗位
├── name: varchar(200)                    -- 模板名称
├── description: text
├── competency_configs: json  -- [{competency_id, question_count, difficulty, assessment_method}]
│                              -- assessment_method: "quiz"/"self_report"/"interview"/"project"
├── pass_threshold: float default 60.0    -- 通过分数线
├── duration_minutes: int                 -- 评估时长
├── is_active: bool default true
├── created_at: datetime
├── updated_at: datetime
```

#### AssessmentRecord（评估记录）

```
assessment_records
├── id: int PK
├── template_id: int FK -> assessment_templates.id
├── user_id: int FK -> users.id
├── learner_id: int FK -> learner_profiles.id
├── position_id: int FK -> positions.id
├── status: enum(draft/in_progress/completed/expired)
├── overall_score: float          -- 综合得分
├── overall_level: int (1-5)      -- 综合能力等级
├── gap_summary: json             -- 差距摘要 [{competency_id, competency_name, current_level, required_level, gap}]
├── ai_diagnosis: text            -- AI生成的诊断报告
├── started_at: datetime
├── completed_at: datetime
├── created_at: datetime
├── updated_at: datetime
```

#### CompetencyScore（胜任力评分明细）

```
competency_scores
├── id: int PK
├── assessment_record_id: int FK -> assessment_records.id
├── competency_id: int FK -> competencies.id
├── current_level: int (1-5)      -- 当前等级
├── current_score: float (0-100)  -- 当前得分
├── required_level: int (1-5)     -- 要求等级（快照）
├── gap: int                      -- 差距 = required_level - current_level（负数表示超出）
├── assessment_method: varchar(20)-- 评估方式
├── evidence: json                -- 评估依据（答题记录ID列表等）
├── created_at: datetime
```

### 2.4 Certification 域

#### Certification（认证定义）

```
certifications
├── id: int PK
├── position_id: int FK -> positions.id
├── name: varchar(200)            -- 认证名称，如 "前端工程师初级认证"
├── code: varchar(50) unique      -- 认证编码
├── level: varchar(20)            -- 认证级别 junior/mid/senior
├── description: text
├── validity_period_months: int   -- 有效期（月），0 表示永久
├── issuer: varchar(100)          -- 发证机构
├── is_active: bool default true
├── created_at: datetime
├── updated_at: datetime
```

#### CertificationRule（发证规则）

```
certification_rules
├── id: int PK
├── certification_id: int FK -> certifications.id
├── rule_type: enum(overall_score / competency_level / all_mandatory_met)
├── rule_config: json
│   -- overall_score: {"min_score": 75}
│   -- competency_level: {"competency_id": 5, "min_level": 3}
│   -- all_mandatory_met: {"allow_gap": 0}  -- 所有必修项达标，允许0个gap
├── created_at: datetime
```

#### CertificationRecord（认证记录）

```
certification_records
├── id: int PK
├── certification_id: int FK -> certifications.id
├── user_id: int FK -> users.id
├── learner_id: int FK -> learner_profiles.id
├── assessment_record_id: int FK -> assessment_records.id  -- 关联评估记录
├── status: enum(pending/approved/rejected/expired/revoked)
├── certificate_number: varchar(100) unique  -- 证书编号
├── issued_at: datetime
├── expires_at: datetime
├── reviewed_by: int FK -> users.id           -- 审核人
├── review_comment: text
├── created_at: datetime
├── updated_at: datetime
```

### 2.5 Training 域（重建）

#### TrainingProject（培训项目）

```
training_projects
├── id: int PK
├── name: varchar(200)                    -- 项目名称
├── description: text
├── position_id: int FK -> positions.id   -- 关联岗位
├── certification_id: int FK -> certifications.id  -- 关联认证（可选）
├── project_type: varchar(20)             -- onboard(入职)/transfer(转岗)/upskill(提升)/compliance(合规)
├── enterprise_name: varchar(100)         -- 所属企业
├── status: enum(draft/active/completed/archived)
├── start_date: date
├── end_date: date
├── config: json                          -- 项目级配置（时间限制、补考次数等）
├── created_by: int FK -> users.id
├── created_at: datetime
├── updated_at: datetime
```

#### TrainingPlan（培训计划/学习路径）

```
training_plans
├── id: int PK
├── project_id: int FK -> training_projects.id
├── enrollment_id: int FK -> training_enrollments.id
├── user_id: int FK -> users.id
├── learner_id: int FK -> learner_profiles.id
├── assessment_record_id: int FK -> assessment_records.id  -- 基于哪次评估生成
├── plan_content: json          -- AI生成的学习计划
│   -- [{stage, title, competency_ids, resources: [], estimated_hours, target_level, deadline}]
├── total_stages: int
├── completed_stages: int default 0
├── progress: float default 0.0
├── status: enum(generating/active/completed/failed)
├── generated_by_ai: bool default true
├── created_at: datetime
├── updated_at: datetime
```

#### TrainingEnrollment（培训报名/参与）

```
training_enrollments
├── id: int PK
├── project_id: int FK -> training_projects.id
├── user_id: int FK -> users.id
├── learner_id: int FK -> learner_profiles.id
├── status: enum(enrolled/in_progress/completed/withdrawn/failed)
├── enrolled_at: datetime
├── completed_at: datetime
├── final_score: float
├── certification_record_id: int FK -> certification_records.id  -- 最终获得的认证
├── created_at: datetime
├── updated_at: datetime
├── UNIQUE(project_id, user_id)
```

---

## 3. AI 融合设计

### 3.1 闭环 6 个 AI 节点

| # | 环节 | AI 能力 | 实现方式 | 复用/新增 |
|---|---|---|---|---|
| 1 | 岗位胜任力拆解 | LLM 根据岗位描述自动生成胜任力维度和建议等级 | 调用 LLM，输入岗位描述+行业知识库，输出胜任力列表 | **新增** prompt: `competency_generation` |
| 2 | 差距分析诊断 | LLM 分析差距数据，生成自然语言诊断报告 | 输入差距摘要+学习者画像，输出诊断报告 | **复用** `learner_diagnosis` prompt + 适配 |
| 3 | 学习计划生成 | LLM 根据差距+知识库生成个性化学习路径 | 输入差距+岗位要求+知识库RAG，输出分阶段计划 | **复用** `path_planning` prompt + 适配 |
| 4 | 培训资料生成 | 多智能体生成+审核+辩论纠偏 | 完整 AgentOrchestrator 流水线 | **直接复用**现有 agent 域 |
| 5 | 自适应练习 | 按岗位能力要求调整题目难度和知识点 | 复用 AdaptiveTutoringService，注入岗位胜任力上下文 | **复用** tutoring 域 + 适配 |
| 6 | 达标评估 | LLM 综合评估是否满足岗位胜任力要求 | 输入评估数据+学习记录，输出评估结论+建议 | **新增** prompt: `competency_evaluation` |

### 3.2 新增 Prompt 模板

#### `competency_generation.txt`

- **用途**: 根据岗位描述自动生成胜任力维度
- **输入变量**: `{position_name}`, `{position_description}`, `{industry}`, `{reference_knowledge}`
- **输出**: JSON 格式的胜任力列表 `[{code, name, category, suggested_level, level_descriptions}]`

#### `competency_evaluation.txt`

- **用途**: 综合评估学员是否达到岗位胜任力要求
- **输入变量**: `{position_name}`, `{competency_scores}`, `{gap_summary}`, `{learning_records}`, `{overall_score}`
- **输出**: JSON `{met: bool, conclusion: str, strengths: [], weaknesses: [], suggestions: []}`

### 3.3 与现有 AgentOrchestrator 的对接

培训资料生成环节直接调用现有 `AgentOrchestrator`，传入参数调整：

```python
# 培训项目调用多智能体生成资料时的参数差异
orchestrator.execute(
    learner_id=enrollment.learner_id,
    task_type="training_resource",  # 新增任务类型
    extra_context={
        "position": position.name,
        "target_competencies": [c.name for c in required_competencies],
        "required_level": competency.required_level,
        "current_level": competency_score.current_level,
        "gap": competency_score.gap,
    }
)
```

`AgentOrchestrator` 内部逻辑不需要改动——它已经接受 `extra_context`，生成时会将岗位胜任力信息注入到 prompt 中。

### 3.4 与自适应导学的对接

现有 `AdaptiveTutoringService` 按 `learner_id` 出题。培训场景下，在调用前注入岗位上下文：

```python
# 培训练习时，传入岗位胜任力约束
AdaptiveTutoringService.generate_dynamic_questions(
    user_id=user_id,
    learner_id=learner_id,
    topic=competency.name,          # 按胜任力维度出题
    difficulty=required_level,       # 按岗位要求等级定难度
    question_count=count,
    replace_pending=True,
)
```

---

## 4. API 端点设计

### 4.1 Position 域

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/api/v1/positions` | 岗位列表（分页+筛选） | 已登录 |
| GET | `/api/v1/positions/{id}` | 岗位详情（含胜任力矩阵） | 已登录 |
| POST | `/api/v1/positions` | 创建岗位 | teacher/admin/enterprise |
| PUT | `/api/v1/positions/{id}` | 更新岗位 | teacher/admin/enterprise |
| DELETE | `/api/v1/positions/{id}` | 删除岗位 | admin |
| POST | `/api/v1/positions/{id}/ai-generate-competencies` | AI生成胜任力建议 | teacher/admin/enterprise |
| GET | `/api/v1/competencies` | 胜任力项列表 | 已登录 |
| POST | `/api/v1/competencies` | 创建胜任力项 | teacher/admin/enterprise |
| PUT | `/api/v1/competencies/{id}` | 更新胜任力项 | teacher/admin/enterprise |
| POST | `/api/v1/positions/{id}/competencies` | 为岗位添加胜任力要求 | teacher/admin/enterprise |
| PUT | `/api/v1/positions/{id}/competencies/{cid}` | 更新岗位胜任力要求 | teacher/admin/enterprise |
| DELETE | `/api/v1/positions/{id}/competencies/{cid}` | 移除岗位胜任力要求 | teacher/admin/enterprise |

### 4.2 Assessment 域

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/api/v1/assessments/templates` | 评估模板列表 | 已登录 |
| POST | `/api/v1/assessments/templates` | 创建评估模板 | teacher/admin/enterprise |
| GET | `/api/v1/assessments/templates/{id}` | 模板详情 | 已登录 |
| POST | `/api/v1/assessments/start` | 开始评估（指定模板+学员） | 已登录 |
| GET | `/api/v1/assessments/records/{id}` | 评估记录详情（含各维度得分） | 已登录 |
| GET | `/api/v1/assessments/records` | 评估记录列表（按user/position筛选） | 已登录 |
| POST | `/api/v1/assessments/records/{id}/submit` | 提交评估答案 | 已登录 |
| POST | `/api/v1/assessments/records/{id}/diagnose` | AI生成差距诊断报告 | teacher/admin/enterprise |
| GET | `/api/v1/assessments/records/{id}/gaps` | 获取差距分析结果 | 已登录 |

### 4.3 Certification 域

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/api/v1/certifications` | 认证列表 | 已登录 |
| POST | `/api/v1/certifications` | 创建认证定义 | teacher/admin/enterprise |
| GET | `/api/v1/certifications/{id}` | 认证详情（含发证规则） | 已登录 |
| POST | `/api/v1/certifications/{id}/rules` | 添加发证规则 | teacher/admin/enterprise |
| POST | `/api/v1/certifications/{id}/apply` | 申请认证（关联评估记录） | 已登录 |
| GET | `/api/v1/certifications/records` | 认证记录列表 | 已登录 |
| GET | `/api/v1/certifications/records/{id}` | 认证记录详情 | 已登录 |
| POST | `/api/v1/certifications/records/{id}/approve` | 审批通过 | teacher/admin/enterprise |
| POST | `/api/v1/certifications/records/{id}/reject` | 审批拒绝 | teacher/admin/enterprise |

### 4.4 Training 域（重建）

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/api/v1/training-projects` | 培训项目列表 | 已登录 |
| POST | `/api/v1/training-projects` | 创建培训项目 | teacher/admin/enterprise |
| GET | `/api/v1/training-projects/{id}` | 项目详情 | 已登录 |
| PUT | `/api/v1/training-projects/{id}` | 更新项目 | teacher/admin/enterprise |
| POST | `/api/v1/training-projects/{id}/enroll` | 报名参加 | 已登录 |
| GET | `/api/v1/training-projects/{id}/enrollments` | 项目学员列表 | teacher/admin/enterprise |
| POST | `/api/v1/training-enrollments/{id}/generate-plan` | AI生成学习计划 | 已登录 |
| GET | `/api/v1/training-enrollments/{id}/plan` | 获取学习计划 | 已登录 |
| PUT | `/api/v1/training-plans/{id}/progress` | 更新学习进度 | 已登录 |
| POST | `/api/v1/training-enrollments/{id}/complete` | 完成培训（触发认证流程） | teacher/admin/enterprise |

---

## 5. 前端设计

### 5.1 导航与路由

侧边栏新增一个菜单项，放在"学习应用"分组中：

```typescript
// src/components/Layout.tsx navigationGroups 修改
{
  name: '学习应用',
  items: [
    { name: '自适应导学', href: '/guidance', icon: GraduationCap },
    { name: '资源生成', href: '/resources', icon: FileText },
    { name: '学情报告', href: '/report', icon: BarChart3 },
    { name: '就业培训', href: '/career-training', icon: Briefcase },  // ← 新增
  ],
},
```

路由修改（`src/App.tsx`）：

```typescript
// 替换原来的重定向
- <Route path="enterprise" element={<Navigate to="/dashboard" replace />} />
+ <Route path="career-training" element={<CareerTraining />} />
+ <Route path="career-training/:tab" element={<CareerTraining />} />
```

### 5.2 聚合页面结构

`src/pages/CareerTraining.tsx` —— 单一页面，内部按闭环环节分步导航：

```
┌─────────────────────────────────────────────────────┐
│  就业培训                                            │
├─────────────────────────────────────────────────────┤
│  [① 岗位与胜任力] [② 能力评估] [③ 学习计划]          │
│  [④ 学习与练习] [⑤ 认证发证]                         │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ← 当前选中 tab 的内容区域                           │
│                                                     │
│  例如选中"② 能力评估"时：                            │
│  ┌─────────────────────────────────────────────┐    │
│  │ 选择岗位: [前端工程师 ▼]                      │    │
│  │ 选择评估模板: [初级能力评估 ▼]                │    │
│  │ [开始评估]                                   │    │
│  │                                              │    │
│  │ 历史评估记录:                                │    │
│  │ ┌──────────────────────────────────────┐    │    │
│  │ │ 2026-08-09  综合分: 72  状态: 已完成   │    │    │
│  │ │ 差距: Python编程 Lv3→Lv4, 系统架构...  │    │    │
│  │ │ [查看详情] [生成学习计划]              │    │    │
│  │ └──────────────────────────────────────┘    │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

Tab 之间通过 URL hash 切换（`/career-training/assessment`），支持直链跳转。

### 5.3 各 Tab 内容

| Tab | 内容 | 交互 |
|---|---|---|
| ① 岗位与胜任力 | 岗位卡片列表 → 点击展开胜任力矩阵雷达图；管理员可创建岗位、AI生成胜任力 | 列表+详情抽屉 |
| ② 能力评估 | 选岗位+模板 → 开始评估 → 查看差距报告（雷达图+差距列表） | 向导式 |
| ③ 学习计划 | 选评估记录 → AI生成计划 → 展示分阶段路径 → 进度跟踪 | 卡片+时间线 |
| ④ 学习与练习 | 培训资料列表（复用资源生成UI）+ 自适应题目练习入口 | 列表+跳转 |
| ⑤ 认证发证 | 认证列表 → 申请 → 审批记录 → 证书查看 | 列表+详情 |

### 5.4 前端新增文件

```
src/
├── pages/
│   └── CareerTraining.tsx              -- 聚合页面主组件（含 tab 路由）
│   └── career-training/
│       ├── PositionTab.tsx             -- Tab 1: 岗位与胜任力
│       ├── AssessmentTab.tsx           -- Tab 2: 能力评估
│       ├── LearningPlanTab.tsx         -- Tab 3: 学习计划
│       ├── PracticeTab.tsx             -- Tab 4: 学习与练习
│       └── CertificationTab.tsx        -- Tab 5: 认证发证
├── api/
│   └── training.ts                     -- 新增 API 客户端（position/assessment/certification/training）
├── types/
│   └── training.ts                     -- 新增类型定义
└── store/
    └── trainingStore.ts               -- 新增 training slice
```

### 5.5 关键 UI 组件复用

| 需求 | 复用现有组件 | 适配方式 |
|---|---|---|
| 胜任力雷达图 | 无现有雷达图 | 新建轻量 SVG 雷达图组件 |
| 资源生成 | ResourceGeneration 页面 | PracticeTab 内嵌或跳转，传入岗位上下文 |
| 自适应练习 | AdaptiveGuidance 页面 | PracticeTab 内嵌或跳转，传入胜任力维度作为 topic |
| 多智能体可视化 | MultiAgentVisualization | 培训资料生成时自动触发，无需额外页面 |
| 学习计划时间线 | 无现有时间线 | 新建轻量时间线组件 |

---

## 6. 删除旧 Training 域的迁移策略

### 6.1 删除范围

```
删除文件:
├── backend/app/domains/training/models.py      ← 旧 EnterpriseTraining
├── backend/app/domains/training/router.py       ← 旧 CRUD 路由
├── backend/app/domains/training/schemas.py      ← 旧 Schema
├── backend/app/domains/training/service.py      ← 旧 Service
├── backend/app/data/trainings.json              ← 旧种子数据
├── backend/tests/test_training_service.py       ← 旧单元测试
├── e2e/enterprise-training-import.spec.ts       ← 旧 E2E 测试
└── e2e/fixtures/sample-training.csv             ← 旧测试夹具

修改文件:
├── backend/app/main.py                           ← 移除旧 training_router 注册和种子初始化
├── backend/app/models/__init__.py               ← 移除 EnterpriseTraining 等导出
├── src/App.tsx                                   ← 移除 /enterprise 重定向，新增 /career-training
└── src/components/Layout.tsx                     ← 侧边栏新增"就业培训"入口
```

### 6.2 数据库迁移

由于旧 `enterprise_trainings` 表的数据无实际价值（种子数据），迁移策略为：

1. 创建 Alembic 迁移脚本：`drop_enterprise_trainings_table`
2. 创建 Alembic 迁移脚本：`create_competency_platform_tables`（新建所有新表）
3. 旧表数据不保留，新表从空数据开始

### 6.3 `__init__.py` 更新

`backend/app/models/__init__.py` 中：
- 移除 `EnterpriseTraining`, `TrainingStatusEnum`, `TransferStatusEnum` 的导入和导出
- 新增所有新模型的导入和导出

---

## 7. 目录结构

### 7.1 后端新增

```
backend/app/domains/
├── position/
│   ├── __init__.py
│   ├── models.py          # Position, Competency, PositionCompetency
│   ├── schemas.py         # Pydantic schemas
│   ├── service.py         # 业务逻辑
│   └── router.py          # API 路由
├── assessment/
│   ├── __init__.py
│   ├── models.py          # AssessmentTemplate, AssessmentRecord, CompetencyScore
│   ├── schemas.py
│   ├── service.py         # 含 AI 诊断调用
│   └── router.py
├── certification/
│   ├── __init__.py
│   ├── models.py          # Certification, CertificationRule, CertificationRecord
│   ├── schemas.py
│   ├── service.py         # 含达标判定逻辑
│   └── router.py
└── training/              ← 重建
    ├── __init__.py
    ├── models.py          # TrainingProject, TrainingPlan, TrainingEnrollment
    ├── schemas.py
    ├── service.py         # 编排闭环流程，调用其他域
    └── router.py

backend/app/prompts/templates/
├── competency_generation.txt    ← 新增
└── competency_evaluation.txt    ← 新增
```

### 7.2 前端新增

```
src/
├── pages/
│   ├── CareerTraining.tsx
│   └── career-training/
│       ├── PositionTab.tsx
│       ├── AssessmentTab.tsx
│       ├── LearningPlanTab.tsx
│       ├── PracticeTab.tsx
│       └── CertificationTab.tsx
├── components/
│   └── career-training/
│       ├── CompetencyRadar.tsx       -- 胜任力雷达图
│       ├── GapAnalysisChart.tsx      -- 差距分析图
│       └── PlanTimeline.tsx          -- 学习计划时间线
├── api/
│   └── training.ts
├── types/
│   └── training.ts
└── store/
    └── trainingStore.ts
```

---

## 8. 错误处理

### 8.1 AI 调用失败

所有 AI 调用节点都有降级策略：

| 节点 | AI 失败时的降级 |
|---|---|
| 胜任力生成 | 返回错误提示，允许手动添加胜任力项 |
| 差距诊断 | 返回结构化差距数据（无 AI 文本报告），提示"诊断报告生成失败" |
| 学习计划生成 | 返回错误提示，允许手动配置学习计划 |
| 培训资料生成 | 复用现有 AgentOrchestrator 的熔断器+规则兜底机制 |
| 达标评估 | 回退到纯规则判定（检查 overall_score >= pass_threshold） |

### 8.2 数据完整性

- `PositionCompetency` 的 `(position_id, competency_id)` 唯一约束防止重复
- `TrainingEnrollment` 的 `(project_id, user_id)` 唯一约束防止重复报名
- `CertificationRecord.certificate_number` 唯一约束
- 评估记录状态机：`draft → in_progress → completed`（不可回退）
- 认证记录状态机：`pending → approved/rejected`，`approved → expired/revoked`

---

## 9. 测试策略

### 9.1 后端单元测试

每个新域独立测试：
- `test_position_service.py`: 岗位CRUD、胜任力矩阵、AI生成mock
- `test_assessment_service.py`: 评估流程、差距计算、AI诊断mock
- `test_certification_service.py`: 发证规则判定、状态流转
- `test_training_service.py`: 闭环编排、计划生成、进度更新

### 9.2 集成测试

- 完整闭环：创建岗位 → 评估 → 生成计划 → 模拟学习 → 再评估 → 发证
- AI 调用全部 mock，验证编排逻辑正确性

### 9.3 前端测试

- 各 Tab 渲染测试
- 关键交互：岗位选择 → 评估 → 查看差距报告
```
