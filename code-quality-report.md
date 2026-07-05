# 代码质量检查报告

> 生成时间：2026-07-01
> 检查范围：前端 `src/`（React 18 + TypeScript + Vite）+ 后端 `backend/app/`（FastAPI + SQLAlchemy）
> 检查方法：tsc / eslint / pyflakes 自动化扫描 + 3 个专项 agent 深度人工审查（安全/逻辑/性能/资源管理/规范）+ 关键发现交叉验证

---

## 一、概述

### 自动化检查结果

| 工具 | 范围 | 结果 |
|------|------|------|
| `tsc --noEmit` | 前端全部 TS/TSX | 0 错误 |
| `eslint` | 前端 `src/` | 0 错误 |
| `pyflakes` | 后端 `app/` | 0 错误 |
| `bandit` | 后端 | 未安装，由人工审查覆盖 |

自动化工具未发现语法/类型/导入错误，所有问题均来自深度人工审查。

### 问题统计（去重后）

| 级别 | 数量 | 说明 |
|------|------|------|
| P0 严重 | 6 | 安全漏洞/数据泄露/脱敏失效 |
| P1 功能性 Bug | 15 | 逻辑错误导致功能异常或数据错误 |
| P2 性能/健壮性 | 30 | 性能瓶颈/资源泄漏/竞态/异常处理 |
| P3 代码规范 | 30 | 弃用 API/死代码/类型断言/风格不统一 |
| **合计** | **81** | |

---

## 二、P0 严重问题（建议立即修复）

### P0-1. SSE/Token 通过 URL Query 参数传递（全栈）

| 项 | 内容 |
|----|------|
| 类别 | 安全 |
| 文件 | `backend/app/routers/agent.py` L188-225；`backend/app/utils/auth.py` L296-298；`src/lib/request.ts` L365-382 |
| 描述 | EventSource 不支持自定义 Header，当前将 JWT access token 拼接到 URL `?token=` 中。该 token 会出现在浏览器历史、服务器 access log、CDN/代理日志、Referer 头中，导致会话凭据大面积泄露。后端 `get_token_from_request` 也开放了 query 参数提取通道。 |
| 修复建议 | 方案一（推荐）：后端签发短期一次性 SSE ticket（30s 有效，仅可用于 SSE），前端先 `POST /agent/tasks/{id}/stream-ticket` 换取 ticket 再连接；方案二：改用 `fetch` + `ReadableStream` 替代 EventSource，可在 Header 中携带 token；方案三：改用 Cookie 鉴权，浏览器自动携带。 |

### P0-2. 限流可被 X-Forwarded-For 头轻易绕过

| 项 | 内容 |
|----|------|
| 类别 | 安全 |
| 文件 | `backend/app/utils/rate_limiter.py` L122-132 |
| 描述 | `_get_client_ip` 无条件信任 `X-Forwarded-For` 和 `X-Real-IP` 头并取第一个值。攻击者每请求设置不同 `X-Forwarded-For` 即可绕过所有登录爆破限流和 API 限流。 |
| 修复建议 | 配置可信代理列表，仅从可信代理转发中读取该头；或取 `X-Forwarded-For` 最后一个非可信 IP；推荐 `uvicorn --proxy-headers --forwarded-allow-ips`。 |

### P0-3. 脱敏工具泄露敏感数据并返回原始未脱敏数据

| 项 | 内容 |
|----|------|
| 类别 | 安全 |
| 文件 | `backend/app/utils/anonymize.py` L59-60, L88-89 |
| 描述 | `anonymize_phone` 和 `anonymize_id_card` 在格式异常时：① `logger.warning(f"...异常: {phone}")` 将原始手机号/身份证号明文写入日志；② 直接 `return phone` / `return id_card` 返回原始未脱敏值。脱敏工具本身泄露并放行敏感数据，完全违背脱敏目的。 |
| 修复建议 | 日志仅记录长度或脱敏后值；格式异常时执行兜底全掩码（如 `****`）而非返回原值。 |

### P0-4. JWT Secret Key 文件权限未设置

