# 知域引擎 Windows 桌面发行 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `agentic-engineering` to implement this plan task-by-task with an eval before and after each task.

**Goal:** 将现有 React + FastAPI 项目交付为可安装、可卸载、可升级并能由 GitHub 标签自动发布的 Windows x64 桌面软件。

**Architecture:** Electron 负责单实例窗口和后端生命周期；PyInstaller `onedir` 后端绑定随机回环端口并同时提供 API 与 Vite 静态文件；electron-builder/NSIS 将 Electron、后端和前端压入一个安装包。现有 Web、Docker、AI 配置和业务流程继续保留。

**Tech Stack:** Electron 44.0.0、electron-builder 26.15.3、PyInstaller 6.22.2、Node.js 22、Python 3.11、React 18、FastAPI、SQLite/Alembic、NSIS、GitHub Actions。

**Spec:** `docs/superpowers/specs/2026-08-27-windows-desktop-distribution-design.md`

## Global Constraints

- 目标平台仅 Windows 10/11 x64。
- 用户机器不得要求安装 Node.js、Python、Git、Redis、Celery、Chroma 服务或浏览器。
- 不提交 `.env`、数据库、日志、构建目录、安装包或任何真实凭据。
- `npm start`、Docker Compose 和现有云端 CI 必须继续可用。
- 数据和密钥只能写入 `%APPDATA%/知域引擎/`，安装目录只读。
- Electron 渲染进程使用 `nodeIntegration: false`、`contextIsolation: true`、`sandbox: true`。
- 桌面后端只绑定 `127.0.0.1`，使用每次启动随机令牌保护全部本机 HTTP 请求。
- 数据库用户配置优先于环境变量；环境变量仅作为未配置用户的回退。
- 无网络或无 Key 时不得伪造 AI 结果；必须保留可启动、可登录和本地数据能力。
- 新增代码只在非显然的生命周期、安全和冻结资源逻辑处写简洁中文注释，关键函数用中文说明用途，不写逐行复述式注释。

---

### Task 1: 固化桌面构建基线和依赖边界

**Files:**
- Create: `backend/requirements-desktop-build.txt`
- Create: `desktop/README.md`
- Modify: `package.json`
- Modify: `package-lock.json`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: 现有 `npm run build`、`backend/requirements.txt`
- Produces: `npm run desktop:icons`、`npm run desktop:backend`、`npm run build:electron`

- [ ] **Step 1: 记录未修改基线**

Run:

```powershell
npm run typecheck
npm test -- src/pages/AiConfig.test.tsx
npm run build
```

Expected: 类型检查通过，AI 配置 16 个测试通过，Vite 生成 `dist/index.html`。后端测试若仍被损坏的本地 venv 阻止，记录该失败并使用全新 Python 3.11 venv 重建，而不是修补 venv 内的绝对路径。

- [ ] **Step 2: 增加固定的桌面 Python 构建依赖**

`backend/requirements-desktop-build.txt` 内容：

```text
-r requirements.txt
pyinstaller==6.22.2
```

- [ ] **Step 3: 安装并锁定桌面 npm 工具**

Run:

```powershell
npm install --save-dev electron@44.0.0 electron-builder@26.15.3 sharp@0.35.4 png-to-ico@3.0.2
```

Expected: `package.json` 与 `package-lock.json` 同步更新，不手工编辑 lockfile。

- [ ] **Step 4: 增加脚本入口**

在 `package.json` 中加入：

```json
{
  "main": "desktop/main.mjs",
  "scripts": {
    "desktop:icons": "node scripts/generate-desktop-icons.mjs",
    "desktop:backend": "python -m PyInstaller --noconfirm --clean --distpath desktop/out --workpath desktop/out/.pyinstaller desktop/backend.spec",
    "desktop:unpacked": "node scripts/build-desktop.mjs --dir",
    "build:electron": "node scripts/build-desktop.mjs --installer"
  }
}
```

- [ ] **Step 5: 收紧忽略规则**

保留源文件，忽略产物：

