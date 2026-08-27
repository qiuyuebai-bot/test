# 知域引擎 Windows 桌面发行设计

## 1. 目标与成功标准

将当前 React + FastAPI 项目交付为 Windows 10/11 x64 安装程序。最终用户只需下载、安装并双击桌面图标，不需要 Node.js、Python、Git、Redis、Celery 或浏览器。

完成必须同时满足：

1. 安装包名称为 `知域引擎-Setup-<version>.exe`，支持图形安装和 `/S` 静默安装。
2. 安装后从桌面或开始菜单启动单窗口应用；不出现命令行窗口，不打开外部浏览器。
3. Electron 启动一个随包分发的 FastAPI 后端，后端只监听 `127.0.0.1`；首次生成高位首选端口并持久化，冲突时自动换端口。
4. 退出应用后 5 秒内后端进程消失；第二次启动只聚焦已有窗口。
5. 数据库、密钥、上传文件、知识库和日志只写入 `%APPDATA%/知域引擎/`，升级安装不覆盖用户数据。
6. 已配置网络和 API Key 时，现有业务功能与 Web 开发模式保持一致；无 Key、无 Redis、无 Celery 或 Chroma 初始化失败时，应用仍可启动并进入明确标识的本地降级路径。
7. `npm run build:electron` 在 Windows 构建机上生成安装包；推送与 `package.json` 版本一致的 `v*.*.*` 标签后，GitHub Actions 自动测试、打包并创建 Release。
8. 安装包不包含 `.env`、真实密钥、开发数据库、日志、测试报告或源码目录中的运行数据。

## 2. 仓库现状结论

当前仓库不是初版方案假设的简单前后端模板：

- 前端使用 React 18、Vite 5、TypeScript、Tailwind、`BrowserRouter`，API 默认走同源 `/api/v1`。
- 后端使用 FastAPI、SQLAlchemy、Alembic 和 SQLite；`init_database()` 已按 Alembic 迁移现有数据库。
- `USE_CELERY` 默认是 `false`，任务已能回退为进程内线程；Redis 限流和事件总线已有本地降级。
- Chroma 导入或初始化失败时已有 SQLite 关键词检索回退。
- AI 配置功能已经存在：`/api/v1/ai-config`、`AiConfig.tsx`、按用户保存、Fernet 加密、连接测试和多提供商配置均已实现。
- 当前登录页公开默认凭据 `admin / admin123`，后端也会创建该管理员；这只适合开发演示，不能原样进入对外安装包。
- `launcher/` 是 .NET WinForms 开发启动器，仍依赖 Node、Python、源码和浏览器，不是可分发桌面应用。
- 当前工作区有大量未提交改动；桌面化实施必须在独立提交中保留并兼容这些改动。
- 当前前端基线通过：`npm run typecheck`、`AiConfig.test.tsx` 的 16 个测试、`npm run build`。后端虚拟环境记录了另一台电脑的 Python 路径，当前无法执行 pytest，这本身说明不能把虚拟环境直接发给用户。

## 3. 对初版方案的关键修正

| 初版想法 | 修正决定 | 原因 |
|---|---|---|
| Electron 加载 `file://` 或另起前端服务 | FastAPI 同时提供 `dist/` 与 API，Electron 加载同一个 `http://127.0.0.1:<随机端口>` | 保持现有 `BrowserRouter`、相对 API、Cookie、SSE 和刷新路由正常；生产环境只需一个子进程 |
| 固定 8000，冲突后后端再通知 Electron | Electron 保存每次安装的高位首选端口，后端优先绑定它，冲突时绑定 `127.0.0.1:0` 并通过 stdout 返回实际端口 | 正常重启保持同一 Web origin 和 localStorage；冲突时仍能恢复，也不需要子进程 IPC |
| PyInstaller `onefile` 后端 | PyInstaller `onedir`，再由 NSIS 压入单个安装包 | 原生科学计算/Chroma 依赖多；`onedir` 启动更快、诊断更清晰，减少每次启动解压和安全软件误报 |
| 新增全局 `/system/config` 并把 Key 放 SQLite | 复用现有 `/api/v1/ai-config` 和 `UserAIConfig` | 现有方案按用户隔离并加密，能力已超过初版；重复接口会产生两套优先级和安全漏洞 |
| 环境变量覆盖用户界面配置 | 用户数据库配置优先，环境变量只作服务器/开发回退 | 否则桌面用户在设置页保存后仍可能不生效 |
| 安装包继续使用 `admin / admin123` | 全新桌面数据库先显示本机管理员初始化页，用户自行设置用户名和强密码；已有数据库直接使用原账户 | 避免向所有安装用户分发同一个管理员凭据，同时不改变 Web/Docker 开发数据 |
| 把 PyInstaller 加到 npm 依赖 | PyInstaller 固定在 `backend/requirements-desktop-build.txt` | PyInstaller 是 Python 工具，不是 npm 包 |
| 把整个 `build/` 忽略又要求提交图标 | 源图标放 `desktop/assets/icon.svg`；生成文件放 `desktop/out/` | 源文件可追踪，产物可忽略，职责清楚 |
| 无网络仍保证所有 AI 能力不变 | 保证应用和本地功能可用；AI 生成明确提示需配置或使用已有规则回退 | 没有模型或网络时无法真实执行大模型推理，不能伪造“完全不受影响” |

