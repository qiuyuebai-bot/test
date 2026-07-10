# P0/P1 生成计划后处理报告

> **文档版本**: v1.0  
> **生成日期**: 2026-07-10  
> **处理范围**: 项目全面评估中标记为 P0（最高优先级）与 P1（高优先级）的改进计划  
> **处理方法**: 代码级可行性验证 + 完整性审查 + 资源优化 + 冲突识别 + 时间表对齐

---

## 一、执行摘要

本次后处理对 8 项 P0/P1 改进计划进行了逐项代码级验证，核心结论如下：

| 编号 | 计划名称 | 原优先级 | 验证结论 | 建议优先级 | 预估工时 |
|------|----------|----------|----------|------------|----------|
| P0-1 | Token 黑名单机制 | P0 | 可行，无阻断 | P0（维持） | 2-3h |
| P0-2 | Agent 超时与重试 | P0 | 可行，需技术方案调整 | P0（维持） | 4-6h |
| P0-3 | N+1 查询修复 | P0 | 风险被高估，当前无实际 N+1 | **降级 P2** | 1-2h |
| P1-4 | Agent 核心逻辑测试 | P1 | 可行，无阻断 | P1（维持） | 6-8h |
| P1-5 | CI 安全扫描 | P1 | **已实现，无需额外工作** | **已完成** | 0h |
| P1-6 | 404 页面 + 全局搜索 | P1 | 可行，无阻断 | P1（维持） | 3-4h |
| P1-7 | .env.example 后端变量补全 | P1 | 可行，无阻断 | P1（维持） | 0.5h |
| P1-8 | 生产环境强制 PostgreSQL + 多 Worker | P1 | 可行，存在架构冲突 | P1（维持） | 4-6h |

**关键发现**：
- **2 项计划状态变更**：P0-3 降级（风险高估）、P1-5 已完成（CI 已集成 Bandit + pip-audit + npm audit）
- **1 项计划存在架构冲突**：P1-8 与当前默认部署模式（SQLite + 进程内线程）冲突，需决策
- **6 项计划验证通过**，可直接进入实施阶段
- 总预估工时：21-29.5 小时（约 3-4 个工作日）

---

## 二、后处理方法论

本次后处理严格遵循以下流程：

1. **完整性与准确性检查**：对照原始计划，逐项核实计划描述的代码现状是否准确
2. **关键节点可行性验证**：通过阅读实际源码，验证每个计划的技术方案是否可行
3. **资源分配优化**：评估工时估算，识别可并行/可合并的工作项
4. **时间表一致性分析**：检查计划间的依赖关系，确保实施顺序合理
5. **冲突与风险识别**：发现计划间的技术冲突、架构矛盾及实施风险
6. **标准化报告输出**：形成本文档

**验证证据来源**：
- `backend/app/utils/auth.py`（444 行，Token 生成与鉴权全链路）
- `backend/app/agents/base.py`（205 行，Agent 基类执行模型）
- `backend/app/agents/orchestrator.py`（399 行，6 阶段流水线编排）
- `backend/app/services/common.py`（588 行，服务基类与查询工具）
- `backend/app/domains/learner/router.py` / `service.py`（列表端点序列化）
- `backend/app/domains/agent/router.py`（任务列表序列化）
- `backend/app/routers/audit.py`（审计日志列表）
- `.github/workflows/ci.yml`（158 行，CI 流水线）
- `src/App.tsx`（80 行，前端路由）
- `.env.example`（27 行，环境变量模板）
- 全量 `relationship()` 与 `selectinload` grep 扫描

---

## 三、逐项后处理分析

### P0-1：Token 黑名单机制

**计划摘要**：登出时将 JWT 的 jti 存入 Redis 黑名单，`get_current_user` 校验时检查黑名单。