```gitignore
desktop/out/
release/
*.exe
*.blockmap
desktop/assets/icon.ico
desktop/assets/icon-*.png
```

Run: `git check-ignore -v desktop/assets/icon.svg desktop/out/backend/zhiyu-backend.exe release/test.exe`

Expected: `icon.svg` 不被忽略，两个产物被忽略。

- [ ] **Step 6: Commit**

```powershell
git add package.json package-lock.json .gitignore backend/requirements-desktop-build.txt desktop/README.md
git commit -m "build(desktop): add pinned Windows packaging toolchain"
```

### Task 2: 建立桌面数据路径和冻结资源定位

**Files:**
- Create: `backend/app/desktop_runtime.py`
- Modify: `backend/app/config.py`
- Modify: `backend/app/database.py`
- Test: `backend/tests/test_desktop_runtime.py`

**Interfaces:**
- Consumes: `APP_DATA_DIR`、`DESKTOP_MODE`、`DESKTOP_WEB_DIR`、`DESKTOP_AUTH_TOKEN`
- Produces: `settings.is_desktop: bool`、`bundle_path(relative: str) -> Path`、稳定的用户数据目录

- [ ] **Step 1: 写路径解析失败测试**

覆盖三种情况：普通源码运行仍解析到项目目录；设置 `APP_DATA_DIR` 后数据库/日志/上传目录落入该目录；冻结模式从 `sys._MEIPASS` 查找 `alembic.ini` 和迁移目录。

Run: `python -m pytest backend/tests/test_desktop_runtime.py -q`

Expected: FAIL，缺少 `desktop_runtime` 和 `APP_DATA_DIR`。

- [ ] **Step 2: 实现最小运行时帮助函数**

核心接口：

```python
def bundle_path(relative: str) -> Path:
    source_backend = Path(__file__).resolve().parents[1]
    root = Path(getattr(sys, "_MEIPASS", source_backend))
    return (root / relative).resolve()

def desktop_data_dir() -> Path:
    configured = os.environ.get("APP_DATA_DIR", "").strip()
    source_root = Path(__file__).resolve().parents[2]
    return Path(configured).resolve() if configured else source_root / "data"
```

`Settings` 新增 `DESKTOP_MODE: bool = False` 和 `APP_DATA_DIR`，所有相对持久化路径在桌面模式下解析到该目录；Web/Docker 模式保持现有路径行为。

- [ ] **Step 3: 让 Alembic 在冻结包内可定位**

将 `database.py` 的固定源码路径替换为：

```python
alembic_ini_path = bundle_path("alembic.ini")
alembic_script_path = bundle_path("alembic")
```

运行升级前，若 SQLite 已存在且当前 revision 与 head 不同，使用 `sqlite3.Connection.backup()` 写入 `data/backups/pre-upgrade-<APP_VERSION>.db`。

- [ ] **Step 4: 验证现有部署不回归**

Run:

```powershell
python -m pytest backend/tests/test_desktop_runtime.py backend/tests/test_ai_config.py -q
docker compose config
```

Expected: 路径、迁移和 AI 配置测试通过，Compose 配置可解析。

- [ ] **Step 5: Commit**

```powershell
git add backend/app/config.py backend/app/database.py backend/app/desktop_runtime.py backend/tests/test_desktop_runtime.py
git commit -m "feat(desktop): isolate runtime data and frozen resources"
```

### Task 3: 增加单进程桌面后端入口和同源 SPA

**Files:**
- Create: `backend/desktop_entry.py`
- Create: `backend/app/middleware/desktop_auth.py`
- Create: `backend/app/routers/desktop.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_desktop_server.py`

**Interfaces:**
- Consumes: `DESKTOP_MODE=true`、`DESKTOP_AUTH_TOKEN`、`DESKTOP_WEB_DIR`、`--preferred-port`
- Produces: stdout `{"event":"desktop-listening","port":<int>}`、`POST /api/v1/desktop/shutdown`

