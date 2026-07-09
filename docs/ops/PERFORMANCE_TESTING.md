# 性能压测指南

> 基于 k6 的性能测试体系，覆盖冒烟、负载、压力、突发四种场景。

## 目录

- [快速开始](#快速开始)
- [安装 k6](#安装-k6)
- [测试场景](#测试场景)
- [运行测试](#运行测试)
- [结果解读](#结果解读)
- [添加自定义场景](#添加自定义场景)
- [CI 集成](#ci-集成)
- [基线管理](#基线管理)

---

## 快速开始

```bash
# 前提: 后端服务已启动 (http://localhost:8000)

# Windows
cd tests/performance
.\run.ps1 -Scenario smoke

# Linux/macOS
cd tests/performance
./run.sh smoke
```

运行脚本会自动检测本地 k6，未安装则回退到 Docker 模式。

---

## 安装 k6

### 方式一: 本地安装

| 平台 | 命令 |
|------|------|
| Windows (choco) | `choco install k6` |
| macOS (brew) | `brew install k6` |
| Linux (apt) | `sudo apt install k6` |
| Linux (dnf) | `sudo dnf install k6` |

详见: https://k6.io/docs/get-started/installation/

### 方式二: Docker (推荐，免安装)

```bash
docker pull grafana/k6:latest
```

运行脚本会自动使用 Docker 模式，无需额外配置。

---

## 测试场景

### 文件结构

```
tests/performance/
├── config.js          # 共享配置: 端点定义、权重、阈值
├── helpers.js         # 辅助函数: 登录、认证请求、权重路由
├── smoke.js           # 冒烟测试
├── load.js            # 负载测试
├── stress.js          # 压力测试
├── spike.js           # 突发测试
├── run.ps1            # Windows 运行脚本
├── run.sh             # Linux/macOS 运行脚本
└── BASELINE.md        # 基线报告
```

### 场景说明

| 场景 | 文件 | VUs | 时长 | 用途 | 通过标准 |
|------|------|-----|------|------|----------|
| 冒烟 | smoke.js | 1 | 30s | 验证所有端点可正常响应 | p95 < 1s, 错误率 < 1% |
| 负载 | load.js | 20 | 3min | 模拟日常流量 | p95 < 500ms, 错误率 < 1% |
| 压力 | stress.js | 10→200 | 6min | 寻找系统瓶颈 | p95 < 2s, 错误率 < 10% |
| 突发 | spike.js | 0→100 | 40s | 瞬时高并发冲击 | p95 < 2s, 错误率 < 10% |

### 覆盖端点

测试脚本按权重混合调用以下 9 个核心端点:

| 端点 | 方法 | 权重 | 说明 |
|------|------|------|------|
| `/health` | GET | 10 | 健康检查 |
| `/api/v1/auth/login` | POST | 5 | 用户登录 |
| `/api/v1/learners` | GET | 15 | 学习者列表 |
| `/api/v1/knowledge/docs` | GET | 15 | 知识文档列表 |
| `/api/v1/knowledge/search` | POST | 10 | 知识检索 |
| `/api/v1/agent/tasks` | GET | 15 | Agent任务列表 |
| `/api/v1/report/metrics` | GET | 10 | 系统指标 |
| `/api/v1/trainings` | GET | 10 | 培训任务列表 |
| `/api/v1/tutoring/questions` | GET | 10 | 导学题库 |

---

## 运行测试

### 基本用法

```bash
# Windows
.\run.ps1 -Scenario smoke           # 运行冒烟测试
.\run.ps1 -Scenario load            # 运行负载测试
.\run.ps1 -Scenario stress          # 运行压力测试
.\run.ps1 -Scenario spike           # 运行突发测试
.\run.ps1 -Scenario all             # 依次运行所有场景

# Linux/macOS
./run.sh smoke
./run.sh load
./run.sh stress
./run.sh spike
./run.sh all
```

### 指定后端地址

```bash
# Windows
.\run.ps1 -Scenario load -BaseUrl http://192.168.1.100:8000

# Linux/macOS
./run.sh load http://192.168.1.100:8000
```

### 强制使用 Docker

```bash
# Windows
.\run.ps1 -Scenario stress -UseDocker

# Linux/macOS
./run.sh stress --docker
```

### 直接使用 k6 命令

```bash
# 本地 k6
k6 run tests/performance/load.js

# Docker
cat tests/performance/load.js | docker run --rm -i --network host \
    -e BASE_URL=http://localhost:8000 \
    grafana/k6 run -
```

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `BASE_URL` | `http://localhost:8000` | 后端服务地址 |
| `ADMIN_USER` | `admin` | 登录用户名 |
| `ADMIN_PASS` | `admin123` | 登录密码 |

---

## 结果解读

k6 输出关键指标:

| 指标 | 说明 | 关注点 |
|------|------|--------|
| `http_reqs` | 总请求数 | 应与预期 VU × duration 匹配 |
| `http_req_failed` | 失败率 | 应低于阈值 (1% 或 5%) |
| `http_req_duration` | 请求延迟 | p95/p99 应低于阈值 |
| `iterations` | 迭代次数 | 每个 VU 完成的循环数 |
| `vus` | 虚拟用户数 | 各阶段的并发数 |

### 判定通过/失败

```
✓ http_req_failed........: rate<0.01  ✓ rate=0.005
✓ http_req_duration......: p(95)<500  ✓ p(95)=320ms

// 失败示例:
✗ http_req_failed........: rate<0.01  ✗ rate=0.05
✗ http_req_duration......: p(95)<500  ✗ p(95)=850ms
```

- `✓` 表示通过阈值
- `✗` 表示未通过阈值，k6 退出码为 1

---

## 添加自定义场景

### 1. 新建场景脚本

```javascript
import { sleep } from 'k6'
import { login, hitEndpoint } from './helpers.js'
import { ENDPOINTS, COMMON_THRESHOLDS } from './config.js'

export const options = {
  vus: 50,
  duration: '2m',
  thresholds: COMMON_THRESHOLDS,
  tags: { scenario: 'custom' },
}

export function setup() {
  return { token: login() }
}

export default function (data) {
  // 只测试知识检索端点
  hitEndpoint('search', ENDPOINTS.knowledgeSearch, data.token)
  sleep(1)
}
```

### 2. 添加端点

在 `config.js` 的 `ENDPOINTS` 中添加:

```javascript
myEndpoint: {
  method: 'GET',
  path: '/api/v1/my-endpoint',
  weight: 10,
  authRequired: true,
},
```

---

## CI 集成

CI 中仅运行冒烟测试（30s，快速验证），见 `.github/workflows/ci.yml` 的 `performance-smoke` job:

- **触发条件**: push 到 main/develop 分支，或手动触发
- **流程**: 安装依赖 → 启动后端 → 等待就绪 → k6 冒烟测试 → 上传结果
- **失败条件**: 任何阈值未通过则 job 失败

负载/压力/突发测试不纳入 CI（耗时过长），建议:
- 每周手动运行一次 `load` 测试
- 每月手动运行一次 `stress` + `spike` 测试
- 更新 `BASELINE.md` 中的历史基线数据

---

## 基线管理

### 更新基线

1. 在固定环境（相同硬件、相同数据量）下运行测试
2. 记录结果到 `tests/performance/BASELINE.md` 的历史基线表
3. 后续测试对比基线，检测性能退化

### 性能退化告警

若 CI 冒烟测试的 p95 延迟超过基线 20%，应检查:
- 是否有新的慢查询
- 是否有未加索引的 DB 操作
- 是否有 N+1 查询问题
- 是否有新增的同步阻塞操作

---

## 常见问题

### Q: Docker 模式无法连接 localhost 后端

A: 确保 Docker 使用 `--network host` 模式（运行脚本已自动配置）。在 Docker Desktop for Mac/Windows 上，`host.docker.internal` 可作为替代。

### Q: 测试报 401 未授权

A: 检查后端是否已初始化 admin 账户（首次启动自动创建 admin/admin123）。如已修改密码，通过 `ADMIN_USER` / `ADMIN_PASS` 环境变量传入。

### Q: SQLite 高并发报错

A: SQLite 默认限制并发写入。开发环境可忽略，生产环境使用 PostgreSQL。压力测试建议针对生产配置环境运行。

### Q: k6 在 Windows 上安装失败

A: 使用 Docker 模式: `.\run.ps1 -Scenario smoke -UseDocker`