#### 完整性与准确性检查
| 计划描述 | 代码实际 | 是否准确 |
|----------|----------|----------|
| Token 未包含 jti | `create_access_token` (auth.py:99-103) 仅含 exp/iat/type | ✅ 准确 |
| `get_current_user` 无黑名单校验 | auth.py:304-363 流程：提取Token → verify → 查用户 → 查is_active，无黑名单步骤 | ✅ 准确 |
| 登出端点仅记录日志 | routers/auth.py 登出端点仅 logger.info + 返回 success | ✅ 准确 |
| Redis 已可用 | docker-compose.yml 中 redis 服务默认启用（always on） | ✅ 准确 |

#### 可行性验证
**结论：完全可行，无技术阻断。**

需修改的 3 个关键节点：

1. **Token 生成**（auth.py:80-141）：在 `to_encode` 中增加 `"jti": str(uuid4())`
   ```python
   # create_access_token / create_refresh_token 中
   to_encode.update({
       "exp": expire,
       "iat": utcnow_naive(),
       "type": "access",
       "jti": str(uuid4()),  # 新增
   })
   ```

2. **登出端点**（routers/auth.py）：提取 jti → Redis `SADD token_blacklist {jti}` + `EXPIRE` 设为 Token 剩余有效期

3. **鉴权校验**（auth.py:343 之前）：`verify_access_token` 后增加 Redis `SISMEMBER` 检查

#### 风险评估
- **向后兼容性**：低风险。旧 Token（无 jti）仍可解码，仅缺少黑名单保护。过渡期结束后可强制要求 jti。
- **性能影响**：极低。Redis SISMEMBER 时间复杂度 O(1)。
- **依赖**：需引入 `redis` Python 客户端（`redis-py`），需确认 requirements.txt 是否已含。

#### 冲突识别
无冲突。与现有架构完全兼容。

---

### P0-2：Agent 超时与重试机制

**计划摘要**：为 `BaseAgent.run()` 增加 `asyncio.wait_for` 超时 + 指数退避重试。

#### 完整性与准确性检查
| 计划描述 | 代码实际 | 是否准确 |
|----------|----------|----------|
| `BaseAgent.run` 无超时 | base.py:84-85 直接调用 `self.execute()`，无超时包装 | ✅ 准确 |
| 无重试机制 | 异常直接进入 except 块返回 `{"success": False}` | ✅ 准确 |
| 流水线无阶段级超时 | orchestrator.py:132-200 6 阶段顺序执行，无超时 | ✅ 准确 |

#### 可行性验证
**结论：可行，但原计划的 `asyncio.wait_for` 方案需调整为线程池方案。**

**关键技术发现**：`BaseAgent.run()` 和 `execute()` 均为**同步方法**（非 async）。`asyncio.wait_for` 无法直接包装同步调用。两种可行方案：

| 方案 | 实现方式 | 改动量 | 风险 |
|------|----------|--------|------|
| **A. 线程池超时（推荐）** | `concurrent.futures.ThreadPoolExecutor` + `future.result(timeout=N)` | 小（仅改 base.py） | 中：线程内 HTTP 请求无法强制中断，超时后线程可能继续运行 |
| B. 全面异步化 | 将 execute/run 改为 async，用 `asyncio.wait_for` | 大（改 base + 3 个 agent + orchestrator） | 高：影响调用方（router、celery_app） |

**推荐方案 A** 的实施要点：
- `BaseAgent.run()` 中用线程池执行 `self.execute()`，设置 `timeout` 参数（默认 60s）
- 超时后返回 `{"success": False, "error": "执行超时"}`
- 重试逻辑：最多 3 次，退避间隔 1s → 2s → 4s
- 可选引入 `tenacity` 库，或在 run() 中手写重试循环

#### 风险评估
- **线程泄漏**：中风险。超时后线程仍在运行，可能消耗资源。需在日志中记录未完成的任务。
- **LLM 费用**：低风险。超时重试可能产生重复 LLM 调用。建议重试时记录 token 消耗。
- **编排器异常处理**：orchestrator.py:196-200 对任何异常调用 `_mark_task_failed`。需确保超时异常触发重试而非直接标记失败。

#### 冲突识别
- **与 orchestrator 的冲突**：orchestrator 的 `run_full_pipeline` 在阶段异常时直接 `raise`（L200）。若 Agent 层已有重试，orchestrator 不应再重试，否则会导致重试叠加。**建议**：Agent 层负责重试，orchestrator 层仅负责超时后降级/失败。