| 项 | 内容 |
|----|------|
| 类别 | 安全 |
| 文件 | `backend/app/config.py` L42-43 |
| 描述 | `_SECRET_FILE.write_text(generated)` 创建密钥文件后未设置权限。Linux/MacOS 默认 644，其他用户可读取 JWT 密钥，可伪造任意用户 token。 |
| 修复建议 | 写入后 `os.chmod(_SECRET_FILE, 0o600)`。 |

### P0-5. Token 存储在 localStorage，存在 XSS 窃取风险

| 项 | 内容 |
|----|------|
| 类别 | 安全 |
| 文件 | `src/lib/request.ts` L6-8, L66-77, L93-97 |
| 描述 | accessToken / refreshToken / user_info 全部存 localStorage，任何 XSS 即可窃取。 |
| 修复建议 | 后端将 token 设为 `httpOnly + Secure + SameSite` Cookie；若必须用 localStorage，需缩短 token 有效期并部署严格 CSP。 |

### P0-6. 匿名化数据表存储加密后的原始数据（脱敏可逆）

| 项 | 内容 |
|----|------|
| 类别 | 安全/合规 |
| 文件 | `backend/app/models/anonymized_data.py` L48 |
| 描述 | `original_data_encrypted` 字段存储加密后的原始敏感数据。密钥泄露后所有"已脱敏"数据可被还原，不符合不可逆匿名化合规要求。 |
| 修复建议 | 若为不可逆脱敏，删除该字段仅保留 `original_data_hash`；若为可还原假名化，需标注并使用 HSM/KMS 管理密钥。 |

---

## 三、P1 功能性 Bug（建议尽快修复）

### P1-1. Chroma 向量索引字段名不一致导致 KeyError

| 项 | 内容 |
|----|------|
| 类别 | 逻辑 |
| 文件 | `backend/app/services/knowledge_service.py` L259, L264 |
| 描述 | `_index_slices_to_chroma` 使用 `slice_data['slice_index']`，但 `TextSliceUtil.slice_by_paragraph` 返回的切片字典字段名为 `'index'`（见 `text_slice.py` L62/75/87）。数据库存储处 L181 正确用 `slice_data.get("index", i)`，但 Chroma 索引处 L259 用 `slice_data['slice_index']` 会抛 KeyError，使文档向量索引失败、知识库检索降级。 |
| 修复建议 | 将 L259/L264 的 `slice_data['slice_index']` 改为 `slice_data.get('slice_index', slice_data.get('index', 0))`。 |

### P1-2. 资源保存 knowledge_topic 字段错误赋值

| 项 | 内容 |
|----|------|
| 类别 | 逻辑 |
| 文件 | `backend/app/services/resource_service.py` L226 |
| 描述 | `knowledge_topic=diagnosis_result.get("overall_level", "")` 将能力等级（如"精通"）赋给知识点主题字段。`overall_level` 是能力等级，不是知识点主题，导致知识溯源和检索失效。 |
| 修复建议 | 将 `target_topic` 传入 `_save_resource` 并使用 `knowledge_topic=target_topic`。 |

### P1-3. 自适应导学更新学习者画像不生效（跨 Session）

| 项 | 内容 |
|----|------|
| 类别 | 逻辑 |
| 文件 | `backend/app/services/tutoring_service.py` L357-383 |
| 描述 | `learner` 由 `get_learner` 在独立 session 中获取，session 关闭后对象脱离。新 `with get_db_context() as db:` 块中 `setattr(learner, ...)` + `db.commit()` 因 learner 不属于当前 session，修改不会持久化。学习者能力分数永远不会因答题更新。 |
| 修复建议 | 新 session 中重新查询：`learner = db.query(LearnerProfile).filter(LearnerProfile.id == learner.id).first()` 后再修改。 |

### P1-4. 批量导入异常后未 Rollback（学习者/培训任务）

| 项 | 内容 |
|----|------|
| 类别 | 逻辑/异常处理 |
| 文件 | `backend/app/services/learner_service.py` L272-304；`backend/app/services/training_service.py` L273-294 |
| 描述 | 循环中 `db.flush()` 失败后捕获异常继续，但未 `db.rollback()`。失败记录污染 session，后续 `db.add()` 持续失败，最终 `db.commit()` 失败导致整批数据丢失。 |
| 修复建议 | except 块中添加 `db.rollback()` 后继续下一条。 |