- [ ] **Step 1: 写桌面安全和 SPA 测试**

测试必须证明：无桌面令牌访问返回 403；正确令牌可访问 `/health/live`；`/dashboard` 返回 `index.html`；`/assets/*` 返回静态文件；路径穿越被拒绝；非桌面模式不注册关闭路由。

Run: `python -m pytest backend/tests/test_desktop_server.py -q`

Expected: FAIL，桌面入口和中间件尚不存在。

- [ ] **Step 2: 实现桌面认证中间件**

使用 `hmac.compare_digest()` 比较 `X-Zhiyu-Desktop-Token`，只在 `DESKTOP_MODE` 下启用。令牌为空时桌面后端必须拒绝启动，且任何日志不得打印令牌。

- [ ] **Step 3: 实现随机端口入口**

`backend/desktop_entry.py` 的关键流程：

```python
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    sock.bind(("127.0.0.1", args.preferred_port))
except OSError:
    sock.bind(("127.0.0.1", 0))
sock.listen(2048)
port = int(sock.getsockname()[1])
config = uvicorn.Config(app, host="127.0.0.1", port=port, log_config=None)
server = uvicorn.Server(config)
app.state.request_desktop_shutdown = lambda: setattr(server, "should_exit", True)
print(json.dumps({"event": "desktop-listening", "port": port}), flush=True)
server.run(sockets=[sock])
```

`--preferred-port` 只接受 49152-65535；另启 daemon watchdog 监视 `--parent-pid`，父进程消失时设置 `server.should_exit = True`。

- [ ] **Step 4: 注册静态文件与关闭路由**

API 路由先注册，桌面静态 catch-all 最后注册。仅允许解析后的资源路径位于 `DESKTOP_WEB_DIR` 内；不存在的前端路由返回 `index.html`，不存在的带扩展名资源返回 404。关闭路由通过 `BackgroundTasks` 调用 `app.state.request_desktop_shutdown`。

- [ ] **Step 5: 隔离可选服务失败**

把 `KnowledgeService.warmup()` 从数据库初始化的 fatal `try` 中分离；Chroma 失败只记录 `degraded`，数据库或 Alembic 失败在生产/桌面模式仍阻止启动。

- [ ] **Step 6: Run tests**

```powershell
python -m pytest backend/tests/test_desktop_server.py backend/tests/test_desktop_runtime.py -q
python backend/desktop_entry.py --parent-pid $PID
```

Expected: 自动分配端口，携带令牌的健康检查成功，缺少令牌为 403，Ctrl+C 后进程退出。

- [ ] **Step 7: Commit**

```powershell
git add backend/desktop_entry.py backend/app/main.py backend/app/middleware/desktop_auth.py backend/app/routers/desktop.py backend/tests/test_desktop_server.py
git commit -m "feat(desktop): serve SPA and API from an isolated local backend"
```

### Task 4: 冻结 FastAPI 后端并验证完整依赖

**Files:**
- Create: `desktop/backend.spec`
- Create: `desktop/hooks/`
- Create: `scripts/smoke-desktop-backend.mjs`
- Modify: `backend/app/desktop_runtime.py`

**Interfaces:**
- Consumes: `backend/desktop_entry.py`、Alembic、提示模板、业务静态 JSON
- Produces: `desktop/out/backend/zhiyu-backend.exe`

- [ ] **Step 1: 编写冻结包冒烟脚本**

脚本创建临时数据目录，生成随机桌面令牌，启动 EXE，解析端口事件，验证健康检查、登录、AI 配置状态、SPA fallback、Chroma 降级和关闭接口，最后断言进程不存在。

Run: `node scripts/smoke-desktop-backend.mjs desktop/out/backend/zhiyu-backend.exe`

Expected: FAIL，冻结包尚不存在。

- [ ] **Step 2: 编写 `onedir` spec**

