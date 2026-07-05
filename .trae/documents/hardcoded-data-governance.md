# 硬编码业务数据治理方案

## Context

项目硬约束明确：学习者信息（个人画像、学习进度、成绩）和企业培训数据（课程内容、自定义设置、员工记录）严禁硬编码处理，必须使用标准化数据存储（数据库、配置文件、API 接口）。

经三路并行审计，前端发现 8 处硬编码（6 个文件），后端发现 7 处硬编码（7 个文件）。项目已有成熟的"JSON 种子文件 + seed_loader + DB 模型"模式（`learners.json`/`trainings.json`），本方案以此为基础进行治理。

---

## 审计发现摘要

### 前端（src/）
| 优先级 | 文件 | 行号 | 硬编码内容 |
|--------|------|------|-----------|
| P0 | EnterpriseTraining.tsx | 172-191 | `handleBatchImport` 写入假培训数据到后端 |
| P0 | LearningReport.tsx | 160-172 | `generateAbilityTrend` 用 Math.sin 伪造能力趋势 |
| P0 | Login.tsx | 104-108 | 明文展示 `admin / admin123` 凭据 |
| P1 | EnterpriseTraining.tsx | 58-63 | `STATUS_TEMPLATES` 培训模板（含课程数） |
| P1 | ResourceGeneration.tsx | 83-90 | `industryOptions` 行业选项（6 项） |
| P1 | KnowledgeBase.tsx | 28-40 | `domainOptions`/`domainToLabel` 领域选项 |
| P1 | LearnerProfile.tsx | 61-68 | `desensitizationRules` 脱敏规则 |
| P2 | LearnerProfile.tsx | 253-283 | 新建画像表单能力维度默认值 50 |

### 后端（backend/app/）
| 优先级 | 文件 | 行号 | 硬编码内容 |
|--------|------|------|-----------|
| P0 | learner_service.py | 652 | `user_id=1` 答题记录归属错误用户（功能缺陷） |
| P0 | tutoring_service.py | 28-65 | `QUESTION_BANK` 3 道完整题目（含答案） |
| P1 | privacy_service.py | 26-82 | `ANONYMIZATION_RULES` 含假 PII 示例 |
| P1 | knowledge_service.py | 72 | `SUPPORTED_INDUSTRIES` 行业列表 |
| P2 | main.py | 537-544 | 默认管理员 `admin/admin123` 硬编码 |
| P2 | orchestrator.py | 596,374 | `judge_confidence=0.8`、`learner_profile={}` |
| P2 | generation_agent.py | 364-384 | 模拟题目生成（占位符内容） |

### 已符合约束的模式（无需改动）
- `backend/app/data/learners.json`（5 条学习者种子）+ `seed_loader.py`
- `backend/app/data/trainings.json`（6 条培训种子）+ `seed_loader.py`
- `backend/app/constants.py`（阈值常量，属系统参数）

---

## 拟议修改

### 第一组：移除假数据写入/生成（P0）

#### 1.1 EnterpriseTraining.tsx — 移除 handleBatchImport 假数据
**文件**：`src/pages/EnterpriseTraining.tsx:172-191`
**问题**：`handleBatchImport` 注释写"模拟批量导入"，硬编码 `companyName: '示范企业'` 等假数据写入后端。
**改法**：移除硬编码数据数组。改为从当前表单状态或文件上传获取数据；若无有效数据则提示用户"请先填写培训信息"并中断。保留 `trainingApi.batchImport` 调用但传入用户实际输入的数据。

#### 1.2 LearningReport.tsx — 移除 generateAbilityTrend 伪造趋势
**文件**：`src/pages/LearningReport.tsx:160-172`
**问题**：用 `Math.sin` 生成假的 6 周能力发展趋势数据，喂给 AreaChart。
**改法**：后端新增 `/api/v1/report/ability-trend/{learner_id}` 端点，从 `AnswerRecord` 按周聚合平均分。前端改为从 `coreApi` 获取真实趋势数据；无数据时返回空数组，前端显示"暂无趋势数据"占位。
**后端实现**：在 `report_service.py` 新增 `get_ability_trend(db, learner_id, weeks=6)` 方法，按 `created_at` 周分组聚合 `score`。在 `routers/core.py` 新增端点。