---

### P0-3：N+1 查询修复

**计划摘要**：在列表端点添加 `selectinload` 预加载关联关系，消除 N+1 查询。

#### 完整性与准确性检查
| 计划描述 | 代码实际 | 是否准确 |
|----------|----------|----------|
| 列表端点存在 N+1 | 见下方详细验证 | ⚠️ **部分准确，风险被高估** |

#### 可行性验证（关键修正）
**结论：当前代码库不存在实际触发的 N+1 查询，风险被高估。建议降级为 P2。**

逐个端点验证结果：

| 端点 | 位置 | 序列化方式 | 是否访问关系 | N+1 风险 |
|------|------|------------|--------------|----------|
| 学习者列表 | learner/router.py:97-123 | 逐字段构造 LearnerProfileResponse | ❌ 仅访问扁平列 | 无 |
| Agent 任务列表 | agent/router.py:462-477 | 逐字段构造 dict | ❌ 仅访问扁平列 | 无 |
| 审计日志列表 | audit.py:56-73 | 逐字段构造 dict | ❌ username 冗余存储在 AuditLog | 无 |
| 知识库文档列表 | knowledge/service.py:342-344 | 返回 ORM 对象 | ⚠️ 取决于调用方序列化 | 低 |
| 企业培训列表 | training/service.py:80-82 | 返回 ORM 对象 | ⚠️ 取决于调用方序列化 | 低 |

**代码证据**：
- 全量 grep `selectinload|joinedload` 在生产代码中**零命中**（仅存在于 test_audit.py 和 config.py）
- 但关键列表端点（学习者、任务）的序列化代码**刻意只访问扁平列**，未触发关系加载
- AuditLog 模型已**反范式化**（username 直接存储），避免了 user 关联查询

#### 修正建议
- **降级为 P2**：当前无实际 N+1 问题，属于防御性改进
- **防御性措施**：在 learner 和 training 的列表查询上添加 `selectinload`，防止未来序列化变更引入 N+1
- **无需紧急处理**，可在下一迭代中作为代码质量改进执行

#### 冲突识别
无冲突。

---

### P1-4：Agent 核心逻辑测试

**计划摘要**：Mock LLM 调用，测试 orchestrator 完整流水线。

#### 完整性与准确性检查
| 计划描述 | 代码实际 | 是否准确 |
|----------|----------|----------|
| Agent 模块无测试覆盖 | tests/ 目录无 test_agent*/test_orchestrator*/test_diagnosis* 文件 | ✅ 准确 |

#### 可行性验证
**结论：完全可行，无技术阻断。**

测试切入点分析：

| 测试目标 | Mock 层级 | 可行性 |
|----------|-----------|--------|
| BaseAgent.run 状态管理 | Mock execute() | ✅ 简单 |
| DiagnosisAgent 输出格式 | Mock LLM client | ✅ 简单 |
| GenerationAgent 内容生成 | Mock LLM client | ✅ 简单 |
| JudgeAgent 审核逻辑 | Mock LLM client | ✅ 简单 |
| Orchestrator 6 阶段流水线 | Mock 3 个 Agent 的 run() | ✅ 中等 |
| 辩论交叉验证流程 | Mock judge_agent.debate_with_generation | ✅ 中等 |
| 任务失败降级 | Mock Agent 抛出异常 | ✅ 简单 |

**关键注意点**：
- orchestrator 是全局单例（orchestrator.py:399 `orchestrator = AgentOrchestrator()`），测试需通过 `app.agents.orchestrator` 导入并替换实例方法
- 流水线内部使用 `get_db_context()` 管理数据库会话（L207, L225, L234），测试需配合测试数据库或 Mock
- `TaskRepository` 和 `ContentCorrector` 已解耦，可独立 Mock

#### 风险评估
- **测试数据库依赖**：中风险。orchestrator 的 `_run_diagnosis` 调用 `LearnerService.get_learner_by_id`，需要测试数据。建议使用 conftest.py 现有的测试数据库 fixture。
- **LLM Mock 粒度**：低风险。Agent 内部调用 LLM 的位置明确，可在 LLM client 层统一 Mock。