spec 只收集：`backend/app` Python 模块、`backend/app/data`、`backend/app/prompts`、`backend/alembic`、`backend/alembic.ini` 及依赖的动态库。显式排除 `.env*`、`*.db`、上传目录、日志、测试和报告。对 `uvicorn`、SQLAlchemy dialect、Chroma、onnxruntime、tokenizers、passlib、jose 和 Google Auth 使用针对性 hook；不使用无边界的仓库级 glob。

- [ ] **Step 3: 构建并修复真实 hidden import**

Run:

```powershell
python -m PyInstaller --noconfirm --clean desktop/backend.spec
node scripts/smoke-desktop-backend.mjs desktop/out/backend/zhiyu-backend.exe
```

Expected: 冒烟测试全部通过；只根据 PyInstaller warning 和运行失败增加 hidden import。

- [ ] **Step 4: 扫描敏感文件和体积**

Run:

```powershell
Get-ChildItem desktop/out/backend -Recurse -File | Where-Object { $_.Name -match '^\.env|\.db$|\.log$|test|report' }
(Get-ChildItem desktop/out/backend -Recurse -File | Measure-Object Length -Sum).Sum
```

Expected: 第一条无输出；记录总大小，禁止为了减小体积删除实际导入的业务依赖。

- [ ] **Step 5: Commit**

```powershell
git add desktop/backend.spec desktop/hooks scripts/smoke-desktop-backend.mjs backend/app/desktop_runtime.py
git commit -m "build(desktop): freeze and smoke-test FastAPI backend"
```

### Task 5: 实现安全 Electron 外壳和进程生命周期

**Files:**
- Create: `desktop/main.mjs`
- Create: `desktop/preload.cjs`
- Create: `desktop/loading.html`
- Create: `desktop/main.test.mjs`

**Interfaces:**
- Consumes: 后端端口事件、`process.resourcesPath/backend/zhiyu-backend.exe`、`process.resourcesPath/web`、`userData/runtime.json`
- Produces: `window.zhiyuDesktop = { isDesktop: true, platform: string }`

- [ ] **Step 1: 写主进程单元测试**

把端口行解析、首选端口读取/原子保存、允许导航判定、后端环境构造和退出超时抽为纯函数。测试非法 JSON、49152 以下端口、损坏的 runtime JSON、恶意相似域名、带空格/中文路径和令牌不进入日志。

Run: `node --test desktop/main.test.mjs`

Expected: FAIL，主进程模块尚不存在。

- [ ] **Step 2: 启动后端并显示加载窗口**

在 `ready` 前创建 `%APPDATA%/知域引擎` 并用 `app.setPath('userData', ...)` 固定 Electron 与后端共享的数据根，避免 package name 与中文产品名不一致。使用 `spawn()` 直接启动唯一的 PyInstaller EXE，参数包含当前 Electron PID 和持久化首选端口；`windowsHide: true`，stdout 按行解析。首次运行生成 49152-65535 的首选端口，后端若因冲突返回新端口则原子更新 `runtime.json`。60 秒未健康或子进程退出时显示原生错误对话框。

- [ ] **Step 3: 创建安全窗口**

BrowserWindow 必须使用：

```javascript
webPreferences: {
  preload: join(import.meta.dirname, 'preload.cjs'),
  nodeIntegration: false,
  contextIsolation: true,
  sandbox: true,
  webSecurity: true,
}
```

默认 1440x900，最小 1100x700；窗口先加载本地 `loading.html`，后端健康后切换到回环 URL。注册单实例锁，第二次启动恢复并聚焦窗口。

- [ ] **Step 4: 注入桌面令牌并限制导航**

在 `session.webRequest.onBeforeSendHeaders` 中仅对精确 `127.0.0.1:<port>` 添加令牌。拒绝所有权限请求；`will-navigate` 只允许同源；`setWindowOpenHandler` 仅将通过 `URL` 解析且协议为 `https:` 的链接交给默认浏览器。

- [ ] **Step 5: 优雅退出**

`before-quit` 先调用受保护关闭接口并等待子进程；5 秒后仍存活才对记录的单一 PID 调用 `child.kill()`。退出、Alt+F4、任务栏关闭和后端异常退出都走同一状态机，避免重复关闭。

