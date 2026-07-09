# 领域知识个性化生成与多智能体协同决策系统

基于多智能体协同的领域知识个性化学习资源生成平台，融合学情分析、知识图谱、幻觉检测与自适应导学能力。

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 18 + TypeScript + Vite + Tailwind CSS + Zustand + React Router |
| 后端 | FastAPI + SQLAlchemy + Pydantic + JWT 认证 |
| 数据库 | SQLite（开发）/ PostgreSQL（生产） |
| 缓存/队列 | Redis + Celery |
| 向量库 | ChromaDB |
| 大模型 | OpenAI API（兼容接口） |
| 部署 | Docker Compose（开发） / Kubernetes + Helm（生产） / Nginx |

## 项目结构

```
.
├── backend/                 # 后端服务
│   ├── app/
│   │   ├── agents/          # 多智能体（诊断/生成/评判/编排）
│   │   ├── models/          # SQLAlchemy 数据模型
│   │   ├── routers/         # API 路由（auth/knowledge/learner/agent/core）
│   │   ├── schemas/         # Pydantic 请求/响应模型
│   │   ├── services/        # 业务逻辑层
│   │   ├── utils/           # 工具（认证/日志/脱敏/幻觉检测/文本切片）
│   │   ├── celery_tasks/    # 异步任务
│   │   ├── config.py        # 配置管理
│   │   ├── database.py      # 数据库连接
│   │   └── main.py          # FastAPI 入口
│   ├── tests/               # 测试用例
│   ├── requirements.txt     # Python 依赖
│   └── Dockerfile
├── src/                     # 前端源码
│   ├── components/          # 通用组件
│   ├── pages/               # 页面
│   ├── store/               # Zustand 状态管理
│   ├── lib/                 # API 请求层、工具
│   └── types/               # TypeScript 类型定义
├── deploy/
│   └── nginx/nginx.conf     # Nginx 反向代理配置
├── docker-compose.yml       # Docker 编排
├── Dockerfile               # 前端多阶段构建
├── .env.example             # 环境变量模板
└── README.md
```

## 快速开始

### 方式一：Docker 部署（推荐）

#### 前置要求
- Docker 20.10+
- Docker Compose v2+

#### 基础模式（SQLite + Redis，适合演示/开发）

```bash
# 1. 克隆项目后进入目录
cd <project-dir>

# 2. 复制环境变量文件（按需修改）
cp .env.example .env

# 3. 启动所有服务（前端+后端+Redis）
docker-compose up -d --build

# 4. 查看服务状态
docker-compose ps

# 5. 访问应用
# 前端：http://localhost
# 后端API文档：http://localhost/docs  或  http://localhost:8000/docs
# 健康检查：http://localhost/health
```

默认管理员账户：`admin` / `admin123`

#### 完整模式（PostgreSQL + Celery + Chroma 向量库）

```bash
docker-compose --profile full up -d --build
```

完整模式额外启动：
- **PostgreSQL**：生产级关系型数据库（端口 5432）
- **Celery Worker**：异步任务处理（知识切片、向量化、长文档处理）
- **ChromaDB**：向量数据库（端口 8001），用于知识检索增强生成（RAG）

#### 常用 Docker 命令

```bash
# 查看日志
docker-compose logs -f backend
docker-compose logs -f frontend

# 重启服务
docker-compose restart backend

# 停止并删除容器（保留数据卷）
docker-compose down

# 停止并删除容器和数据卷（⚠️ 会清除数据库数据）
docker-compose down -v

# 重新构建某个服务
docker-compose build --no-cache backend
```

### 方式二：一键启动脚本（本地开发推荐）

项目提供跨平台一键启动脚本，自动检测环境、并行启动前后端，无需手动开多个终端。

#### 前置要求
- Node.js 18+（脚本运行依赖）
- Python 3.11+（后端运行依赖）
- 首次使用需先初始化环境（创建虚拟环境、安装依赖、复制配置文件）

#### 步骤 1：环境初始化（仅首次执行）

```bash
# 任选其一
node scripts/start.mjs --setup     # 跨平台
npm run start:setup                 # 等价命令
```

Windows 用户也可双击 `start.bat` 并传入参数：
```cmd
start.bat --setup
```

该命令会自动完成：
1. 从 `.env.example` 复制 `.env`
2. 在 `backend/venv` 创建 Python 虚拟环境
3. 安装后端 `requirements.txt` 依赖
4. 安装前端 `node_modules` 依赖

#### 步骤 2：一键启动前后端

```bash
# 任选其一
node scripts/start.mjs          # 跨平台
npm start                       # 等价命令
```

Windows：双击 `start.bat`
Linux/macOS：`./start.sh`

启动后效果：
- 实时聚合输出，带 `[backend]` / `[frontend]` 前缀着色
- 显示服务地址（后端 API + 前端页面 + API 文档）
- `Ctrl+C` 一键优雅关闭两个服务

#### 启动选项