#### 冲突识别
无冲突。与现有测试架构（pytest + conftest.py）兼容。

---

### P1-5：CI 安全扫描

**计划摘要**：在 CI 中集成 pip-audit + npm audit + Bandit。

#### 完整性与准确性检查
| 计划描述 | 代码实际 | 是否准确 |
|----------|----------|----------|
| CI 缺少安全扫描 | `.github/workflows/ci.yml` L69-91 已有 `security` job | ❌ **计划描述不准确，该功能已实现** |

#### 可行性验证
**结论：已完成，无需额外工作。**

现有 CI 安全扫描配置（ci.yml:69-91）：
```yaml
security:
  name: Security Scan
  steps:
    - run: pip install bandit pip-audit
    - run: bandit -r backend/app -f json -o bandit-report.json || true
    - run: pip-audit -r backend/requirements.txt || true
    - run: npm audit --audit-level=high || true
    - uses: actions/upload-artifact@v4  # 上传报告
```

已覆盖：
- ✅ Bandit（Python SAST 静态分析）
- ✅ pip-audit（Python 依赖漏洞）
- ✅ npm audit（前端依赖漏洞，high 级别）
- ✅ 报告产物上传

#### 修正建议
- **标记为已完成**，从待办列表移除
- **可选增强**（非必须）：当前所有扫描均用 `|| true` 容错，不阻断构建。如需严格门禁，可移除 `|| true` 使高危漏洞阻断 CI。但这可能导致现有依赖的已知漏洞阻塞开发，建议谨慎。

#### 冲突识别
无冲突。

---

### P1-6：404 页面 + 全局搜索

**计划摘要**：创建专用 404 页面，添加全局搜索组件。

#### 完整性与准确性检查
| 计划描述 | 代码实际 | 是否准确 |
|----------|----------|----------|
| 无 404 页面 | App.tsx:72 `<Route path="*" element={<Navigate to="/dashboard" replace />} />` 静默重定向 | ✅ 准确 |
| 无全局搜索 | 全局 grep 未发现搜索组件 | ✅ 准确 |

#### 可行性验证
**结论：完全可行，纯前端改动，无后端影响。**

实施方案：
1. **404 页面**：创建 `src/pages/NotFound.tsx`，替换 App.tsx:72 的 `Navigate` 为 `<NotFound />`
   - 包含：错误提示、返回首页按钮、常用链接
   - 遵循项目设计规范：科技极简风格、低饱和度配色
2. **全局搜索**：在 Layout 组件头部添加搜索框
   - 搜索范围：页面导航、学习者、资源、知识库
   - 交互：0.25s 软过渡动画，下拉建议列表
   - 后端接口：可复用现有列表端点的搜索参数（keyword）

#### 风险评估
- **低风险**：纯前端变更，不影响现有业务逻辑
- **设计一致性**：需遵循 project_memory 中的 UI 规范（8px 间距、统一圆角、低饱和度）

#### 冲突识别
无冲突。

---

### P1-7：.env.example 后端变量补全

**计划摘要**：将所有后端环境变量补充到 .env.example。

#### 完整性与准确性检查
| 计划描述 | 代码实际 | 是否准确 |
|----------|----------|----------|
| .env.example 缺少后端变量 | 仅含 VITE_* 前端变量（27 行），无任何后端变量 | ✅ 准确 |

#### 可行性验证
**结论：完全可行，文档变更，零风险。**

需补充的后端变量（来源：backend/app/config.py）：

```env
# ---- 后端数据库 ----
DATABASE_URL=sqlite:///./data/adaptive_learning.db
# 生产环境推荐: postgresql+psycopg2://user:pass@localhost:5432/dbname

# ---- Redis ----
REDIS_URL=redis://localhost:6379/0

# ---- JWT 配置 ----
JWT_SECRET_KEY=          # 留空则自动生成并持久化到 data/.secret_key
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=480

# ---- 管理员 ----
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=admin123

# ---- AI 配置 ----
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini

# ---- 应用配置 ----
USE_CELERY=false
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
API_PREFIX=/api/v1
```