- [ ] **Step 6: Run tests**

```powershell
node --test desktop/main.test.mjs
npm run desktop:unpacked
```

Expected: 纯函数测试通过；unpacked 应用启动、只显示一个窗口，关闭后没有 `zhiyu-backend.exe`。

- [ ] **Step 7: Commit**

```powershell
git add desktop/main.mjs desktop/preload.cjs desktop/loading.html desktop/main.test.mjs
git commit -m "feat(desktop): add secure Electron lifecycle shell"
```

### Task 6: 移除桌面包共享默认管理员凭据

**Files:**
- Create: `src/pages/DesktopBootstrap.tsx`
- Create: `src/pages/DesktopBootstrap.test.tsx`
- Modify: `backend/app/routers/desktop.py`
- Modify: `backend/app/schemas/auth.py`
- Modify: `backend/app/seed_data.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_desktop_server.py`
- Modify: `src/App.tsx`
- Modify: `src/pages/Login.tsx`
- Modify: `src/lib/routePrefetch.ts`

**Interfaces:**
- Consumes: `settings.DESKTOP_MODE`、`UserRoleEnum.ADMIN`、现有密码校验规则
- Produces: `GET /api/v1/desktop/bootstrap-status`、`POST /api/v1/desktop/bootstrap`

- [ ] **Step 1: 写桌面初始化安全测试**

覆盖：全新桌面数据库 status 为 required；bootstrap 创建唯一管理员并返回登录态；第二次 bootstrap 返回 409；弱密码返回 422；Web 模式下端点不存在；已有管理员数据库 status 为 complete；任何请求都必须携带桌面令牌。

Run: `python -m pytest backend/tests/test_desktop_server.py -q`

Expected: FAIL，bootstrap 接口尚不存在。

- [ ] **Step 2: 隔离桌面与 Web 种子策略**

`main.py` 在桌面模式下只迁移数据库，不调用 `init_default_admin()` 和演示数据种子；非桌面模式保持现有顺序。bootstrap 在单个事务中确认管理员不存在、按现有 password policy 创建管理员，然后调用演示学习者和知识数据种子。已有数据库只要存在管理员就不进入 bootstrap。

- [ ] **Step 3: 实现首次管理员页面**

桌面启动先读取 bootstrap status：required 时渲染用户名、密码、确认密码表单；complete 时进入原登录页。表单复用现有 Zod 密码规则和输入组件，不显示或接受 `admin123` 默认值。成功后使用后端返回的登录态进入 `/onboarding/name` 或 Dashboard。

- [ ] **Step 4: 隐藏桌面模式的默认凭据提示**

`Login.tsx` 仅在普通 Web 开发模式显示现有默认账号说明；桌面模式不渲染该文案。不得只隐藏文案而保留全新桌面数据库中的已知默认密码。

- [ ] **Step 5: 验证回归**

```powershell
python -m pytest backend/tests/test_desktop_server.py backend/tests/test_auth.py -q
npm test -- src/pages/DesktopBootstrap.test.tsx src/App.test.tsx
npm run typecheck
```

Expected: 桌面首次设置、重复设置保护和现有 Web 登录注册均通过。

- [ ] **Step 6: Commit**

```powershell
git add src/pages/DesktopBootstrap.tsx src/pages/DesktopBootstrap.test.tsx backend/app/routers/desktop.py backend/app/schemas/auth.py backend/app/seed_data.py backend/app/main.py backend/tests/test_desktop_server.py src/App.tsx src/pages/Login.tsx src/lib/routePrefetch.ts
git commit -m "fix(desktop): require secure first-run administrator setup"
```

### Task 7: 复用现有 AI 设置完成首次启动引导