### P1-5. 种子数据初始化日志泄露默认密码

| 项 | 内容 |
|----|------|
| 类别 | 安全 |
| 文件 | `backend/app/main.py` L610 |
| 描述 | `logger.info(f"... (默认密码 {default_password})")` 将学习者默认密码明文写入日志。 |
| 修复建议 | 移除密码，仅记录"默认密码已配置"。 |

### P1-6. 文本切片段落重复（缺 continue）

| 项 | 内容 |
|----|------|
| 类别 | 逻辑 |
| 文件 | `backend/app/utils/text_slice.py` L56-97（`slice_by_paragraph`），L145-184（`slice_by_semantic`） |
| 描述 | 超长段落既被分割为子切片加入结果，又因缺 `continue` 继续执行 `current_slice.append(para)`，导致内容重复。`slice_by_semantic` 同样缺陷。 |
| 修复建议 | 在 `if para_length > max_length:` 块末尾添加 `continue`。 |

### P1-7. 请求追踪中间件信任客户端 X-Request-ID（日志注入）

| 项 | 内容 |
|----|------|
| 类别 | 安全 |
| 文件 | `backend/app/middleware/tracing.py` L33 |
| 描述 | 直接采用客户端传入 `X-Request-ID`，未清洗。攻击者可注入含换行符的值伪造日志行，干扰日志分析和告警。 |
| 修复建议 | 清洗为 `re.sub(r'[^a-zA-Z0-9\-]', '', request_id)`，或忽略客户端头始终服务端生成。 |

### P1-8. ProtectedRoute 初始化期间重定向导致登录页闪烁

| 项 | 内容 |
|----|------|
| 类别 | 逻辑 |
| 文件 | `src/components/ProtectedRoute.tsx` L10-16；`src/store/index.ts` L114-115, L169-180 |
| 描述 | store 初始 `isLoggedIn: false`，`onRehydrateStorage` 异步 `setTimeout(initializeAuth)`。React 首次渲染同步，`ProtectedRoute` 立即跳转 `/login`，刷新任意已登录页面都会闪登录页。 |
| 修复建议 | store 初始状态同步读 localStorage；或 ProtectedRoute 检测 `isAuthenticated()` 为 true 但 `isLoggedIn` 未就绪时返回 LoadingState。 |

### P1-9. LearnerProfile formatDate 时区错误

| 项 | 内容 |
|----|------|
| 类别 | 逻辑 |
| 文件 | `src/pages/LearnerProfile.tsx` L74-81 |
| 描述 | `new Date(dateStr).toISOString().split('T')[0]` 转 UTC 取日期，UTC+8 凌晨 0-8 点创建的记录日期会少一天。 |
| 修复建议 | 改用本地日期格式化 `toLocaleDateString('zh-CA')` 或手动拼年月日。 |

### P1-10. MultiAgentVisualization 日志去重逻辑失效

| 项 | 内容 |
|----|------|
| 类别 | 逻辑 |
| 文件 | `src/pages/MultiAgentVisualization.tsx` L205-218 |
| 描述 | 日志 `id = Date.now() + Math.random()`，去重判断 `Date.now() - l.id < 6000` 因 Math.random() 使差值恒近 0 或负数，`< 6000` 永远为 true，6 秒时间窗口失效。 |
| 修复建议 | 用独立 `timestamp` 字段，去重判断基于 `Date.now() - l.timestamp < 6000`。 |

### P1-11. KnowledgeBase handlePreview 竞态条件

| 项 | 内容 |
|----|------|
| 类别 | 逻辑 |
| 文件 | `src/pages/KnowledgeBase.tsx` L228-234 |
| 描述 | 快速点击文档 A、B 时，A 后完成会把 A 切片设给显示 B 的 modal，造成文档与切片错位。 |
| 修复建议 | 用 ref 记录当前请求 id，回调中校验是否仍为最新请求。 |

### P1-12. AdaptiveGuidance setInterval 未在 unmount 清理