#### 1.3 Login.tsx — 移除明文凭据
**文件**：`src/pages/Login.tsx:104-108`
**问题**：登录页底部明文展示 `admin / admin123`。
**改法**：移除该 `<p>` 块。如需开发提示，改为仅显示"默认管理员账号请参考系统文档"，不展示密码。

#### 1.4 learner_service.py — 修复 user_id=1 硬编码
**文件**：`backend/app/services/learner_service.py:652`
**问题**：`add_answer_record` 中 `user_id=1,  # 临时用户ID`，导致所有答题记录归属 ID=1 用户。
**改法**：改为 `user_id=answer_data.user_id`（`AnswerRecordCreate` schema 已有 `user_id` 字段，路由层已传入）。

---

### 第二组：前端业务配置外置到 API（P1）

#### 2.1 新增统一配置端点
**新建**：在 `routers/core.py` 新增 `GET /api/v1/config/options` 端点，返回前端需要的业务选项：
```python
{
  "industries": [{"value": "technology", "label": "信息技术"}, ...],
  "domains": [{"value": "smart_manufacturing", "label": "智能制造", ...}, ...],
  "training_templates": [{"title": "新员工入职", "duration": "2周", "courses": 12}, ...]
}
```
**数据来源**：新建 `backend/app/data/business_config.json`（遵循现有 JSON 种子模式），通过 `seed_loader.py` 加载。`ConfigService.get_options()` 读取并返回。

#### 2.2 前端新增 configApi + 替换硬编码
**新建**：`src/api/config.ts` — `configApi.getOptions()` 调用 `/api/v1/config/options`
**修改**：
- `ResourceGeneration.tsx`：移除 `industryOptions` 硬编码，改为 `useEffect` 从 `configApi` 获取
- `KnowledgeBase.tsx`：移除 `domainOptions`/`domainToLabel` 硬编码，改为 API 获取
- `EnterpriseTraining.tsx`：移除 `STATUS_TEMPLATES` 硬编码，改为 API 获取

#### 2.3 替换脱敏规则硬编码
**文件**：`src/pages/LearnerProfile.tsx:61-68`
**改法**：移除 `desensitizationRules` 硬编码。后端已有 `GET /api/v1/privacy/anonymization` 端点（返回 `PrivacyService.get_anonymization_rules()`）。前端改为通过 `privacyApi` 获取。

---

### 第三组：后端业务数据迁移到 JSON 配置（P1）

#### 3.1 QUESTION_BANK → JSON 种子文件
**新建**：`backend/app/data/questions.json`，包含 3 道导学题（反向传播/优化器/正则化），结构含 `question_type`/`topic`/`difficulty`/`content`/`options`/`correct_answer`/`explanation`。
**修改**：`tutoring_service.py` 移除 `QUESTION_BANK` 类属性（28-65 行），改为在 `__init__` 或模块级从 `seed_loader.load_seed_data("questions.json")` 加载。`get_questions()` 返回加载的数据。
**同时迁移**：`explanations`（240-244 行）、`points`（419-423 行）知识点解释也移入 `questions.json` 的 `explanations`/`key_points` 字段。

#### 3.2 ANONYMIZATION_RULES 假 PII → JSON 配置
**新建**：`backend/app/data/privacy_rules.json`，包含脱敏规则定义（`field_type`/`mask_pattern`/`preserve_prefix` 等），**移除假 PII 示例**（"张明远"、"13812345678" 等）。
**修改**：`privacy_service.py` 的 `ANONYMIZATION_RULES`（26-82 行）改为从 JSON 加载；`original`/`anonymized` 示例字段改为通用占位（如 `"张***"`、`"138****5678"`）或移除。