**Files:**
- Create: `src/components/DesktopAIConfigGate.tsx`
- Create: `src/components/DesktopAIConfigGate.test.tsx`
- Create: `src/types/desktop.d.ts`
- Create: `backend/alembic/versions/d2e3f4a5b6c7_add_ai_onboarding_dismissed.py`
- Modify: `src/components/Layout.tsx`
- Modify: `src/pages/AiConfig.tsx`
- Modify: `src/pages/AiConfig.test.tsx`
- Modify: `backend/app/models/user.py`
- Modify: `backend/app/routers/ai_config.py`
- Modify: `backend/app/services/ai_config_service.py`
- Modify: `backend/app/schemas/ai_config.py`
- Modify: `backend/tests/test_ai_config.py`

**Interfaces:**
- Consumes: `window.zhiyuDesktop?.isDesktop`、`aiConfigApi.getConfig()`、当前用户 ID
- Produces: 首次跳转 `/ai-config?onboarding=1`、`POST /api/v1/ai-config/dismiss-onboarding`、响应字段 `onboardingDismissed: boolean`

- [ ] **Step 1: 写首次引导测试**

测试桌面未配置且未跳过时跳转；Web 模式不跳转；已配置不跳转；用户点击“稍后配置”后写入当前用户记录并返回 Dashboard；切换用户互不影响。

Run: `npm test -- src/components/DesktopAIConfigGate.test.tsx src/pages/AiConfig.test.tsx`

Expected: FAIL，Gate 和 onboarding 模式尚不存在。

- [ ] **Step 2: 持久化按用户引导状态**

给 `users` 表增加 nullable 时间字段 `ai_config_onboarding_dismissed_at`；迁移 revision 为 `d2e3f4a5b6c7`，down revision 为当前 AI 配置迁移 `c1d2e3f4a5b6`，upgrade 添加字段、downgrade 删除字段。现有 AI 配置 GET 返回 `onboardingDismissed`，新增受认证的 dismiss POST，只能修改当前用户。接口不接收 user ID，避免越权。

- [ ] **Step 3: 实现最小 Gate**

Gate 只在认证后的 `Layout` 内执行，不新增接口或配置表。若当前路径已经是 `/ai-config`，不得递归跳转；请求失败只显示现有错误反馈，不阻塞整个应用。

- [ ] **Step 4: 为现有页面增加引导状态**

保留当前提供商和高级配置，仅在 `onboarding=1` 时增加简洁页头和“稍后配置”。稍后配置调用 dismiss POST；保存成功后直接导航 Dashboard。Key 仍只提交给后端，不写 localStorage。

- [ ] **Step 5: UI 质量检查**

验证输入都有 `label/htmlFor`，错误靠近字段，连接测试有 loading/success/error，密码显示按钮有 `aria-label`，键盘焦点可见，文本在 1100x700 和 1440x900 不重叠。沿用现有深空蓝、青色强调和 8px 间距，不引入整页紫色主题。

- [ ] **Step 6: Run tests**

```powershell
npm test -- src/components/DesktopAIConfigGate.test.tsx src/pages/AiConfig.test.tsx
npm run typecheck
npm run build
python -m pytest backend/tests/test_ai_config.py -q
```

Expected: 所有测试、类型检查和生产构建通过。

- [ ] **Step 7: Commit**

```powershell
git add src/components/DesktopAIConfigGate.tsx src/components/DesktopAIConfigGate.test.tsx src/types/desktop.d.ts src/components/Layout.tsx src/pages/AiConfig.tsx src/pages/AiConfig.test.tsx backend/alembic/versions backend/app/models/user.py backend/app/routers/ai_config.py backend/app/services/ai_config_service.py backend/app/schemas/ai_config.py backend/tests/test_ai_config.py
git commit -m "feat(desktop): guide first-time AI provider setup"
```

### Task 8: 品牌图标、NSIS 安装器和本地一键构建

**Files:**
- Create: `desktop/assets/icon.svg`
- Create: `desktop/assets/license.txt`
- Create: `desktop/installer.nsh`
- Create: `desktop/electron-builder.yml`
- Create: `scripts/generate-desktop-icons.mjs`
- Create: `scripts/build-desktop.mjs`
- Modify: `package.json`