| 命令 | 说明 |
|------|------|
| `npm start` | 同时启动前后端（默认） |
| `npm run start:backend` | 仅启动后端 |
| `npm run start:frontend` | 仅启动前端 |
| `npm run start:setup` | 自动准备环境（创建 venv、安装依赖、复制 .env） |
| `node scripts/start.mjs --help` | 查看帮助 |

#### 服务地址

| 服务 | 地址 |
|------|------|
| 前端页面 | http://localhost:5173 |
| 后端 API | http://localhost:8000 |
| Swagger 文档 | http://localhost:8000/docs |
| ReDoc 文档 | http://localhost:8000/redoc |
| 健康检查 | http://localhost:8000/health |

#### 脚本文件说明

| 文件 | 作用 |
|------|------|
| [scripts/start.mjs](scripts/start.mjs) | 跨平台核心启动脚本（Node.js ES Module） |
| [start.bat](start.bat) | Windows 双击入口 |
| [start.sh](start.sh) | Linux/macOS 入口 |
| [package.json](package.json) `scripts` 字段 | npm 命令别名 |

#### 常见问题

| 问题 | 解决方法 |
|------|----------|
| `未检测到 Node.js` | 安装 Node.js 18+：https://nodejs.org/ |
| `未检测到 Python` | 安装 Python 3.11+，确保 `python` 或 `python3` 在 PATH |
| 端口 8000/5173 被占用 | 关闭占用进程，或修改 `scripts/start.mjs` 中的 `CONFIG.backend.port` |
| 后端启动失败 | 进入 `backend/`，激活 venv 后运行 `uvicorn app.main:app --reload` 排查错误 |
| 前端启动失败 | 运行 `npm run lint` 与 `npm run typecheck` 排查代码问题 |

### 方式三：手动启动（如需更细控制）

#### 后端（Python 3.11+）

```bash
cd backend

# 创建虚拟环境
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动服务（默认使用 SQLite，自动创建数据目录）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

后端启动后访问：
- API 根地址：http://localhost:8000
- 自动文档：http://localhost:8000/docs（Swagger UI）
- ReDoc：http://localhost:8000/redoc

#### 前端（Node.js 18+）

```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build
```

前端启动后访问：http://localhost:5173

开发模式下 Vite 已配置 `/api` 代理到后端 `http://localhost:8000`，无需额外 CORS 配置。

#### 代码检查

```bash
# 前端
npm run lint        # ESLint 检查
npm run typecheck   # TypeScript 类型检查
npm run format      # Prettier 格式化

# 后端（需安装 ruff）
pip install ruff
ruff check backend/app
ruff format backend/app
```

### 方式四：K8s 部署（生产推荐）

项目提供完整的 Helm Chart，支持多环境（dev/staging/prod）一键部署到 Kubernetes 集群，含监控告警、备份恢复、蓝绿/金丝雀发布等生产级能力。

#### 前置要求

- K8s 集群 1.26+（云厂商托管 ACK/TKE 或自建）
- Helm 3.10+、kubectl 已配置
- 容器镜像仓库（阿里云 ACR / Docker Hub / Harbor）
- 域名 + TLS 证书（生产）

#### 快速部署

```bash
# 1. 部署到开发环境（minikube/kind）
helm install knowledge-system ./deploy/helm \
  -f deploy/helm/values-dev.yaml \
  -n knowledge-dev --create-namespace

# 2. 部署到生产环境
helm install knowledge-system ./deploy/helm \
  -f deploy/helm/values-prod.yaml \
  -n knowledge-prod --create-namespace

# 3. 查看部署状态
kubectl get pods -n knowledge-prod -w
```

#### 核心能力

| 能力 | 说明 |
|------|------|
| 多环境配置 | dev/staging/prod 三套 values，差异化资源配置 |
| 自动扩缩 | HPA 基于 CPU 自动扩缩容（backend 2-10 副本） |
| 数据库迁移 | helm hook 自动执行 Alembic 迁移（pre-install/pre-upgrade） |
| 监控告警 | Prometheus + Grafana + Alertmanager（10 条告警规则 + 3 个 Dashboard） |
| 蓝绿/金丝雀发布 | 零停机发布、渐进切流、秒级回滚 |
| 备份恢复 | PostgreSQL 每日备份 + Velero PVC 快照 + 跨区域复制 |
| 自我修复 | startupProbe + livenessProbe + OOM 调优 + LLM 熔断器 |
| GitOps | ArgoCD 自动同步 + Argo Rollouts 指标驱动回滚 |

#### 运维文档索引

详细的 K8s 部署与运维文档位于 `docs/ops/` 目录：