#### 3.3 SUPPORTED_INDUSTRIES → 从枚举派生
**文件**：`backend/app/services/knowledge_service.py:72`
**问题**：`SUPPORTED_INDUSTRIES = ["智能制造","工业互联网","软件开发","人工智能训练"]` 与 `IndustryEnum` 重复且不一致（枚举有 6 项，硬编码只有 4 项）。
**改法**：移除硬编码列表，改为 `SUPPORTED_INDUSTRIES = [e.value for e in IndustryEnum]`，或直接引用 `IndustryEnum`。

---

### 第四组：安全加固（P2）

#### 4.1 默认管理员密码改为环境变量
**文件**：`backend/app/main.py:537-544`
**改法**：`_init_default_admin` 读取 `settings.DEFAULT_ADMIN_PASSWORD`（默认 `"admin123"` 但可通过 `.env` 覆盖）。移除日志中的明文密码输出（547 行）。
**config.py**：新增 `default_admin_password: str = "admin123"` 配置项。

#### 4.2 orchestrator.py 传入真实数据
**文件**：`backend/app/agents/orchestrator.py`
- 596 行 `judge_confidence=0.8` → 改为从 `judge_result` 中提取实际置信度（`judge_result.get("confidence", 0.0)`）
- 374 行 `"learner_profile": {}` → 改为传入实际 `LearnerProfile` 数据（从 DB 查询后序列化）

---

### 不在本次范围

| 项 | 原因 |
|----|------|
| `generation_agent.py` 模拟题目生成 | 属功能缺失（无 LLM 集成），非数据存储问题，需独立功能开发 |
| `judge_agent.py` 校验权重 0.4/0.35/0.25 | 属算法调参，非业务数据硬编码 |
| `LearnerProfile.tsx` 表单默认值 50 | 属 UI 初始值约定，非业务数据；可接受 |
| 新建 QuestionBank DB 模型 | 仅 3 道题，JSON 配置更轻量；题库扩展后再建表 |
| 全量 Alembic 迁移 | 项目使用 `create_all`，结构未变，无需迁移 |

---

## 执行顺序

1. **第一组**（P0 假数据移除）→ 跑后端 200 + 前端 72 测试
2. **第三组**（后端 JSON 迁移）→ 跑后端测试 + pyflakes
3. **第二组**（前端配置外置）→ 跑前端 typecheck + 测试
4. **第四组**（安全加固）→ 跑全量测试
5. 最终回归：`pytest tests/ -q` + `tsc --noEmit` + `vitest run`

每组完成后验证，失败则回滚该组改动。

---

## 验证步骤

1. **后端测试**：`cd backend && .\venv\Scripts\python.exe -m pytest tests\ -q`（预期 200 passed）
2. **前端类型检查**：`node node_modules/typescript/bin/tsc --noEmit`（0 错误）
3. **前端测试**：`node node_modules/vitest/vitest.mjs run`（72 passed）
4. **后端静态检查**：`python -m pyflakes backend/app/services/ backend/app/main.py backend/app/agents/orchestrator.py`
5. **手动验证**：
   - EnterpriseTraining 批量导入不再写入假数据
   - LearningReport 能力趋势图显示真实数据或"暂无数据"
   - Login 页不再显示明文凭据
   - ResourceGeneration/KnowledgeBase 行业/领域选项正常加载
   - LearnerProfile 脱敏规则从 API 加载

## 假设与决策

1. **JSON 配置优先于新 DB 模型**：题库仅 3 题、脱敏规则仅 5 条，JSON 文件比新建表更轻量，符合现有 `learners.json`/`trainings.json` 模式。
2. **统一配置端点**：一个 `/api/v1/config/options` 聚合返回所有前端选项，减少请求次数，比分散到各路由更简洁。
3. **ability-trend 真实数据**：从 AnswerRecord 按周聚合，无数据时返回空数组（非假数据）。
4. **orchestrator 修复**：`judge_confidence` 从 judge 结果提取，`learner_profile` 从 DB 查询——属功能缺陷修复，不仅是数据治理。
5. **Edit 持久化防范**：每处编辑后 Grep 验证，未持久化则重试。
