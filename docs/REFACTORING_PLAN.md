# 项目全面重构规划文档

> 版本：v1.0 · 编制日期：2026-07-05
> 适用项目：领域知识个性化生成与多智能体协同决策系统
> 当前阶段：已通过 P0–P3 多轮优化，处于"运行稳定、可演示"状态
> 重构目标：从"功能完备的原型"升级为"可长期演进、可水平扩展、可观测可治理"的生产级系统

---

## 目录

1. [项目现状评估](#1-项目现状评估)
2. [重构目标与范围](#2-重构目标与范围)
3. [技术方案设计](#3-技术方案设计)
4. [分阶段重构计划](#4-分阶段重构计划)
5. [质量保障体系](#5-质量保障体系)
6. [上线与监控计划](#6-上线与监控计划)
7. [附录：风险登记与回滚机制](#7-附录风险登记与回滚机制)

---

## 1. 项目现状评估

### 1.1 代码质量审计

#### 1.1.1 代码规模

| 维度 | 数值 | 评估 |
|---|---|---|
| 后端 Python 文件 | 76 个 / 17,344 行 | 中等规模，单文件可控 |
| 前端 TS/TSX 文件 | 66 个 / 11,245 行 | 中等规模 |
| 后端测试 | 9 文件 / 219 用例 | 单元覆盖较全，集成覆盖不足 |
| 前端测试 | 7 文件 / 72 用例 | 单元 + 组件测试，缺 E2E |
| API 端点数 | 81 个 | 接口规模适中 |
| ORM 模型数 | 17 个 | 领域边界清晰 |

#### 1.1.2 技术债务扫描

| 检测项 | 结果 | 说明 |
|---|---|---|
| TODO/FIXME/XXX/HACK | **0 处** | 业务代码无技术债标记 |
| `# type: ignore` / `@ts-ignore` | **0 处** | 类型安全良好 |
| `@ts-nocheck` / `@ts-expect-error` | **0 处** | — |
| 硬编码业务数据 | 2 处残留 | `tutoring_service.py` 引用 `_QUESTION_BANK`、`privacy_service.py` 引用 `_ANONYMIZATION_RULES`（已迁至 JSON 但仍保留旧引用） |
| 未使用依赖 | 1 个 | `langchain==0.1.0` 与 `langchain-openai==0.0.2` 在 requirements.txt 中，业务代码无任何 import |
| 未使用组件 | 0 个 | 前端 19 个组件均被至少 1 文件引用 |

#### 1.1.3 架构合理性

**优点**：
- 后端分层清晰：`routers → services → models`，无跨层调用（services 不导入 routers，utils 不依赖 services）
- 前端组件库统一：19 个共享组件，业务页面与 UI 组件解耦
- 配置集中：`config.py` 41 个 Field + 11 个 validator，`.env.example` 43 项

**问题**：
- 后端按"技术分层"组织，未按"业务领域"切分（学习者、知识、资源、Agent 4 个领域的代码混在 routers/services 目录）
- `main.py` 单文件 660+ 行，承担启动 + 异常处理 + 基础路由 + 种子数据 4 类职责
- 前端 `store/` 单一 store，未按领域拆分，selector 复用度高时易引发性能问题
- Agent 编排逻辑（`agents/orchestrator.py`）与业务服务耦合，难以独立演进

### 1.2 功能模块梳理

#### 1.2.1 核心功能（必须保留并优化）

| 模块 | 后端路由 | 前端页面 | 优先级 |
|---|---|---|---|
| 多智能体协同可视化 | `agent.py` (14 端点) | `MultiAgentVisualization.tsx` | P0 核心演示 |
| 学习者画像诊断 | `learner.py` (12 端点) | `LearnerProfile.tsx`、`LearningReport.tsx` | P0 |
| 个性化资源生成 | `agent.py` 资源生成流 | `ResourceGeneration.tsx` | P0 |
| 自适应导学 | `learner.py` 导学流 | `AdaptiveGuidance.tsx` | P1 |
| 知识库管理 | `knowledge.py` (11 端点) | `KnowledgeBase.tsx` | P1 |
| 企业培训管理 | `training.py` (9 端点) | `EnterpriseTraining.tsx` | P1 |

#### 1.2.2 边缘功能（评估后决定保留/精简）

| 模块 | 状态 | 建议 |
|---|---|---|
| `SystemTest.tsx` | 系统自测页，演示价值低 | 重构后保留为内部工具页 |
| `Deployment.tsx` | 部署说明页 | 改为静态文档 |
| `MetricsDashboard.tsx` | 指标看板 | 与运维监控整合 |
| `Dashboard.tsx` | 综合首页 | 简化为入口卡片 |

#### 1.2.3 数据流梳理

```
用户 → 前端 (Zustand store) → API (axios + interceptor)
                                    ↓
                              FastAPI router
                                    ↓
                              Service 层（业务逻辑 + LLM 调用）
                                    ↓
                         ┌──────────┴──────────┐
                         ↓                     ↓
                    SQLAlchemy ORM         ChromaDB 向量库
                         ↓                     ↓
                    PostgreSQL              本地持久化
```

### 1.3 性能瓶颈分析

#### 1.3.1 已优化项（P0–P3 完成情况）

| 优化项 | 状态 | 效果 |
|---|---|---|
| N+1 查询修复 | ✅ 已完成 | 核心指标接口 8→4 次查询 |
| 缓存三重防护 | ✅ 已完成 | TTL 抖动 + 空值短 TTL + 互斥锁 |
| LLM Prompt 哈希缓存 | ✅ 已完成 | 低温度调用命中即返回 |
| 前端轮询优化 | ✅ 已完成 | `document.hidden` 跳过 |
| 骨架屏 | ✅ 已完成 | 11 个页面替换 LoadingState |
| 数据库索引 | ✅ 已完成 | 29 处 `index=True` |

#### 1.3.2 待优化瓶颈

| 瓶颈 | 影响 | 优先级 |
|---|---|---|
| 缺少复合索引（如 `learner_id + created_at`） | 学习者资源列表分页慢 | P1 |
| 前端无路由懒加载 | 首屏加载全量 bundle | P1 |
| 前端单一 store，selector 未 memo | 全局重渲染风险 | P2 |
| ChromaDB 单机部署 | 向量检索无法水平扩展 | P2 |
| Celery 单 worker | 任务串行执行 | P2 |
| 无数据库读写分离 | 读多写少场景下主库压力大 | P3 |

### 1.4 用户反馈收集

> 注：当前项目处于"揭榜挂帅"演示阶段，无线上用户反馈。以下为**演示场景下识别的痛点**：

| 痛点 | 来源 | 严重度 |
|---|---|---|
| 首次加载白屏时间 > 1s | 演示时观察到 | 中 |
| LLM 调用偶发 30s+ 超时 | 网络波动时 | 高 |
| 演示数据硬编码在 seed 文件中 | 难以快速切换场景 | 中 |
| 无演示模式开关 | 演示时需手动跳过权限校验 | 低 |
| 错误提示技术化（如 "SQLAlchemyError"） | 评委不易理解 | 中 |

---

## 2. 重构目标与范围

### 2.1 功能保留与优化清单

#### 2.1.1 必须保留（行为不变）

- 全部 81 个 API 端点及其请求/响应格式
- 17 个 ORM 模型的字段定义与外键关系
- 前端 11 个业务页面的功能与交互
- JWT 认证、速率限制、CORS、脱敏规则
- LLM 调用链（含缓存、流式、Mock 兜底）
- Celery 异步任务（4 个 task）
- Prometheus + OpenTelemetry 可观测性

#### 2.1.2 允许优化（行为增强）

- 数据库索引（新增复合索引）
- 前端 bundle 拆分（路由懒加载）
- 状态管理按领域拆分（不改变 API）
- 错误提示文案优化（不改变状态码）
- LLM Prompt 模板化升级（已有 `app/prompts/`，扩展到全部场景）

#### 2.1.3 允许移除

- `langchain` 与 `langchain-openai` 依赖（业务代码无引用）
- 旧版 `_QUESTION_BANK`、`_ANONYMIZATION_RULES` 引用（已迁移到 JSON）
- 未使用的 `LoadingState` 组件（骨架屏已替代，但保留以兼容渐进迁移）

### 2.2 技术栈升级方案

#### 2.2.1 后端升级

| 组件 | 当前版本 | 目标版本 | 升级理由 |
|---|---|---|---|
| Python | 3.11 | 3.12 | 性能提升 5%、更好错误信息 |
| FastAPI | 0.109.0 | 0.115.x | 安全补丁 + lifespan 增强 |
| SQLAlchemy | 2.0.25 | 2.0.32+ | bug 修复 |
| Pydantic | 2.5.3 | 2.9.x | 性能优化 + 新特性 |
| Celery | 5.3.6 | 5.4.x | 安全补丁 |
| httpx | 0.26.0 | 0.27.x | HTTP/2 支持 |
| langchain | 0.1.0 | **移除** | 未使用 |

#### 2.2.2 前端升级

| 组件 | 当前版本 | 目标版本 | 升级理由 |
|---|---|---|---|
| React | 18.x | 18.3.x | 稳定版最新 |
| TypeScript | 5.x | 5.5+ | 类型推断增强 |
| Vite | 5.x | 5.4+ | 构建性能 |
| recharts | 2.x | 2.12+ | bug 修复 |
| Zustand | 4.x | 4.5+ | selector 性能优化 |
| ESLint | 8.x | 9.x | flat config 支持 |

#### 2.2.3 新增技术栈

| 组件 | 用途 | 选型理由 |
|---|---|---|
| Playwright | E2E 测试 | 跨浏览器、API 强大 |
| pytest-cov | 测试覆盖率量化 | 已配置 `pytest.ini` |
| vitest coverage | 前端覆盖率 | 已配置 `vite.config` |
| Sentry SDK | 错误聚合 | 前后端统一 |
| Locust | 性能压测 | Python 生态友好 |
| MkDocs | 架构文档站 | 静态站点 |

### 2.3 架构调整方向

#### 2.3.1 后端：从技术分层到领域模块化（不拆微服务）

**当前结构**（技术分层）：
```
app/
├── routers/      # 按技术分类
├── services/      # 9 个 service 混在一起
├── models/        # 17 个 model 混在一起
└── ...
```

**目标结构**（领域模块化）：
```
app/
├── domains/                    # 业务领域
│   ├── learner/               # 学习者域
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── models.py           # LearnerProfile、AnswerRecord、LearningPath
│   │   └── schemas.py
│   ├── knowledge/              # 知识域
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── models.py           # KnowledgeDoc、KnowledgeSlice
│   │   └── repository.py       # ChromaDB 访问
│   ├── resource/               # 资源域
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── models.py           # LearningResource、ResourceSection...
│   │   └── prompts/            # 资源生成 prompt 模板
│   ├── agent/                  # Agent 编排域
│   │   ├── router.py
│   │   ├── orchestrator.py
│   │   └── agents/             # 5 个 agent 实现
│   └── training/               # 企业培训域
│       ├── router.py
│       ├── service.py
│       └── models.py
├── shared/                     # 跨域共享
│   ├── models.py               # User、TestMetrics、AnonymizedData
│   ├── cache.py                # BaseService 缓存
│   ├── llm.py                  # LLMUtil
│   ├── observability/          # OTel + Prometheus
│   └── middleware/             # 限流、追踪、CORS
└── main.py                     # 仅启动 + lifespan
```

**调整原则**：
- 不拆微服务（团队规模与流量不支持）
- 按领域目录组织，每个领域内 router→service→model 闭环
- `main.py` 仅保留启动逻辑，异常处理移至 `shared/exception_handlers.py`
- 原有路由 URL 不变（`/api/v1/learner/...` 等）

#### 2.3.2 前端：状态分域 + 路由懒加载

**状态管理改造**：
```typescript
// 当前：单一 store
src/store/index.ts

// 目标：按领域拆分
src/store/
├── authStore.ts        // 认证状态
├── learnerStore.ts     // 学习者数据
├── knowledgeStore.ts   // 知识库
├── resourceStore.ts    // 资源
├── agentStore.ts       // Agent 任务
└── index.ts            // 聚合导出（兼容旧 import）
```

**路由懒加载**：
```typescript
// 当前：全部同步 import
import Dashboard from '@/pages/Dashboard'
import LearnerProfile from '@/pages/LearnerProfile'

// 目标：按路由分组懒加载
const Dashboard = lazy(() => import('@/pages/Dashboard'))
const LearnerProfile = lazy(() => import('@/pages/LearnerProfile'))

// Suspense fallback 使用 PageSkeleton
```

#### 2.3.3 数据库结构优化

详见 [3.2 数据库结构优化方案](#32-数据库结构优化方案)。

### 2.4 非功能性需求指标

| 维度 | 当前值 | 目标值 | 验证方式 |
|---|---|---|---|
| API P95 响应时间 | 未量化 | < 200ms | Locust 压测 |
| 首屏 LCP | 未量化 | < 1.5s | Lighthouse |
| 后端测试覆盖率 | 未量化 | ≥ 80% | pytest-cov |
| 前端测试覆盖率 | 未量化 | ≥ 70% | vitest coverage |
| E2E 关键路径覆盖 | 0 | 6 条核心流程 | Playwright |
| LLM 缓存命中率 | 未量化 | ≥ 40% | LLMUtil.get_usage_stats() |
| 静态扫描告警 | 0 | 0 | bandit + ESLint |
| 依赖漏洞 | 未量化 | 0 高危 | pip-audit + npm audit |
| 文档覆盖率 | < 30% | ≥ 80% | MkDocs |

---

## 3. 技术方案设计

### 3.1 新架构详细设计文档

#### 3.1.1 组件关系图

```
┌─────────────────────────────────────────────────────────────┐
│                         前端 (React)                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │  Pages   │→│  Stores  │→│   API    │→│  Axios   │    │
│  │ (lazy)   │  │ (分域)   │  │ Client  │  │ Interceptor │
│  └──────────┘  └──────────┘  └──────────┘  └──────┬─────┘    │
└─────────────────────────────────────────────────────┼────────┘
                                                       │ HTTPS
┌──────────────────────────────────────────────────────┼────────┐
│                    后端 (FastAPI)                    │        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┴─────┐  │
│  │ Middleware│→│  Router  │→│  Service │→│   Repository  │  │
│  │ (限流/追踪)│  │ (按域)   │  │ (业务)   │  │ (DB/向量库)  │  │
│  └──────────┘  └──────────┘  └────┬─────┘  └──────┬───────┘  │
│                     ↑              │                │         │
│              ┌──────┴──────┐       │                │         │
│              │  Shared     │       │                │         │
│              │ LLM/Cache   │←──────┘                │         │
│              └─────────────┘                        │         │
└─────────────────────────────────────────────────────┼─────────┘
                                                      │
              ┌───────────────────────────────────────┼─────┐
              │              数据层                    │     │
              │  ┌────────────┐  ┌────────────┐  ┌────┴───┐ │
              │  │ PostgreSQL │  │  ChromaDB  │  │ Redis  │ │
              │  │  (主库)    │  │ (向量库)   │  │ (缓存) │ │
              │  └────────────┘  └────────────┘  └────────┘ │
              └──────────────────────────────────────────────┘
```

#### 3.1.2 接口定义规范

**RESTful 命名约定**：
- 资源用名词复数：`/api/v1/learners`、`/api/v1/knowledge-docs`
- 动作用子资源：`/api/v1/learners/{id}/diagnosis`、`/api/v1/resources/{id}/validate`
- 状态码：200 成功、201 创建、400 参数错、401 未认证、403 无权限、404 不存在、429 限流、500 服务器错
- 分页：`?page=1&page_size=20`，响应含 `pagination` 对象
- 排序：`?sort=-created_at`（前缀 `-` 为降序）

**请求/响应规范**：
```json
// 成功响应
{
  "code": 200,
  "message": "success",
  "data": { ... },
  "timestamp": "2026-07-05T20:00:00+08:00"
}

// 错误响应
{
  "code": 400,
  "message": "请求参数校验失败",
  "data": { "errors": [{ "field": "name", "message": "..." }] },
  "timestamp": "2026-07-05T20:00:00+08:00"
}

// 分页响应
{
  "code": 200,
  "data": {
    "items": [...],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 100,
      "total_pages": 5
    }
  }
}
```

#### 3.1.3 错误处理分层

```
Middleware (限流/追踪)
    ↓
Exception Handler (按异常类型)
    ├── HTTPException → 4xx
    ├── RequestValidationError → 400
    ├── IntegrityError → 400
    ├── OperationalError → 503
    └── Exception → 500
    ↓
Service 层（业务异常用 ValueError）
```

### 3.2 数据库结构优化方案

#### 3.2.1 索引优化

**当前索引**：29 处单列索引。

**待新增复合索引**：

```sql
-- 学习者资源列表（高频查询）
CREATE INDEX idx_resource_learner_created ON learning_resources (learner_id, created_at DESC);

-- 学习者答题记录分页
CREATE INDEX idx_answer_learner_created ON answer_records (learner_id, created_at DESC);

-- 知识文档按状态查询
CREATE INDEX idx_knowledge_doc_status ON knowledge_docs (status, updated_at);

-- Agent 任务按状态查询
CREATE INDEX idx_agent_task_status ON agent_tasks (status, created_at);
```

**迁移策略**：通过 Alembic 创建新迁移文件 `add_composite_indexes.py`，`upgrade` 时创建，`downgrade` 时删除。

#### 3.2.2 表结构调整

**新增字段**：
- `learning_resources.is_archived BOOLEAN DEFAULT FALSE` — 软归档标记
- `answer_records.archived_at TIMESTAMP` — 归档时间戳
- `agent_tasks.retry_count INTEGER DEFAULT 0` — 重试计数

**拆分大表**（数据量超过 100 万行时）：
- `answer_records` 按月分区（PostgreSQL 原生分区）
- `agent_task_logs`（新增）记录任务执行日志，按周分区

#### 3.2.3 数据迁移策略

**阶段 1：在线迁移（零停机）**
1. 创建新表/索引（`CREATE INDEX CONCURRENTLY`）
2. 双写：旧表 + 新表
3. 数据回填：`INSERT INTO new_table SELECT ... FROM old_table`
4. 校验：行数 + 抽样比对
5. 切换读取：Service 层切到新表
6. 删除旧表

**阶段 2：存量数据归档**
1. 调用 `ArchiveService.archive_old_data(days=90)`
2. 归档表 `archived_answer_records` 用于历史查询
3. 主表数据量降低 60%+

#### 3.2.4 读写分离方案（后期）

**适用场景**：日活 > 1000、读 QPS > 100。

**方案**：
- PostgreSQL 主从复制（1 主 2 从）
- SQLAlchemy `Session` 区分读写：
  ```python
  # 写
  db = SessionLocal()  # 主库
  # 读
  db = ReadOnlySessionLocal()  # 从库
  ```
- Celery 任务用从库
- LLM 缓存查询用从库

### 3.3 前端架构改进

#### 3.3.1 组件化设计

**分层规范**：
```
src/
├── components/         # 通用 UI 组件（无业务依赖）
│   ├── ui/             # 基础元素：Button、Input、Card
│   ├── feedback/       # 反馈：Toast、Modal、Skeleton
│   └── layout/         # 布局：Layout、PageTransition
├── features/           # 业务组件（依赖 store/api）
│   ├── learner/
│   │   ├── LearnerList.tsx
│   │   ├── LearnerDetail.tsx
│   │   └── AbilityRadar.tsx
│   ├── knowledge/
│   ├── resource/
│   ├── agent/
│   └── training/
├── pages/              # 页面（组合 features）
├── store/              # 按域拆分
├── api/                # API 客户端
└── lib/                # 工具函数
```

**组件 API 设计原则**：
- 受控 vs 非受控：表单组件受控，展示组件非受控
- Props 接口：必填 props 在前，可选 props 在后，回调用 `on*` 前缀
- 默认值：所有可选 props 必须有默认值，避免 `undefined`

#### 3.3.2 状态管理方案

**Zustand 按域拆分**：

```typescript
// store/learnerStore.ts
interface LearnerState {
  learners: Learner[]
  selected: Learner | null
  loading: boolean
  error: string | null
  fetchLearners: () => Promise<void>
  selectLearner: (id: number) => void
}

export const useLearnerStore = create<LearnerState>((set, get) => ({
  // ...
}))

// 选择器 memo（避免全局重渲染）
export const useLearnerList = () => useLearnerStore(s => s.learners)
export const useSelectedLearner = () => useLearnerStore(s => s.selected)
```

**状态分层**：
- 服务器状态（API 数据）→ 可选 React Query 或自维护
- UI 状态（弹窗、Tab）→ 局部 useState
- 全局状态（认证、主题）→ Zustand 全局 store

#### 3.3.3 构建流程优化

**Vite 配置增强**：
```typescript
// vite.config.ts
export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-recharts': ['recharts'],
          'vendor-utils': ['axios', 'zustand', 'clsx', 'lucide-react'],
        },
      },
    },
    chunkSizeWarningLimit: 500, // kb
  },
})
```

**路由懒加载**：
```typescript
const Dashboard = lazy(() => import('@/pages/Dashboard'))
// Suspense fallback 用 PageSkeleton
```

### 3.4 后端服务重构

#### 3.4.1 API 设计规范

详见 [3.1.2 接口定义规范](#312-接口定义规范)。

#### 3.4.2 中间件选择

**当前中间件链**（按注册顺序）：
1. CORS
2. Prometheus（最先执行）
3. RequestTracing
4. RateLimit

**新增中间件**：
- `RequestLoggingMiddleware` — 结构化访问日志（含 request_id、user_id、duration）
- `ErrorBoundaryMiddleware` — 兜底未捕获异常（已有全局 handler，中间件用于增强可观测性）

#### 3.4.3 服务间通信机制

**当前**：单体应用，函数直接调用。

**重构后（仍单体）**：
- 同领域内：Service 直接调用 Service
- 跨领域：通过事件总线（轻量级，基于 Python `blinker` 或自实现）
  ```python
  # 学习者提交答题后触发
  learner_submitted_answer.send(learner_id=1, answer_id=100)
  
  # 资源生成服务订阅
  @learner_submitted_answer.connect
  def trigger_resource_generation(learner_id, answer_id):
      ResourceService.generate_for_learner(learner_id)
  ```

**未来微服务化时**：替换为 RabbitMQ / Kafka。

---

## 4. 分阶段重构计划

### 4.1 任务优先级排序

按"风险 vs 价值"四象限排序：

| 优先级 | 任务 | 风险 | 价值 |
|---|---|---|---|
| **P0** | 移除 langchain 依赖 | 低 | 中 |
| **P0** | 清理硬编码残留 | 低 | 中 |
| **P0** | 新增复合索引 | 低 | 高 |
| **P0** | 测试覆盖率量化（pytest-cov + vitest coverage） | 低 | 高 |
| **P1** | 前端路由懒加载 | 低 | 高 |
| **P1** | 前端 store 按域拆分 | 中 | 中 |
| **P1** | 后端领域模块化（目录重组） | 中 | 中 |
| **P1** | E2E 测试体系（Playwright） | 低 | 高 |
| **P2** | `main.py` 拆分 | 中 | 中 |
| **P2** | 错误提示文案优化 | 低 | 中 |
| **P2** | LLM Prompt 模板全量化 | 低 | 中 |
| **P2** | Sentry 错误聚合接入 | 低 | 中 |
| **P3** | 数据库读写分离 | 高 | 中 |
| **P3** | 表分区（answer_records 按月） | 高 | 低 |
| **P3** | K8s 部署方案 | 高 | 中 |

### 4.2 各阶段里程碑与交付物

#### 阶段 1：清理与量化（1–2 周）

**目标**：消除已知技术债，建立质量基线。

**交付物**：
- ✅ 移除 `langchain`、`langchain-openai` 依赖
- ✅ 清理 `_QUESTION_BANK`、`_ANONYMIZATION_RULES` 旧引用
- ✅ 新增 4 个复合索引（通过 Alembic 迁移）
- ✅ 配置 `pytest-cov`，输出后端覆盖率报告
- ✅ 配置 `vitest coverage`，输出前端覆盖率报告
- ✅ 建立覆盖率 CI 门禁（后端 ≥ 70%、前端 ≥ 60%）
- ✅ 生成覆盖率基线文档

**里程碑**：CI 在每次 PR 中输出覆盖率变化（+/-）。

#### 阶段 2：前端性能优化（2–3 周）

**目标**：首屏 LCP < 1.5s，bundle 体积降低 40%。

**交付物**：
- ✅ 路由懒加载（11 个页面全部 lazy）
- ✅ Vite manualChunks 拆包
- ✅ Store 按域拆分（5 个领域 store）
- ✅ Selector memo 化
- ✅ Lighthouse 性能基线报告
- ✅ 图片资源懒加载（如有）

**里程碑**：Lighthouse Performance ≥ 85。

#### 阶段 3：后端领域模块化（3–4 周）

**目标**：从技术分层迁移到领域模块化，URL 不变。

**交付物**：
- ✅ 创建 `app/domains/` 目录结构
- ✅ 迁移 `learner` 域（router + service + model）
- ✅ 迁移 `knowledge` 域
- ✅ 迁移 `resource` 域
- ✅ 迁移 `agent` 域
- ✅ 迁移 `training` 域
- ✅ `main.py` 拆分：启动、异常处理、种子数据分离
- ✅ 全部 219 后端测试通过（URL 不变）

**里程碑**：领域目录结构稳定，`main.py` < 100 行。

#### 阶段 4：E2E 测试体系（2 周）

**目标**：6 条核心业务流程 E2E 覆盖。

**交付物**：
- ✅ Playwright 环境搭建
- ✅ 6 条 E2E 用例：
  1. 登录 → 查看学习者列表 → 进入详情 → 查看能力雷达
  2. 创建知识文档 → 切片 → 向量化 → 检索
  3. 触发 Agent 任务 → 查看实时进度 → 查看生成资源
  4. 学习者答题 → 自适应导学决策 → 推荐资源
  5. 创建企业培训 → 批量导入 → 查看统计
  6. 系统健康检查 → 指标看板 → 报告导出
- ✅ E2E 加入 CI（nightly 执行）

**里程碑**：E2E 在演示前自动跑通。

#### 阶段 5：可观测性增强（1–2 周）

**目标**：错误聚合 + 用户行为埋点 + 告警规则。

**交付物**：
- ✅ Sentry SDK 接入（前后端）
- ✅ 用户行为埋点（核心按钮点击、页面停留）
- ✅ Prometheus 告警规则（错误率、延迟、资源使用）
- ✅ Grafana Dashboard 模板
- ✅ 错误提示文案优化（业务化表述）

**里程碑**：演示前可一键查看系统健康度。

#### 阶段 6：部署与文档（2 周）

**目标**：K8s 部署方案 + 文档站建设。

**交付物**：
- ✅ Helm Chart（替代 docker-compose）
- ✅ 蓝绿/金丝雀发布脚本
- ✅ MkDocs 文档站（架构、API、运维、开发指南）
- ✅ 重构效果评估报告（对比阶段 0 基线）

**里程碑**：文档站上线，部署可一键回滚。

### 4.3 代码迁移策略

#### 4.3.1 增量迁移（推荐）

**原则**：每个阶段独立交付，不阻塞业务。

**策略**：
1. 新建目标目录结构（如 `app/domains/learner/`）
2. 在新目录创建新文件（复制旧代码 + 调整 import）
3. 旧文件保留，标记 `# DEPRECATED: will be removed in phase X`
4. `main.py` 同时注册新旧 router（用环境变量切换）
5. 测试通过后删除旧文件
6. 更新 CI 矩阵

**示例**：
```python
# 阶段 3.1：新建 app/domains/learner/router.py
# 复制 app/routers/learner.py 内容
# main.py 同时注册：
if settings.ENABLE_DOMAIN_ROUTER:
    from app.domains.learner.router import router as learner_domain_router
    app.include_router(learner_domain_router, prefix=...)
else:
    from app.routers.learner import router as learner_router
    app.include_router(learner_router, prefix=...)
```

#### 4.3.2 整体替换（不推荐）

仅适用于：依赖版本升级、配置格式变更等无法共存的场景。

### 4.4 回滚机制

详见 [第 7 章](#7-附录风险登记与回滚机制)。

---

## 5. 质量保障体系

### 5.1 单元测试覆盖率目标

| 模块 | 当前覆盖率 | 目标覆盖率 | 验证方式 |
|---|---|---|---|
| 后端 services | 未量化 | ≥ 85% | pytest-cov |
| 后端 routers | 部分覆盖 | ≥ 80% | API 测试 |
| 后端 utils | 部分覆盖 | ≥ 90% | 单元测试 |
| 后端 agents | 0 | ≥ 70% | 单元测试 + mock LLM |
| 前端 store | 部分覆盖 | ≥ 85% | vitest |
| 前端 lib | 部分覆盖 | ≥ 90% | vitest |
| 前端 components | 0 | ≥ 60% | 组件测试 |

**CI 门禁**：
- 总覆盖率不下降（diff 覆盖率 ≥ 0%）
- 新增代码覆盖率 ≥ 80%
- 关键 service（如 `resource_service.py`）必须 100%

### 5.2 集成测试与 E2E 测试方案

#### 5.2.1 集成测试（后端）

**目标**：验证 service → repository → DB 全链路。

**方案**：
- 使用测试数据库（SQLite in-memory）
- 每个测试用例独立事务，结束回滚
- Mock LLM 调用（避免真实 API 消耗）
- 覆盖核心 service 的 CRUD + 边界条件

**新增测试文件**：
- `tests/test_resource_service.py`（当前缺失）
- `tests/test_common_service.py`（当前缺失）
- `tests/test_archive_service.py`（当前缺失）

#### 5.2.2 集成测试（前端）

**目标**：验证页面与 store/api 的集成。

**方案**：
- Mock API 响应（MSW）
- 测试用户交互流程（点击、输入、跳转）
- 覆盖 11 个核心页面

#### 5.2.3 E2E 测试（Playwright）

详见 [4.2 阶段 4](#阶段-4e2e-测试体系2-周)。

**执行频率**：
- 本地开发：手动执行
- CI：nightly 执行
- 发布前：必须通过

### 5.3 代码审查流程规范

#### 5.3.1 PR 规范

- 标题：`[类型][模块] 简述`，如 `[feat][learner] 新增批量导入`
- 描述：包含背景、变更、测试方式、影响范围
- 关联 Issue
- 截图（UI 变更必填）

#### 5.3.2 审查清单

**必查项**：
- [ ] 测试通过（CI 绿色）
- [ ] 覆盖率不下降
- [ ] 无 lint 警告
- [ ] 无新增 TODO/FIXME（除非标注原因）
- [ ] 无硬编码业务数据
- [ ] 错误处理完整（无静默 catch）
- [ ] 接口兼容性（如改 schema 必须迁移）

**建议项**：
- [ ] 命名清晰
- [ ] 单一职责
- [ ] 注释解释 WHY 而非 WHAT
- [ ] 性能考虑（N+1、循环内 IO）

#### 5.3.3 审查流程

1. 作者自审
2. 1 人审查（小改动）
3. 2 人审查（架构变更、核心模块）
4. 维护者批准
5. 合并到 `develop` 分支
6. 发布到 `main` 分支

### 5.4 CI/CD 管道配置

#### 5.4.1 当前 CI（已建立）

4 个 job：`lint`、`backend-test`、`frontend-test`、`security`。

#### 5.4.2 增强项

```yaml
# .github/workflows/ci.yml 增强
jobs:
  coverage:
    runs-on: ubuntu-latest
    steps:
      - run: pytest --cov=app --cov-report=xml
      - run: vitest run --coverage
      - uses: codecov/codecov-action@v3  # 上传到 Codecov
      
  e2e:
    runs-on: ubuntu-latest
    schedule:
      - cron: '0 2 * * *'  # nightly
    steps:
      - run: docker compose up -d
      - run: npx playwright test
      
  dependabot:
    # 已配置，保持
```

#### 5.4.3 发布流程

```
feature/xxx → develop (PR + CI) → main (release) → tag → deploy
```

---

## 6. 上线与监控计划

### 6.1 灰度发布策略

#### 6.1.1 蓝绿发布（推荐）

**适用场景**：后端 API 升级。

**步骤**：
1. 部署新版本（Green）到独立容器
2. 健康检查通过后，Nginx 切换流量到 Green
3. 观察 30 分钟，无异常则下线旧版本（Blue）
4. 异常则秒级回滚到 Blue

**Nginx 配置示例**：
```nginx
upstream backend {
    server blue:8000 weight=0;
    server green:8000 weight=100;
}
```

#### 6.1.2 金丝雀发布

**适用场景**：高风险变更（如数据库迁移）。

**步骤**：
1. 部署 1 个新版本实例（10% 流量）
2. 监控错误率、延迟、用户反馈
3. 逐步增加流量（10% → 30% → 50% → 100%）
4. 异常则切回 100% 旧版本

### 6.2 线上监控指标设定

#### 6.2.1 系统指标（Prometheus）

| 指标 | 阈值 | 告警动作 |
|---|---|---|
| HTTP 5xx 错误率 | > 1% | 立即告警 |
| P95 响应时间 | > 500ms | 5 分钟内告警 |
| CPU 使用率 | > 80% | 10 分钟持续则告警 |
| 内存使用率 | > 90% | 立即告警 |
| 磁盘剩余 | < 10% | 立即告警 |
| DB 连接数 | > 80% 池上限 | 5 分钟内告警 |

#### 6.2.2 业务指标

| 指标 | 含义 | 采集方式 |
|---|---|---|
| LLM 调用次数 | 总调用 / 缓存命中 | `LLMUtil.get_usage_stats()` |
| 资源生成成功率 | 生成成功 / 总尝试 | Service 日志 |
| 学习者答题正确率 | 正确 / 总答题 | answer_record 表 |
| Agent 任务完成率 | 完成 / 总任务 | agent_task 表 |
| 知识库覆盖率 | 已切片文档 / 总文档 | knowledge_doc 表 |

#### 6.2.3 用户行为数据

**前端埋点**：
```typescript
// utils/analytics.ts
export function track(event: string, props?: Record<string, any>) {
  // 发送到后端 /api/v1/analytics/track
  // 或第三方（如 PostHog）
}

// 使用示例
track('learner_detail_view', { learner_id: 1 })
track('resource_generate_click', { type: 'guide' })
```

**采集维度**：
- 页面停留时长
- 按钮点击
- 表单提交成功率
- 错误发生（含 Sentry 关联 ID）

### 6.3 问题快速响应机制

#### 6.3.1 错误分级

| 级别 | 定义 | 响应时间 | 处理人 |
|---|---|---|---|
| P0 | 核心功能不可用 | 5 分钟 | 主维护者 |
| P1 | 部分功能异常 | 30 分钟 | 模块负责人 |
| P2 | 体验问题 | 4 小时 | 值班人员 |
| P3 | 优化建议 | 下个迭代 | — |

#### 6.3.2 响应流程

```
Sentry 告警 → 值班群通知 → 确认分级 → 排查定位 → 修复 → 验证 → 复盘
```

**Sentry 接入**：
```python
# backend/app/main.py
import sentry_sdk
sentry_sdk.init(
    dsn=settings.SENTRY_DSN,
    traces_sample_rate=0.1,
    environment=settings.APP_ENV,
)
```

### 6.4 重构效果评估方法

#### 6.4.1 评估维度

| 维度 | 基线（当前） | 目标 | 验证方式 |
|---|---|---|---|
| API P95 响应时间 | 未量化 | < 200ms | Locust 压测 |
| 首屏 LCP | 未量化 | < 1.5s | Lighthouse |
| 后端测试覆盖率 | 未量化 | ≥ 80% | pytest-cov |
| 前端测试覆盖率 | 未量化 | ≥ 70% | vitest coverage |
| E2E 用例数 | 0 | 6 | Playwright |
| 静态扫描告警 | 0 | 0 | bandit + ESLint |
| 依赖漏洞 | 未量化 | 0 高危 | pip-audit + npm audit |
| 文档覆盖率 | < 30% | ≥ 80% | MkDocs |
| `main.py` 行数 | 660+ | < 100 | 文件统计 |
| 领域模块化率 | 0% | 100% | 目录检查 |

#### 6.4.2 评估流程

1. **阶段 0**：记录基线指标（重构前）
2. **每阶段结束**：记录当前指标 + 对比基线
3. **全部完成**：生成《重构效果评估报告》
4. **3 个月后**：复评，验证长期收益

---

## 7. 附录：风险登记与回滚机制

### 7.1 风险登记表

| 风险 | 概率 | 影响 | 应对措施 |
|---|---|---|---|
| 数据库迁移失败 | 中 | 高 | Alembic `downgrade` 回滚 + 备份 |
| 领域模块化导致 import 错误 | 高 | 中 | 增量迁移 + 全量测试 |
| 前端 store 拆分引发状态丢失 | 中 | 中 | 兼容旧 import + 渐进切换 |
| Playwright E2E 环境复杂 | 中 | 低 | Docker 化测试环境 |
| 依赖升级引入 breaking change | 中 | 高 | 锁定补丁版本 + 回归测试 |
| K8s 部署学习成本 | 高 | 中 | 文档 + 培训 + 保留 docker-compose |

### 7.2 回滚机制

#### 7.2.1 代码回滚

- 每个 PR 独立可回滚（git revert）
- 主分支保护：必须 PR + CI 通过
- 关键发布打 tag，可快速 `git checkout <tag>`

#### 7.2.2 数据库回滚

- 每次迁移生成 `upgrade` + `downgrade`
- 迁移前自动备份：`scripts/backup_db.py`
- 回滚命令：`alembic downgrade -1`

#### 7.2.3 部署回滚

- Docker 镜像保留最近 5 个版本
- K8s `kubectl rollout undo deployment/backend`
- Nginx 蓝绿切换秒级回滚

#### 7.2.4 配置回滚

- `.env` 文件版本化（去除敏感信息后）
- 配置变更走 PR 审查
- 敏感配置（API Key、SECRET_KEY）通过 Secret Manager

---

## 附录 A：重构前后对比表

| 维度 | 重构前 | 重构后 |
|---|---|---|
| 后端架构 | 技术分层（routers/services/models） | 领域模块化（domains/learner/knowledge/...） |
| 前端状态 | 单一 store | 按域拆分（5 个 store） |
| 前端路由 | 同步 import | 路由懒加载 |
| 测试覆盖 | 未量化 | 后端 ≥ 80%、前端 ≥ 70% |
| E2E 测试 | 0 | 6 条核心流程 |
| 错误监控 | 日志 | Sentry + 告警 |
| 数据库索引 | 29 单列 | 29 + 4 复合 |
| `main.py` 行数 | 660+ | < 100 |
| 部署方式 | docker-compose | Helm + K8s |
| 文档 | 分散 | MkDocs 集中 |

## 附录 B：参考资料

- FastAPI 官方文档：https://fastapi.tiangolo.com/
- SQLAlchemy 2.0 文档：https://docs.sqlalchemy.org/en/20/
- Alembic 迁移指南：https://alembic.sqlalchemy.org/en/latest/
- Playwright 文档：https://playwright.dev/
- Prometheus 最佳实践：https://prometheus.io/docs/practices/
- 12-Factor App：https://12factor.net/

---

**文档维护者**：项目维护团队
**最后更新**：2026-07-05
**下次评审**：阶段 1 完成后