| 文档 | 说明 |
|------|------|
| [部署运维手册](docs/ops/DEPLOYMENT_GUIDE.md) | 集群前置条件、首次部署、多环境配置、升级扩容、日常运维 |
| [故障处理指南](docs/ops/TROUBLESHOOTING.md) | 12 类常见故障的排查步骤与解决方案 |
| [发布操作手册](docs/ops/RELEASE_SOP.md) | 蓝绿/金丝雀/回滚 SOP、Argo Rollouts 自动化 |
| [备份恢复手册](docs/ops/BACKUP_RECOVERY.md) | 备份策略、恢复操作、监控验证 |
| [监控告警手册](docs/ops/MONITORING_ALERTING.md) | 指标体系、10 条告警规则、3 个 Dashboard |
| [Helm Chart 使用文档](docs/ops/HELM_CHART_GUIDE.md) | 完整参数说明、自定义配置、依赖组件安装 |
| [灾难恢复演练手册](docs/DR_RUNBOOK.md) | RTO/RPO 定义、演练流程、10 项验证清单 |
| [K8s 部署总体规划](docs/K8S_DEPLOYMENT_PLAN.md) | 9 阶段 57 任务总体计划 |

#### 部署架构

```
                        ┌─────────────────────┐
                        │     Ingress (TLS)    │
                        └──────────┬──────────┘
                                   │
                            ┌───────▼───────┐
                            │    frontend   │ (HPA 2-5 副本)
                            └───────┬───────┘
                                    │
                            ┌───────▼───────┐
                            │    backend    │ (HPA 2-10 副本)
                            └───┬───┬───┬───┘
                                │   │   │
                ┌───────────────┘   │   └───────────────┐
                ▼                   ▼                   ▼
          ┌──────────┐        ┌──────────┐        ┌──────────┐
          │ postgres │        │  redis   │        │  chroma  │
          │StatefulSet│       │StatefulSet│       │StatefulSet│
          └──────────┘        └──────────┘        └──────────┘
```

完整部署文档详见 [docs/ops/DEPLOYMENT_GUIDE.md](docs/ops/DEPLOYMENT_GUIDE.md)。

## API 概览

| 模块 | 前缀 | 主要功能 |
|------|------|----------|
| 认证 | `/api/v1/auth` | 登录、注册、Token 刷新、当前用户 |
| 学习者 | `/api/v1/learners` | 学习者画像 CRUD、学情分析 |
| 知识库 | `/api/v1/knowledge` | 文档上传、切片管理、检索 |
| 智能体 | `/api/v1/agents` | 多智能体协同任务、辩论记录 |
| 核心业务 | `/api/v1/core` | 资源生成、报告导出、自适应导学、量化指标 |
| 系统 | `/health` `/` | 健康检查、系统信息 |

## 环境变量配置

所有配置项见 `.env.example`，复制为 `.env` 后修改：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SECRET_KEY` | `change-me-in-production-please` | JWT 签名密钥，**生产必须修改** |
| `DATABASE_URL` | `sqlite:////app/data/app.db` | 数据库连接 URL |
| `REDIS_URL` | `redis://redis:6379/0` | Redis 连接 |
| `OPENAI_API_KEY` | 空 | OpenAI API 密钥 |
| `OPENAI_API_BASE` | `https://api.openai.com/v1` | 兼容 OpenAI 接口的大模型地址 |
| `DEBUG_MODE` | `false` | 调试模式（输出详细错误） |
| `FRONTEND_PORT` | `80` | 前端对外端口 |
| `BACKEND_PORT` | `8000` | 后端对外端口 |

## 健康检查

所有服务均配置了容器健康检查：

| 服务 | 检查方式 | 端点/命令 |
|------|----------|-----------|
| backend | Python urllib | `GET /health`（无额外系统依赖） |
| frontend (Nginx) | wget | `GET /` |
| redis | redis-cli | `PING` |
| postgres | pg_isready | PostgreSQL 内置检查 |

检查策略：每 30 秒一次，超时 5-10 秒，启动宽限 10-15 秒，失败 3 次标记为 unhealthy。

可通过以下命令查看健康状态：

```bash
docker-compose ps
# 或
docker inspect --format='{{.State.Health.Status}}' knowledge-backend
```

## 核心功能模块

1. **多智能体协同决策**：诊断智能体（学情分析）、生成智能体（资源制作）、评判智能体（质量审核/幻觉检测），通过编排智能体协调多轮辩论优化。
2. **学习者画像**：基于答题记录和行为数据构建多维画像（知识掌握度、学习风格、认知水平）。
3. **领域知识库管理**：支持文档上传、智能切片、向量索引、语义检索。
4. **个性化资源生成**：根据学情画像动态生成练习题、讲解材料、学习路径。
5. **幻觉检测与纠偏**：自动检测生成内容中的事实性错误并纠偏。
6. **量化指标监控**：幻觉率、匹配准确率、知识覆盖率、智能体成功率等核心指标。
7. **数据脱敏**：内置姓名、手机号、身份证、地址脱敏，满足隐私合规要求。

## 默认账户

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 管理员 | `admin` | `admin123` |

## 开发注意事项

- 前后端通过 `/api` 前缀通信，Nginx 自动反向代理到后端 8000 端口
- 前端开发服务器（Vite）已配置 proxy，开发时无需额外 CORS 处理
- API 响应统一格式：`{code, message, data, timestamp}`，前端请求层自动转换 snake_case → camelCase
- JWT Token 存储在 localStorage，过期后自动尝试刷新
- Python 代码遵循 PEP8，使用 Ruff 格式化；前端使用 ESLint + Prettier

## License

MIT
