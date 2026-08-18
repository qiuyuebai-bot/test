# 项目全面优化分析报告

> **生成日期**：2026-08-18
> **分析范围**：前端（React 18 + TypeScript + Vite + TailwindCSS）、后端（FastAPI + SQLAlchemy + Celery + ChromaDB）、部署（Docker + K8s Helm + Nginx）
> **分析方法**：全量代码审查 + 配置审计 + 架构分析 + 既有代码质量报告交叉验证

---

## 目录

1. [执行摘要](#一执行摘要)
2. [前端性能优化](#二前端性能优化)
3. [后端性能优化](#三后端性能优化)
4. [代码质量提升](#四代码质量提升)
5. [用户体验优化](#五用户体验优化)
6. [实施路线图](#六实施路线图)
7. [量化预期收益](#七量化预期收益)

---

## 一、执行摘要

本报告对领域知识个性化生成与多智能体协同决策系统进行了全面的性能、代码质量和用户体验分析，共识别出 **32 项** 具体优化建议，按优先级分布如下：

| 优先级 | 数量 | 说明 |
|--------|------|------|
| 🔴 P0（立即修复） | 8 项 | 影响安全、核心性能或阻塞上线的问题 |
| 🟡 P1（尽快修复） | 14 项 | 显著影响用户体验、性能或可维护性 |
| 🟢 P2（迭代优化） | 10 项 | 锦上添花，持续改进 |

**最关键的发现**：
- 后端在 async 路由中全程使用同步数据库访问，事件循环被阻塞，并发能力被严重压制
- 生产环境 Nginx 对所有静态资源设置 `no-cache`，浏览器缓存完全未被利用
- Vite 构建未配置代码分割策略，重型依赖打包进主 chunk，首屏加载体积过大
- 生产环境部署为单进程 Uvicorn，无法利用多核 CPU
- 已有代码质量报告中的 6 项 P0 安全问题需逐项验证修复状态

---

## 二、前端性能优化

### FE-P0-1：Vite 构建未配置代码分割策略

| 属性 | 内容 |
|------|------|
| **问题描述** | `scripts/vite.config.mjs` 的 `build` 配置仅设置了 `chunkSizeWarningLimit: 600`，没有 `rollupOptions.output.manualChunks`。`recharts`（~100KB+ gzip）、`react-markdown + katex + remark/rehype 插件链`（~250KB+ gzip）等重型依赖被打包进主 chunk 或随机分裂，首屏加载体积过大。当前所有页面的 JS 都在首次访问时被加载（虽然有 lazy 路由，但 chunk 边界不合理导致 vendor 代码仍在主 chunk）。 |
| **涉及文件** | `scripts/vite.config.mjs` |
| **优化方案** | 添加 `rollupOptions.output.manualChunks`，将重型库拆分为独立 chunk：① `recharts` 单独打包（仅 MetricsDashboard/AdminOpsOverview/LearningReport 使用）；② `react-markdown + katex + remark-gfm + remark-math + rehype-katex` 打包为 markdown chunk（仅 ResourceGeneration/LearningReport/KnowledgeBase 使用）；③ `react-hook-form + @hookform/resolvers + zod` 打包为 form chunk；④ 其余 node_modules 统一打包为 vendor chunk。 |
| **预期效果** | 首屏 JS 体积减少 40-60%，首屏加载时间缩短 30-50%，路由间切换时利用浏览器缓存避免重复加载已下载的 vendor chunk。 |
| **实施优先级** | 🔴 P0 |
| **预计工作量** | 0.5 天 |

**参考配置**：
```ts
// vite.config.mjs - build.rollupOptions
rollupOptions: {
  output: {
    manualChunks: {
      'vendor-react': ['react', 'react-dom', 'react-router-dom'],
      'vendor-query': ['@tanstack/react-query', 'zustand'],
      'vendor-charts': ['recharts'],
      'vendor-markdown': ['react-markdown', 'remark-gfm', 'remark-math', 'rehype-katex', 'katex'],
      'vendor-form': ['react-hook-form', '@hookform/resolvers', 'zod'],
      'vendor-ui': ['lucide-react', 'clsx'],
      'vendor-sentry': ['@sentry/react'],
    },
  },
}
```

---

### FE-P0-2：Nginx 静态资源缓存策略在生产环境完全禁用

| 属性 | 内容 |
|------|------|
| **问题描述** | `deploy/nginx/nginx.conf` 第 17-21 行对所有静态资源（js/css/图片/字体）设置了 `expires -1; add_header Cache-Control "no-cache"`，这意味着**每次访问**都要向服务器重新请求验证所有静态资源，完全没有利用浏览器缓存。Vite 构建产物中 JS/CSS 文件名已包含 hash（如 `index-a1b2c3d4.js`），内容变化时 hash 变化，完全可以设置永久缓存。 |
| **涉及文件** | `deploy/nginx/nginx.conf`、`Dockerfile`（前端） |
| **优化方案** | 对带 hash 的资源设置 `expires 1y; add_header Cache-Control "public, immutable"`；对 `index.html` 保持 `no-cache`（因为文件名不含 hash，需要每次验证更新）。可通过 Nginx 配置中的正则匹配 hash 模式的文件名，或在 Dockerfile 中按构建环境生成不同的 nginx 配置。 |
| **预期效果** | 二次访问静态资源加载时间从数百毫秒降至 0（disk cache），服务器带宽消耗降低 80%+，用户感知页面加载速度大幅提升。 |
| **实施优先级** | 🔴 P0 |
| **预计工作量** | 0.5 天 |

**参考配置**：
```nginx
# index.html - 不缓存，每次验证
location = /index.html {
    add_header Cache-Control "no-cache, no-store, must-revalidate";
}
# 带 hash 的静态资源 - 永久缓存
location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff2?|ttf|eot)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
    try_files $uri =404;
}
```

---

### FE-P1-1：未启用 Brotli 压缩

| 属性 | 内容 |
|------|------|
| **问题描述** | Nginx 配置仅启用了 gzip 压缩，未启用 Brotli 压缩。Brotli 相比 gzip 对文本资源（JS/CSS/HTML/JSON）压缩率高 15-25%，且主流浏览器（Chrome/Firefox/Edge/Safari）均已支持。 |
| **涉及文件** | `deploy/nginx/nginx.conf`、前端 `Dockerfile` |
| **优化方案** | 方案一（推荐）：在 Vite 构建阶段使用 `vite-plugin-compression` 预生成 `.br` 和 `.gz` 文件，Nginx 配置 `gzip_static on; brotli_static on;` 直接返回预压缩文件（零 CPU 开销）。方案二：使用支持 brotli 模块的 Nginx 镜像（如 `nginx:alpine` + 安装 `nginx-mod-http-brotli`），实时压缩。 |
| **预期效果** | JS/CSS 传输体积再减少 15-25%，FCP/LCP 指标改善。 |
| **实施优先级** | 🟡 P1 |
| **预计工作量** | 0.5 天 |

---

### FE-P1-2：中文字体未优化，存在 FOUT/布局抖动风险

| 属性 | 内容 |
|------|------|
| **问题描述** | `src/index.css` 引用了 `'Noto Sans SC'` 字体作为首选字体，但项目中没有通过 `@font-face` 声明该字体，也没有通过 `<link>` 预加载。浏览器会先尝试加载 Noto Sans SC（找不到则回退到系统字体），中文字体文件通常 3-8MB，若在后续动态加载会导致 FOUT（Flash of Unstyled Text）和布局抖动。 |
| **涉及文件** | `src/index.css`、`index.html` |
| **优化方案** | 方案一（推荐）：使用 `font-spider` 或 `glyphhanger` 对 Noto Sans SC 子集化，仅包含项目实际使用的汉字（通常可压缩至 100-300KB），通过 `@font-face` 自托管 + `<link rel="preload">` 预加载。方案二（最简便）：移除 Noto Sans SC 引用，完全使用系统字体栈（`-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif`），零加载开销且各平台体验好。 |
| **预期效果** | 消除字体加载导致的 CLS（布局偏移），提升文字渲染一致性，若选方案二则字体加载开销为 0。 |
| **实施优先级** | 🟡 P1 |
| **预计工作量** | 0.5 天 |

---

### FE-P1-3：Dashboard 页面未使用 React Query，手动管理状态

| 属性 | 内容 |
|------|------|
| **问题描述** | `src/pages/Dashboard.tsx` 使用 `useState + useEffect` 手动管理 loading/error/data 状态和 AbortController 刷新逻辑，而项目已集成 `@tanstack/react-query`（其他页面如 Agent、Training 等已使用）。这导致：Dashboard 数据无缓存（切路由回来重新 loading）、无自动重试、无 stale-while-revalidate、与全局 QueryClient 配置不一致、多写约 50 行样板代码。 |
| **涉及文件** | `src/pages/Dashboard.tsx`、`src/features/dashboard/` |
| **优化方案** | 将 Dashboard 的数据加载迁移到 `useQuery`，创建 `useDashboardData(role)` 自定义 hook，复用现有的 `queryClient` 配置。`useDashboardRefresh` 改为调用 `queryClient.invalidateQueries()`。 |
| **预期效果** | 减少 ~50 行样板代码，自动获得缓存/重试/后台刷新能力，路由切换回 Dashboard 时数据秒显（stale cache 先显示再后台刷新）。 |
| **实施优先级** | 🟡 P1 |
| **预计工作量** | 1 天 |

---

### FE-P1-4：路由切换动画实际不生效

| 属性 | 内容 |
|------|------|
| **问题描述** | `src/components/PageTransition.tsx` 的 `useEffect([], ...)` 依赖为空数组，仅在组件首次挂载时触发入场动画。在 `src/components/Layout.tsx` 中，`<PageTransition><Outlet /></PageTransition>` 没有 `key` 属性，路由切换时 Outlet 内容变化但 PageTransition 组件不重新挂载，导致入场动画永远不会再次播放。用户在页面切换时看到的是内容瞬间替换，无过渡效果。 |
| **涉及文件** | `src/components/Layout.tsx`、`src/components/PageTransition.tsx` |
| **优化方案** | 在 Layout 中将 `<PageTransition key={location.pathname}><Outlet /></PageTransition>` 设置 key，路由变化时触发 PageTransition 重新挂载。或在 PageTransition 内部监听 `location.pathname` 变化重置 `isVisible` 状态。 |
| **预期效果** | 页面切换有流畅的淡入+上移动画，消除白屏闪烁，用户感知导航更顺滑。 |
| **实施优先级** | 🟡 P1 |
| **预计工作量** | 0.5 天 |

---

### FE-P2-1：路由无预加载策略

| 属性 | 内容 |
|------|------|
| **问题描述** | 所有路由使用 `lazy()` 按需加载，但无预加载（prefetch/preload）策略。用户在 Dashboard 页面时，空闲时间没有预取可能访问的相邻路由 chunk，点击导航链接时需要等待 chunk 网络加载（通常 100-500ms），产生可感知的延迟。 |
| **涉及文件** | `src/App.tsx`、`src/components/Layout.tsx` |
| **优化方案** | 在侧边栏导航链接上添加 `onMouseEnter` 事件触发动态 `import()` 预取对应的路由 chunk；或使用 `requestIdleCallback` 在首屏加载完成后空闲时预加载高概率路由（如 KnowledgeBase、AdaptiveGuidance）。 |
| **预期效果** | 用户点击导航时目标路由 chunk 已在浏览器缓存中，实现秒开，导航感知速度大幅提升。 |
| **实施优先级** | 🟢 P2 |
| **预计工作量** | 0.5 天 |

---

### FE-P2-2：React Query 缺少持久化缓存，staleTime 配置一刀切

| 属性 | 内容 |
|------|------|
| **问题描述** | `src/lib/queryClient.ts` 全局设置 `staleTime: 30s`，对不常变化的数据（如系统配置、知识库文档列表、用户基本信息）30秒后即标记为过期重新请求。刷新页面后所有 React Query 缓存丢失（内存缓存），重新发起全量 API 请求，导致整页 loading。 |
| **涉及文件** | `src/lib/queryClient.ts`、各 `useXxxQueries.ts` |
| **优化方案** | ① 按查询粒度调整 staleTime：配置类/字典类数据 5 分钟，列表数据 1 分钟，实时任务状态 5 秒；② 引入 `@tanstack/react-query-persist-client` 将缓存持久化到 localStorage/sessionStorage，刷新后先显示缓存数据再后台静默刷新（stale-while-revalidate）。 |
| **预期效果** | 页面刷新后瞬时显示数据（消除 loading 闪烁），减少无效 API 请求 30-50%。 |
| **实施优先级** | 🟢 P2 |
| **预计工作量** | 1 天 |

---

### FE-P2-3：登录页背景图未优化

| 属性 | 内容 |
|------|------|
| **问题描述** | `public/login-cover.jpg` 作为登录页背景图，未经过 WebP 格式转换和尺寸优化。JPG 格式的背景图通常 200-500KB，WebP 可减少 50%+ 体积。图片可能分辨率过高（超过 1920px），浪费带宽。 |
| **涉及文件** | `public/login-cover.jpg`、`src/pages/Login.tsx` |
| **优化方案** | 将图片转换为 WebP（质量 75-80），使用 `<picture>` 标签提供 WebP + JPG 回退；压缩图片尺寸至实际显示分辨率（最大宽度 1920px）；考虑使用 CSS 渐变或低质量模糊占位（LQIP）改善加载体验。 |
| **预期效果** | 登录页图片加载体积减少 50-70%，登录页 LCP 提升。 |
| **实施优先级** | 🟢 P2 |
| **预计工作量** | 0.5 天 |

---

## 三、后端性能优化

### BE-P0-1：异步 FastAPI 中全程使用同步数据库访问，阻塞事件循环

| 属性 | 内容 |
|------|------|
| **问题描述** | 整个后端使用同步 SQLAlchemy（`create_engine` + `SessionLocal = sessionmaker()`），在 `async def` 路由中直接执行同步 DB 操作（如 `db.execute()`, `db.query().all()`, `db.commit()`）。同步 I/O 在 asyncio 事件循环中会阻塞整个线程，导致单进程 Uvicorn 在等待 DB 查询返回时完全无法处理其他请求。FastAPI 对此的处理是：`async def` 路由中的同步代码会直接运行在事件循环线程上（不会自动丢到线程池），**只有普通 `def` 路由才会被放到线程池执行**。这是当前后端最大的性能瓶颈。 |
| **涉及文件** | `backend/app/database.py`、所有 `@router.get/post/...` 下的 `async def` 路由、所有 service 层函数 |
| **优化方案** | 方案一（最小改动，推荐优先实施）：将所有包含 DB 操作的路由函数从 `async def` 改为普通 `def`。FastAPI 会自动将同步路由放到外部线程池执行（默认 40 线程），不阻塞事件循环。SSE 等必须保持 `async def` 的端点，其内部的 DB 操作使用 `await asyncio.to_thread(db_operation)` 包裹。方案二（长期方案）：迁移到 SQLAlchemy 2.0 async session + `asyncpg`/`aiosqlite`，全链路异步。方案三（折中）：在 `database.py` 中提供 `async_get_db()` 依赖，底层用 `asyncio.to_thread` 包装同步 session。 |
| **预期效果** | API 并发吞吐量提升 3-10 倍，p95 延迟降低 50%+，SSE 长连接不再被 DB 查询阻塞而断连。 |
| **实施优先级** | 🔴 P0 |
| **预计工作量** | 2-3 天 |

---

### BE-P0-2：生产环境单进程 Uvicorn，无法利用多核 CPU

| 属性 | 内容 |
|------|------|
| **问题描述** | 后端 `Dockerfile` 的 CMD 为 `["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]`，Helm `values.yaml` 中 `backend.workers: 1`，即单进程运行。单进程 Uvicorn 只能利用 1 个 CPU 核心。对于有 LLM 调用、向量检索、同步 I/O 等操作的服务，一个 Pod 的 CPU 利用率会在达到 1 核时即触顶，大量请求排队等待。 |
| **涉及文件** | `backend/Dockerfile`、`deploy/helm/values.yaml`、`deploy/helm/values-prod.yaml` |
| **优化方案** | 生产环境使用 Gunicorn + UvicornWorker：`gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --timeout 120`。Worker 数量建议：CPU 密集型取 `CPU核心数`，I/O 密集型取 `CPU核心数 * 2 + 1`。注意：① 每个 worker 独立加载 Chroma/LLM 客户端，内存限制需相应调整；② 内存限流器（RateLimitMiddleware）多 worker 下失效，需迁移到 Redis（见 BE-P1-3）；③ LLM 进程内 LRU 缓存多 worker 不共享，需迁移到 Redis（见 BE-P1-4）。 |
| **预期效果** | 吞吐量线性提升（多核下 2-8 倍），单 worker 因异常崩溃不影响整体服务可用性，实现零发布停机。 |
| **实施优先级** | 🔴 P0 |
| **预计工作量** | 0.5 天（配置变更）+ 配套 Redis 迁移（见 BE-P1-3/4） |

---

### BE-P1-1：健康检查端点执行全量查询，K8s 探针造成 DB 持续压力

| 属性 | 内容 |
|------|------|
| **问题描述** | `backend/app/health.py` 的 `/health/ready` 端点在每次请求时执行：`db.query(KnowledgeDoc).filter(...).all()` 加载所有启用文档到内存（遍历 Python 对象统计 status），然后执行 3 个 COUNT 查询。K8s 配置 `readinessProbe.periodSeconds: 15`，即每个 Pod 每分钟 4 次全量查询。随着知识库文档数量增长，这个端点的延迟会从毫秒级升至百毫秒甚至秒级，对 DB 造成持续不必要的压力。此外，`/health/live` 路由（Liveness 探针）也映射到同一个执行了全量检查的 readiness 函数（通过路由装饰器叠加），存在配置错误。 |
| **涉及文件** | `backend/app/health.py`、`deploy/helm/templates/` |
| **优化方案** | ① 分离 liveness 和 readiness：liveness 仅需进程存活检查（如返回 200 或 `SELECT 1`），readiness 包含业务依赖检查。② readin ess 检查结果增加 TTL 缓存（10-30秒），避免每次探针都查 DB。③ 文档统计使用 SQL 聚合查询（`func.count`, `func.sum(case(...))`）替代 Python 端遍历。④ 修复路由装饰器，`/health/live` 映射到轻量存活检查函数。 |
| **预期效果** | Liveness 探针响应 <5ms，Readiness 探针 DB 负载降低 90%+，文档量大时 readiness 延迟稳定在 <20ms。 |
| **实施优先级** | 🟡 P1 |
| **预计工作量** | 1 天 |

---

### BE-P1-2：SSE 流式端点中同步 queue.get 阻塞事件循环

| 属性 | 内容 |
|------|------|
| **问题描述** | Agent 任务的 SSE 流式端点（如 `/agent/diagnose`、`/agent/run/full-pipeline`）使用同步 `queue.Queue` 的 `q.get(timeout=1.0)` 从异步生成器中获取事件。`queue.Queue.get()` 是阻塞调用，在 `async def` 的 async generator 中直接调用会阻塞整个事件循环 1 秒，期间该 worker 无法处理任何其他请求。 |
| **涉及文件** | `backend/app/domains/agent/router.py`（SSE 端点）、`backend/app/agents/orchestrator.py` |
| **优化方案** | 方案一：使用 `asyncio.Queue` 替代同步 `queue.Queue`，用 `await asyncio.wait_for(queue.get(), timeout=1.0)` 异步等待。方案二：使用 `await asyncio.to_thread(q.get, True, 1.0)` 将同步 get 放到线程池。 |
| **预期效果** | SSE 并发连接数支持能力从数十提升到数百，SSE 长连接不再阻塞其他 API 请求处理。 |
| **实施优先级** | 🟡 P1 |
| **预计工作量** | 1 天 |

---

### BE-P1-3：内存限流器多 Worker/多 Pod 部署下失效

| 属性 | 内容 |
|------|------|
| **问题描述** | `backend/app/utils/rate_limiter.py` 的 `SlidingWindowRateLimiter` 使用进程内 `Dict + threading.Lock` 实现滑动窗口限流。部署多 worker（Gunicorn）或多 Pod（K8s HPA）时，每个进程/Pod 独立计数，限流效果被稀释 N 倍（4 workers = 实际限流阈值 x4）。登录防爆破限流（10次/分钟）在多实例下形同虚设。 |
| **涉及文件** | `backend/app/utils/rate_limiter.py` |
| **优化方案** | 生产环境使用 Redis 实现分布式滑动窗口限流：使用 Redis Sorted Set（`ZADD`/`ZREMRANGEBYSCORE`/`ZCARD`）实现精确滑动窗口，或使用固定窗口 + Lua 脚本保证原子性。开发/测试环境保留内存限流作为降级。推荐使用成熟的 `slowapi` 库 + Redis 后端。 |
| **预期效果** | 多实例部署下限流策略准确生效，登录爆破防护和 API 滥用防护在扩容后依然可靠。 |
| **实施优先级** | 🟡 P1 |
| **预计工作量** | 1.5 天 |

---

### BE-P1-4：LLM 响应缓存为进程内 OrderedDict，多 Worker 不共享且重启丢失

| 属性 | 内容 |
|------|------|
| **问题描述** | `backend/app/utils/llm.py` 使用进程内 `OrderedDict` 做 LRU 缓存（1024 条，TTL 1小时），仅缓存 temperature ≤ 0.3 的确定性调用。多 worker 部署下每个进程独立缓存相同的 LLM 响应，内存浪费且缓存命中率低（4 workers = 4 份独立缓存，命中率约 1/4）。服务重启后缓存全部丢失，冷启动阶段重复调用 LLM。 |
| **涉及文件** | `backend/app/utils/llm.py` |
| **优化方案** | 将 LLM 响应缓存迁移到 Redis：key 为 `llm:cache:{sha256(system_prompt + user_prompt + model + temperature)}`，value 为 JSON 序列化的响应，TTL 3600秒。使用 Redis SET 带 EX 参数自动过期。注意：仅缓存 temperature ≤ 0.3 的确定性调用，流式输出不缓存。 |
| **预期效果** | 所有 worker 共享缓存，LLM 确定性调用（如知识检索验证、评分判断、结构化提取）重复请求命中缓存时，响应延迟从秒级降至毫秒级，LLM API 调用成本减少 30-60%。 |
| **实施优先级** | 🟡 P1 |
| **预计工作量** | 1 天 |

---

### BE-P2-1：Prometheus 指标每次抓取执行数据库 COUNT 查询

| 属性 | 内容 |
|------|------|
| **问题描述** | `backend/app/middleware/prometheus.py` 在 `/metrics` 端点被抓取时执行数据库 COUNT 查询（统计用户数、任务数、文档数等）。Prometheus 默认 15-30 秒抓取一次，高频抓取场景下增加数据库不必要的负载。 |
| **涉及文件** | `backend/app/middleware/prometheus.py` |
| **优化方案** | 对 COUNT/SUM 类聚合指标使用后台定时任务（`APScheduler` 或 asyncio task）每 30-60 秒更新一次缓存值，`/metrics` 端点直接读取缓存值返回。请求延迟 Histogram 和计数器类指标保持实时增量更新（这部分本就是内存操作，无 DB 开销）。 |
| **预期效果** | 指标采集零 DB 开销，采集延迟稳定在 <5ms。 |
| **实施优先级** | 🟢 P2 |
| **预计工作量** | 0.5 天 |

---

### BE-P2-2：数据库连接池配置未适配多 Worker 部署

| 属性 | 内容 |
|------|------|
| **问题描述** | `backend/app/config.py` 默认 `DATABASE_POOL_SIZE=10, DATABASE_MAX_OVERFLOW=20`（每个进程最多 30 个 DB 连接）。多 worker 部署下总连接数 = workers * 30。4 workers * 30 = 120 连接，可能超过 PostgreSQL 默认 `max_connections=100`，导致连接拒绝错误。当前 SQLite 配置不使用连接池（合理），但 PostgreSQL 生产部署需精细调整。 |
| **涉及文件** | `backend/app/config.py`、`deploy/helm/values-prod.yaml` |
| **优化方案** | ① 根据 worker 数量和 DB max_connections 合理分配：每个 worker `pool_size=5, max_overflow=10`（共 15/worker），4 workers = 60 连接，留有余量。② 推荐在应用和 DB 之间部署 PgBouncer 做连接池中间件，设置 `pool_mode=transaction`，将数百个应用连接复用到数十个 DB 连接。③ PostgreSQL 端调整 `max_connections=200`（根据内存情况）。 |
| **预期效果** | 避免连接耗尽导致的 503 错误，数据库连接利用率更稳定，支持更高并发。 |
| **实施优先级** | 🟢 P2 |
| **预计工作量** | 0.5 天 |

---

## 四、代码质量提升

### Q-P0-1：既有代码质量报告中的 P0 安全问题需逐项验证修复

| 属性 | 内容 |
|------|------|
| **问题描述** | `code-quality-report.md`（2026-07-01 生成）记录了 6 项 P0 安全问题。经本次审查发现：P0-2（限流 X-Forwarded-For 绕过）已修复（`rate_limiter.py` 中增加了 `TRUSTED_PROXIES` 白名单逻辑）；P0-4（JWT 密钥文件权限）已修复（`config.py` 中有 `os.chmod(_SECRET_FILE, 0o600)`）。其余 4 项需逐项验证当前修复状态：P0-1（SSE Token 通过 URL query 参数传递，存在日志/Referer 泄露风险）、P0-3（脱敏工具日志泄露原始数据+异常时返回未脱敏值）、P0-5（Token 存储在 localStorage 有 XSS 窃取风险）、P0-6（匿名化数据可逆，存储了加密原始数据）。 |
| **涉及文件** | 见 `code-quality-report.md` P0 节 |
| **优化方案** | **P0-1 SSE Token**：短期方案是改用 `fetch + ReadableStream` 替代 EventSource（可在 Header 中携带 Authorization）；中期方案是后端签发短期 SSE ticket（30秒有效，单次使用）。**P0-3 脱敏**：检查 `backend/app/utils/anonymize.py` 确保格式异常时返回全掩码（`****`）而非原值，日志中不输出原始敏感数据。**P0-5 localStorage Token**：短期方案是确保部署严格 CSP 策略防止 XSS、缩短 access_token 有效期至 15 分钟；中期方案是迁移到 `httpOnly + Secure + SameSite=Strict` Cookie。**P0-6 匿名化可逆**：评估是否需要还原能力，若为不可逆匿名化则删除 `original_data_encrypted` 字段。 |
| **预期效果** | 消除所有已知安全漏洞，通过安全审计，合规风险降低。 |
| **实施优先级** | 🔴 P0 |
| **预计工作量** | 1-2 天（逐项验证+修复） |

---

### Q-P0-2：手动管理的 DB Session 上下文不严谨，存在连接泄漏风险

| 属性 | 内容 |
|------|------|
| **问题描述** | `get_db()` 依赖注入（`database.py`）有完整的 try/finally 确保 session 关闭，但部分代码直接使用 `db = SessionLocal()` 手动管理 session，若中间逻辑异常可能跳过 `db.close()`。如 `backend/app/health.py` 第 72 行和第 227 行直接创建 SessionLocal，虽然有 try/finally，但如果被复制到其他地方容易遗漏 close。既有代码质量报告 P2-19 也指出 health_readiness 的 except 分支中未 close session。 |
| **涉及文件** | `backend/app/health.py`、`backend/app/database.py`、可能存在的其他手动 SessionLocal 使用处 |
| **优化方案** | ① 所有路由统一使用 `Depends(get_db)` 依赖注入获取 session。② 非请求场景（脚本、定时任务）必须使用 `with get_db_context() as db:` 上下文管理器。③ 全面搜索 `SessionLocal()` 的使用，确保每个手动创建都有 try/finally 或上下文管理器。 |
| **预期效果** | 消除数据库连接泄漏，防止长时间运行后连接池耗尽导致 503。 |
| **实施优先级** | 🔴 P0 |
| **预计工作量** | 0.5 天 |

---

### Q-P1-1：后端路由缺少 response_model 类型声明

| 属性 | 内容 |
|------|------|
| **问题描述** | 大多数路由直接 `return success({...})` 而没有声明 FastAPI 的 `response_model` 参数，导致：① OpenAPI 文档（`/docs`）中响应 schema 不准确，前端无法通过 `openapi-typescript` 生成精确的 TypeScript 类型；② Pydantic 验证和序列化未执行，可能意外返回 ORM 内部字段或敏感数据；③ 自动生成的 `src/types/api/generated.ts` 类型不完整，前端被迫使用 `as unknown as` 类型断言。 |
| **涉及文件** | `backend/app/routers/*.py`、`backend/app/domains/**/router.py`、`backend/app/schemas/` |
| **优化方案** | 为每个路由添加 `response_model=XxxResponse` 参数，在 `schemas/` 目录下定义各端点的响应 Pydantic 模型。使用 `model_config = {"from_attributes": True}` 支持从 ORM 对象直接序列化。定期运行 `npm run openapi:gen` 更新前端类型。 |
| **预期效果** | API 文档更准确，前端自动生成类型完整，自动序列化防止意外数据泄露，前后端类型一致性保障。 |
| **实施优先级** | 🟡 P1 |
| **预计工作量** | 3-5 天（可分域逐步补充） |

---

### Q-P1-2：except Exception 过宽，吞掉编程错误

| 属性 | 内容 |
|------|------|
| **问题描述** | 后端多处使用 `except Exception` 捕获所有异常，然后返回空值、mock 数据或仅记 warning 日志。如 `llm.py` 中多处 except 返回 mock 数据、`agent.py` 中 `get_debate_records` 用 except Exception 吞掉 JSON 解析错误。这掩盖了 NullPointer、KeyError、AttributeError 等编程错误，使 Bug 在生产环境静默存在，直到数据不一致才被发现。 |
| **涉及文件** | `backend/app/utils/llm.py`、`backend/app/domains/agent/router.py`、`backend/app/services/*.py` 多处 |
| **优化方案** | ① 将宽泛的 `except Exception` 改为捕获具体异常类型（`json.JSONDecodeError`、`httpx.TimeoutException`、`sqlalchemy.exc.SQLAlchemyError`、`IOError` 等）。② 捕获未知异常时使用 `logger.exception()` 记录完整堆栈并 re-raise 或返回 500 错误，不要静默返回 mock 数据。③ LLM 调用的 fallback 逻辑应显式标记 `mock_mode=True`，前端可提示用户"当前使用离线模式"。 |
| **预期效果** | 编程错误在测试/灰度阶段快速暴露（而不是在生产中静默返回错误数据），Sentry/日志中可追踪到完整堆栈。 |
| **实施优先级** | 🟡 P1 |
| **预计工作量** | 2 天 |

---

### Q-P1-3：前端错误处理不统一，console.error 未接入 Sentry

| 属性 | 内容 |
|------|------|
| **问题描述** | 前端部分 catch 块使用 `console.error()` 打印错误（如 `authStore.ts` 第 60 行 `console.error('logout failed:', err)`、第 73 行 `console.error('fetchCurrentUser failed:', err)`），用户看不到这些日志，开发团队也无法在 Sentry 中追踪。项目已集成 `@sentry/react` 和 toast 系统，但未统一使用。 |
| **涉及文件** | `src/store/authStore.ts`、`src/store/*.ts`、各页面组件 catch 块 |
| **优化方案** | 制定统一错误处理规范：① 用户操作相关错误（网络、权限、表单验证）调用 `toast.error()` 给出明确提示；② 编程/未知错误调用 `reportError()` 上报 Sentry；③ 移除裸 `console.error`，使用统一的 logger 工具函数；④ ESLint 规则禁止 `console.error`（已配置 `no-console: ['warn', { allow: ['warn', 'error'] }]`，建议改为 `allow: []` 仅允许通过统一工具输出）。 |
| **预期效果** | 用户收到一致的错误反馈，所有异常都被追踪到 Sentry，便于排查线上问题。 |
| **实施优先级** | 🟡 P1 |
| **预计工作量** | 1 天 |

---

### Q-P2-1：测试覆盖率存在盲区

| 属性 | 内容 |
|------|------|
| **问题描述** | 项目已有较完善的测试体系：前端 35+ 测试文件（Vitest + Testing Library）、后端 33+ 测试文件（pytest）、E2E 测试 5 个核心流程（Playwright）。但核心复杂模块仍缺少测试覆盖：① 后端 orchestrator 多智能体编排（含并发事件总线）缺少单元测试；② SSE 流式端点缺少集成测试；③ 前端 ErrorBoundary/Sentry 集成缺少错误边界测试；④ KnowledgeBase 上传→解析→检索完整链路缺少 E2E 测试；⑤ ResourceGeneration 生成→查看流程缺少 E2E 测试。 |
| **涉及文件** | `backend/app/agents/`、`e2e/`、前端各 `*.test.tsx` |
| **优化方案** | ① 为 orchestrator 添加单元测试（mock agent，验证事件流和状态转换）。② 为 SSE 端点添加集成测试（使用 httpx streaming client 验证事件序列）。③ 补充 KnowledgeBase 上传文档→处理→检索验证的 E2E 测试。④ 补充 ResourceGeneration 触发→SSE 进度→查看结果的 E2E 测试。⑤ 在 CI 中配置覆盖率阈值（前端语句覆盖率 >70%、后端 >80%）。 |
| **预期效果** | 核心业务逻辑测试覆盖率 >80%，关键用户路径 E2E 全覆盖，重构和迭代时减少回归 Bug。 |
| **实施优先级** | 🟢 P2 |
| **预计工作量** | 3-5 天（持续补充） |

---

### Q-P2-2：前端类型断言 `as unknown as` 绕过类型检查

| 属性 | 内容 |
|------|------|
| **问题描述** | 前端代码中存在多处 `as unknown as SomeType` 双重类型断言，直接绕过了 TypeScript 的类型检查。这通常发生在 API 响应类型与实际使用不匹配时（因为 response_model 缺失导致 generated.ts 类型不精确），本质上放弃了类型安全。 |
| **涉及文件** | `src/pages/AdaptiveGuidance.tsx`、`src/pages/multi-agent/` 等多处 |
| **优化方案** | ① 配合 Q-P1-1（后端 response_model）补全 API 类型，使 openapi-typescript 生成精确类型。② 定义准确的 Zod schema 进行运行时验证（项目已引入 zod），替代类型断言。③ 在 ESLint 中添加规则禁止 `as unknown as` 模式（可通过自定义规则或 `@typescript-eslint/consistent-type-assertions`）。 |
| **预期效果** | 编译时捕获字段名/类型错误，减少运行时数据异常，前后端类型一致性提升。 |
| **实施优先级** | 🟢 P2 |
| **预计工作量** | 2 天（依赖 Q-P1-1 完成） |

---

### Q-P2-3：前端定时器/副作用清理不彻底

| 属性 | 内容 |
|------|------|
| **问题描述** | 既有代码质量报告 P1-12/P1-13/P2-29/P2-30 指出多处 setTimeout/setInterval 未在组件 unmount 时清理，导致内存泄漏和 "setState on unmounted component" 警告。虽然部分可能已修复，但需要全面排查。 |
| **涉及文件** | `src/pages/AdaptiveGuidance.tsx`、`src/pages/ResourceGeneration.tsx`、`src/pages/SystemTest.tsx` 等 |
| **优化方案** | 全面搜索 `setTimeout`/`setInterval`/`setInterval`/`addEventListener` 使用，确保：① 定时器 id 存 useRef，useEffect cleanup 函数中 clearTimeout/clearInterval；② 事件监听器在 cleanup 中 removeEventListener；③ AbortController 传递给所有 fetch 请求，组件卸载时 abort。建议添加 ESLint 插件 `eslint-plugin-react-hooks` 的 `exhaustive-deps` 规则为 error 级别。 |
| **预期效果** | 消除内存泄漏，控制台无 React warning，长时间使用后页面不卡顿。 |
| **实施优先级** | 🟢 P2 |
| **预计工作量** | 1 天 |

---

## 五、用户体验优化

### UX-P0-1：路由切换无过渡动画（同 FE-P1-4）

| 属性 | 内容 |
|------|------|
| **问题描述** | （详见 FE-P1-4）PageTransition 组件的入场动画在路由切换时不重新触发，页面内容瞬间替换，感知生硬。 |
| **优化方案** | （同 FE-P1-4）Layout 中 Outlet 设置 `key={location.pathname}`。 |
| **预期效果** | 页面切换流畅淡入/上移，消除白屏闪烁，提升感知速度。 |
| **实施优先级** | 🔴 P0 |
| **预计工作量** | 0.5 天 |

---

### UX-P1-1：各页面 Loading 状态不统一，缺少内容骨架屏

| 属性 | 内容 |
|------|------|
| **问题描述** | 项目已有 `src/components/Skeleton.tsx` 提供了通用骨架屏组件，`src/components/LoadingState.tsx` 提供了加载状态。但各页面数据加载时使用的 loading UI 不一致：部分页面使用 Spinner 转圈、部分页面显示空白、部分页面直接显示空状态。关键内容区域（Dashboard 卡片、表格行、图表区域）在加载时没有对应的骨架屏占位，导致页面布局跳动（CLS）。 |
| **涉及文件** | `src/components/Skeleton.tsx`、各页面组件中的 loading 渲染逻辑 |
| **优化方案** | ① 为 Dashboard 指标卡片设计卡片骨架屏（模拟数值/标签/图标布局）。② 为表格列表设计行骨架屏（3-5 行灰色条）。③ 为图表区域设计矩形骨架屏（带 shimmer 动画）。④ 统一规范：React Query `isLoading`（首次加载无数据）显示骨架屏，`isFetching`（后台刷新）显示 subtle loading 指示器（顶部进度条或小 spinner），不阻塞已有内容。 |
| **预期效果** | 加载过程中保持布局稳定（无 CLS），用户感知等待时间减少（骨架屏比空白+Spinner感觉更快），各页面 loading 体验一致。 |
| **实施优先级** | 🟡 P1 |
| **预计工作量** | 2 天 |

---

### UX-P1-2：缺少全局网络状态感知和 SSE 断线重连提示

| 属性 | 内容 |
|------|------|
| **问题描述** | `src/lib/request.ts` 中 `NetworkError` 在单次请求失败时 toast 提示"网络连接失败"，但没有主动监听 `navigator.onLine` 状态。用户完全断网后继续操作才报错，没有提前的离线状态指示条。SSE 连接（`useTaskSSE`）断开后也没有自动重连机制和状态提示，用户可能误以为任务卡住。 |
| **涉及文件** | `src/lib/request.ts`、`src/hooks/useTaskSSE.ts`、`src/components/Layout.tsx` |
| **优化方案** | ① 在 Layout 顶部添加网络状态横幅：`navigator.onLine === false` 时显示"当前网络不可用，部分功能暂不可用"的黄色提示条。② `useTaskSSE` 添加自动重连逻辑（指数退避：1s→2s→4s→8s，最多 5 次），重连时显示"连接中断，正在重连..."状态。③ 重连失败后提示用户手动刷新。 |
| **预期效果** | 用户明确感知网络状态变化，SSE 任务进度不再静默中断，弱网环境下体验更可靠。 |
| **实施优先级** | 🟡 P1 |
| **预计工作量** | 1.5 天 |

---

### UX-P1-3：表单错误提示未精确到字段级别

| 属性 | 内容 |
|------|------|
| **问题描述** | `src/lib/request.ts` 第 345-349 行对后端 422 校验错误将所有错误信息 `Object.values().flat().join('；')` 合并为一个 toast 提示，用户无法定位到具体哪个字段出错。Login、注册、批量导入等表单也缺少字段级内联错误提示样式。项目已集成 `react-hook-form + @hookform/resolvers + zod`，但未充分利用其字段级错误能力。 |
| **涉及文件** | `src/lib/request.ts`、`src/components/FormField.tsx`、各表单页面 |
| **优化方案** | ① 在 `FormField` 组件中接入字段级错误显示（红色边框 + 字段下方错误文字）。② 后端 422 响应的字段错误映射回 react-hook-form 的 `setError` 方法，逐字段显示。③ Toast 仅显示通用提示"请检查表单中的错误"，具体错误由字段内联提示承载。 |
| **预期效果** | 用户能直接看到哪个字段有问题以及错误原因，减少表单填写挫败感，表单提交一次成功率提升。 |
| **实施优先级** | 🟡 P1 |
| **预计工作量** | 2 天 |

---

### UX-P1-4：Nginx 静态资源不缓存（同 FE-P0-2）

| 属性 | 内容 |
|------|------|
| **问题描述** | （详见 FE-P0-2）生产环境静态资源 `no-cache` 导致每次刷新都重新加载，用户感觉应用"卡"。 |
| **优化方案** | （同 FE-P0-2） |
| **预期效果** | 二次访问秒开，无重复加载等待。 |
| **实施优先级** | 🟡 P1 |

---

### UX-P2-1：缺少操作乐观更新（Optimistic UI）

| 属性 | 内容 |
|------|------|
| **问题描述** | 用户操作（如引导 snooze/接受、主题切换、侧边栏折叠、收藏等）目前都等待 API 返回成功后才更新 UI，用户感知有 100-500ms 的延迟。例如 `Dashboard.tsx` 中 `handleGuidanceAction` 先 await API 再更新 state，点击后有明显迟滞。 |
| **涉及文件** | `src/pages/Dashboard.tsx`、`src/components/Layout.tsx`、各交互组件 |
| **优化方案** | 对低风险操作使用 React Query 的 `onMutate` 实现乐观更新：① 触发 mutation 前立即更新 UI 状态；② API 失败时回滚到原状态并 toast 错误提示；③ 适合乐观更新的操作：引导 snooze/接受、暗黑模式切换、侧边栏折叠、表单草稿保存、分页切换。不适合乐观更新的操作：登录、支付、删除等不可逆操作。 |
| **预期效果** | 操作响应瞬时反馈（<50ms），感知速度大幅提升，应用感觉更"跟手"。 |
| **实施优先级** | 🟢 P2 |
| **预计工作量** | 1-2 天 |

---

### UX-P2-2：移动端体验适配不足

| 属性 | 内容 |
|------|------|
| **问题描述** | Layout 已实现移动端抽屉式侧边栏，但：① 侧边栏关闭按钮（X）不够显眼，用户打开后可能不知道如何关闭；② 主内容区数据表格（如知识库列表、任务列表、培训管理）在小屏幕上横向溢出，没有横向滚动提示或卡片式布局适配；③ 核心页面（Dashboard 指标卡片、图表）在窄屏下布局未充分优化；④ 缺少移动端底部导航栏，侧边栏操作不便（拇指热区不在屏幕底部）。 |
| **涉及文件** | `src/components/Layout.tsx`、各页面组件、`src/index.css` |
| **优化方案** | ① 关键数据页面（知识库列表、任务列表）增加移动端卡片式布局：在 < md breakpoint 下将表格改为卡片列表，每个卡片展示一行数据。② 图表区域支持横向滚动并添加视觉提示（如右侧渐隐遮罩提示"可滑动"）。③ Dashboard 指标卡片在移动端改为 2 列布局。④ 评估是否需要底部 Tab 栏（如果移动端是主要使用场景之一）。 |
| **预期效果** | 移动端可用性显著提升，覆盖更多使用场景（如管理层手机查看报表）。 |
| **实施优先级** | 🟢 P2 |
| **预计工作量** | 3-5 天 |

---

### UX-P2-3：空状态和错误状态缺少引导性 CTA

| 属性 | 内容 |
|------|------|
| **问题描述** | 项目有 `EmptyState.tsx` 和 `ErrorState.tsx` 组件，但部分场景的空状态仅显示文字描述，没有提供下一步操作引导。例如：知识库为空时仅显示"暂无文档"，没有"上传文档"按钮；无学习资源时没有"开始生成资源"按钮；错误状态仅显示"加载失败"和"重试"，没有"联系管理员"或"返回首页"等辅助操作。 |
| **涉及文件** | `src/components/EmptyState.tsx`、`src/components/ErrorState.tsx`、各使用处 |
| **优化方案** | ① 增强 EmptyState 组件支持 `action` prop（主操作按钮）和 `secondaryAction` prop（次要链接）。② 各场景空状态添加对应 CTA：无文档→"上传文档"、无资源→"开始诊断"、无培训项目→"创建培训项目"。③ 错误状态除"重试"外提供"返回首页"按钮，网络错误提供"检查网络"提示。 |
| **预期效果** | 减少用户在空页面困惑，新用户引导更顺畅，降低跳出率。 |
| **实施优先级** | 🟢 P2 |
| **预计工作量** | 1 天 |

---

### UX-P2-4：Toast 通知缺乏自动清理和堆叠管理

| 属性 | 内容 |
|------|------|
| **问题描述** | 代码质量报告 P3-19 指出 `toastStore.ts` 中 setTimeout 未保存 id，无法提前取消或去重。快速触发多个操作时 Toast 堆叠过多，遮挡页面内容。 |
| **涉及文件** | `src/components/toastStore.ts`、`src/components/Toast.tsx` |
| **优化方案** | ① 使用 Map 记录每个 toast 的 timeout id，toast 被手动关闭或自动过期时正确清理。② 同类 toast 去重（如连续触发"网络错误"只显示一个）。③ 最多同时显示 3-5 个 toast，超出的排队等待。④ 添加 Toast 暂停 hover 功能（鼠标悬停时不自动关闭）。 |
| **预期效果** | Toast 通知不遮挡页面、不重复、不堆积，信息传达清晰。 |
| **实施优先级** | 🟢 P2 |
| **预计工作量** | 1 天 |

---

## 六、实施路线图

### 第一阶段：P0 紧急修复（第 1 周）

> 目标：阻塞性问题修复，为后续优化打基础

| 序号 | 优化项 | 领域 | 预计工作量 |
|------|--------|------|-----------|
| 1 | BE-P0-1：同步 DB 阻塞 async 事件循环 | 后端性能 | 2-3 天 |
| 2 | FE-P0-1：Vite manualChunks 代码分割 | 前端性能 | 0.5 天 |
| 3 | FE-P0-2：Nginx 静态资源缓存策略 | 前端性能 | 0.5 天 |
| 4 | BE-P0-2：生产环境多 Worker 部署 | 后端性能 | 0.5 天 |
| 5 | Q-P0-1：P0 安全问题验证与修复 | 代码质量 | 1-2 天 |
| 6 | Q-P0-2：DB Session 泄漏修复 | 代码质量 | 0.5 天 |
| 7 | UX-P0-1：路由切换动画修复 | 用户体验 | 0.5 天 |
| | **合计** | | **6-8 天** |

> ⚠️ 注意：BE-P0-2（多 Worker）部署后会导致 BE-P1-3（限流）和 BE-P1-4（LLM 缓存）的多进程问题暴露，建议连续实施。

---

### 第二阶段：P1 重要改进（第 2-3 周）

> 目标：显著提升用户体验、性能和可维护性

| 序号 | 优化项 | 领域 | 预计工作量 |
|------|--------|------|-----------|
| 8 | FE-P1-1：Brotli 压缩 | 前端性能 | 0.5 天 |
| 9 | FE-P1-2：字体子集化 | 前端性能 | 0.5 天 |
| 10 | FE-P1-3：Dashboard 迁移 React Query | 前端性能 | 1 天 |
| 11 | FE-P1-4：路由动画（已含 P0-1） | 前端性能 | - |
| 12 | BE-P1-1：健康检查端点优化 | 后端性能 | 1 天 |
| 13 | BE-P1-2：SSE 同步阻塞修复 | 后端性能 | 1 天 |
| 14 | BE-P1-3：Redis 分布式限流 | 后端性能 | 1.5 天 |
| 15 | BE-P1-4：Redis LLM 缓存 | 后端性能 | 1 天 |
| 16 | Q-P1-1：response_model 类型声明 | 代码质量 | 3-5 天 |
| 17 | Q-P1-2：except Exception 收窄 | 代码质量 | 2 天 |
| 18 | Q-P1-3：统一错误处理 | 代码质量 | 1 天 |
| 19 | UX-P1-1：统一骨架屏 Loading | 用户体验 | 2 天 |
| 20 | UX-P1-2：网络状态与 SSE 重连 | 用户体验 | 1.5 天 |
| 21 | UX-P1-3：表单字段级错误 | 用户体验 | 2 天 |
| | **合计** | | **18-21 天** |

---

### 第三阶段：P2 持续优化（第 4 周及以后）

> 目标：锦上添花，持续打磨产品体验

| 序号 | 优化项 | 领域 | 预计工作量 |
|------|--------|------|-----------|
| 22 | FE-P2-1：路由预加载 | 前端性能 | 0.5 天 |
| 23 | FE-P2-2：React Query 持久化 | 前端性能 | 1 天 |
| 24 | FE-P2-3：登录页图片优化 | 前端性能 | 0.5 天 |
| 25 | BE-P2-1：Prometheus 指标缓存 | 后端性能 | 0.5 天 |
| 26 | BE-P2-2：连接池配置优化 | 后端性能 | 0.5 天 |
| 27 | Q-P2-1：测试覆盖率提升 | 代码质量 | 3-5 天 |
| 28 | Q-P2-2：类型安全修复 | 代码质量 | 2 天 |
| 29 | Q-P2-3：副作用清理排查 | 代码质量 | 1 天 |
| 30 | UX-P2-1：乐观更新 | 用户体验 | 1-2 天 |
| 31 | UX-P2-2：移动端适配 | 用户体验 | 3-5 天 |
| 32 | UX-P2-3：空状态引导 CTA | 用户体验 | 1 天 |
| 33 | UX-P2-4：Toast 管理优化 | 用户体验 | 1 天 |
| | **合计** | | **15-21 天** |

---

## 七、量化预期收益

| 指标 | 当前估算 | P0 优化后 | P1+P2 优化后 | 改善幅度 |
|------|---------|----------|-------------|---------|
| **首屏加载时间（宽带/Fast 3G）** | ~1.5-2.5s / ~3-5s | ~1-1.5s / ~2-3s | ~0.6-1s / ~1.5-2s | 50-60%↓ |
| **首屏 JS 体积（gzip）** | ~300-500KB（估算） | ~150-250KB | ~120-200KB | 50-60%↓ |
| **静态资源缓存命中率** | ~0%（no-cache） | ~95%+（immutable） | ~95%+ | 从无到有 |
| **API 并发吞吐（单 Pod）** | ~10-30 RPS（事件循环阻塞） | ~100-200 RPS | ~200-500 RPS | **10-20x↑** |
| **API p95 延迟（列表查询）** | ~200-500ms | ~50-150ms | ~30-80ms | 70-85%↓ |
| **API p95 延迟（LLM 确定性调用）** | ~2-5s（每次调用 LLM） | ~2-5s | ~50ms（缓存命中） | **95%+↓** |
| **SSE 最大并发连接数** | ~10-30（阻塞事件循环） | ~100-300 | ~500-1000 | **20-50x↑** |
| **CLS（布局抖动分数）** | 0.15-0.25（估算） | 0.1-0.15 | <0.1 | 50-60%↓ |
| **已知 P0 安全漏洞** | 4 项（待验证） | 0 | 0 | 100% 修复 |
| **前端核心路径测试覆盖** | ~60%（估算） | ~60% | >80% | +20% |
| **后端核心路径测试覆盖** | ~70%（估算） | ~70% | >85% | +15% |

---

## 附录：关键文件索引

| 模块 | 关键文件路径 |
|------|-------------|
| 前端构建配置 | `scripts/vite.config.mjs` |
| 前端入口 | `src/main.tsx`、`src/App.tsx` |
| 路由与布局 | `src/components/Layout.tsx`、`src/components/PageTransition.tsx` |
| 网络请求 | `src/lib/request.ts`、`src/lib/queryClient.ts` |
| 状态管理 | `src/store/index.ts`、`src/store/authStore.ts` |
| 全局样式 | `src/index.css`、`tailwind.config.js` |
| 后端入口 | `backend/app/main.py` |
| 配置管理 | `backend/app/config.py` |
| 数据库 | `backend/app/database.py` |
| 健康检查 | `backend/app/health.py` |
| 限流 | `backend/app/utils/rate_limiter.py` |
| LLM 调用 | `backend/app/utils/llm.py` |
| 指标中间件 | `backend/app/middleware/prometheus.py` |
| Nginx 配置 | `deploy/nginx/nginx.conf` |
| 前端 Dockerfile | `Dockerfile` |
| 后端 Dockerfile | `backend/Dockerfile` |
| K8s Helm Values | `deploy/helm/values.yaml` |
| 既有质量报告 | `code-quality-report.md` |
| 性能基线 | `tests/performance/BASELINE.md` |

---

*报告结束。建议按 P0→P1→P2 顺序实施，P0 阶段预计 1 周可完成，完成后核心性能和安全问题得到根本性改善。*
