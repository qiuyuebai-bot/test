# API 参考文档

> **领域知识个性化生成与多智能体协同决策系统** 后端 API 完整参考
>
> - OpenAPI 规范: [`docs/api/openapi.json`](api/openapi.json)
> - Swagger UI: `http://localhost:8000/docs`
> - ReDoc: `http://localhost:8000/redoc`
> - 版本: 1.0.0 | 路径数: 82 | 模型数: 27

---

## 目录

- [认证方式](#认证方式)
- [统一响应格式](#统一响应格式)
- [错误码](#错误码)
- [速率限制](#速率限制)
- [接口清单](#接口清单)
  - [认证模块](#认证模块)
  - [学习者画像模块](#学习者画像模块)
  - [知识库模块](#知识库模块)
  - [Agent 协同调度模块](#agent-协同调度模块)
  - [核心业务模块](#核心业务模块)
  - [企业培训模块](#企业培训模块)
  - [数据隐私与合规模块](#数据隐私与合规模块)
  - [审计日志模块](#审计日志模块)
  - [运维与监控模块](#运维与监控模块)

---

## 认证方式

系统使用 **JWT Bearer Token** 认证。

| 步骤 | 说明 |
|------|------|
| 1. 登录 | `POST /api/v1/auth/login` 获取 `access_token` 和 `refresh_token` |
| 2. 携带Token | 请求头添加 `Authorization: Bearer <access_token>` |
| 3. 刷新Token | `access_token` 过期后，`POST /api/v1/auth/refresh` 获取新Token |
| 4. 验证 | `GET /api/v1/auth/verify` 检查Token有效性 |

**Token 有效期**: 由 `JWT_EXPIRE_MINUTES` 配置（默认 1440 分钟 = 24 小时）

**公开接口**（无需认证）:
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/register`
- `GET /` `GET /health` `GET /health/live` `GET /health/ready`
- `GET /api/v1/info`

---

## 统一响应格式

所有接口返回统一的 JSON 结构：

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {},
  "timestamp": "2024-03-15 14:30:00"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | int | 业务状态码，`200` 表示成功 |
| `message` | string | 提示消息 |
| `data` | any | 业务数据（对象、数组或 null） |
| `timestamp` | string | 响应时间戳 `YYYY-MM-DD HH:MM:SS` |

**分页响应**的 `data` 结构：

```json
{
  "items": [],
  "total": 100,
  "page": 1,
  "page_size": 10,
  "total_pages": 10
}
```

---

## 错误码

| HTTP 状态码 | code | 说明 |
|-------------|------|------|
| 200 | 200 | 成功 |
| 201 | 201 | 创建成功 |
| 400 | 400 | 请求参数错误 |
| 401 | 401 | 未授权（Token缺失/过期/无效） |
| 403 | 403 | 权限不足 |
| 404 | 404 | 资源不存在 |
| 413 | 413 | 上传文件超出大小限制 |
| 422 | 422 | 请求体验证失败（Pydantic校验） |
| 500 | 500 | 服务器内部错误 |
| 503 | 503 | 服务不可用 |

---

## 速率限制

| 接口类别 | 限制 | 环境变量 |
|----------|------|----------|
| 登录接口 | 10次/分钟 | `RATE_LIMIT_LOGIN` |
| 上传接口 | 20次/分钟 | `RATE_LIMIT_UPLOAD` |
| 通用API | 100次/分钟 | `RATE_LIMIT_API` |

超出限制返回 `429 Too Many Requests`。

---

## 接口清单

### 认证模块

路由前缀: `/api/v1/auth`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/auth/register` | 用户注册（默认 learner 角色） |
| POST | `/auth/login` | 用户登录，返回 JWT Token 对 |
| POST | `/auth/refresh` | 刷新 Token |
| GET | `/auth/me` | 获取当前用户信息 |
| POST | `/auth/change-password` | 修改密码 |
| POST | `/auth/logout` | 用户登出 |
| GET | `/auth/verify` | 验证 Token 有效性 |

---

### 学习者画像模块

路由前缀: `/api/v1/learners`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/learners` | 创建学习者画像 |
| GET | `/learners` | 获取学习者列表（分页） |
| GET | `/learners/{learner_id}` | 获取学习者详情 |
| PUT | `/learners/{learner_id}` | 更新学习者画像 |
| DELETE | `/learners/{learner_id}` | 删除学习者画像 |
| POST | `/learners/batch-import` | 批量导入学习者 |
| POST | `/learners/batch-export` | 批量导出学习者 |
| POST | `/learners/{learner_id}/analyze` | 学情分析 |
| POST | `/learners/{learner_id}/anonymize` | 数据脱敏 |
| POST | `/learners/{learner_id}/answers` | 添加答题记录 |
| GET | `/learners/{learner_id}/answers` | 获取答题记录（分页） |
| GET | `/learners/{learner_id}/blind-areas` | 获取知识盲区标签云 |

---

### 知识库模块

路由前缀: `/api/v1/knowledge`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/knowledge/upload` | 上传知识库文档（multipart/form-data 或 JSON） | 管理员 |
| GET | `/knowledge/docs` | 获取文档列表（分页） | 登录 |
| GET | `/knowledge/docs/{doc_id}` | 获取文档详情 | 登录 |
| PUT | `/knowledge/docs/{doc_id}` | 更新文档信息 | 管理员 |
| DELETE | `/knowledge/docs/{doc_id}` | 删除文档 | 管理员 |
| POST | `/knowledge/docs/batch-delete` | 批量删除文档 | 管理员 |
| POST | `/knowledge/search` | 知识库相似度检索 | 登录 |
| GET | `/knowledge/preview/{doc_id}` | 文档内容预览 | 登录 |
| GET | `/knowledge/trace/{resource_id}` | 知识溯源查询 | 登录 |
| GET | `/knowledge/stats/industries` | 各行业知识库统计 | 登录 |
| POST | `/knowledge/docs/{doc_id}/reindex` | 重新索引文档 | 管理员 |

---

### Agent 协同调度模块

路由前缀: `/api/v1/agent`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/agent/status` | 获取所有 Agent 状态 |
| GET | `/agent/status/{agent_type}` | 获取指定 Agent 状态 |
| POST | `/agent/tasks` | 创建 Agent 任务 |
| POST | `/agent/tasks/{task_id}/start` | 启动任务执行 |
| POST | `/agent/tasks/{task_id}/stream-ticket` | 获取 SSE 短期票据 |
| GET | `/agent/tasks/{task_id}/events` | SSE 实时任务进度流 |
| GET | `/agent/tasks/{task_id}/status` | 查询任务状态 |
| GET | `/agent/tasks/{task_id}/logs` | 查询任务执行日志 |
| GET | `/agent/tasks` | 获取任务列表（分页） |
| POST | `/agent/diagnose` | 执行学情诊断 |
| GET | `/agent/debate/{task_id}` | 获取辩论记录 |
| GET | `/agent/metrics/hallucination` | 幻觉率统计 |
| GET | `/agent/metrics/performance` | Agent 性能统计 |
| POST | `/agent/run/full-pipeline` | 一键执行完整流水线 |

---

### 核心业务模块

路由前缀: `/api/v1`

#### 资源生成

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/resources/generate` | 生成三类个性化学习资源（Celery异步） |
| POST | `/resources/generate/batch` | 批量生成资源（Celery异步） |
| POST | `/resources/generate/sync` | 同步生成三类资源 |
| GET | `/resources` | 获取资源列表（分页） |
| GET | `/resources/{resource_id}` | 获取资源详情 |
| GET | `/resources/{resource_id}/export` | 导出资源 |

#### 异步任务

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/tasks/{task_id}/status` | 查询 Celery 任务进度 |

#### 学情报告

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/report/learner/{learner_id}` | 生成完整学情报告 |
| GET | `/report/learner/{learner_id}/pdf` | 导出学情报告 PDF |
| GET | `/report/heatmap/{learner_id}` | 获取知识盲区热力图数据 |
| GET | `/report/match-curve/{learner_id}` | 获取难度匹配曲线数据 |
| GET | `/report/ability-trend/{learner_id}` | 获取能力发展趋势数据 |
| GET | `/report/learning-path/{learner_id}` | 获取学习路径拓扑数据 |
| GET | `/report/ability-radar/{learner_id}` | 获取能力雷达图数据 |
| GET | `/report/metrics` | 获取系统核心指标 |
| POST | `/report/metrics/update` | 更新指标统计 |

#### 自适应导学

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/tutoring/questions` | 获取导学题库 |
| POST | `/tutoring/answer` | 提交答题结果 |
| GET | `/tutoring/history/{learner_id}` | 获取交互历史记录（分页） |
| GET | `/tutoring/decision-logic` | 获取自适应决策逻辑说明 |

#### 前端配置

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/config/options` | 获取前端业务配置选项 |

---

### 企业培训模块

路由前缀: `/api/v1/trainings`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/trainings` | 获取培训任务列表（分页） |
| POST | `/trainings` | 创建培训任务 |
| GET | `/trainings/stats/overview` | 获取培训统计 |
| GET | `/trainings/transfers/list` | 获取转岗培训列表 |
| GET | `/trainings/skill-gaps/analysis` | 获取技能差距分析 |
| POST | `/trainings/batch-import` | 批量导入培训任务 |
| GET | `/trainings/{training_id}` | 获取培训任务详情 |
| PUT | `/trainings/{training_id}` | 更新培训任务 |
| DELETE | `/trainings/{training_id}` | 删除培训任务 |

---

### 数据隐私与合规模块

路由前缀: `/api/v1/privacy`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/privacy/overview` | 获取隐私合规总览 |
| GET | `/privacy/compliance` | 获取隐私合规检查项 |
| GET | `/privacy/anonymization` | 获取数据脱敏规则 |
| POST | `/privacy/anonymization/test` | 测试数据脱敏 |
| GET | `/privacy/permissions` | 获取数据权限配置 |
| GET | `/privacy/keys` | 获取密钥管理信息（脱敏展示） |
| GET | `/privacy/documents` | 获取合规文档列表 |

---

### 运维与监控模块

无需 API 前缀，直接在根路径提供。

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/` | 根路径 - 系统信息 | 否 |
| GET | `/health` | 存活检查（Liveness） | 否 |
| GET | `/health/live` | 存活检查 | 否 |
| GET | `/health/ready` | 就绪检查（Readiness） | 否 |
| GET | `/api/v1/health` | 存活检查（带前缀） | 否 |
| GET | `/api/v1/health/live` | 存活检查（带前缀） | 否 |
| GET | `/api/v1/health/ready` | 就绪检查（带前缀） | 否 |
| GET | `/metrics` | Prometheus 指标端点 | 否 |
| GET | `/api/v1/metrics/prometheus` | Prometheus 指标（带前缀） | 否 |
| GET | `/api/v1/info` | 系统详细信息 | 否 |
| GET | `/api/v1/metrics` | 系统核心指标 | 是 |

---

### 审计日志模块

路由前缀: `/api/v1/audit`，仅管理员可访问。中间件自动记录写操作（POST/PUT/PATCH/DELETE）和关键读操作（登录/登出/注册/导出/搜索），健康检查与 OPTIONS 预检不记录。

| 方法 | 路径 | 说明 | 认证 | 权限 |
|------|------|------|------|------|
| GET | `/api/v1/audit/logs` | 分页查询审计日志（支持 user_id/action/resource_type/日期/关键词筛选） | 是 | admin |
| GET | `/api/v1/audit/stats` | 审计统计概览（操作分布、活跃用户、资源分布、错误率） | 是 | admin |
| GET | `/api/v1/audit/actions` | 获取已记录的操作类型列表（用于前端筛选下拉框） | 是 | admin |

**审计日志字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 日志ID |
| `created_at` | datetime | 记录时间 |
| `user_id` | int/null | 操作者用户ID（未登录为 null） |
| `username` | string/null | 操作者用户名 |
| `action` | string | 操作类型: LOGIN/LOGOUT/REGISTER/CREATE/UPDATE/DELETE/EXPORT/SEARCH/ACCESS |
| `resource_type` | string/null | 资源类型: auth/learner/knowledge/agent/training/resource/report/privacy 等 |
| `resource_id` | string/null | 资源ID（从路径提取） |
| `method` | string | HTTP 方法 |
| `path` | string | 请求路径 |
| `status_code` | int/null | 响应状态码 |
| `ip_address` | string/null | 客户端 IP |
| `duration_ms` | int/null | 请求耗时（毫秒） |
| `request_id` | string/null | 链路追踪 ID |

---

## 角色权限

| 角色 | 说明 | 典型操作 |
|------|------|----------|
| `admin` | 管理员 | 全部操作，包括知识库上传/删除、用户管理、审计日志查询 |
| `teacher` | 教师 | 查看学习者、创建任务、生成报告 |
| `learner` | 学习者 | 个人信息查看、答题、导学交互 |
| `enterprise` | 企业用户 | 企业培训任务管理 |

---

## OpenAPI 导出

### 本地导出

```bash
cd backend
python scripts/export_openapi.py
# 输出: docs/api/openapi.json
```

### CI 校验模式

```bash
python scripts/export_openapi.py --check
# 仅校验 OpenAPI 可生成，不写文件
```

### 使用 openapi.json

- **Swagger UI 离线托管**: 将 `openapi.json` 放入静态资源，用 swagger-ui-dist 加载
- **前端代码生成**: 使用 `openapi-generator` 生成 TypeScript SDK
- **API 变更检测**: 对比 git 中 `openapi.json` 的 diff 检测破坏性变更