**Interfaces:**
- Consumes: `dist/`、`desktop/out/backend/`、`package.json.version`
- Produces: `release/知域引擎-Setup-<version>.exe` 与 SHA-256 文件

- [ ] **Step 1: 创建可缩放品牌源图标**

SVG 使用 256x256 viewBox、深空蓝 `#23324A`、知识页白色 `#F7FAFC`、连接强调 `#47A7A0`。使用大轮廓和三个节点，不使用文字、渐变、阴影或小于 12px 的关键结构。图标含义为“领域知识页 + 多智能体连接”。

- [ ] **Step 2: 实现确定性图标生成**

`generate-desktop-icons.mjs` 用 `sharp` 输出 16/32/48/256px PNG，再由 `png-to-ico` 合并成 `desktop/assets/icon.ico`。每次生成前只删除脚本拥有的 `icon-*.png` 和 `icon.ico`，并校验输出存在且大于 1KB。

- [ ] **Step 3: 配置 electron-builder**

关键配置：

```yaml
appId: io.github.qiuyuebaibot.zhiyuengine
productName: 知域引擎
directories:
  output: release
  buildResources: desktop/assets
files:
  - desktop/main.mjs
  - desktop/preload.cjs
  - desktop/loading.html
  - package.json
extraResources:
  - from: dist
    to: web
  - from: desktop/out/backend
    to: backend
win:
  target:
    - target: nsis
      arch: [x64]
  icon: desktop/assets/icon.ico
nsis:
  oneClick: false
  perMachine: false
  allowToChangeInstallationDirectory: true
  createDesktopShortcut: true
  createStartMenuShortcut: true
  shortcutName: 知域引擎
  artifactName: 知域引擎-Setup-${version}.${ext}
  include: desktop/installer.nsh
  license: desktop/assets/license.txt
```

- [ ] **Step 4: 定制卸载数据选项**

`installer.nsh` 增加欢迎页、开始菜单卸载快捷方式和默认不选的数据删除 section：

```nsh
!macro customWelcomePage
  !insertmacro MUI_PAGE_WELCOME
!macroend

!macro customInstall
  SetShellVarContext current
  CreateDirectory "$SMPROGRAMS\${PRODUCT_NAME}"
  CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\卸载 ${PRODUCT_NAME}.lnk" "$INSTDIR\${UNINSTALL_FILENAME}"
!macroend

!macro customUnInstallSection
  Section /o "un.同时删除用户数据与 AI 配置"
    SetShellVarContext current
    RMDir /r "$APPDATA\知域引擎"
  SectionEnd
!macroend
```

静默卸载不会选中该 section；覆盖升级必须通过安装测试确认不出现删除提示且数据保留。

- [ ] **Step 5: 添加构建编排**

`build-desktop.mjs` 顺序执行：版本/许可/环境预检 -> 清理仅属于 `desktop/out` 和 `release` 的旧产物 -> `npm run build` -> 图标生成 -> PyInstaller -> 后端冒烟 -> electron-builder `--dir` 或 NSIS -> SHA-256。任何步骤非零立即退出。

- [ ] **Step 6: 负责人确认许可文本**

`desktop/assets/license.txt` 必须由项目负责人提供并确认。构建脚本拒绝空文件、示例占位文本或少于 100 个字符的文件；工程实现不得自行声明版权授权范围。

- [ ] **Step 7: 安装验证**

```powershell
npm run build:electron
Start-Process -Wait '.\release\知域引擎-Setup-1.0.0.exe' -ArgumentList '/S'
```

Expected: 安装包、桌面快捷方式、开始菜单和卸载项存在；启动后数据写入 AppData；升级覆盖保留数据；手工卸载可选择保留或删除数据。

- [ ] **Step 8: Commit**

```powershell
git add desktop/assets/icon.svg desktop/assets/license.txt desktop/installer.nsh desktop/electron-builder.yml scripts/generate-desktop-icons.mjs scripts/build-desktop.mjs package.json package-lock.json
git commit -m "build(desktop): create branded NSIS installer"
```