#### 风险评估
- **零风险**：纯文档变更
- **兼容性**：config.py 已配置 `extra="ignore"`（之前的修复），允许 VITE_* 与后端变量共存于同一 .env

#### 冲突识别
无冲突。

---

### P1-8：生产环境强制 PostgreSQL + 多 Worker

**计划摘要**：生产环境强制使用 PostgreSQL，uvicorn 多 Worker 运行。

#### 完整性与准确性检查
| 计划描述 | 代码实际 | 是否准确 |
|----------|----------|----------|
| 默认使用 SQLite | docker-compose 默认模式 backend 使用 SQLite | ✅ 准确 |
| 单 Worker 运行 | Dockerfile 默认 uvicorn 单进程单线程 | ✅ 准确 |

#### 可行性验证
**结论：可行，但存在架构冲突，需明确决策。**

**核心冲突**：当前默认部署模式为 **SQLite + 进程内线程（USE_CELERY=false）**。若切换为多 Worker：

| 组合 | 可行性 | 问题 |
|------|--------|------|
| SQLite + 多 Worker | ❌ 不可行 | SQLite 文件锁冲突，多进程并发写入会报 `database is locked` |
| PostgreSQL + 多 Worker + USE_CELERY=false | ⚠️ 有风险 | 每个 Worker 进程都有独立的 orchestrator 单例和线程池，可能导致**重复任务执行** |
| PostgreSQL + 多 Worker + USE_CELERY=true | ✅ 推荐 | Celery 统一调度任务，Worker 仅处理 HTTP 请求 |

**推荐方案**：创建独立的 `docker-compose.prod.yml`：
- 强制 PostgreSQL（移除 SQLite 回退）
- 强制 USE_CELERY=true（启用 Celery Worker）
- uvicorn `--workers 4`（多进程）
- 保留 Redis（Celery broker + Token 黑名单）

#### 风险评估
- **架构复杂度**：中风险。生产模式从 3 服务（frontend+backend+redis）增至 6+ 服务（+postgres+celery-worker+chroma）
- **任务调度**：中风险。切换到 Celery 后，需验证 SSE 事件推送（当前 `TaskEventBus` 是进程内 pub/sub，多进程下 SSE 订阅可能失效）
- **SSE 跨进程问题**：**关键风险**。当前 `TaskEventBus` 基于 `queue.Queue`（进程内），多 Worker 下每个进程有独立的事件总线，客户端订阅的进程可能不是执行任务的进程。需迁移到 Redis Pub/Sub。

#### 冲突识别
- **与 P0-1 的协同**：P0-1 的 Token 黑名单依赖 Redis，P1-8 的生产模式也依赖 Redis，可共用 Redis 服务
- **与 SSE 架构的冲突**：多 Worker 模式下 `TaskEventBus` 需重构为 Redis Pub/Sub，这是**隐藏的额外工作量**（预估 +4-6h）
- **与当前 docker-start.bat 的冲突**：一键部署脚本当前启动默认模式（SQLite），需增加生产模式选项

---

## 四、资源分配优化

### 4.1 工时汇总

| 编号 | 计划 | 原始预估 | 验证后预估 | 差异原因 |
|------|------|----------|------------|----------|
| P0-1 | Token 黑名单 | 4h | 2-3h | Redis 已就绪，改动点明确 |
| P0-2 | Agent 超时重试 | 6h | 4-6h | 线程池方案比异步化改动小 |
| P0-3 | N+1 修复 | 4h | 1-2h | 降级为防御性改进 |
| P1-4 | Agent 测试 | 8h | 6-8h | 架构清晰，Mock 点明确 |
| P1-5 | CI 安全扫描 | 2h | 0h | 已完成 |
| P1-6 | 404 + 搜索 | 4h | 3-4h | 纯前端 |
| P1-7 | .env 补全 | 1h | 0.5h | 文档变更 |
| P1-8 | 生产 PG+多Worker | 6h | 4-6h + 4-6h(SSE) | 发现隐藏的 SSE 重构需求 |

