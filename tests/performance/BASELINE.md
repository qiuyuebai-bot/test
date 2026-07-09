# 性能压测基线报告

> 本文件记录性能基线数据，每次压测后更新。用于对比检测性能退化。

## 环境基线

| 项目 | 值 |
|------|-----|
| 后端框架 | FastAPI + Uvicorn (单进程) |
| 数据库 | SQLite (开发) / PostgreSQL (生产) |
| 运行环境 | 本地开发机 / Docker / K8s |
| Python 版本 | 3.11 |
| CPU / 内存 | 待填写 |
| 网络 | localhost |

## 通过标准 (SLA)

| 指标 | 冒烟 | 负载 | 压力 | 突发 |
|------|------|------|------|------|
| 错误率 | < 1% | < 1% | < 10% | < 10% |
| p95 延迟 | < 1s | < 500ms | < 2s | < 2s |
| p99 延迟 | < 2s | < 1.5s | < 5s | < 5s |
| 持续时间 | 30s | 3min | 6min | 40s |
| 并发用户 | 1 | 20 | 10→200 | 0→100 |

## 端点预期性能

### 轻量端点 (DB 单表查询 / 健康检查)

| 端点 | 预期 p50 | 预期 p95 | 备注 |
|------|----------|----------|------|
| GET /health | < 5ms | < 20ms | 无 DB 访问 |
| GET /api/v1/info | < 10ms | < 50ms | 配置读取 |
| GET /metrics | < 20ms | < 50ms | Prometheus 采集 |

### 中等端点 (DB 分页查询)

| 端点 | 预期 p50 | 预期 p95 | 备注 |
|------|----------|----------|------|
| GET /api/v1/learners | < 50ms | < 200ms | 分页查询 |
| GET /api/v1/knowledge/docs | < 50ms | < 200ms | 分页查询 |
| GET /api/v1/agent/tasks | < 50ms | < 200ms | 分页查询 |
| GET /api/v1/trainings | < 50ms | < 200ms | 分页查询 |
| GET /api/v1/report/metrics | < 100ms | < 300ms | 聚合查询 |

### 重量端点 (向量检索 / LLM 调用)

| 端点 | 预期 p50 | 预期 p95 | 备注 |
|------|----------|----------|------|
| POST /api/v1/knowledge/search | < 500ms | < 2s | 向量检索 |
| POST /api/v1/auth/login | < 100ms | < 300ms | 密码哈希 |
| POST /api/v1/agent/diagnose | < 5s | < 15s | LLM 调用 |
| POST /api/v1/agent/run/full-pipeline | < 30s | < 60s | 多Agent流水线 |

## 历史基线数据

> 每次正式压测后在此追加记录，格式: `日期 | 场景 | VUs | p50 | p95 | p99 | 错误率 | 备注`

| 日期 | 场景 | VUs | p50 | p95 | p99 | 错误率 | 备注 |
|------|------|-----|-----|-----|-----|--------|------|
| - | - | - | - | - | - | - | 首次基线待填写 |

## 性能退化检测

在 CI 中运行冒烟测试时，若结果超出基线阈值 20% 以上，标记为告警：

```
# 在 CI 日志中查找以下标记
[PERF-DEGRADE] p95=XXXms, baseline=YYYms, degrade=ZZ%
```

## 已知性能瓶颈

1. **SQLite 并发写入**: SQLite 在高并发写入时性能急剧下降，生产环境应使用 PostgreSQL
2. **LLM 调用延迟**: `/agent/diagnose` 和 `/agent/run/full-pipeline` 依赖外部 LLM API，延迟不可控
3. **向量检索**: `/knowledge/search` 在知识库规模大时延迟会增加，需要监控 ChromaDB 索引健康
4. **单进程 Uvicorn**: 开发环境单进程无法充分利用多核，生产环境应使用 Gunicorn + 多 worker
