# 项目重写计划：6 人团队四周冲刺方案

> 生成时间：2026-07-11
> 项目：领域知识个性化生成与多智能体协同决策系统
> 目标：以十年工程师视角，6 人团队四周完成项目高质量重写
> 场景：Challenge Cup 揭榜挂帅演示与答辩

---

## 目录

- [一、团队分工](#一团队分工)
- [二、四周冲刺计划](#二四周冲刺计划)
  - [第 1 周：地基（Day 1-5）](#第-1-周地基day-1-5)
  - [第 2 周：核心功能（Day 6-10）](#第-2-周核心功能day-6-10)
  - [第 3 周：集成与高级功能（Day 11-15）](#第-3-周集成与高级功能day-11-15)
  - [第 4 周：打磨与交付（Day 16-20）](#第-4-周打磨与交付day-16-20)
- [三、关键依赖路径](#三关键依赖路径)
- [四、协作机制](#四协作机制)
- [五、风险预案](#五风险预案)
- [六、核心设计决策](#六核心设计决策第-1-天必须确认)
- [附录：十年工程师视角的 14 个考量维度](#附录十年工程师视角的-14-个考量维度)

---

## 一、团队分工

| 角色 | 人员 | 职责 | 技能要求 |
|------|------|------|----------|
| **Tech Lead / 架构师** | P1 | 系统设计、API 契约、代码审查、后端核心模块、技术决策 | 全栈 + 架构经验 |
| **后端工程师** | P2 | 数据层、认证授权框架、CRUD API、业务 Service 层 | FastAPI + SQLAlchemy |
| **AI/Agent 工程师** | P3 | LLM 调用层、Agent 编排、知识库检索、幻觉检测、辩论机制 | Python + LLM 集成 |
| **前端工程师 A** | P4 | UI 框架、设计系统、组件库、页面布局、路由 | React + TypeScript |
| **前端工程师 B** | P5 | 状态管理、SSE 实时通信、图表可视化、数据流 | React + Zustand/TanStack Query |
| **DevOps / 测试工程师** | P6 | CI/CD、Docker、测试体系、监控告警、部署 | Docker + GitHub Actions |

**分工原则**：每人有明确的"领地"，避免交叉冲突；通过 API 契约和代码审查保持全局一致性。

---

## 二、四周冲刺计划

### 第 1 周：地基（Day 1-5）

> **目标**：全员对齐设计，搭好骨架，能跑通"Hello World"全链路。

#### Day 1-2：设计对齐（全员参与，P1 主导）

| 时段 | 内容 | 产出 |
|------|------|------|
| 上午 | 领域建模工作坊：梳理 Learner / KnowledgeDoc / AgentTask / DebateRecord 的关系和字段 | ER 图（白板 + 数字化） |
| 下午 | API 契约设计：定义所有端点的 URL、Method、Request/Response Schema | OpenAPI spec 文件（`docs/api/openapi.yaml`） |
| 上午 | 技术选型确认：数据库（PG vs SQLite）、任务队列（Celery vs 进程内）、前端状态（Zustand vs TanStack Query） | 技术决策记录（ADR） |
| 下午 | 项目骨架搭建分工：各自认领并初始化自己的模块 | 可运行的空项目 |

**关键决策点**：
- 数据库：比赛演示用 SQLite，但 schema 设计兼容 PostgreSQL
- Agent 执行：单机用进程内线程 + SSE queue，预留 Celery 切换点
- 前端状态：TanStack Query 管服务端状态（自动处理缓存/竞态/重试），Zustand 只管全局 UI 状态

#### Day 3-5：并行开发启动

| 人员 | 任务 | 交付物 | 依赖 |
|------|------|--------|------|
| P1（架构师） | ① 数据库 schema + Alembic 迁移初始化<br>② 统一响应契约（`BaseResponse` + 错误码枚举）<br>③ 全局异常处理中间件 | `models/` 完整模型定义 + 迁移文件 + `schemas/response.py` | 无 |
| P2（后端） | ① 认证授权框架：JWT 中间件 + RBAC 装饰器 + `check_data_permission` 拦截器<br>② 用户注册/登录 API<br>③ 健康检查 + 系统信息 API | `utils/auth.py` + `domains/auth/router.py` | P1 的 schema |
| P3（AI） | ① `LLMClient` 抽象层（支持多 provider + 超时 + 重试 + 降级）<br>② `BaseAgent` 无状态化设计（状态由 Orchestrator 管理）<br>③ Prompt 模板集中管理 | `utils/llm.py` + `agents/base.py` + `prompts/` 目录 | 无 |
| P4（前端 A） | ① Vite + React + TypeScript 项目初始化<br>② 设计系统：色彩/字体/间距 token + 暗色模式<br>③ 基础组件库：Card / Badge / Button / Modal / Input<br>④ 路由结构 + 布局框架 | `src/components/` + `src/styles/` + `src/router.tsx` | OpenAPI spec |
| P5（前端 B） | ① 请求层封装（基于 fetch + AbortController + 统一错误处理）<br>② TanStack Query 配置 + 全局 query client<br>③ Zustand 全局 store（auth + theme）<br>④ OpenAPI 类型生成脚本 | `src/lib/request.ts` + `src/lib/queryClient.ts` + `src/store/` | OpenAPI spec |
| P6（DevOps） | ① GitHub Actions CI pipeline（lint + typecheck + test + build）<br>② Dockerfile 多阶段构建 + docker-compose.yml<br>③ pre-commit hooks（black + isort + eslint + tsc）<br>④ 开发环境一键启动脚本 | `.github/workflows/ci.yml` + `Dockerfile` + `docker-compose.yml` | 无 |

**第 1 周末验收清单**：
- [ ] 后端能启动，`/health` 返回 200，`/auth/login` 能签发 JWT
- [ ] 前端能启动，登录页能调通后端，Token 存入 store
- [ ] CI pipeline 能跑通（即使测试只有占位）
- [ ] Docker compose 能一键拉起前后端

---

### 第 2 周：核心功能（Day 6-10）

> **目标**：核心业务流跑通——学习者管理 + 知识库 + Agent 任务 + 基础可视化。

| 人员 | 任务 | 交付物 |
|------|------|--------|
| P1（架构师） | ① 统一 Service 层模式（Repository → Service → Router）<br>② 分页/过滤/排序公共依赖<br>③ 代码审查：确保 P2/P3 的代码符合架构规范<br>④ IDOR 防护装饰器 `@require_owner_or_admin` | `core/deps.py` + `core/decorators.py` |
| P2（后端） | ① 学习者 CRUD API（含 IDOR 校验）<br>② 知识库文档 CRUD + 分块上传 API<br>③ 答题记录 + 盲区分析 API<br>④ 配置选项 API（行业/资源类型枚举） | `domains/learner/` + `domains/knowledge/` |
| P3（AI） | ① 三个 Agent 实现：DiagnosisAgent / GenerationAgent / JudgeAgent<br>② Orchestrator 编排器：任务创建 + 状态管理 + 事件发布<br>③ 知识库检索（Chroma 向量库集成）<br>④ 幻觉检测策略（规则 + 嵌入相似度） | `agents/diagnosis.py` + `agents/generation.py` + `agents/judge.py` + `agents/orchestrator.py` |
| P4（前端 A） | ① 登录页（表单验证 + 错误提示 + Token 持久化）<br>② Dashboard 首页（统计卡片 + 快捷入口）<br>③ 学习者管理页（列表 + 详情 + CRUD 弹窗）<br>④ 知识库管理页（文档列表 + 上传 + 检索） | `src/pages/Login/` + `src/pages/Dashboard/` + `src/pages/Learners/` + `src/pages/KnowledgeBase/` |
| P5（前端 B） | ① TanStack Query hooks（learners / knowledge / config）<br>② SSE 通信封装（`useTaskSSE` hook）<br>③ 图表组件（雷达图 + 热力图 + 趋势曲线，基于 recharts）<br>④ 路由级 ErrorBoundary + 降级 UI | `src/hooks/` + `src/components/charts/` |
| P6（DevOps） | ① 后端 pytest 测试框架 + conftest fixtures<br>② 前端 vitest 测试框架 + MSW mock<br>③ 基础测试用例（认证流 + CRUD 冒烟）<br>④ Prometheus 指标采集 + Grafana dashboard | `backend/tests/` + `src/test/` + 监控配置 |

**第 2 周末验收清单**：
- [ ] 学习者 CRUD 全链路通（前端创建 → 后端存储 → 前端列表展示）
- [ ] 知识库文档上传 + 检索可用
- [ ] Agent 任务能创建并执行（即使输出是 mock）
- [ ] CI 中测试覆盖核心路径
- [ ] Grafana 能看到基础指标

---

### 第 3 周：集成与高级功能（Day 11-15）

> **目标**：Agent 全流水线跑通 + SSE 实时推送 + 报告生成 + 辩论机制。

| 人员 | 任务 | 交付物 |
|------|------|--------|
| P1（架构师） | ① 前后端联调协调（解决契约不一致）<br>② Agent 任务的事务边界设计<br>③ 性能瓶颈排查（N+1 查询、重复 COUNT）<br>④ 安全审计：认证白名单、IDOR 全量检查、密钥管理 | 审计报告 + 性能优化 |
| P2（后端） | ① Agent 任务管理 API（创建/启动/状态/日志/列表）<br>② SSE 票据机制（短期票据 + 线程安全）<br>③ 报告生成 API（学情报告 + PDF 导出）<br>④ 辅导交互历史 API | `domains/agent/` + `domains/report/` + `domains/tutoring/` |
| P3（AI） | ① 全流水线编排：诊断 → 知识检索 → 生成 → 审核 → 辩论 → 修正<br>② 辩论闭环：JudgeAgent 反馈 → GenerationAgent 修正 → 再审核<br>③ LLM 调用链路追踪（trace_id 贯穿）<br>④ Token 用量统计 + 成本控制 | 完整 Agent 流水线 |
| P4（前端 A） | ① 多智能体协同页面（核心演示页）<br>② Agent 任务面板（创建/启动/SSE 进度/日志流）<br>③ 学情报告页（雷达图 + 热力图 + 趋势曲线 + 学习路径）<br>④ 企业培训管理页 | `src/pages/MultiAgent/` + `src/pages/LearningReport/` + `src/pages/Enterprise/` |
| P5（前端 B） | ① SSE 实时事件流可视化（Agent 阶段进度条 + 辩论轮次展示）<br>② 报告数据图表集成<br>③ 自适应辅导页面<br>④ 响应式适配（768px / 1024px / 1440px） | SSE 可视化 + 图表集成 |
| P6（DevOps） | ① 安全测试套件（IDOR / 认证 / 授权 全端点覆盖）<br>② 并发测试（Agent 状态竞态、SSE 票据竞态）<br>③ E2E 测试（Playwright：登录 → 创建学习者 → 启动任务 → 查看报告）<br>④ 日志聚合（结构化 JSON 日志 + trace_id） | 测试套件 + 日志规范 |

**第 3 周末验收清单**：
- [ ] Agent 全流水线：创建任务 → 启动 → SSE 实时推送进度 → 完成 → 查看报告
- [ ] 辩论机制：至少 2 轮辩论 + 修正方案输出
- [ ] 报告页：雷达图 + 热力图 + 趋势曲线正常渲染
- [ ] 安全测试：全部端点 IDOR 测试通过
- [ ] E2E 测试：核心业务流通过

---

### 第 4 周：打磨与交付（Day 16-20）

> **目标**：生产级质量 + 演示就绪 + 文档完善。

#### Day 16-17：性能与安全加固

| 人员 | 任务 |
|------|------|
| P1 | 全局代码审查 + 技术债务清理 + 架构一致性检查 |
| P2 | 数据库索引优化 + 查询性能调优 + 异常信息脱敏 |
| P3 | LLM 调用降级策略（API 不可用时 fallback）+ 缓存命中率优化 |
| P4 | UI 打磨：加载骨架屏 + 空状态 + 错误状态 + 微交互动画 |
| P5 | 前端性能：代码分割 + 图表懒加载 + useMemo 优化 + Bundle 分析 |
| P6 | 安全扫描（Bandit + npm audit + Docker 镜像扫描）+ 性能压测 |

#### Day 18-19：文档与部署

| 人员 | 任务 |
|------|------|
| P1 | 架构文档（C4 模型）+ ADR 决策记录 |
| P2 | API 文档校验（OpenAPI spec 与实现一致）+ 数据库迁移文档 |
| P3 | Agent 系统设计文档 + Prompt 管理说明 + LLM 配置指南 |
| P4 | 前端组件文档（Storybook 或 Markdown）+ UI 设计规范 |
| P5 | 前端开发文档 + 状态管理说明 + 图表配置指南 |
| P6 | 部署文档（Docker 一键部署 + 环境变量说明）+ 运维手册 + CI/CD 文档 |

#### Day 20：演示彩排

| 时段 | 内容 |
|------|------|
| 上午 | 全链路演示彩排：登录 → 创建学习者 → 上传知识库 → 启动 Agent → SSE 实时进度 → 辩论过程 → 生成报告 → PDF 导出 |
| 下午 | 答辩准备：架构图讲解 + 技术亮点提炼 + 常见问题预案 + 录屏备份 |

**第 4 周末验收清单**：
- [ ] 全部自动化检查通过：typecheck 0 errors / lint 0 warnings / 后端测试 100%+ / 前端测试 100%+ / build 成功
- [ ] 安全扫描无 Critical/High 发现
- [ ] Docker 一键部署可用（双击脚本 → 浏览器自动打开）
- [ ] 演示全流程无报错、无白屏、无卡顿
- [ ] 文档完备：架构文档 + API 文档 + 部署文档 + 运维手册

---

## 三、关键依赖路径

```
P1: 数据库Schema ──→ P2: CRUD API ──→ P4/P5: 前端页面
         │                                    │
         └──→ P3: Agent设计 ──→ P3: 全流水线 ──→ P4: 多智能体页面
                                    │
                                    └──→ P5: SSE可视化

P6: CI/CD ──→ P6: 测试框架 ──→ P6: 安全测试 ──→ P6: 部署
```

**关键阻塞点**：
1. **Day 1-2 的 API 契约**——如果 OpenAPI spec 没定下来，前后端无法并行。必须 Day 2 结束前冻结。
2. **Week 2 的 Agent 基类**——如果 P3 的 BaseAgent 设计不稳定，Week 3 的全流水线无法启动。
3. **Week 3 的前后端联调**——这是最容易延期的环节，预留 1 天 buffer。

---

## 四、协作机制

### 4.1 每日节奏

| 时段 | 活动 | 时长 |
|------|------|------|
| 09:30 | 每日站会：昨天做了什么 / 今天做什么 / 有什么阻塞 | 15 分钟 |
| 14:00 | 下午编码（专注模式，减少会议） | — |
| 18:00 | 代码提交截止（当天代码当天 push） | — |

### 4.2 代码协作规范

| 规则 | 说明 |
|------|------|
| **分支策略** | `main`（可发布）← `develop`（集成）← `feature/xxx`（个人开发） |
| **PR 规则** | 所有代码通过 PR 合并，至少 1 人审查（P1 架构师必审核心模块） |
| **PR 模板** | 改了什么 / 为什么改 / 怎么测的 / 影响范围 |
| **契约先行** | 后端改 API 必须先改 OpenAPI spec，前端基于生成的类型开发 |
| **提交频率** | 每天至少 push 1 次，避免长期分支偏离 |

### 4.3 沟通渠道

| 渠道 | 用途 |
|------|------|
| 微信群/钉钉 | 日常即时协调 |
| GitHub PR Review | 代码审查 |
| GitHub Issues | 问题追踪（bug / feature / question 三种 label） |
| `docs/` 目录 | 文档沉淀，Markdown 格式，随代码版本管理 |

---

## 五、风险预案

| 风险 | 概率 | 影响 | 预案 |
|------|------|------|------|
| **LLM API 不可用**（比赛现场网络问题） | 高 | 核心功能不可用 | 预录视频备份 + 本地 mock LLM 响应 + 缓存历史生成结果 |
| **前后端联调延期** | 中 | 第 3 周压缩 | 第 1 周末就做一次"冒烟联调"（即使只有登录接口），提前暴露契约问题 |
| **Agent 全流水线不稳定** | 中 | 演示失败 | 拆分可演示的最小闭环：诊断 → 生成（跳过辩论），保底演示 |
| **人员请假/生病** | 低 | 进度阻塞 | 每个模块至少 2 人了解（结对编程 + 代码审查），关键知识不单点依赖 |
| **Docker 部署环境差异** | 中 | 现场无法启动 | 提前在 3 台不同机器上测试一键部署脚本 + 准备备用笔记本 |
| **数据库迁移失败** | 低 | 数据丢失 | 使用 Alembic 迁移 + 每次迁移前自动备份 + 回滚脚本 |

---

## 六、核心设计决策（第 1 天必须确认）

以下决策必须在 Day 1-2 对齐，否则后续返工成本极高：

| 决策项 | 推荐选择 | 理由 |
|--------|----------|------|
| 数据库 | SQLite（演示） / PostgreSQL（生产） | schema 兼容设计，切换只需改连接串 |
| 任务队列 | 进程内 threading + queue（演示） / Celery + Redis（生产） | 预留 `USE_CELERY` 开关 |
| 前端状态 | TanStack Query（服务端状态） + Zustand（UI 状态） | 自动处理缓存/竞态/重试，解决前端竞态类问题 |
| Agent 状态管理 | Orchestrator 集中管理（非 Agent 实例变量） | 消除单例共享状态竞态根源 |
| 认证策略 | 路由级 `dependencies=[Depends(get_current_user)]` 默认开启 | 白名单制，消除认证遗漏根源 |
| 授权策略 | Service 层装饰器 `@require_owner_or_admin` | 统一调用，消除 IDOR 手写遗漏 |
| API 契约 | OpenAPI spec 先行 → 生成前后端类型 | 消除手动类型维护不一致 |
| 错误处理 | 业务异常 + 系统异常分层，系统异常不返回 `str(e)` | 消除内部信息泄露 |

---

## 附录：十年工程师视角的 14 个考量维度

### 1. 业务理解与领域建模

- 核心业务流拆解：学习者输入 → 学情诊断 → 知识检索 → 资源生成 → 审核校验 → 输出报告
- 领域模型设计：明确聚合根、实体、值对象，消除模糊性（如 `task.learner_id` 可为 NULL 的边界）
- 业务规则显式化：辩论轮次、上传限制、缓存策略等集中为配置，不用魔法数字
- 非功能性需求量化：并发量、响应时间、数据量预期——演示与生产 SLA 不同

### 2. 架构与系统设计

- 分层架构：Router（协议转换）→ Service（业务逻辑）→ Repository（数据访问），职责清晰
- Agent 编排架构：进程内线程 vs Celery 分布式队列，取决于扩展需求
- 同步 vs 异步：不混用——全异步或全同步，避免 `asyncio.to_thread` 桥接
- 事件驱动 vs 请求响应：SSE 进程内 queue vs Redis Pub/Sub，预留切换点

### 3. 数据模型与存储设计

- 数据库选型：SQLite 演示 / PostgreSQL 生产，可切换
- Schema 设计：JSON 字段谨慎使用，大表拆分，软删除策略
- 索引策略：根据查询模式设计组合索引
- 数据一致性：多表写入的事务边界

### 4. API 设计

- RESTful 规范：资源嵌套风格统一
- 统一响应契约：HTTP status + 错误码枚举 + 业务消息
- 分页/过滤/排序标准化：公共依赖抽取
- 幂等性：`Idempotency-Key` header 防重复
- OpenAPI 契约先行：生成前后端类型

### 5. 安全设计

- 认证：路由级默认开启 JWT，白名单制
- 授权：RBAC + 数据级权限（ownership），装饰器统一调用
- 输入校验：Pydantic + 文件类型白名单 + 注入防护
- 密钥管理：环境变量 / 密钥管理服务，启动校验非默认值
- 速率限制：IP 级 + 用户级双重
- 审计日志：记录操作者、时间、变更内容

### 6. 前端架构

- 状态管理分层：全局状态（Zustand）vs 服务端状态（TanStack Query）vs 局部状态
- 请求层：TanStack Query 内置缓存/重试/竞态处理
- 路由与代码分割：路由级 + 组件级懒加载
- 组件分层：原子 → 组合 → 业务 → 页面
- 类型安全：OpenAPI 生成统一类型
- 错误边界：路由级 ErrorBoundary + 降级 UI

### 7. AI/Agent 系统设计

- Agent 抽象：无状态纯函数 or Actor 模型，状态由 Orchestrator 管理
- LLM 调用层：接口抽象，多 provider，超时/重试/降级
- Prompt 管理：集中化、版本化、可 A/B 测试
- 幻觉检测：可插拔策略，规则 → 嵌入 → LLM 自校验分级
- 辩论机制：真实闭环，JudgeAgent 反馈 → GenerationAgent 修正
- 可观测性：全链路 trace_id 贯穿

### 8. 性能与可扩展性

- 数据库查询：预加载关联，窗口函数优化 COUNT
- 缓存策略：元数据 / 业务数据 / 计算结果分层缓存
- 异步任务：大文件解析、报告生成走队列
- 前端性能：useMemo、懒加载、虚拟列表
- 水平扩展：Session/缓存/SSE 预留 Redis 切换点

### 9. 测试策略

- 测试金字塔：单测 → 集成测试 → E2E
- 安全测试：每个端点测未认证、跨用户、跨角色
- 并发测试：Agent 状态竞态、SSE 票据竞态
- 测试数据：factory pattern 统一管理
- 前端测试：渲染 + 交互 + 异常场景

### 10. DevOps 与部署

- Docker 多阶段构建：生产镜像不含 dev 依赖
- 环境管理：dev / staging / prod 分离
- CI/CD：lint + test + build + 安全扫描 + 契约校验
- 数据库迁移：Alembic 管理，支持回滚
- 零停机部署：健康检查 + 滚动更新

### 11. 可观测性

- 结构化日志：JSON 格式 + trace_id
- 指标采集：业务指标（成功率、延迟、准确率）
- 分布式追踪：OpenTelemetry 全链路
- 告警：错误率、延迟、失败率阈值
- 前端监控：Sentry 错误上报 + Core Web Vitals

### 12. 代码质量与工程规范

- 编码规范：pre-commit hooks + import 排序 + 复杂度检查
- 命名规范：统一驼峰/蛇形
- 错误处理：业务异常 vs 系统异常分层
- 依赖管理：锁文件确保可复现构建
- 代码审查：PR 模板 + CODEOWNERS

### 13. 文档

- API 文档：OpenAPI 自动生成
- 架构文档：C4 模型（Context/Container/Component/Code）
- 开发文档：环境搭建、种子数据、调试技巧
- 决策记录：ADR 记录技术决策背景/选项/理由
- 运维手册：故障排查、备份恢复、密钥轮换

### 14. 十年程序员的核心区别

1. **先想后写**——30% 时间设计，70% 时间实现
2. **防御性思维**——假设一切都会出错
3. **可维护性优先**——代码是写给人读的
4. **知道什么不该做**——不过度设计，但预留扩展点
5. **自动化一切**——格式化、测试、部署、监控

---

> 本计划为指导性文档，实际执行中应根据团队反馈和进度灵活调整。每周末验收是关键检查点，发现偏离及时纠正。