## 4. 推荐架构

```text
桌面快捷方式
    -> Electron 主进程（单实例、窗口、安装身份）
       -> 启动 resources/backend/zhiyu-backend.exe
          -> 优先绑定持久化的高位端口，冲突时绑定 127.0.0.1:0
          -> Alembic 升级 %APPDATA%/知域引擎/data/app.db
          -> 提供 /api/v1/* 和 resources/web/*
       -> Electron 给本机请求注入一次性 X-Zhiyu-Desktop-Token
       -> BrowserWindow 加载同源 SPA
       -> 退出时请求受保护的桌面关闭接口，超时后终止唯一后端子进程
```

Electron 不加载远程页面，不给渲染进程 Node 权限。`preload.cjs` 只暴露冻结的 `{ isDesktop: true, platform }`，不暴露文件系统、Shell 或任意 IPC。

## 5. 运行时契约

Electron 启动后端时设置以下环境变量：

```text
APP_ENV=production
DESKTOP_MODE=true
APP_DATA_DIR=<userData>/data
DATABASE_URL=sqlite:///<userData>/data/app.db
CHROMA_DB_PATH=<userData>/data/chroma_db
UPLOAD_DIR=<userData>/data/uploads
KNOWLEDGE_DOC_DIR=<userData>/data/knowledge_docs
RESOURCE_OUTPUT_DIR=<userData>/data/resources
LOG_DIR=<userData>/logs
DESKTOP_WEB_DIR=<resources>/web
DESKTOP_AUTH_TOKEN=<每次启动随机 32 字节>
USE_CELERY=false
APP_VERSION=<package.json version>
```

Electron 在 `%APPDATA%/知域引擎/runtime.json` 保存 `preferredPort`。第一次从 49152-65535 生成端口；后端成功返回其他端口时原子更新该文件，下一次优先复用。端口不是安全边界，真正的访问控制仍是一次性桌面令牌。

后端入口输出一行机器可读事件：

```json
{"event":"desktop-listening","port":49152}
```

Electron 只接受端口为 1 到 65535 的该事件，并在 60 秒内携带桌面令牌轮询 `/health/live`。超时、进程提前退出或返回异常时显示“重试 / 打开日志目录 / 退出”的原生错误对话框。

## 6. 数据、迁移与卸载

数据目录固定为：

```text
%APPDATA%\知域引擎\
  data\app.db
  data\.secret_key
  data\chroma_db\
  data\uploads\
  data\knowledge_docs\
  data\resources\
  logs\
  runtime.json
```

PyInstaller 必须包含 `backend/alembic.ini` 和 `backend/alembic/`。首次启动创建数据库；升级启动前检测 Alembic 版本差异，使用 SQLite backup API 写入 `data/backups/pre-upgrade-<version>.db`，再执行 `upgrade head`。迁移失败时不覆盖备份，也不打开主窗口。

卸载默认保留上述目录。NSIS 卸载器提供一个默认不勾选的“同时删除用户数据与 AI 配置”选项；静默卸载和覆盖升级永远保留数据。

## 7. 离线与可选服务策略

| 条件 | 桌面行为 |
|---|---|
| 无 Redis | 使用现有内存限流和进程内事件队列 |
| 无 Celery | 固定 `USE_CELERY=false`，使用现有进程内后台线程 |
| Chroma 不可导入或初始化失败 | 使用现有 SQLite 关键词检索，健康状态标记 `degraded`，不阻止启动 |
| 无 API Key | 登录、画像、知识文档、历史数据、规则功能可用；AI 生成入口显示“配置 AI 服务”动作或使用现有确定性回退 |
| 无网络但已有 Key | 网络调用给出可恢复错误，不保存伪造的 AI 结果；本地数据不受影响 |