| 项 | 内容 |
|----|------|
| 类别 | 资源管理 |
| 文件 | `src/pages/AdaptiveGuidance.tsx` L235-246, L292-293 |
| 描述 | 动画 interval 仅在 finally 清理，组件 unmount 后仍触发 setState，导致泄漏和警告。 |
| 修复建议 | interval id 存 ref，unmount 时清理。 |

### P1-13. ResourceGeneration handleGenerate 与 handleCancel 状态竞争

| 项 | 内容 |
|----|------|
| 类别 | 逻辑 |
| 文件 | `src/pages/ResourceGeneration.tsx` L208-243 |
| 描述 | 取消后 runFullPipeline 返回仍执行 setSseTaskId 重连 SSE，请求未用 AbortController 取消，UI 进入混乱状态。 |
| 修复建议 | 用 cancelledRef 或 AbortController 终止请求并在返回后检查标志。 |

### P1-14. 文档处理异常时未 Rollback 导致 Session 损坏

| 项 | 内容 |
|----|------|
| 类别 | 异常处理 |
| 文件 | `backend/app/services/knowledge_service.py` L223-233 |
| 描述 | `process_doc` except 块重新查询并修改 doc 状态后 commit，但若异常为 SQLAlchemy 异常（IntegrityError），session 已损坏，重新查询和 commit 都会失败。 |
| 修复建议 | except 中先 `db.rollback()` 再查询更新状态。 |

### P1-15. 学情诊断任务失败时状态永久停留 "running"

| 项 | 内容 |
|----|------|
| 类别 | 逻辑 |
| 文件 | `backend/app/routers/agent.py` L471-491 |
| 描述 | `run_diagnosis` 先 commit task 为 "running"，`agent.run()` 抛异常时外层 except 仅记日志，task 状态永不更新，前端误以为任务仍在执行。 |
| 修复建议 | except 中更新 task.status="failed" 并 commit。 |

---

## 四、P2 性能/健壮性问题

### 安全/异常处理类

| 编号 | 文件 | 行号 | 描述 | 修复建议 |
|------|------|------|------|----------|
| P2-1 | `backend/app/main.py` | 276-280 | DEBUG_MODE 下全局异常返回完整 traceback，生产误开会泄露代码结构 | 确保 DEBUG_MODE 生产强制 False |
| P2-2 | `backend/app/main.py` | 87-88 | CORS `allow_methods=["*"]`、`allow_headers=["*"]` 过宽 | 显式列出允许方法和头 |
| P2-3 | `backend/app/routers/agent.py` | 533-537 | `get_debate_records` 用 `except Exception` 吞掉所有异常，掩盖真实错误 | 只捕获 `json.JSONDecodeError`/`TypeError` |
| P2-4 | `backend/app/routers/knowledge.py` | 72 | UTF-8 解码 `errors="ignore"` 静默丢弃字节，知识库内容损坏无感知 | 用 `errors="replace"` 或检测编码 |
| P2-5 | `backend/app/utils/llm.py` | 223-397 | 多处 `except Exception` 返回 mock 数据，吞掉编程错误 | 分别捕获具体异常，未知异常 raise |
| P2-6 | `backend/app/services/learner_service.py` | 129-133 等 | LIKE 查询未转义 `%`/`_`，输入 `%` 匹配所有记录 | 转义通配符并指定 escape |
| P2-7 | `backend/app/utils/auth.py` | 35 | bcrypt 截断 >72 字节密码静默无提示 | schema 校验或改用 argon2 |

### 性能类