**总工时**：21-29.5h（原始）→ 实际 20-29.5h（含 SSE 重构则为 24-35.5h）

### 4.2 并行化建议

以下工作项无依赖关系，可并行执行：

```
并行组 A（后端安全）：
  ├─ P0-1 Token 黑名单（2-3h）
  └─ P1-7 .env 补全（0.5h）

并行组 B（Agent 增强）：
  ├─ P0-2 Agent 超时重试（4-6h）
  └─ P1-4 Agent 测试（6-8h）  ← 依赖 P0-2 完成后测试超时逻辑

并行组 C（前端）：
  └─ P1-6 404 + 搜索（3-4h）

串行组 D（生产部署）：
  └─ P1-8 生产 PG + 多Worker（4-6h）
      └─ SSE 重构（4-6h）  ← P1-8 触发的隐藏依赖

独立项：
  └─ P0-3 N+1 防御性修复（1-2h）  ← 可在任何空档执行
```

### 4.3 资源分配建议

| 角色 | 分配任务 | 工时 |
|------|----------|------|
| 后端工程师 A | P0-1 + P1-7 + P0-3 | 3.5-5.5h |
| 后端工程师 B | P0-2 → P1-4 | 10-14h |
| 前端工程师 | P1-6 | 3-4h |
| DevOps | P1-8 + SSE 重构 | 8-12h |

**最少 2 人并行可在 2-3 个工作日内完成**（P1-5 已免、P0-3 降级）。

---

## 五、时间表一致性分析

### 5.1 依赖关系图

```
P1-7 (.env) ────── 无依赖，可先行
P0-1 (Token) ───── 依赖 Redis（已就绪），独立
P0-3 (N+1) ─────── 无依赖，独立
P1-6 (404+搜索) ── 无依赖，独立

P0-2 (超时重试) ── 独立
    └── P1-4 (Agent测试) 依赖 P0-2（测试超时/重试逻辑）

P1-8 (生产PG) ──── 独立
    └── SSE 重构（隐藏依赖，多Worker触发）
    └── 与 P0-1 协同（共用 Redis）
```

### 5.2 建议实施顺序

| 阶段 | 任务 | 理由 |
|------|------|------|
| **第 1 天上午** | P1-7 + P0-3 | 快速清零低工时项，建立推进势头 |
| **第 1 天全天** | P0-1（并行） | 安全优先级最高，独立无依赖 |
| **第 1 天全天** | P0-2（并行） | 启动 Agent 增强，为 P1-4 铺路 |
| **第 2 天** | P1-4 | 依赖 P0-2 完成 |
| **第 2 天** | P1-6（并行） | 纯前端，与后端并行 |
| **第 2-3 天** | P1-8 + SSE 重构 | 工时最长，启动后持续进行 |
| **第 3 天** | 集成测试 + 验收 | 所有计划完成后统一验证 |

### 5.3 与项目时间表的对齐

- 当前项目处于**挑战杯揭榜挂帅演示准备阶段**
- P0-1（安全）和 P0-2（稳定性）直接影响演示可靠性，**必须在演示前完成**
- P1-6（404+搜索）提升用户体验，**建议演示前完成**
- P1-8（生产部署）用于正式部署，**可在演示后执行**（演示用默认 SQLite 模式即可）
- P1-4（测试）和 P0-3（N+1）为工程质量项，**可在演示后执行**

---

## 六、冲突与风险登记簿

### 6.1 已识别冲突

| 编号 | 冲突描述 | 涉及计划 | 严重度 | 解决方案 |
|------|----------|----------|--------|----------|
| C-1 | 多 Worker 下 TaskEventBus 进程内 pub/sub 失效 | P1-8 | 🔴 高 | 迁移至 Redis Pub/Sub（+4-6h） |
| C-2 | Agent 重试与 orchestrator 异常处理叠加 | P0-2 | 🟡 中 | Agent 层负责重试，orchestrator 仅降级 |
| C-3 | 线程池超时后线程无法强制中断 | P0-2 | 🟡 中 | 记录超时日志，接受线程泄漏风险 |