桌面包保留 Chroma 运行库，但不把模型下载作为启动前提。发布验收分别覆盖“Chroma 可用”和“强制 Chroma 失败”两条路径。

## 8. AI 首次配置体验

全新桌面数据库不执行默认管理员和演示用户种子。启动页先调用受桌面令牌保护的 bootstrap status；没有管理员时让本机用户创建首个管理员账户，成功后再初始化演示数据。已有数据库检测到管理员后直接进入正常登录。Web/Docker 继续使用现有种子策略。

管理员建立或登录成功后，不新增第二套 AI 配置表，桌面端读取现有 `/api/v1/ai-config`：

- `configured=false` 且 `apiKeyConfigured=false` 时跳转到现有 AI 配置页的首次引导模式。
- 引导模式复用当前提供商、Base URL、Key 显示/隐藏、模型、连接测试和保存逻辑。
- 增加“稍后配置”，在 `users.ai_config_onboarding_dismissed_at` 记录按用户跳过状态；设置导航仍始终可访问。
- Key 不回传明文、不写前端存储、不进入日志；继续使用后端 Fernet 加密。
- 表单保留可见标签、键盘焦点、字段级错误、加载状态和成功/失败反馈。

## 9. 品牌与安装体验

名称候选：

1. **知域引擎（推荐）**：突出领域知识生成，“引擎”表达持续驱动和多智能体协作。
2. **智学协同**：强调智能学习和协同决策，语义直接。
3. **知策中枢**：强调知识汇聚、推理和决策中枢，更偏企业系统。

默认品牌配置：

```text
productName: 知域引擎
appId: io.github.qiuyuebaibot.zhiyuengine
artifactName: 知域引擎-Setup-${version}.${ext}
```

图标采用扁平矢量：深空蓝方形底、开放知识页轮廓、三个协同节点和一条青绿色连接线。避免紫色渐变、细碎线条和文字；16px 下仍能识别中心符号。源文件为 SVG，构建时用 `sharp` 和 `png-to-ico` 生成 16/32/48/256px ICO。

NSIS 使用辅助安装模式：欢迎页、经负责人确认的许可协议、安装目录、桌面快捷方式、开始菜单、进度、完成。仓库目前没有可确认的许可文本，因此发布工作流在 `desktop/assets/license.txt` 未经负责人加入前必须失败，不能由工程代码虚构法律条款。

未配置代码签名证书时安装包可以正常安装，但 Windows SmartScreen 可能显示“未知发布者”。正式对外发布的高级体验需要后续配置受信任的 Windows 代码签名证书；证书和密码只放 GitHub Secrets。

## 10. 构建和自动发布

本地构建工具仅开发者需要：Node.js 22、Python 3.11、npm。安装用户不需要这些环境。

```text
npm ci
python -m pip install -r backend/requirements-desktop-build.txt
npm run build:electron
```

输出：

```text
release/知域引擎-Setup-1.0.0.exe
release/知域引擎-Setup-1.0.0.exe.sha256
```

自动发版不是“每次 push 都发布”，而是两层流程：

1. 普通 push / PR：运行现有 CI，不创建 Release。
2. 合并并确认可发布：更新 `package.json` 版本，创建同版本标签，例如 `v1.0.1`，推送标签。
3. `windows-release.yml` 在 Windows runner 上验证标签与版本一致，运行前后端回归、构建 unpacked 应用、桌面冒烟测试、NSIS 打包、SHA-256 校验，最后用 `GITHUB_TOKEN` 创建 Release 并上传安装包。
4. `workflow_dispatch` 只生成可下载的 Actions artifact，用于手工验证，不创建正式 Release。

## 11. 范围边界

- 保留 `npm start`、`scripts/start.mjs`、Docker 和 Kubernetes 流程，开发者继续按 Web 模式工作。
- 保留 `launcher/` 作为开发辅助工具，但 README 明确它不是最终安装包入口。
- 第一版只发布 Windows x64，不添加自动更新、macOS、Linux、ARM64 或在线安装器。
- 不修改多智能体、学习分析和知识生成算法；只修正桌面运行时所必需的路径、启动、降级和配置入口。