| 编号 | 文件 | 行号 | 描述 | 修复建议 |
|------|------|------|------|----------|
| P2-8 | `backend/app/services/report_service.py` | 730-778 | `update_metrics_periodically` N+1 查询 + 嵌套循环字符串匹配 | 单条 SQL 聚合 |
| P2-9 | `backend/app/services/report_service.py` | 291-328 | `_calculate_core_metrics` 全表加载资源/答题记录到内存算平均 | 用 SQL `func.avg`/`func.sum` 聚合 |
| P2-10 | `backend/app/services/report_service.py` | 182-188 | `_generate_path_topology` 全表加载资源 | SQL GROUP BY 聚合或加 limit |
| P2-11 | `backend/app/routers/agent.py` | 275 | `q.get(timeout=1.0)` 同步阻塞在 async 协程中，阻塞事件循环 1 秒 | `await asyncio.to_thread(q.get, ...)` |
| P2-12 | `backend/app/utils/metrics.py` | 120-123 | `calculate_knowledge_coverage_rate` 加载全部文档到内存求和 | SQL `func.sum` 聚合 |
| P2-13 | `backend/app/middleware/prometheus.py` | 367-385 | 每次抓取执行 COUNT 查询 | 加 TTL 缓存或用近似值 |
| P2-14 | `backend/app/utils/logger.py` | 131-139 | 文件日志固定 DEBUG 级别，生产日志爆炸 | 按 DEBUG_MODE 动态调整 |
| P2-15 | `src/pages/Dashboard.tsx` | 17-28 | `useStore()` 无 selector 订阅整个 store，过度渲染 | 用 selector + shallow |
| P2-16 | `src/pages/ResourceGeneration.tsx` | 177-194 | 三个 useEffect 派生状态链导致额外渲染 | 渲染时直接计算派生值 |
| P2-17 | `src/pages/LearnerProfile.tsx` | 608-616 | 搜索框无防抖，每次输入触发后端请求 | 加 300-500ms 防抖 |
| P2-18 | `src/pages/Deployment.tsx` | 88-96 | `sampleLearners` IIFE 每次渲染重算 | 用 useMemo |

### 资源管理/竞态类

| 编号 | 文件 | 行号 | 描述 | 修复建议 |
|------|------|------|------|----------|
| P2-19 | `backend/app/main.py` | 350-361 | `health_readiness` DB Session 异常时未 close，连接泄漏 | try/finally 确保 close |
| P2-20 | `backend/app/utils/llm.py` | 95-97 | 异步 httpx 客户端未调用 `aclose()`，连接池泄漏 | shutdown 事件中 await aclose |
| P2-21 | `backend/app/celery_app.py` | 18-29 | 缺 `task_acks_late`/`result_expires`，worker 崩溃丢任务、结果无限堆积 | 添加 acks_late=True 等 |
| P2-22 | `backend/app/services/knowledge_service.py` | 404-414 | 删文档时 DB 与 Chroma 向量可能不一致 | 先删向量或加补偿对账 |
| P2-23 | `backend/app/agents/orchestrator.py` | 183-249 | `_running_tasks` 字典多步读写未全程加锁，get_task_status 锁外读 | 所有读写在锁内 |
| P2-24 | `backend/app/utils/rate_limiter.py` | 24-39 | 清理用调用方 window_seconds，会误清其他窗口有效记录 | 按各自窗口或固定保守 cutoff |
| P2-25 | `backend/app/utils/rate_limiter.py` | 26-28 | 清理检查与更新未全程在锁内，并发重复清理 | 检查+更新移入锁内 |
| P2-26 | `backend/app/utils/hallucination.py` | 31, 153-222 | `_deep_check_cache` 非线程安全，并发读写可能 RuntimeError | 加 Lock 或用 cachetools.TTLCache |
| P2-27 | `backend/app/services/learner_service.py` | 589 | 脱敏响应 `record_id=1` 硬编码，审计追踪失效 | flush 后取 record.id |
| P2-28 | `src/components/ErrorBoundary.tsx` | 58-72 | 生产环境展示 error.stack 泄露源码路径 | PROD 仅显示通用提示 |
| P2-29 | `src/pages/SystemTest.tsx` | 154-159 | setTimeout 未保存 id，unmount 后触发 setState | ref 保存 id 并清理 |
| P2-30 | `src/pages/ResourceGeneration.tsx` | 133-141 | onComplete 中 setTimeout 未清理 | ref 保存 id 并清理 |
| P2-31 | `src/store/index.ts` | 169-180 | initializeAuth 重复注册全局事件监听器 | 模块级标志位去重 |
| P2-32 | `src/store/index.ts` | 375-401 | `pollTaskStatus` 死代码且定时器无取消 | 删除该方法 |