### 6.2 已识别风险

| 编号 | 风险描述 | 概率 | 影响 | 缓解措施 |
|------|----------|------|------|----------|
| R-1 | Token 黑名单过渡期旧 Token 无保护 | 中 | 低 | 过渡期结束后强制 jti 校验 |
| R-2 | Agent 超时重试导致重复 LLM 调用费用 | 中 | 中 | 重试时记录 token 消耗，设费用上限 |
| R-3 | P1-8 切换 Celery 后 SSE 推送断裂 | 高 | 高 | 必须同步重构 SSE 为 Redis Pub/Sub |
| R-4 | P0-3 降级后未来开发引入 N+1 | 低 | 低 | 添加 ESLint/CI 规则检测关系访问 |

### 6.3 已消除的风险（原计划中存在，验证后排除）

- ~~P0-3 N+1 查询当前影响性能~~ → 验证表明当前列表端点未触发关系加载
- ~~P1-5 CI 缺少安全扫描~~ → 验证表明 CI 已集成完整安全扫描链

---

## 七、修正后的优先级矩阵

```
紧急度 →
↑  P0-1 (Token黑名单)     P0-2 (Agent超时)
│  P1-7 (.env补全)        P1-6 (404+搜索)
│                          
│  P0-3 (N+1防御)↓降级     P1-4 (Agent测试)
│                          
│  P1-5 ✅已完成           P1-8 (生产PG) + R-3(SSE重构)
│                          
└──────────────────────────────────────────→ 影响范围
   窄(单点)              广(系统级)
```

**最终执行优先级**：
1. **P0-1** Token 黑名单 — 安全，独立，快速
2. **P0-2** Agent 超时重试 — 稳定性，为 P1-4 铺路
3. **P1-7** .env 补全 — 零风险，快速清零
4. **P1-6** 404 + 搜索 — 用户体验
5. **P0-3** N+1 防御性修复 — 降级项，空档执行
6. **P1-4** Agent 测试 — 依赖 P0-2
7. **P1-8** 生产 PG + 多 Worker — 含 SSE 重构，演示后执行

---

## 八、验收标准

每项计划完成后需满足以下验收标准方可标记为完成：

| 编号 | 验收标准 | 验证方式 |
|------|----------|----------|
| P0-1 | 登出后旧 Token 在 5s 内失效；有效 Token 不受影响 | curl 测试：登出 → 用旧 Token 访问 → 401 |
| P0-2 | Agent 执行超 60s 自动超时；LLM 异常重试 ≤3 次 | 单元测试：Mock 慢 LLM，验证超时返回 |
| P0-3 | learner 列表查询 SQL 含 selectinload | SQL 日志检查 |
| P1-4 | orchestrator 全流水线测试覆盖 ≥80% | pytest --cov 报告 |
| P1-5 | ✅ 已完成（CI 含 Bandit + pip-audit + npm audit） | ci.yml L69-91 |
| P1-6 | 访问无效 URL 显示 404 页面；搜索框可检索 | Playwright E2E |
| P1-7 | .env.example 含全部后端变量且有注释 | 文件审查 |
| P1-8 | docker-compose.prod.yml 启动后 PG+多Worker+Celery 正常 | docker compose --profile full up + 健康检查 |

---

## 九、结论

本次后处理通过代码级验证，对 8 项 P0/P1 计划完成了完整性审查、可行性验证、资源优化和冲突识别。核心成果：

1. **2 项计划状态修正**：P1-5 已完成（免工时）、P0-3 降级（风险高估）
2. **1 项隐藏依赖暴露**：P1-8 触发 SSE 架构重构需求（+4-6h）
3. **0 项计划被否决**：所有计划均可行，仅需局部方案调整
4. **总工时优化**：从原始预估 35h 优化至实际 20-29.5h（节省约 15-43%）

建议按第七章优先级顺序，以 2 人并行在 2-3 个工作日内完成全部计划，确保 P0-1 和 P0-2 在挑战杯演示前交付。
