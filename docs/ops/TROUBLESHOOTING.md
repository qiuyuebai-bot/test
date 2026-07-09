# 故障处理指南

> 版本：v1.0 · 编制日期：2026-07-07
> 适用项目：领域知识个性化生成与多智能体协同决策系统
> 关联文档：[DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)、[MONITORING_ALERTING.md](./MONITORING_ALERTING.md)

本指南覆盖 K8s 部署中常见的 12 类故障场景，每类故障给出**症状 → 排查步骤 → 根因 → 解决方案 → 预防措施**的标准化处理流程。

---

## 目录

1. [Pod CrashLoopBackOff](#1-pod-crashloopbackoff)
2. [Pod OOMKilled](#2-pod-oomkilled)
3. [Pod ImagePullBackOff](#3-pod-imagepullbackoff)
4. [数据库连接失败](#4-数据库连接失败)
5. [Ingress 502/503/504](#5-ingress-502503504)
6. [PVC 磁盘满](#6-pvc-磁盘满)
7. [HPA 不触发扩容](#7-hpa-不触发扩容)
8. [LLM 调用熔断](#8-llm-调用熔断)
9. [Celery 任务积压](#9-celery-任务积压)
10. [备份任务失败](#10-备份任务失败)
11. [Helm 升级卡住](#11-helm-升级卡住)
12. [证书过期 / TLS 失败](#12-证书过期--tls-失败)
13. [附录：通用排查流程](#13-附录通用排查流程)

---

## 1. Pod CrashLoopBackOff

### 症状

```bash
$ kubectl get pods -n knowledge-prod
NAME                                READY   STATUS             RESTARTS   AGE
knowledge-system-backend-xxx-yyy    0/1     CrashLoopBackOff   7          12m
```

### 排查步骤

```bash
# 1. 查看当前日志（最后一次崩溃前的输出）
kubectl logs <pod-name> -n knowledge-prod

# 2. 查看上一次崩溃前的日志
kubectl logs <pod-name> -n knowledge-prod --previous

# 3. 查看 Pod 事件（启动序列、健康检查失败原因）
kubectl describe pod <pod-name> -n knowledge-prod | tail -40

# 4. 检查容器退出码
kubectl get pod <pod-name> -n knowledge-prod -o jsonpath='{.status.containerStatuses[0].lastState}'
```

### 常见根因与解决方案

| 退出码 | 含义 | 根因 | 解决方案 |
|---|---|---|---|
| 1 | 应用错误 | 代码异常、依赖缺失 | 查看 traceback，修复代码后重新构建镜像 |
| 137 | OOMKilled | 内存超限 | 见 [§2 Pod OOMKilled](#2-pod-oomkilled) |
| 139 | SIGSEGV | 段错误（C 扩展） | 检查原生依赖版本兼容性 |
| 143 | SIGTERM | 收到终止信号 | 正常关闭，无需处理 |

**典型场景 1：应用启动失败（数据库未就绪）**

```bash
# 日志特征
$ kubectl logs <pod-name> -n knowledge-prod --previous
...
sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) could not connect to server: Connection refused
```

解决方案：startupProbe 已配置 5 分钟等待窗口（failureThreshold=30, periodSeconds=10s）。如仍失败，检查 postgres Service 是否就绪：

```bash
kubectl get pods -l app.kubernetes.io/component=postgres -n knowledge-prod
kubectl get svc -l app.kubernetes.io/component=postgres -n knowledge-prod
```

**典型场景 2：环境变量缺失**

```bash
# 日志特征
$ kubectl logs <pod-name> -n knowledge-prod
...
pydantic_core.ValidationError: SECRET_KEY: field required
```

解决方案：检查 ConfigMap 和 Secret 是否正确注入：

```bash
kubectl get configmap -n knowledge-prod
kubectl get secret -n knowledge-prod
# 查看 Pod 实际加载的环境变量
kubectl exec <pod-name> -n knowledge-prod -- env | grep SECRET_KEY
```

### 预防措施

- 启动慢的服务（backend）：startupProbe 配置足够等待时间（默认 5 分钟）
- 依赖顺序：使用 helm hook（pre-install 迁移 Job）确保数据库就绪
- 配置完整性：部署前运行 `python deploy/helm/validate_chart.py` 校验

---

## 2. Pod OOMKilled

### 症状

```bash
$ kubectl describe pod <pod-name> -n knowledge-prod | grep -A 2 "Last State"
    Last State:     Terminated
      Reason:       OOMKilled
      Exit Code:    137
```

监控告警：`KnowledgeSystemContainerMemoryHigh` 触发（容器内存使用率 > 85% 持续 5 分钟）。

### 排查步骤

```bash
# 1. 查看历史 OOM 事件
kubectl get events -n knowledge-prod --field-selector reason=OOMKilling

# 2. 查看当前内存使用
kubectl top pod <pod-name> -n knowledge-prod --containers

# 3. 查看容器内存 limit
kubectl get pod <pod-name> -n knowledge-prod -o jsonpath='{.spec.containers[0].resources}'

# 4. 检查是否还有重启
kubectl get pod <pod-name> -n knowledge-prod -o jsonpath='{.status.containerStatuses[0].restartCount}'
```

### 根因分析

| 根因 | 现象 | 解决方案 |
|---|---|---|
| limits.memory 太小 | backend 256Mi 不够 | 调高到 1Gi（生产 2Gi） |
| 内存泄漏 | 内存持续增长不回落 | 排查代码：未关闭的连接、缓存无上限 |
| 大批量 LLM 调用 | 响应缓存堆积 | 调小缓存大小或限制并发 |
| ChromaDB 索引膨胀 | 向量库内存占用高 | 扩容 chroma 内存限制 |

### 解决方案

**临时扩容（立即生效）：**

```bash
# 调整 backend 内存限制（不通过 helm upgrade）
kubectl set resources deployment/knowledge-system-backend \
  --limits=memory=2Gi,cpu=2000m \
  -n knowledge-prod
```

**永久调整：**

```yaml
# values-prod.yaml
backend:
  resources:
    limits:
      memory: 2Gi  # 从 1Gi 调整为 2Gi
      cpu: 2000m
```

```bash
helm upgrade knowledge-system ./deploy/helm -f deploy/helm/values-prod.yaml -n knowledge-prod
```

### 预防措施

- 已配置 `KnowledgeSystemContainerMemoryHigh` 告警（> 85% 持续 5 分钟），见 [prometheusrules.yaml](../../deploy/helm/templates/monitoring/prometheusrules.yaml)
- backend 生产环境默认 1Gi（staging）/ 2Gi（prod），见 [values.yaml](../../deploy/helm/values.yaml) L119
- 配合 HPA：高内存时优先扩容副本而非单 Pod 加内存

---

## 3. Pod ImagePullBackOff

### 症状

```bash
$ kubectl get pods -n knowledge-prod
NAME                                READY   STATUS              RESTARTS   AGE
knowledge-system-backend-xxx-yyy    0/1     ImagePullBackOff    0          3m
```

### 排查步骤

```bash
# 1. 查看事件，确认失败原因
kubectl describe pod <pod-name> -n knowledge-prod | tail -20

# 常见错误信息：
# Failed to pull image "registry.xxx/backend:1.0.0": rpc error: code = Unknown
#   → 镜像不存在 / tag 错误 / 仓库不可达
# Failed to pull image: ... unauthorized: authentication required
#   → 缺少镜像拉取凭证
```

### 根因与解决方案

| 根因 | 解决方案 |
|---|---|
| 镜像 tag 不存在 | 检查 `images.backend.tag` 是否与仓库一致 |
| 仓库地址错误 | 检查 `global.imageRegistry` 配置 |
| 凭证缺失 | 创建 `registry-credentials` Secret 并配置 `global.imagePullSecrets` |
| 仓库网络不通 | 检查集群到仓库的网络连通性；考虑配置镜像加速器 |
| 镜像过大拉取超时 | 优化 Dockerfile（多阶段构建），目标 < 200MB |

```bash
# 创建镜像拉取凭证
kubectl create secret docker-registry registry-credentials \
  --docker-server=registry.cn-hangzhou.aliyuncs.com \
  --docker-username=<username> \
  --docker-password=<password> \
  --docker-email=<email> \
  -n knowledge-prod

# 验证凭证已注入 Pod
kubectl get pod <pod-name> -n knowledge-prod -o jsonpath='{.spec.imagePullSecrets}'
```

### 预防措施

- CI 流水线已自动更新 values 中的 image tag（见 `.github/workflows/docker-images.yml`）
- 镜像漏洞扫描（Trivy）已集成到 CI
- 镜像缓存与层复用优化（BuildKit cache mount）

---

## 4. 数据库连接失败

### 症状

- backend Pod 日志报错：`sqlalchemy.exc.OperationalError: could not connect to server`
- API 返回 500：`{"detail":"Database connection failed"}`
- 监控告警：`KnowledgeSystemDBConnectionsHigh` 触发（连接数 > 25）

### 排查步骤

```bash
# 1. 检查 postgres Pod 状态
kubectl get pods -l app.kubernetes.io/component=postgres -n knowledge-prod -w

# 2. 检查 postgres Service
kubectl get svc -l app.kubernetes.io/component=postgres -n knowledge-prod
kubectl get endpoints -l app.kubernetes.io/component=postgres -n knowledge-prod

# 3. 从 backend Pod 测试连通性
kubectl exec deployment/knowledge-system-backend -n knowledge-prod -- \
  python -c "import socket; s=socket.socket(); s.settimeout(3); s.connect(('knowledge-system-postgres',5432)); print('OK')"

# 4. 查看 postgres 当前连接数
kubectl exec statefulset/knowledge-system-postgres -n knowledge-prod -- \
  psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"

# 5. 检查连接池配置
kubectl exec deployment/knowledge-system-backend -n knowledge-prod -- \
  env | grep -E "DATABASE_POOL_SIZE|DATABASE_MAX_OVERFLOW"
```

### 根因与解决方案

**场景 1：postgres Pod 未就绪**

```bash
# 查看 postgres 启动日志
kubectl logs statefulset/knowledge-system-postgres -n knowledge-prod
# 常见问题：PVC 未绑定、内存不足、配置文件错误

# 解决：等 Pod 就绪后 backend 会自动重连（pool_pre_ping 已启用）
```

**场景 2：连接池耗尽（连接数超限）**

```bash
# 查看活跃连接
kubectl exec statefulset/knowledge-system-postgres -n knowledge-prod -- \
  psql -U postgres -c "SELECT client_addr, state, count(*) FROM pg_stat_activity GROUP BY 1,2;"

# 解决：调整 backend 副本数或连接池配置
# values-prod.yaml: DATABASE_POOL_SIZE=20, DATABASE_MAX_OVERFLOW=40
```

**场景 3：云 RDS 网络不通（生产）**

```bash
# 检查 VPC 网络配置、安全组、白名单
# 从 Pod 测试 RDS 连通性
kubectl exec deployment/knowledge-system-backend -n knowledge-prod -- \
  python -c "import psycopg2; psycopg2.connect('postgresql://user:pwd@rm-xxx.rds.aliyuncs.com:5432/db').close(); print('OK')"
```

### 预防措施

- 已启用 `pool_pre_ping=True` + `pool_recycle=3600`（见 [database.py](../../backend/app/database.py) L38-L46），自动剔除失效连接
- 已配置 `KnowledgeSystemDBConnectionsHigh` 告警（连接数 > 25 持续 5 分钟）
- 生产建议使用云 RDS，自带高可用与连接池

---

## 5. Ingress 502/503/504

### 症状

- 用户访问返回 502（Bad Gateway）：backend 未就绪或 Pod 不可达
- 用户访问返回 503（Service Unavailable）：无可用 Pod（被 PDB 阻止或全部未就绪）
- 用户访问返回 504（Gateway Timeout）：backend 响应超时

### 排查步骤

```bash
# 1. 检查 Ingress 配置
kubectl get ingress -n knowledge-prod
kubectl describe ingress knowledge-system-ingress -n knowledge-prod

# 2. 检查 backend Service 与 Endpoints
kubectl get svc knowledge-system-backend -n knowledge-prod
kubectl get endpoints knowledge-system-backend -n knowledge-prod
# Endpoints 列表为空 → 无 Pod 可用

# 3. 检查 backend Pod 是否就绪
kubectl get pods -l app.kubernetes.io/component=backend -n knowledge-prod

# 4. 检查 Ingress Controller 日志
kubectl logs -n ingress-nginx -l app.kubernetes.io/component=controller --tail=50

# 5. 测试 backend 直连
kubectl port-forward svc/knowledge-system-backend 8000:8000 -n knowledge-prod
curl http://localhost:8000/health/ready
```

### 根因与解决方案

| 错误 | 根因 | 解决方案 |
|---|---|---|
| 502 | backend Pod 未就绪或 readinessProbe 失败 | 修复 backend 启动问题 |
| 502 | backend Service 与 Pod label 不匹配 | 检查 selectorLabels |
| 503 | 所有 Pod 被 PDB 阻止驱逐 | 检查 PDB 配置，临时调小 minAvailable |
| 504 | backend 响应慢（LLM 调用阻塞） | 调整 `proxy-read-timeout` 注解 |
| 502 | 蓝绿发布期间新旧 slot 切换 | 检查 `deployment.slot` label 一致性 |

**504 超时调优：**

```yaml
# values-prod.yaml 的 ingress.annotations
nginx.ingress.kubernetes.io/proxy-read-timeout: "600"   # 10 分钟
nginx.ingress.kubernetes.io/proxy-send-timeout: "600"
nginx.ingress.kubernetes.io/proxy-body-size: "100m"     # 大文件上传
```

### 预防措施

- backend 配置 readinessProbe（`/health/ready`），未就绪 Pod 自动从 Endpoints 剔除
- backend 配置 startupProbe（最多等 5 分钟），慢启动不被误判
- Ingress annotations 已针对 LLM 长响应调优（`proxy-read-timeout=600`）

---

## 6. PVC 磁盘满

### 症状

- 监控告警：`KnowledgeSystemPVCDiskRunningFull` 触发（磁盘使用率 > 85%）
- postgres 写入失败：`psycopg2.OperationalError: no space left on device`
- backend 上传文件失败：`OSError: [Errno 28] No space left on device`

### 排查步骤

```bash
# 1. 查看 PVC 状态
kubectl get pvc -n knowledge-prod

# 2. 查看 PVC 实际使用率（需进入 Pod 内执行 df）
kubectl exec statefulset/knowledge-system-postgres -n knowledge-prod -- \
  df -h /var/lib/postgresql/data

# 3. 找出大文件
kubectl exec statefulset/knowledge-system-postgres -n knowledge-prod -- \
  du -sh /var/lib/postgresql/data/* | sort -h

# 4. 检查 backup PVC
kubectl exec job/backup-xxx -n knowledge-prod -- df -h /backup/data
```

### 解决方案

**方案 1：在线扩容 PVC（前提：StorageClass 支持）**

```bash
# 检查 StorageClass 是否支持扩容
kubectl get storageclass -o jsonpath='{.items[*].allowVolumeExpansion}'

# 扩容 postgres PVC
kubectl patch pvc data-knowledge-system-postgres-0 -n knowledge-prod \
  -p '{"spec":{"resources":{"requests":{"storage":"100Gi"}}}}'

# 监控扩容状态
kubectl get pvc -n knowledge-prod -w
```

**方案 2：清理旧数据（postgres）**

```bash
# 进入 psql
kubectl exec -it statefulset/knowledge-system-postgres -n knowledge-prod -- psql -U postgres

# 查看各表大小
SELECT relname, pg_size_pretty(pg_total_relation_size(relid))
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC LIMIT 10;

# 清理旧日志表（按业务确认）
TRUNCATE TABLE api_logs WHERE created_at < NOW() - INTERVAL '30 days';
VACUUM FULL;
```

**方案 3：清理旧备份（backup PVC）**

```bash
# 进入 backup Pod（或 CronJob Pod）
kubectl exec job/backup-xxx -n knowledge-prod -- sh -c "ls -lh /backup/data"

# 手动清理 N 天前的备份
kubectl exec job/backup-xxx -n knowledge-prod -- \
  find /backup/data -name "db_backup_*.dump" -mtime +7 -delete
```

### 预防措施

- backup CronJob 已配置 `find -mtime +N -delete` 自动清理（见 [cronjob.yaml](../../deploy/helm/templates/backup/cronjob.yaml) L66）
- 已配置 `KnowledgeSystemPVCDiskRunningFull` 告警（> 85% 持续 10 分钟）
- 生产建议 postgres 使用云 RDS（自动扩容）
- 定期检查 PVC 使用率，主动扩容而非被动响应

---

## 7. HPA 不触发扩容

### 症状

- backend CPU 明显高（> 80%），但副本数未增加
- API 响应慢，但 HPA 状态显示 `<unknown>`

### 排查步骤

```bash
# 1. 查看 HPA 状态
kubectl get hpa -n knowledge-prod
kubectl describe hpa knowledge-system-backend -n knowledge-prod

# 2. 检查 metrics-server 是否运行
kubectl get apiservice | grep metrics
kubectl top pods -n knowledge-prod  # 能正常输出说明 metrics-server 正常

# 3. 检查 HPA 配置
kubectl get hpa knowledge-system-backend -n knowledge-prod -o yaml
```

### 根因与解决方案

| 根因 | 现象 | 解决方案 |
|---|---|---|
| metrics-server 未安装 | `kubectl top` 无输出 | 安装 metrics-server |
| HPA 当前 CPU 为 `<unknown>` | Pod 未配置 resources.requests | backend 必须配置 `resources.requests.cpu` |
| 已达 maxReplicas | `ScalingActive` 但副本数 = max | 调高 maxReplicas |
| stabilizationWindow 限制 | 短时高峰不立即扩容 | 调小 `scaleDown.stabilizationWindowSeconds` |
| Pod 启动慢，HPA 误判 | 新副本未就绪前 CPU 偏高 | 配置 startupProbe |

**检查 HPA 事件：**

```bash
kubectl describe hpa knowledge-system-backend -n knowledge-prod | grep -A 20 "Events:"
# 可看到扩缩容决策历史
```

### 预防措施

- staging/prod 环境 HPA 默认开启（见 values-staging/prod.yaml）
- backend 配置了合理的 resources.requests（HPA 计算基准）
- 生产建议同时监控 CPU 和内存，避免单维度误判

---

## 8. LLM 调用熔断

### 症状

- API 返回 mock 兜底响应（非真实 LLM 输出）
- backend 日志：`[CircuitBreaker:llm] 连续失败 5 次，状态切换为 OPEN`
- 监控告警：`KnowledgeSystemLLMHighErrorRate` 触发（错误率 > 30%）

### 排查步骤

```bash
# 1. 查看熔断器状态
kubectl exec deployment/knowledge-system-backend -n knowledge-prod -- \
  python -c "from app.utils.llm import LLMUtil; import json; print(json.dumps(LLMUtil.get_usage_stats(), indent=2, default=str))"
# 关注 circuit_breaker.state 字段：CLOSED / OPEN / HALF_OPEN

# 2. 查看 LLM 调用日志
kubectl logs deployment/knowledge-system-backend -n knowledge-prod | grep -E "CircuitBreaker|LLM"

# 3. 测试 LLM API 可达性
kubectl exec deployment/knowledge-system-backend -n knowledge-prod -- \
  python -c "import os; from app.config import settings; print(settings.OPENAI_API_BASE)"
```

### 根因与解决方案

| 根因 | 现象 | 解决方案 |
|---|---|---|
| OpenAI API Key 失效 | 401 Unauthorized | 更新 `OPENAI_API_KEY` Secret |
| API 限流 | 429 Too Many Requests | 降低并发，使用队列 |
| 网络不通 | timeout | 检查出口网络、代理配置 |
| 余额耗尽 | 402 Payment Required | 充值或更换账号 |
| 模型下线 | 404 Model Not Found | 更新 `OPENAI_MODEL_NAME` |

**重置熔断器：**

```bash
# 方式 1：等待冷却时间（默认 60s）后自动转 HALF_OPEN
# 方式 2：重启 backend Pod 重置熔断器状态
kubectl rollout restart deployment/knowledge-system-backend -n knowledge-prod
```

### 预防措施

- 熔断器配置见 [circuit_breaker.py](../../backend/app/utils/circuit_breaker.py)（默认失败 5 次熔断，60s 冷却）
- 熔断时返回 mock 兜底，不影响调用方代码
- 已配置 `KnowledgeSystemLLMHighErrorRate` / `KnowledgeSystemLLMHighLatency` 告警
- 生产建议配置 LLM 多供应商 fallback（未来增强）

---

## 9. Celery 任务积压

### 症状

- 异步任务（知识切片、向量化）长时间未完成
- Redis 队列长度持续增长
- 监控告警：worker 长时间无心跳

### 排查步骤

```bash
# 1. 查看 celery-worker Pod 状态
kubectl get pods -l app.kubernetes.io/component=celery-worker -n knowledge-prod

# 2. 查看 worker 日志
kubectl logs -l app.kubernetes.io/component=celery-worker -n knowledge-prod --tail=50

# 3. 查看 Redis 队列长度
kubectl exec statefulset/knowledge-system-redis -n knowledge-prod -- \
  redis-cli LLEN celery

# 4. 查看 worker 并发配置
kubectl exec deployment/knowledge-system-celery-worker -n knowledge-prod -- \
  ps aux | grep celery
```

### 解决方案

**临时扩容 worker：**

```bash
# 扩容到 4 副本
kubectl scale deployment/knowledge-system-celery-worker \
  --replicas=4 -n knowledge-prod
```

**调整 worker 并发：**

```yaml
# values-prod.yaml
celeryWorker:
  replicaCount: 3
  command: ["celery", "-A", "app.celery_app", "worker", "--loglevel=info", "--concurrency=4"]
  # 默认 concurrency=2，生产可调到 4-8（取决于 CPU 与内存）
```

**清理失败任务：**

```bash
# 进入 worker Pod 执行 celery 命令
kubectl exec -it deployment/knowledge-system-celery-worker -n knowledge-prod -- \
  celery -A app.celery_app purge

# 查看任务状态
kubectl exec -it deployment/knowledge-system-celery-worker -n knowledge-prod -- \
  celery -A app.celery_app inspect active
```

### 预防措施

- celery_app.py 已配置 `autoretry_for=(Exception,)` + `max_retries=3` + `retry_backoff=True`
- worker 配置了 `task_acks_late=True`（任务执行完才 ACK，崩溃不丢任务）
- 已配置 `worker_prefetch_multiplier=1`（避免单 worker 抢占过多任务）

---

## 10. 备份任务失败

### 症状

```bash
$ kubectl get jobs -n knowledge-prod
NAME                         COMPLETIONS   DURATION   AGE
knowledge-system-backup-xxx  0/1           30m        30m   # 未完成
```

### 排查步骤

```bash
# 1. 查看 CronJob 状态
kubectl get cronjob -n knowledge-prod

# 2. 查看失败 Job 日志
kubectl logs job/knowledge-system-backup-xxx -n knowledge-prod

# 3. 查看 PVC 空间
kubectl exec job/knowledge-system-backup-xxx -n knowledge-prod -- df -h /backup/data

# 4. 测试数据库连通性（备份 Pod 内）
kubectl exec job/knowledge-system-backup-xxx -n knowledge-prod -- \
  sh -c 'echo "SELECT 1" | psql "$DATABASE_URL"'
```

### 根因与解决方案

| 根因 | 现象 | 解决方案 |
|---|---|---|
| 数据库不可达 | `pg_dump: connection refused` | 检查 DATABASE_URL 与 postgres 状态 |
| 备份文件过小 | `备份文件过小 (xxx bytes)` | 数据库为空 / pg_dump 失败，重试 |
| PVC 空间不足 | `No space left on device` | 扩容 backup PVC 或清理旧备份 |
| pg_dump 版本不匹配 | `pg_dump: server version mismatch` | 备份 Pod 使用 postgres:16-alpine 镜像 |

**手动触发备份验证：**

```bash
# 创建一次性备份 Job
kubectl create job manual-backup-$(date +%Y%m%d-%H%M) \
  --from=cronjob/knowledge-system-backup -n knowledge-prod

# 监控执行
kubectl get jobs -n knowledge-prod -w
kubectl logs job/manual-backup-xxx -n knowledge-prod -f
```

### 预防措施

- backup CronJob 已配置 `backoffLimit=2`（失败重试 2 次）
- 备份文件大小验证（< 1KB 视为失败，自动删除并退出非零）
- `failedJobsHistoryLimit=5`（保留 5 次失败历史便于排查）
- 详见 [BACKUP_RECOVERY.md](./BACKUP_RECOVERY.md) §3 备份验证

---

## 11. Helm 升级卡住

### 症状

```bash
$ helm upgrade knowledge-system ./deploy/helm -f values-prod.yaml -n knowledge-prod
# 长时间无响应，或卡在 "PENDING_UPGRADE"
```

### 排查步骤

```bash
# 1. 查看 release 状态
helm history knowledge-system -n knowledge-prod
# 状态可能是 pending-upgrade / pending-install / pending-rollback

# 2. 检查 helm hook 是否卡住
kubectl get jobs -n knowledge-prod
kubectl logs job/db-migrate -n knowledge-prod -f

# 3. 检查资源是否已就绪
kubectl get pods,svc,deployment -n knowledge-prod

# 4. 查看 helm 进程（如果还在运行）
ps aux | grep helm
```

### 解决方案

**方案 1：等待 hook 完成（推荐）**

```bash
# db-migrate Job 可能正在执行（首次迁移或大变更）
kubectl logs job/db-migrate -n knowledge-prod -f
# 等 Job 完成后 helm 会自动继续
```

**方案 2：手动清理卡住的 hook Job**

```bash
# 仅当确认 Job 已失败（非正在执行）
kubectl delete job db-migrate -n knowledge-prod
# helm 会重新触发 hook
```

**方案 3：回滚到上一个稳定版本**

```bash
# 查看历史
helm history knowledge-system -n knowledge-prod

# 回滚到上一个 revision
helm rollback knowledge-system <revision> -n knowledge-prod

# 回滚也会触发 post-rollback hook 执行 alembic downgrade
```

**方案 4：强制清理卡住的 release（最后手段）**

```bash
# ⚠️ 谨慎：会丢失未完成的升级状态
# 仅当确认无法恢复时使用
kubectl get secret -n knowledge-prod -l owner=helm,name=knowledge-system
# 删除对应 revision 的 Secret（status=pending-upgrade）
kubectl delete secret sh.helm.release.v1.knowledge-system.v<N> -n knowledge-prod
```

### 预防措施

- helm hook Job 已配置 `ttlSecondsAfterFinished=3600`（1 小时后自动清理）
- 迁移 Job 配置 `backoffLimit=3`（失败重试 3 次后标记失败）
- 升级前先在 staging 验证，避免 prod 出现意外
- 升级前运行 `helm diff upgrade` 查看变更
- 重要升级前先备份（pg_dump）

---

## 12. 证书过期 / TLS 失败

### 症状

- 浏览器访问显示 `NET::ERR_CERT_DATE_INVALID` 或 `NET::ERR_CERT_AUTHORITY_INVALID`
- 监控告警：证书即将过期（如已配置）
- 用户反馈 HTTPS 访问异常

### 排查步骤

```bash
# 1. 查看证书资源
kubectl get certificates -A
kubectl describe certificate knowledge-system-prod-tls -n knowledge-prod

# 2. 查看 CertificateRequest
kubectl get certificaterequests -A

# 3. 查看 cert-manager Pod 日志
kubectl logs -n cert-manager -l app.kubernetes.io/component=controller --tail=50

# 4. 手动检查证书有效期
kubectl get secret knowledge-system-prod-tls -n knowledge-prod -o jsonpath='{.data.tls\.crt}' | base64 -d | openssl x509 -noout -dates

# 5. 查看 ClusterIssuer
kubectl get clusterissuer letsencrypt-prod -o yaml
```

### 根因与解决方案

| 根因 | 现象 | 解决方案 |
|---|---|---|
| 证书过期 | `notAfter` 已过 | cert-manager 应自动续期；若未续期，检查 `certificate.spec.renewBefore` |
| Let's Encrypt 限流 | `too many certificates` | 检查是否多次重复申请；使用 staging issuer 测试 |
| DNS 未生效 | `challenge failed` | 检查域名 A 记录是否指向正确 Ingress LB |
| HTTP-01 challenge 失败 | Ingress 不可达 | 检查 Ingress 配置，确保 80 端口可访问 |
| cert-manager 未安装 | `kubectl get certificates` 无资源 | 安装 cert-manager |

**手动触发证书重新签发：**

```bash
# 删除证书 Secret，让 cert-manager 重新申请
kubectl delete secret knowledge-system-prod-tls -n knowledge-prod

# 等待 cert-manager 重新签发
kubectl get certificate knowledge-system-prod-tls -n knowledge-prod -w
# 期望 Ready=True
```

### 预防措施

- cert-manager 自动续期（Let's Encrypt 证书 90 天有效，默认提前 30 天续期）
- 生产建议配置 `KnowledgeSystemCertExpiringSoon` 告警（自定义 PrometheusRule）
- 多个证书建议统一管理（cert-manager + ClusterIssuer）
- 测试环境用 Let's Encrypt staging issuer（避免限流）

---

## 13. 附录：通用排查流程

### 13.1 SOS 五步排查法

```
1. Scope    定位范围 — 哪个 namespace / Pod / 服务异常
2. Observe  观察现象 — Pod 状态、日志、事件、监控
3. Search   查找根因 — 应用层 / 配置层 / 基础设施层
4. Solve    解决问题 — 修复 / 回滚 / 扩容 / 降级
5. Save     总结预防 — 更新文档、加监控、加告警、加预防措施
```

### 13.2 通用诊断命令组合

```bash
# 一键诊断某 Pod（替换 POD_NAME 与 NAMESPACE）
POD=<pod-name>
NS=<namespace>

echo "===== Pod 状态 ====="
kubectl get pod $POD -n $NS -o wide
echo ""
echo "===== Pod 描述（事件 + 状态）====="
kubectl describe pod $POD -n $NS | tail -60
echo ""
echo "===== 当前日志 ====="
kubectl logs $POD -n $NS --tail=50
echo ""
echo "===== 上次崩溃前日志 ====="
kubectl logs $POD -n $NS --previous --tail=30
echo ""
echo "===== 命名空间事件 ====="
kubectl get events -n $NS --sort-by='.lastTimestamp' | tail -20
echo ""
echo "===== 资源使用 ====="
kubectl top pod $POD -n $NS --containers 2>/dev/null
```

### 13.3 升级回滚决策树

```
故障发生
  │
  ├─ 影响范围小（单 Pod 异常）？
  │    └─ 是 → 重启 Pod: kubectl rollout restart
  │
  ├─ 影响范围中（服务不可用）？
  │    └─ 是 → HPA 自动扩容 / 手动扩容 / 蓝绿切换到旧 slot
  │
  └─ 影响范围大（生产故障）？
       ├─ 数据问题 → 回滚数据库: helm rollback + alembic downgrade
       └─ 代码问题 → 回滚 release: helm rollback knowledge-system <rev>
```

### 13.4 紧急联系人

| 角色 | 职责 | 联系方式 |
|---|---|---|
| On-Call 工程师 | 第一响应 | 见 [On-Call 排班表] |
| DevOps 负责人 | 基础设施决策 | 见团队 wiki |
| 后端负责人 | 应用层问题 | 见团队 wiki |
| 数据库管理员 | 数据层问题 | 见团队 wiki |

---

## 相关文档

| 文档 | 说明 |
|---|---|
| [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) | 部署运维手册 |
| [RELEASE_SOP.md](./RELEASE_SOP.md) | 发布操作手册（回滚流程） |
| [BACKUP_RECOVERY.md](./BACKUP_RECOVERY.md) | 备份恢复手册 |
| [MONITORING_ALERTING.md](./MONITORING_ALERTING.md) | 监控告警手册 |
| [DR_RUNBOOK.md](../DR_RUNBOOK.md) | 灾难恢复演练手册 |
| [K8S_DEPLOYMENT_PLAN.md](../K8S_DEPLOYMENT_PLAN.md) | K8s 部署总体规划 |