### 逻辑健壮性类

| 编号 | 文件 | 行号 | 描述 | 修复建议 |
|------|------|------|------|----------|
| P2-33 | `backend/app/utils/hallucination.py` | 99 | 综合评分公式 `rule_score*0.5+llm_score*0.5+rule_score*0.3` 实为 0.8+0.5，与注释不符 | 明确权重 `rule_score*0.6+llm_score*0.4` |
| P2-34 | `backend/app/utils/text_slice.py` | 320-338 | `overlap >= max_length` 时 start 不前进，死循环 | 入口校验或强制 `min(overlap, max_length//2)` |
| P2-35 | `backend/app/utils/metrics.py` | 290 | `record_date=datetime.now()` 用本地时间，与 utcnow_naive 混用 | 统一用 utcnow_naive |
| P2-36 | `backend/app/schemas/response.py` | 92, 101 | 响应时间戳用 `datetime.now()` 与全局不统一 | 用 utcnow_naive |
| P2-37 | `backend/app/models/learner_profile.py` | 68-79 | 能力分数 0-100 仅应用层校验，无 DB CheckConstraint | 模型加 CheckConstraint |
| P2-38 | `backend/app/services/tutoring_service.py` | 349 | `session_id=f"session_{int(time.time())}"` 同秒重复 | 用 uuid4 |
| P2-39 | `backend/app/utils/llm.py` | 406-439 | mock 响应用脆弱字符串匹配选分支 | 用显式 mock_type 参数 |
| P2-40 | `backend/app/middleware/tracing.py` | 33 | `uuid4()[:8]` 仅 32 位熵，高并发碰撞致追踪失效 | 用完整 UUID 或至少 16 字符 |

---

## 五、P3 代码规范问题

### 弃用 API / 死代码

| 编号 | 文件 | 行号 | 描述 | 修复建议 |
|------|------|------|------|----------|
| P3-1 | `backend/app/routers/agent.py` | 119 | `request.dict()` Pydantic v2 弃用 | 改 `request.model_dump()` |
| P3-2 | `backend/app/utils/text_slice.py` | 342-370 | `_add_context` 死代码无调用 | 删除 |
| P3-3 | `backend/app/utils/hallucination.py` | 22-25 | `TECH_KEYWORDS_TO_VERIFY` 未使用 | 删除 |
| P3-4 | `backend/app/middleware/prometheus.py` | 17 | `import logging` 与统一 loguru 不一致 | 改用 loguru |
| P3-5 | `backend/app/main.py` | 494-496 | `get_core_metrics` 中无用 COUNT 查询未赋值 | 删除或使用 |
| P3-6 | `backend/app/utils/logger.py` | 324 | `init_logger()` 模块导入时执行 | 移至 lifespan 启动事件 |
| P3-7 | `backend/app/celery_app.py` | 42 等 | `industry: str = None` 类型注解错误 | 改 `Optional[str] = None` |

### 模型/规范

| 编号 | 文件 | 行号 | 描述 | 修复建议 |
|------|------|------|------|----------|
| P3-8 | `backend/app/models/anonymized_data.py` | 25 | 注释"铸箱"应为"邮箱" | 修正 |
| P3-9 | `backend/app/models/knowledge_slice.py` | 28 | 注释"内容哈值"应为"内容哈希值" | 修正 |
| P3-10 | `backend/app/models/knowledge_slice.py` | 43 | 列名 `metadata` 易混淆/部分方言保留字 | 改 `slice_metadata` |
| P3-11 | `backend/app/models/learner_profile.py` | 142-153 | `if scores else 0` 不可达分支 | 简化 |
| P3-12 | `backend/app/models/answer_record.py` | 92-93 | 缺 `updated_at` 审计字段 | 添加 onupdate 时间戳 |
| P3-13 | `backend/app/services/report_service.py` | 825-833 | 系统指标 fallback 硬编码 mock 值（2.3/94.7/87.2 等）误导用户 | 无数据返回 0 或 None |

### 前端规范