### Task 9: GitHub 标签自动发布和交付文档

**Files:**
- Create: `.github/workflows/windows-release.yml`
- Create: `docs/BUILD_GUIDE.md`
- Create: `docs/RELEASE_GUIDE.md`
- Create: `docs/USER_INSTALL.md`
- Create: `docs/DEV_GUIDE.md`
- Modify: `README.md`
- Modify: `launcher/README.md`

**Interfaces:**
- Consumes: 标签 `v*.*.*`、`package.json.version`、`npm run build:electron`
- Produces: GitHub Release 安装包与 `.sha256`；手工 workflow artifact

- [ ] **Step 1: 创建最小权限工作流**

触发和权限：

```yaml
on:
  push:
    tags: ['v*.*.*']
  workflow_dispatch:
permissions:
  contents: write
jobs:
  windows-release:
    runs-on: windows-latest
```

步骤固定为 checkout -> Node 22 + npm cache -> Python 3.11 + pip cache -> `npm ci` -> Python desktop requirements -> 标签/版本校验 -> 前后端测试 -> `npm run build:electron` -> 安装包冒烟 -> artifact 上传。仅 tag 事件执行 `gh release create`，使用 `GH_TOKEN: ${{ github.token }}` 和 `--generate-notes`。

- [ ] **Step 2: 加版本一致性闸门**

PowerShell 读取 `package.json.version`，要求 `GITHUB_REF_NAME` 精确等于 `v$version`。不一致时在打包前失败，避免 Release 名与安装包版本不同。

- [ ] **Step 3: 添加签名的条件分支**

当 `CSC_LINK` 和 `CSC_KEY_PASSWORD` 均存在时交给 electron-builder 签名；未配置时仍构建，但在 job summary 明确标记“Unsigned / 可能触发 SmartScreen”。任何 secret 都不得打印或作为命令行普通参数回显。

- [ ] **Step 4: 编写四份面向不同用户的文档**

`BUILD_GUIDE` 只写首次本地构建；`RELEASE_GUIDE` 写版本更新、标签和 Actions；`USER_INSTALL` 写安装、首次配置、数据保留卸载；`DEV_GUIDE` 写开发者继续使用 `npm start`，不要求每次开发生成安装包。

推荐发版命令：

```powershell
npm version patch
git push origin main --follow-tags
```

执行前必须确认 `npm version` 生成的标签与准备发布的提交一致，且分支保护允许推送标签。

- [ ] **Step 5: 在 GitHub 上验证一次候选版本**

先用 `workflow_dispatch` 下载 artifact 并在干净 Windows 用户账户安装测试；通过后创建 `v1.0.0` 标签。确认 Release 同时包含 EXE、SHA-256 和自动生成的版本说明。

- [ ] **Step 6: 最终回归矩阵**

验证：全新安装、中文和空格路径、无网络、无 Key、错误 Key、Chroma 强制失败、已有 SQLite 升级、重复启动、Alt+F4、任务栏关闭、静默安装、保留数据卸载、删除数据卸载、开发模式、Docker Compose、GitHub 手工构建、标签正式发布。

- [ ] **Step 7: Commit**

```powershell
git add .github/workflows/windows-release.yml docs/BUILD_GUIDE.md docs/RELEASE_GUIDE.md docs/USER_INSTALL.md docs/DEV_GUIDE.md README.md launcher/README.md
git commit -m "ci(desktop): publish tagged Windows installers"
```

## Final Verification

```powershell
npm run lint
npm run typecheck
npm test
npm run build
python -m pytest backend/tests -q
node --test desktop/main.test.mjs
npm run build:electron
Get-FileHash '.\release\知域引擎-Setup-1.0.0.exe' -Algorithm SHA256
git status --short
```

通过标准：全部自动检查成功；安装、启动、退出、升级和卸载矩阵无阻断问题；`git status` 中没有 EXE、数据库、日志、`.env`、图标中间 PNG 或其他构建产物。
