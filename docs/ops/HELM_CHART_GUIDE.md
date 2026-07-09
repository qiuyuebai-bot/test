# Helm Chart 使用文档

> 版本：v1.0 · 编制日期：2026-07-07
> 适用项目：领域知识个性化生成与多智能体协同决策系统
> Chart 路径：`deploy/helm/`
> 关联文档：[DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)、[K8S_DEPLOYMENT_PLAN.md](../K8S_DEPLOYMENT_PLAN.md)

本手册覆盖 Helm Chart 结构、values.yaml 完整参数说明、多环境配置、常用命令、自定义最佳实践、依赖组件安装、validate_chart.py 使用。

---

## 目录

1. [Chart 结构](#1-chart-结构)
2. [values.yaml 完整参数说明](#2-valuesyaml-完整参数说明)
3. [多环境配置](#3-多环境配置)
4. [常用 Helm 命令](#4-常用-helm-命令)
5. [常用 --set 参数覆盖](#5-常用---set-参数覆盖)
6. [自定义配置最佳实践](#6-自定义配置最佳实践)
7. [依赖组件安装](#7-依赖组件安装)
8. [validate_chart.py 使用](#8-validate_chartpy-使用)
9. [Chart 升级与版本管理](#9-chart-升级与版本管理)
10. [附录：模板渲染问题排查](#10-附录模板渲染问题排查)

---

## 1. Chart 结构

```
deploy/helm/
├── Chart.yaml                      # Chart 元数据（版本、依赖、维护者）
├── values.yaml                     # 默认配置（开发环境基准）
├── values-dev.yaml                 # 开发环境覆盖
├── values-staging.yaml             # 预发布环境覆盖
├── values-prod.yaml                # 生产环境覆盖
├── validate_chart.py               # Chart 综合校验脚本（16 项检查）
├── .helmignore
└── templates/
    ├── _helpers.tpl                # 命名、标签 helper 函数
    ├── NOTES.txt                   # 安装后提示信息
    ├── configmap.yaml              # 应用非敏感配置
    ├── secret.yaml                 # 敏感配置（SECRET_KEY、API_KEY）
    ├── serviceaccount.yaml         # ServiceAccount
    ├── ingress.yaml                # Ingress 路由
    ├── hpa.yaml                     # HPA 自动扩缩
    ├── poddisruptionbudget.yaml    # PDB
    ├── networkpolicy.yaml          # 网络隔离
    ├── rollout.yaml                # Argo Rollouts CRD
    │
    ├── frontend/
    │   ├── deployment.yaml         # 前端 Deployment
    │   └── service.yaml
    │
    ├── backend/
    │   ├── deployment.yaml         # 后端 Deployment（含 startupProbe、lifecycle）
    │   └── service.yaml
    │
    ├── postgres/
    │   ├── statefulset.yaml        # PostgreSQL StatefulSet
    │   └── service.yaml
    │
    ├── redis/
    │   ├── statefulset.yaml        # Redis StatefulSet
    │   └── service.yaml
    │
    ├── celery-worker/
    │   └── deployment.yaml
    │
    ├── chroma/
    │   ├── statefulset.yaml        # Chroma 向量库 StatefulSet
    │   └── service.yaml
    │
    ├── jobs/
    │   ├── db-migrate.yaml         # Alembic 迁移 Job（helm hook: pre-install, pre-upgrade）
    │   ├── seed-data.yaml          # 种子数据 Job（helm hook: post-install, post-upgrade）
    │   └── db-rollback.yaml        # 回滚 Job（helm hook: post-rollback）
    │
    ├── backup/
    │   ├── cronjob.yaml            # PostgreSQL 备份 CronJob
    │   └── velero-backup.yaml      # Velero 备份配置（含跨区域）
    │
    ├── monitoring/
    │   ├── servicemonitor.yaml     # Prometheus ServiceMonitor
    │   ├── prometheusrules.yaml    # 10 条告警规则
    │   ├── grafana-dashboard.yaml  # 3 个 Dashboard
    │   └── alertmanager-config.yaml # 通知渠道配置
    │
    └── argocd-sync-hooks/
        ├── presync-migrate.yaml   # ArgoCD PreSync hook
        └── postsync-healthcheck.yaml # ArgoCD PostSync hook
```

### Chart.yaml 关键字段

```yaml
apiVersion: v2            # Helm v2+ Chart 格式
name: knowledge-system     # Chart 名称
version: 1.0.0            # Chart 版本（每次修改递增）
appVersion: "1.0.0"        # 应用版本
type: application          # application | library
home: https://github.com/qiuyuebai-bot/test
maintainers: [...]         # 维护者
keywords: [education, multi-agent, llm, fastapi, react, challenge-cup]
```

---

## 2. values.yaml 完整参数说明

### 2.1 全局参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| `global.imageRegistry` | `""` | 镜像仓库地址（如 `registry.cn-hangzhou.aliyuncs.com/knowledge-system`） |
| `global.imagePullSecrets` | `[]` | 镜像拉取凭证列表 |
| `global.storageClass` | `""` | 默认存储类（空=集群默认） |
| `global.namespaceSuffix` | `""` | 命名空间后缀 |
| `global.appVersion` | `1.0.0` | 应用版本标签 |

### 2.2 镜像配置

```yaml
images:
  frontend:
    repository: knowledge-frontend
    tag: "1.0.0"
    pullPolicy: IfNotPresent
  backend:
    repository: knowledge-backend
    tag: "1.0.0"
    pullPolicy: IfNotPresent
  postgres:
    repository: postgres
    tag: "16-alpine"
  redis:
    repository: redis
    tag: "7-alpine"
  backup:
    repository: python          # 仅备份镜像（已改为复用 postgres 镜像）
    tag: "3.11-slim"
```

### 2.3 frontend 配置

| 参数 | 默认值 | 说明 |
|---|---|---|
| `frontend.enabled` | `true` | 是否启用前端 |
| `frontend.replicaCount` | `2` | 副本数 |
| `frontend.resources.requests` | `{cpu: 50m, memory: 64Mi}` | 资源请求 |
| `frontend.resources.limits` | `{cpu: 200m, memory: 128Mi}` | 资源上限 |
| `frontend.service.port` | `80` | Service 端口 |
| `frontend.livenessProbe` | `{path: /, ...}` | 存活探针 |
| `frontend.readinessProbe` | `{path: /, ...}` | 就绪探针 |
| `frontend.startupProbe` | `{failureThreshold: 12, ...}` | 启动探针（等 1 分钟） |
| `frontend.lifecycle.preStop` | `{command: ["sleep 10"]}` | 优雅关闭 hook |
| `frontend.hpa.enabled` | `false` | 是否启用 HPA |
| `frontend.hpa.minReplicas` | `2` | 最小副本 |
| `frontend.hpa.maxReplicas` | `5` | 最大副本 |
| `frontend.hpa.targetCPUUtilizationPercentage` | `70` | CPU 触发阈值 |

### 2.4 backend 配置

| 参数 | 默认值 | 说明 |
|---|---|---|
| `backend.enabled` | `true` | 是否启用后端 |
| `backend.replicaCount` | `2` | 副本数 |
| `backend.workers` | `1` | uvicorn workers 数 |
| `backend.command` | `["uvicorn", "app.main:app", ...]` | 启动命令 |
| `backend.resources.limits.memory` | `1Gi` | 内存上限（Phase 7 调优） |
| `backend.startupProbe.failureThreshold` | `30` | 启动失败重试次数（30×10s=5min） |
| `backend.lifecycle.preStop` | `{command: ["sleep 15"]}` | 优雅关闭（等 15s 摘流量） |
| `backend.hpa` | `{...}` | HPA 配置（同 frontend） |
| `backend.extraEnv` | `[]` | 额外环境变量 |

### 2.5 postgresql 配置

| 参数 | 默认值 | 说明 |
|---|---|---|
| `postgresql.enabled` | `true` | 是否启用集群内 postgres |
| `postgresql.external.enabled` | `false` | 是否使用外部云 RDS |
| `postgresql.external.host` | `""` | 外部 RDS 地址 |
| `postgresql.external.existingSecret` | `""` | RDS 密码 Secret |
| `postgresql.auth.username` | `postgres` | 数据库用户 |
| `postgresql.auth.password` | `ChangeMeInProduction` | 数据库密码（**生产必须覆盖**） |
| `postgresql.auth.database` | `knowledge_system` | 数据库名 |
| `postgresql.persistence.size` | `20Gi` | PVC 大小 |
| `postgresql.resources` | `{...}` | 资源限制 |

### 2.6 redis 配置

| 参数 | 默认值 | 说明 |
|---|---|---|
| `redis.enabled` | `true` | 是否启用集群内 redis |
| `redis.external.enabled` | `false` | 是否使用外部云 Redis |
| `redis.auth.enabled` | `false` | 是否启用密码 |
| `redis.persistence.size` | `5Gi` | PVC 大小 |
| `redis.args` | `["redis-server", "--appendonly", "yes"]` | 启动参数（开启 AOF） |

### 2.7 celeryWorker 配置

| 参数 | 默认值 | 说明 |
|---|---|---|
| `celeryWorker.enabled` | `false` | 默认关闭，staging/prod 启用 |
| `celeryWorker.replicaCount` | `2` | 副本数 |
| `celeryWorker.command` | `["celery", "-A", ...]` | 启动命令 |
| `celeryWorker.resources.limits.memory` | `1Gi` | 内存上限（Phase 7 调优） |

### 2.8 chroma 配置

| 参数 | 默认值 | 说明 |
|---|---|---|
| `chroma.enabled` | `false` | 默认关闭，staging/prod 启用 |
| `chroma.persistence.size` | `20Gi` | PVC 大小 |
| `chroma.env.isPersistent` | `TRUE` | 启用持久化 |

### 2.9 backup 配置

| 参数 | 默认值 | 说明 |
|---|---|---|
| `backup.enabled` | `false` | 默认关闭 |
| `backup.schedule` | `"0 18 * * *"` | UTC 18:00 = 北京 02:00 |
| `backup.retention.days` | `7` | 备份保留天数 |
| `backup.persistence.size` | `10Gi` | 备份 PVC 大小 |
| `backup.image` | 复用 `images.postgres` | 内置 pg_dump |

### 2.10 velero 配置

```yaml
velero:
  enabled: false              # 默认关闭
  schedule: "0 2 * * *"       # 每日 02:00
  ttl: "168h"                 # 保留 7 天
  backupStorageLocation:      # 主备份位置
    provider: aws             # S3 兼容协议
    bucket: ""                # 对象存储 bucket
    region: "cn-hangzhou"
    endpoint: ""              # OSS 端点
    accessKey: ""
    secretKey: ""
    existingCredential: ""   # 生产推荐使用已有 Secret
  volumeSnapshotLocation:     # 卷快照位置
    provider: aws
    region: "cn-hangzhou"
    enabled: true
  replication:                # 跨区域复制
    enabled: false
    region: "cn-shanghai"     # 异地 region
    bucket: ""
    accessKey: ""
    secretKey: ""
```

### 2.11 monitoring 配置

```yaml
monitoring:
  serviceMonitor:
    enabled: false              # 默认关闭
    namespace: monitoring       # ServiceMonitor 部署位置
    interval: 30s
    path: /metrics
  prometheusRule:
    enabled: false              # 10 条告警规则
    namespace: monitoring
  grafanaDashboard:
    enabled: false              # 3 个 Dashboard
    namespace: monitoring
  alertmanager:
    enabled: false
    channel: dingtalk          # dingtalk | wechat | slack | email
    webhookUrl: ""
    smtp: { from, smarthost, authUsername, authPassword }
```

### 2.12 migration 配置

```yaml
migration:
  enabled: true                  # helm hook 自动迁移
  command: ["alembic", "upgrade", "head"]
  seedAdmin: true                # 是否初始化 admin 账户
  rollbackRevision: "-1"         # post-rollback hook 回滚版本
  ttlSecondsAfterFinished: 3600  # Job 完成后保留 1 小时
  backoffLimit: 3                # 失败重试 3 次
```

### 2.13 argocd 配置

```yaml
argocd:
  syncHooks:
    enabled: false                # ArgoCD 管理时启用
    preSync:                      # PreSync: alembic 迁移
      enabled: true
      command: ["alembic", "upgrade", "head"]
    postSync:                     # PostSync: 健康检查
      enabled: true
      healthCheckPath: "/health/ready"
      smokeTestPath: "/api/v1/info"
    hookDeletePolicy: HookSucceeded
    ttlSecondsAfterFinished: 3600
```

### 2.14 rollouts 配置

```yaml
rollouts:
  enabled: false                  # 启用后用 Rollout CRD 替代 backend Deployment
  strategy: canary
  canary:
    steps:                        # 渐进式切流
      - setWeight: 20
      - pause: { duration: 30s }
      - setWeight: 40
      - pause: { duration: 30s }
      - setWeight: 60
      - pause: { duration: 30s }
      - setWeight: 80
      - pause: { duration: 30s }
    analysis:                     # 指标分析（失败自动回滚）
      enabled: true
      prometheusAddress: "http://prometheus-server.monitoring.svc.cluster.local:9090"
      metrics:
        - name: error-rate
          threshold: "0.05"        # 5xx > 5% 触发回滚
        - name: p99-latency
          threshold: "2"           # P99 > 2s 触发回滚
```

### 2.15 ingress 配置

```yaml
ingress:
  enabled: false
  className: nginx
  annotations: { cert-manager.io/cluster-issuer: letsencrypt-prod, ... }
  hosts:
    - host: knowledge-system.example.com
      paths:
        - { path: /, service: frontend }
        - { path: /api, service: backend }
        - { path: /docs, service: backend }
        - { path: /health, service: backend }
        - { path: /metrics, service: backend }
  tls:
    - secretName: knowledge-system-tls
      hosts: [knowledge-system.example.com]
```

### 2.16 Pod 安全与调度

| 参数 | 说明 |
|---|---|
| `podSecurityContext` | fsGroup、runAsUser、runAsNonRoot 等 |
| `containerSecurityContext` | allowPrivilegeEscalation: false、drop ALL capabilities |
| `podAntiAffinity.enabled` | 默认开启，跨节点分布 |
| `podAntiAffinity.type` | preferred（软策略）/ required（硬策略） |
| `topologySpreadConstraints.enabled` | 跨 zone 均匀分布 |
| `podDisruptionBudget.enabled` | 默认开启，minAvailable=1 |
| `networkPolicy.enabled` | 默认关闭，启用后限制服务间通信 |
| `terminationGracePeriodSeconds` | 60（含 preStop sleep 15s） |

---

## 3. 多环境配置

### 3.1 配置覆盖层级

```
values.yaml               # 基础默认值（dev 基准）
  └── values-dev.yaml     # 开发覆盖（minikube/kind）
  └── values-staging.yaml # 预发布覆盖（云集群）
  └── values-prod.yaml    # 生产覆盖（高可用 + 云服务）
```

### 3.2 环境差异速查表

| 维度 | dev | staging | prod |
|---|---|---|---|
| frontend 副本 | 1 | 2 | 3 |
| backend 副本 | 1 | 3 | 4 |
| backend workers | 1 | 2 | 4 |
| backend memory | 256Mi | 1Gi | 2Gi |
| postgres | 集群内 5Gi | 集群内 30Gi | 云 RDS |
| redis | 集群内 1Gi | 集群内 5Gi | 云 Redis |
| celery-worker | 关闭 | 2 副本 | 3 副本 |
| chroma | 关闭 | 20Gi | 50Gi |
| backup | 关闭 | 14 天 | 30 天 |
| HPA | 关闭 | 开启 | 开启 |
| Ingress | knowledge-system.local | staging.xxx.com | xxx.com |
| TLS | 无 | Let's Encrypt | Let's Encrypt |
| DEBUG_MODE | true | false | false |
| Secret 管理方式 | 内置 | 内置 | existingSecret |
| 镜像拉取凭证 | 无 | registry-credentials | registry-credentials |

### 3.3 创建自定义覆盖文件

如需针对特定部署自定义配置，建议创建 `values-<env>-custom.yaml`：

```bash
# 创建生产自定义覆盖
cat > deploy/helm/values-prod-custom.yaml <<EOF
backend:
  replicaCount: 5  # 临时扩容到 5 副本

backup:
  retention:
    days: 60  # 备份保留 60 天
EOF

# 部署时叠加
helm upgrade knowledge-system ./deploy/helm \
  -f deploy/helm/values-prod.yaml \
  -f deploy/helm/values-prod-custom.yaml \
  -n knowledge-prod
```

---

## 4. 常用 Helm 命令

### 4.1 安装与升级

```bash
# 首次安装
helm install knowledge-system ./deploy/helm \
  -f deploy/helm/values-prod.yaml \
  -n knowledge-prod --create-namespace

# 升级
helm upgrade knowledge-system ./deploy/helm \
  -f deploy/helm/values-prod.yaml \
  -n knowledge-prod

# 升级并附加参数
helm upgrade knowledge-system ./deploy/helm \
  -f deploy/helm/values-prod.yaml \
  --set backend.replicaCount=5 \
  --set images.backend.tag=1.1.0 \
  -n knowledge-prod

# Dry-run（仅渲染不部署）
helm upgrade knowledge-system ./deploy/helm \
  -f deploy/helm/values-prod.yaml \
  -n knowledge-prod --dry-run > /tmp/dryrun.yaml
```

### 4.2 查看与回滚

```bash
# 查看 release 列表
helm list -n knowledge-prod

# 查看 release 历史
helm history knowledge-system -n knowledge-prod

# 查看当前 values
helm get values knowledge-system -n knowledge-prod
helm get values knowledge-system -n knowledge-prod --all

# 查看渲染后的 manifest
helm get manifest knowledge-system -n knowledge-prod

# 回滚到指定 revision
helm rollback knowledge-system <revision> -n knowledge-prod
```

### 4.3 验证与调试

```bash
# 语法检查
helm lint deploy/helm

# 渲染模板（不部署）
helm template knowledge-system ./deploy/helm \
  -f deploy/helm/values-prod.yaml \
  -n knowledge-prod > /tmp/render.yaml

# 查看 diff（需 helm-diff 插件）
helm plugin install https://github.com/databus23/helm-diff
helm diff upgrade knowledge-system ./deploy/helm \
  -f deploy/helm/values-prod.yaml \
  -n knowledge-prod

# 综合校验
python deploy/helm/validate_chart.py
```

### 4.4 卸载

```bash
# 卸载 release（保留 PVC）
helm uninstall knowledge-system -n knowledge-prod

# 清理 helm hook 创建的 Job
kubectl delete jobs -n knowledge-prod --all
```

---

## 5. 常用 --set 参数覆盖

### 5.1 镜像版本升级

```bash
helm upgrade knowledge-system ./deploy/helm \
  -f deploy/helm/values-prod.yaml \
  --set images.backend.tag=1.1.0 \
  --set images.frontend.tag=1.1.0 \
  -n knowledge-prod
```

### 5.2 副本数调整

```bash
helm upgrade knowledge-system ./deploy/helm \
  -f deploy/helm/values-prod.yaml \
  --set backend.replicaCount=6 \
  --set frontend.replicaCount=4 \
  -n knowledge-prod
```

### 5.3 资源调整

```bash
helm upgrade knowledge-system ./deploy/helm \
  -f deploy/helm/values-prod.yaml \
  --set backend.resources.limits.memory=3Gi \
  --set backend.resources.limits.cpu=3000m \
  -n knowledge-prod
```

### 5.4 启用/禁用功能

```bash
# 启用备份
helm upgrade knowledge-system ./deploy/helm \
  -f deploy/helm/values-prod.yaml \
  --set backup.enabled=true \
  --set backup.retention.days=30 \
  -n knowledge-prod

# 启用监控
helm upgrade knowledge-system ./deploy/helm \
  -f deploy/helm/values-prod.yaml \
  --set monitoring.serviceMonitor.enabled=true \
  --set monitoring.prometheusRule.enabled=true \
  --set monitoring.grafanaDashboard.enabled=true \
  --set monitoring.alertmanager.enabled=true \
  --set monitoring.alertmanager.webhookUrl=https://oapi.dingtalk.com/robot/send?access_token=xxx \
  -n knowledge-prod

# 切换到云 RDS
helm upgrade knowledge-system ./deploy/helm \
  -f deploy/helm/values-prod.yaml \
  --set postgresql.enabled=false \
  --set postgresql.external.enabled=true \
  --set postgresql.external.host=rm-xxx.rds.aliyuncs.com \
  --set postgresql.external.existingSecret=knowledge-system-db-secret \
  -n knowledge-prod
```

### 5.5 紧急扩容

```bash
# 临时扩容（不修改 values.yaml）
helm upgrade knowledge-system ./deploy/helm \
  -f deploy/helm/values-prod.yaml \
  --set backend.replicaCount=8 \
  --set backend.hpa.maxReplicas=12 \
  -n knowledge-prod
```

---

## 6. 自定义配置最佳实践

### 6.1 配置管理原则

| 原则 | 说明 |
|---|---|
| **环境隔离** | 每个环境使用独立 values-<env>.yaml |
| **敏感信息** | 生产必须用 `existingSecret`，禁止明文 |
| **版本控制** | values-*.yaml 提交到 Git，使用 GitOps |
| **最小权限** | Pod Security Standards: restricted |
| **资源限制** | 所有容器必须配置 requests + limits |

### 6.2 Secret 管理策略

| 环境 | 策略 | 实现 |
|---|---|---|
| dev | 内置 Secret（明文存 values） | `secrets.data.SECRET_KEY=dev-only-xxx` |
| staging | 内置 Secret（占位符） | `secrets.data.SECRET_KEY=staging-xxx` |
| **prod** | **外部 Secret（强制）** | `secrets.existingSecret=knowledge-system-prod-secrets` |

**生产 Secret 创建（见 [DEPLOYMENT_GUIDE.md §3.1](./DEPLOYMENT_GUIDE.md#31-准备-secret生产环境)）：**

```bash
kubectl create secret generic knowledge-system-prod-secrets \
  --from-literal=SECRET_KEY=$(openssl rand -hex 32) \
  --from-literal=OPENAI_API_KEY=sk-xxx \
  --from-literal=DEFAULT_ADMIN_PASSWORD=$(openssl rand -base64 16) \
  --from-literal=POSTGRES_PASSWORD=$(openssl rand -hex 16) \
  -n knowledge-prod
```

### 6.3 镜像仓库策略

| 环境 | 镜像仓库 | 凭证 |
|---|---|---|
| dev | 本地（minikube 加载） | 无需 |
| staging | 阿里云 ACR | `registry-credentials` Secret |
| prod | 阿里云 ACR | `registry-credentials` Secret |

### 6.4 配置变更流程

```
1. 修改 values-<env>.yaml
   ↓
2. 本地验证
   helm lint deploy/helm
   python deploy/helm/validate_chart.py
   ↓
3. 渲染检查
   helm template ... > /tmp/render.yaml
   grep -E "password|secret|key" /tmp/render.yaml
   ↓
4. Staging 验证（先在 staging 部署）
   ↓
5. 生产部署（蓝绿或金丝雀）
   ↓
6. 验证与监控
```

---

## 7. 依赖组件安装

### 7.1 必需组件（启用对应功能时）

| 组件 | 必需场景 | 安装命令 |
|---|---|---|
| ingress-nginx | `ingress.enabled=true` | `helm install ingress-nginx ingress-nginx/ingress-nginx -n ingress-nginx --create-namespace` |
| cert-manager | `ingress.tls` 配置 | `kubectl apply -f https://github.com/cert-manager/cert-manager/releases/latest/download/cert-manager.yaml` |
| metrics-server | `*.hpa.enabled=true` | `kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml` |
| kube-prometheus-stack | `monitoring.*.enabled=true` | `helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack -n monitoring --create-namespace` |
| Velero | `velero.enabled=true` | `velero install --provider aws --bucket xxx ...` |
| ArgoCD | `argocd.syncHooks.enabled=true` | `kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml` |
| Argo Rollouts | `rollouts.enabled=true` | `kubectl apply -f https://github.com/argoproj/argo-rollouts/manifests/install.yaml` |

### 7.2 验证依赖组件就绪

```bash
# 1. ingress-nginx
kubectl get pods -n ingress-nginx -w

# 2. cert-manager
kubectl get pods -n cert-manager -w
kubectl get clusterissuer

# 3. metrics-server
kubectl top nodes  # 能正常输出说明就绪

# 4. kube-prometheus-stack
kubectl get pods -n monitoring -w
kubectl get servicemonitor -n monitoring

# 5. Velero
kubectl get pods -n velero -w
velero version

# 6. ArgoCD
kubectl get pods -n argocd -w
argocd version

# 7. Argo Rollouts
kubectl get pods -n argo-rollouts -w
kubectl argo rollouts version
```

### 7.3 依赖与 Chart 功能对应表

```
ingress.enabled=true         → 需 ingress-nginx
ingress.tls 配置             → 需 ingress-nginx + cert-manager
*.hpa.enabled=true           → 需 metrics-server
monitoring.*.enabled=true    → 需 kube-prometheus-stack
velero.enabled=true          → 需 Velero 控制器
argocd.syncHooks.enabled=true → 需 ArgoCD
rollouts.enabled=true        → 需 Argo Rollouts 控制器
```

---

## 8. validate_chart.py 使用

### 8.1 运行校验

```bash
cd deploy/helm
python validate_chart.py
```

### 8.2 校验项（16 项）

| 序号 | 检查项 | 说明 |
|---|---|---|
| 1-4 | 必需文件 | Chart.yaml、values.yaml、_helpers.tpl、NOTES.txt |
| 5-6 | YAML 语法 | Chart.yaml、values.yaml 解析 |
| 7-8 | helper 引用 | _helpers.tpl 中函数都被引用、模板引用的函数都已定义 |
| 9-10 | 模板完整性 | .helmignore 存在、templates 目录结构 |
| 11-13 | 关键资源 | Deployment、Service、ConfigMap 存在 |
| 14-16 | 业务资源 | frontend、backend、postgres 模板存在 |

### 8.3 输出示例

```
============================================================
Helm Chart 验证报告
============================================================

[1/6] 检查必需文件...
  [OK] Chart.yaml 存在
  [OK] values.yaml 存在
  [OK] templates/_helpers.tpl 存在
  [OK] templates/NOTES.txt 存在

...

============================================================
总结：
  通过: 16 项
  警告: 0 项
  失败: 0 项
所有关键检查项通过！Chart 可用于部署。
```

### 8.4 CI 集成

建议在 GitHub Actions 中集成校验：

```yaml
# .github/workflows/validate-chart.yml
name: Validate Helm Chart
on: [push, pull_request]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - name: Install PyYAML
        run: pip install pyyaml
      - name: Validate Chart
        run: python deploy/helm/validate_chart.py
      - name: Helm lint
        run: |
          curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
          helm lint deploy/helm
```

---

## 9. Chart 升级与版本管理

### 9.1 版本号规范

| 版本 | 含义 | 何时递增 |
|---|---|---|
| `Chart.yaml.version` | Chart 自身版本 | 模板、values 结构变更 |
| `Chart.yaml.appVersion` | 应用版本 | 应用代码版本升级 |

### 9.2 升级兼容性

| 变更类型 | 兼容性 | 用户感知 |
|---|---|---|
| 新增可选字段 | 向后兼容 | 无需调整 |
| 新增必需字段 | 破坏性 | 需更新 values |
| 删除字段 | 破坏性 | 需清理引用 |
| 默认值变更 | 视情况 | 可能影响行为 |
| helper 重命名 | 破坏性 | 需同步更新 |

### 9.3 升级流程

```bash
# 1. 备份当前 values
helm get values knowledge-system -n knowledge-prod --all > /tmp/values-backup.yaml

# 2. 更新 Chart 代码
git pull origin main

# 3. 验证新版本
helm lint deploy/helm
python deploy/helm/validate_chart.py

# 4. 渲染对比
helm diff upgrade knowledge-system ./deploy/helm \
  -f deploy/helm/values-prod.yaml \
  -n knowledge-prod

# 5. 执行升级
helm upgrade knowledge-system ./deploy/helm \
  -f deploy/helm/values-prod.yaml \
  -n knowledge-prod

# 6. 验证升级
kubectl get pods -n knowledge-prod -w
bash deploy/scripts/smoke-test.sh --host https://knowledge-system.example.com
```

---

## 10. 附录：模板渲染问题排查

### 10.1 常见渲染错误

#### 错误 1：helper 函数未定义

```bash
$ helm template ... 
Error: could not parse template: template: knowledge-system/templates/xxx.yaml:5: function "knowledge-system.xxx" not defined
```

**排查：** 检查 `_helpers.tpl` 中是否定义了对应函数，函数名拼写是否一致。

#### 错误 2：values 字段不存在

```bash
$ helm template ...
Error: execution error at (knowledge-system/templates/xxx.yaml:5:5): template: ... nil pointer evaluating interface {}
```

**排查：** 检查 values.yaml 中对应字段是否存在，使用 `{{- if .Values.xxx }}` 条件渲染。

#### 错误 3：YAML 缩进错误

```bash
$ helm template ...
Error: YAML parse error on knowledge-system/templates/xxx.yaml: error converting YAML to JSON
```

**排查：** 检查 `nindent` 的缩进数（如 nindent 12 表示 12 个空格），与上下文结构对齐。

#### 错误 4：Go template 与 Mustache 模板冲突

```bash
$ helm template ... | grep  # 渲染输出包含 {{xxx}} 字符串异常
```

**排查：** Grafana/Prometheus 模板中的 `{{xxx}}` 会被 Helm Go template 误解析。已在 [prometheusrules.yaml](../../deploy/helm/templates/monitoring/prometheusrules.yaml) 和 [grafana-dashboard.yaml](../../deploy/helm/templates/monitoring/grafana-dashboard.yaml) 中通过 `{{- $lb := "{{" -}}` 和 `{{- $rb := "}}" -}}` 定义变量替换解决。

### 10.2 调试技巧

```bash
# 1. 渲染单个模板
helm template knowledge-system ./deploy/helm \
  -f deploy/helm/values-prod.yaml \
  -s templates/backend/deployment.yaml \
  -n knowledge-prod

# 2. 查看特定值
helm template knowledge-system ./deploy/helm \
  -f deploy/helm/values-prod.yaml \
  --set backend.replicaCount=10 \
  -n knowledge-prod | grep -A 2 "replicas:"

# 3. 输出调试信息
# 在模板中添加 {{ printf "%#v" .Values.backend }}

# 4. 使用 helm-diff 对比
helm diff upgrade knowledge-system ./deploy/helm \
  -f deploy/helm/values-prod.yaml \
  -n knowledge-prod --detailed-exitcode
```

### 10.3 渲染验证清单

部署前必须验证：
- [ ] `helm lint deploy/helm` 0 失败
- [ ] `python deploy/helm/validate_chart.py` 16/16 通过
- [ ] `helm template` 三环境渲染 exit 0
- [ ] 渲染输出无明文敏感信息（grep password/secret/key）
- [ ] 关键资源都存在（Deployment/Service/ConfigMap/Secret）
- [ ] Mustache 模板 `{{xxx}}` 正确渲染（非被 Helm 求值）

---

## 相关文档

| 文档 | 说明 |
|---|---|
| [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) | 部署运维手册（部署流程） |
| [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) | 故障处理指南 |
| [RELEASE_SOP.md](./RELEASE_SOP.md) | 发布操作手册 |
| [BACKUP_RECOVERY.md](./BACKUP_RECOVERY.md) | 备份恢复手册 |
| [MONITORING_ALERTING.md](./MONITORING_ALERTING.md) | 监控告警手册 |
| [K8S_DEPLOYMENT_PLAN.md](../K8S_DEPLOYMENT_PLAN.md) | K8s 部署总体规划 |