| 编号 | 文件 | 行号 | 描述 | 修复建议 |
|------|------|------|------|----------|
| P3-14 | `src/pages/LearningReport.tsx` 等多处 | 480 等 | 列表用 `key={idx}`，顺序变化时 DOM 复用错误 | 用稳定 id |
| P3-15 | `src/store/index.ts` | 317-471 | 多处 `catch { // silent fail }` 吞错无 error 状态 | 设 error 字段或 toast 提示 |
| P3-16 | `src/pages/ResourceGeneration.tsx` | 96-155 | 变量声明顺序混乱，useCallback 引用未声明 setter | useState 集中顶部 |
| P3-17 | `src/pages/AdaptiveGuidance.tsx` 等 | - | 大量 `as unknown as` 类型断言绕过检查 | 定义准确 interface 或用 zod |
| P3-18 | `src/pages/EnterpriseTraining.tsx` 等 | 175 等 | 混用 `alert()` 而非项目 toast 系统 | 统一用 toast |
| P3-19 | `src/components/toastStore.ts` | 22-25 | setTimeout 未保存 id，无法提前取消 | Map 记录并清理 |
| P3-20 | `src/pages/MultiAgentVisualization.tsx` | 70-71 | inline style 覆盖 Tailwind class，冗余 | 删除其一 |

---

## 六、修复优先级建议

### 第一优先级（立即修复，影响安全与核心功能）

1. **P0-1** SSE Token URL 泄露 → 改短期 ticket 机制（全栈改动）
2. **P0-2** 限流 X-Forwarded-For 绕过 → 配置可信代理
3. **P0-3** 脱敏工具泄露+返回原值 → 日志脱敏+兜底全掩码
4. **P0-4** JWT 密钥文件权限 → `os.chmod(0o600)`
5. **P1-1** Chroma 索引 KeyError → 修复字段名（知识库检索降级）
6. **P1-2** knowledge_topic 错误赋值 → 用 target_topic（知识溯源失效）
7. **P1-3** 画像更新不生效 → 新 session 重查（自适应导学失效）
8. **P1-4** 批量导入未 rollback → 加 rollback（整批数据丢失）
9. **P1-6** 文本切片重复 → 加 continue（知识库内容损坏）

### 第二优先级（尽快修复，影响体验与数据一致性）

10. **P1-8** ProtectedRoute 登录闪烁 → 同步初始化
11. **P1-14** 文档处理未 rollback → except 先 rollback
12. **P1-15** 任务状态永久 running → except 更新为 failed
13. **P1-7** X-Request-ID 日志注入 → 清洗
14. **P0-6** 匿名化可逆 → 评估是否删除加密字段
15. **P1-12/13** 前端定时器/竞态 → ref + AbortController

### 第三优先级（迭代优化，性能与健壮性）

16. P2 性能类：N+1 查询、全表加载、事件循环阻塞 → SQL 聚合
17. P2 资源管理：DB Session 泄漏、LLM 客户端未关闭、Celery acks_late
18. P2 前端：过度渲染、防抖缺失、useMemo

### 第四优先级（代码清理）

19. P3 弃用 API、死代码、注释错误、类型断言、key 规范

---

## 七、附：已交叉验证的关键发现

以下发现已通过直接读取源码逐行核实，确认准确：

| 发现 | 验证结果 |
|------|----------|
| P1-1 Chroma `slice_data['slice_index']` vs dict 'index' | ✅ 确认：text_slice.py 字段名为 'index'，knowledge_service.py L259 用 'slice_index' 必抛 KeyError |
| P1-2 knowledge_topic=overall_level | ✅ 确认：resource_service.py L226 确实赋值 overall_level |
| P1-3 画像更新跨 session | ✅ 确认：learner 脱离原 session，新 session 中未重查 |
| P1-6 文本切片重复缺 continue | ✅ 确认：L56-79 块后无 continue，继续执行 L96 append |
| P0-3 脱敏工具泄露+返回原值 | ✅ 确认：L59-60/L88-89 日志明文+return 原值 |

---

*报告结束。共 81 项问题，其中 6 项 P0 严重、15 项 P1 功能性 Bug、30 项 P2 性能/健壮性、30 项 P3 规范。建议按第六节优先级顺序修复。*
