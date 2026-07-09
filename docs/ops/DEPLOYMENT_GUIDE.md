# K8s 部署运维手册

> 版本：v1.0 · 编制日期：2026-07-07
> 适用项目：领域知识个性化生成与多智能体协同决策系统
> Helm Chart 路径：`deploy/helm/`
> 关联文档：[K8S_DEPLOYMENT_PLAN.md](../K8S_DEPLOYMENT_PLAN.md)、[HELM_CHART_GUIDE.md](./HELM_CHART_GUIDE.md)

---

## 目录

1. [集群前置条件](#1-集群前置条件)
2. [服务清单与架构](#2-服务清单与架构)
3. [首次部署流程](#3-首次部署流程)
4. [多环境配置](#4-多环境配置)
5. [升级流程](#5-升级流程)
6. [扩缩容操作](#6-扩缩容操作)
7. [日志查看与排查](#7-日志查看与排查)
8. [日常运维任务](#8-日常运维任务)
9. [卸载与清理](#9-卸载与清理)
10. [附录：常用 kubectl 速查](#10-附录常用-kubectl-速查)

---

## 1. 集群前置条件

### 1.1 基础设施

| 项 | 要求 | 验证命令 |
|---|---|---|
| K8s 版本 | 1.26+ | `kubectl version --short` |
| Helm | 3.10+ | `helm version` |
| kubectl | 已配置集群上下文 | `kubectl get nodes` |
| 节点数 | ≥ 2（生产 ≥ 3，跨 AZ） | `kubectl get nodes -L topology.kubernetes.io/zone` |
| 节点资源 | dev: 2C4G；staging: 4C8G；prod: 8C16G+ | `kubectl describe nodes | grep -A 5 Capacity` |

### 1.2 集群组件（按需启用）

| 组件 | 用途 | 安装命令（参考） | 必需性 |
|---|---|---|---|
| ingress-nginx | 流量入口 | `helm install ingress-nginx ingress-nginx/ingress-nginx -n ingress-nginx --create-namespace` | 启用 Ingress 时必需 |
| cert-manager | TLS 证书自动签发 | `kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml` | 启用 TLS 时必需 |
| metrics-server | HPA 指标采集 | `kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml` | 启用 HPA 时必需 |
| kube-prometheus-stack | 监控告警 | 见 [MONITORING_ALERTING.md](./MONITORING_ALERTING.md) | 启用监控时必需 |
| Velero | 备份恢复 | 见 [BACKUP_RECOVERY.md](./BACKUP_RECOVERY.md) | 启用 Velero 备份时必需 |
| ArgoCD | GitOps 自动同步 | `kubectl create namespace argocd && kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml` | 可选 |
| Argo Rollouts | 基于指标自动回滚 | `kubectl apply -f https://github.com/argoproj/argo-rollouts/manifests/install.yaml` | 可选 |

### 1.3 镜像仓库准备

```bash
# 1. 创建镜像仓库（阿里云 ACR / Docker Hub / Harbor）
# 2. 创建镜像拉取凭证
kubectl create secret docker-registry registry-credentials \
  --docker-server=registry.cn-hangzhou.aliyuncs.com \
  --docker-username=<your-username> \
  --docker-password=<your-password> \
  --docker-email=<your-email> \
  -n knowledge-prod

# 3. 验证
kubectl get secret registry-credentials -n knowledge-prod
```

### 1.4 域名与 DNS

| 环境 | 域名示例 | DNS 记录 |
|---|---|---|
| dev | knowledge-system.local | 本地 hosts 文件或 minikube tunnel |
| staging | staging.knowledge-system.example.com | A 记录指向 staging Ingress LB |
| prod | knowledge-system.example.com | A 记录指向 prod Ingress LB |

```bash
# 获取 Ingress LB 外网 IP（云厂商）
kubectl get svc -n ingress-nginx ingress-nginx-controller -o jsonpath='{.status.loadBalancer.ingress[0].ip}'

# 本地开发（minikube）
minikube tunnel
```

---

## 2. 服务清单与架构

### 2.1 服务拓扑

```
                        ┌─────────────────────┐
                        │     Ingress (TLS)    │
                        │   cert-manager + ACME│
                        └──────────┬──────────┘
                                   │
                  ┌────────────────┼────────────────┐
                  │                 │                │
            ┌─────▼─────┐    ┌─────▼─────┐    ┌─────▼─────┐
            │ frontend  │    │ frontend  │    │ frontend  │
            │ (2 副本)  │    │           │    │           │
            └─────┬─────┘    └─────┬─────┘    └─────┬─────┘
                  │                 │                │
                  └─────────────────┼────────────────┘
                                    │
                            ┌───────▼───────┐
                            │    backend    │  (HPA 2-6 副本)
                            │   FastAPI     │
                            └───┬───┬───┬───┘
                                │   │   │
                ┌───────────────┘   │   └───────────────┐
                │                   │                   │
        ┌───────▼───────┐   ┌───────▼───────┐   ┌───────▼───────┐
        │   postgres    │   │     redis     │   │    chroma     │
        │  StatefulSet  │   │  StatefulSet  │   │  StatefulSet  │
        │     PVC       │   │     PVC       │   │     PVC       │
        └───────────────┘   └───────────────┘   └───────────────┘
                │                                     │
        ┌───────▼───────┐                     ┌───────▼───────┐
        │ celery-worker │                     │   backup      │
        │  (2 副本)    │                     │   CronJob     │
        └───────────────┘                     └───────────────┘
```

### 2.2 服务清单

| 服务 | 资源类型 | 默认副本 | 端口 | 备注 |
|---|---|---|---|---|
| frontend | Deployment + Service | 2 | 80 | Nginx 静态文件 |
| backend | Deployment + Service | 2 | 8000 | FastAPI + uvicorn |
| postgres | StatefulSet + Service | 1 | 5432 | 生产建议云 RDS |
| redis | StatefulSet + Service | 1 | 6379 | 缓存 + Celery 队列 |
| celery-worker | Deployment | 2 | - | 异步任务处理 |
| chroma | StatefulSet + Service | 1 | 8000 | 向量数据库（可选） |
| backup | CronJob | - | - | 每日 02:00 备份 |
| db-migrate | Job (helm hook) | - | - | pre-install/pre-upgrade |
| seed-data | Job (helm hook) | - | - | post-install/post-upgrade |

### 2.3 命名空间规划

| 命名空间 | 用途 | 创建命令 |
|---|---|---|
| `knowledge-dev` | 开发环境 | `kubectl create namespace knowledge-dev` |
| `knowledge-staging` | 预发布环境 | `kubectl create namespace knowledge-staging` |
| `knowledge-prod` | 生产环境 | `kubectl create namespace knowledge-prod` |
| `monitoring` | 监控基础设施 | 由 kube-prometheus-stack 创建 |
| `velero` | 备份控制器 | 由 Velero 安装创建 |
| `argocd` | GitOps 控制器 | 由 ArgoCD 安装创建 |

---

## 3. 首次部署流程

### 3.1 准备 Secret（生产环境）

```bash
# 生产环境必须使用 existingSecret，禁止在 values.yaml 明文存储
kubectl create secret generic knowledge-system-prod-secrets \
  --from-literal=SECRET_KEY=$(openssl rand -hex 32) \
  --from-literal=OPENAI_API_KEY=sk-your-real-api-key \
  --from-literal=DEFAULT_ADMIN_PASSWORD=$(openssl rand -base64 16) \
  --from-literal=POSTGRES_PASSWORD=$(openssl rand -hex 16) \
  --from-literal=REDIS_PASSWORD=$(openssl rand -hex 16) \
  -n knowledge-prod

# 数据库独立 Secret（用于云 RDS）
kubectl create secret generic knowledge-system-db-secret \
  --from-literal=password=$(openssl rand -hex 16) \
  -n knowledge-prod
```

### 3.2 验证 Helm Chart

```bash
cd deploy/helm

# 1. 语法检查
helm lint .

# 2. 模板渲染检查（dry-run）
helm template knowledge-system . -f values-dev.yaml -n knowledge-dev > /tmp/render-dev.yaml
helm template knowledge-system . -f values-staging.yaml -n knowledge-staging > /tmp/render-staging.yaml
helm template knowledge-system . -f values-prod.yaml -n knowledge-prod > /tmp/render-prod.yaml

# 3. 综合校验（16 项检查）
python validate_chart.py
```

### 3.3 部署到 dev 环境（minikube/kind）

```bash
# 1. 创建命名空间
kubectl create namespace knowledge-dev

# 2. 安装 Chart
helm install knowledge-system ./deploy/helm \
  -f deploy/helm/values-dev.yaml \
  -n knowledge-dev \
  --create-namespace

# 3. 等待 Pod 就绪
kubectl get pods -n knowledge-dev -w
# 期望看到所有 Pod Running 且 READY 1/1

# 4. 验证服务
kubectl get svc -n knowledge-dev
kubectl get ingress -n knowledge-dev

# 5. 本地访问（minikube）
minikube tunnel
curl -k https://knowledge-system.local/health
```

### 3.4 部署到 staging 环境

```bash
# 1. 准备镜像拉取凭证（如未创建）
kubectl create secret docker-registry registry-credentials \
  --docker-server=registry.cn-hangzhou.aliyuncs.com \
  --docker-username=<username> \
  --docker-password=<password> \
  -n knowledge-staging

# 2. 安装
helm install knowledge-system ./deploy/helm \
  -f deploy/helm/values-staging.yaml \
  -n knowledge-staging \
  --create-namespace

# 3. 验证
kubectl get pods -n knowledge-staging -w
kubectl get ingress -n knowledge-staging

# 4. 冒烟测试
bash deploy/scripts/smoke-test.sh \
  --host https://staging.knowledge-system.example.com \
  --retry 10 --interval 6
```

### 3.5 部署到 prod 环境

```bash
# 1. 创建 Secret（见 3.1 节）

# 2. 安装（务必使用 --dry-run 先验证）
helm install knowledge-system ./deploy/helm \
  -f deploy/helm/values-prod.yaml \
  -n knowledge-prod \
  --create-namespace \
  --dry-run > /tmp/prod-dryrun.log

# 检查渲染输出，确认无明文敏感信息后执行真实安装
helm install knowledge-system ./deploy/helm \
  -f deploy/helm/values-prod.yaml \
  -n knowledge-prod \
  --create-namespace

# 3. 等待所有 Pod 就绪（生产 backend 启动慢，最多 5 分钟）
kubectl get pods -n knowledge-prod -w

# 4. 验证迁移 Job 成功
kubectl get jobs -n knowledge-prod
kubectl logs job/db-migrate -n knowledge-prod

# 5. 冒烟测试
bash deploy/scripts/smoke-test.sh \
  --host https://knowledge-system.example.com
```

---

## 4. 多环境配置

### 4.1 配置层级

```
values.yaml              # 基础默认值
  └── values-dev.yaml    # 开发覆盖
  └── values-staging.yaml # 预发布覆盖
  └── values-prod.yaml   # 生产覆盖
```

### 4.2 环境差异速查

| 维度 | dev | staging | prod |
|---|---|---|---|
| frontend 副本 | 1 | 2 | 3 |
| backend 副本 | 1 | 3 | 4 |
| backend workers | 1 | 2 | 4 |
| backend memory limit | 256Mi | 1Gi | 2Gi |
| postgres | 集群内 5Gi | 集群内 30Gi | 云 RDS |
| redis | 集群内 1Gi | 集群内 5Gi | 云 Redis |
| celery-worker | 关闭 | 2 副本 | 3 副本 |
| chroma | 关闭 | 20Gi | 50Gi |
| backup | 关闭 | 14 天保留 | 30 天保留 |
| HPA | 关闭 | 开启 | 开启 |
| Ingress | knowledge-system.local | staging.xxx.com | xxx.com |
| TLS | 无 | Let's Encrypt | Let's Encrypt |
| DEBUG_MODE | true | false | false |
| SECRET_KEY | 内置 dev | 内置 staging | existingSecret |
| 镜像拉取凭证 | 无 | registry-credentials | registry-credentials |

### 4.3 临时覆盖参数

```bash
# 单次部署时覆盖某项参数
helm upgrade knowledge-system ./deploy/helm \
  -f deploy/helm/values-prod.yaml \
  --set backend.replicaCount=6 \
  --set backup.retention.days=60 \
  -n knowledge-prod

# 多个参数使用 --set-file 或 values 文件
# 推荐：创建 values-prod-custom.yaml 覆盖
helm upgrade knowledge-system ./deploy/helm \
  -f deploy/helm/values-prod.yaml \
  -f deploy/helm/values-prod-custom.yaml \
  -n knowledge-prod
```

---

## 5. 升级流程

### 5.1 常规升级（Helm upgrade）

```bash
# 1. 拉取最新 Chart 代码
git pull origin main

# 2. 验证 Chart
helm lint deploy/helm
python deploy/helm/validate_chart.py

# 3. 查看将变更的 diff（需要 helm-diff 插件）
helm plugin install https://github.com/databus23/helm-diff
helm diff upgrade knowledge-system ./deploy/helm \
  -f deploy/helm/values-prod.yaml \
  -n knowledge-prod

# 4. 执行升级
helm upgrade knowledge-system ./deploy/helm \
  -f deploy/helm/values-prod.yaml \
  -n knowledge-prod

# 5. 监控升级状态
kubectl get pods -n knowledge-prod -w
helm history knowledge-system -n knowledge-prod

# 6. 验证（PostSync hook 会自动执行健康检查）
kubectl logs job/postsync-healthcheck -n knowledge-prod
```

### 5.2 镜像版本升级

```bash
# 仅更新镜像 tag（无需改 Chart）
helm upgrade knowledge-system ./deploy/helm \
  -f deploy/helm/values-prod.yaml \
  --set images.backend.tag=1.1.0 \
  --set images.frontend.tag=1.1.0 \
  -n knowledge-prod

# 或修改 values-prod.yaml 中的 images.*.tag 后 helm upgrade
```

### 5.3 蓝绿发布（零停机）

详见 [RELEASE_SOP.md](./RELEASE_SOP.md) §1 蓝绿发布。

```bash
bash deploy/scripts/blue-green-deploy.sh \
  --release knowledge-system \
  --namespace knowledge-prod \
  --chart ./deploy/helm \
  --values deploy/helm/values-prod.yaml
```

### 5.4 金丝雀发布（渐进切流）

详见 [RELEASE_SOP.md](./RELEASE_SOP.md) §2 金丝雀发布。

```bash
bash deploy/scripts/canary-deploy.sh \
  --release knowledge-system \
  --namespace knowledge-prod \
  --chart ./deploy/helm \
  --values deploy/helm/values-prod.yaml \
  --host knowledge-system.example.com \
  --auto
```

---

## 6. 扩缩容操作

### 6.1 手动扩缩容（即时生效）

```bash
# 扩容 backend 到 4 副本
kubectl scale deployment knowledge-system-backend \
  --replicas=4 -n knowledge-prod

# 扩容 frontend 到 5 副本
kubectl scale deployment knowledge-system-frontend \
  --replicas=5 -n knowledge-prod

# 扩容 celery-worker 到 4 副本
kubectl scale deployment knowledge-system-celery-worker \
  --replicas=4 -n knowledge-prod
```

### 6.2 HPA 自动扩缩容

```bash
# 查看当前 HPA 配置
kubectl get hpa -n knowledge-prod

# 查看 HPA 详细状态（含扩缩容历史）
kubectl describe hpa knowledge-system-backend -n knowledge-prod

# 临时调整 HPA 阈值
kubectl patch hpa knowledge-system-backend -n knowledge-prod \
  --type merge -p '{"spec":{"metrics":[{"type":"Resource","resource":{"name":"cpu","target":{"type":"Utilization","averageUtilization":60}}}]}}'
```

### 6.3 永久调整 HPA 范围

```yaml
# 编辑 values-prod.yaml
backend:
  hpa:
    enabled: true
    minReplicas: 4   # 原 4
    maxReplicas: 12  # 原 10 调整为 12
    targetCPUUtilizationPercentage: 65
```

```bash
helm upgrade knowledge-system ./deploy/helm \
  -f deploy/helm/values-prod.yaml -n knowledge-prod
```

### 6.4 数据库扩容（PVC 扩容）

```bash
# 在线扩容 PVC（前提：StorageClass 支持 allowVolumeExpansion）
kubectl patch pvc data-knowledge-system-postgres-0 -n knowledge-prod \
  -p '{"spec":{"resources":{"requests":{"storage":"100Gi"}}}}'

# 查看扩容状态
kubectl get pvc -n knowledge-prod -w
```

### 6.5 节点扩容

```bash
# 查看节点资源使用率
kubectl top nodes

# 查看节点 Pod 分布
kubectl get pods -n knowledge-prod -o wide --no-headers | awk '{print $7}' | sort | uniq -c

# 标记节点不可调度（维护前）
kubectl cordon <node-name>

# 驱逐节点 Pod（维护）
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data
```

---

## 7. 日志查看与排查

### 7.1 Pod 日志

```bash
# 查看 backend 日志
kubectl logs -f deployment/knowledge-system-backend -n knowledge-prod

# 查看 backend 所有副本日志
kubectl logs -l app.kubernetes.io/name=knowledge-system,app.kubernetes.io/component=backend \
  -n knowledge-prod --all-containers=true --tail=200

# 查看某次重启前的日志
kubectl logs knowledge-system-backend-xxxxx-yyyyy -n knowledge-prod --previous

# 查看迁移 Job 日志
kubectl logs job/db-migrate -n knowledge-prod
```

### 7.2 多容器 Pod 日志

```bash
# Pod 内多容器需指定容器名
kubectl logs <pod-name> -c backend -n knowledge-prod
kubectl logs <pod-name> -c frontend -n knowledge-prod
```

### 7.3 结构化日志查询（Loki / 云日志）

若集群已部署 Loki + Promtail：

```bash
# 查询最近 1 小时 backend 5xx 错误
logcli query --tail \
  '{namespace="knowledge-prod",app="backend"} |= "ERROR" | json | status_code >= 500' \
  --since 1h
```

### 7.4 事件查看

```bash
# 命名空间事件（Pod 调度、拉镜像、健康检查失败等）
kubectl get events -n knowledge-prod --sort-by='.lastTimestamp'

# 仅查看 Warning 事件
kubectl get events -n knowledge-prod --field-selector type=Warning
```

---

## 8. 日常运维任务

### 8.1 日常检查清单（每日）

```bash
# 1. Pod 状态
kubectl get pods -n knowledge-prod | grep -v Running

# 2. 资源使用率
kubectl top pods -n knowledge-prod --sort-by=cpu
kubectl top pods -n knowledge-prod --sort-by=memory

# 3. 事件告警
kubectl get events -n knowledge-prod --field-selector type=Warning --since 24h

# 4. 备份任务状态
kubectl get cronjob -n knowledge-prod
kubectl get jobs -n knowledge-prod --sort-by='.metadata.creationTimestamp' | tail -5

# 5. PVC 使用情况
kubectl get pvc -n knowledge-prod

# 6. 证书过期检查
kubectl get certificates -A -o custom-columns=NAME:.metadata.name,NOT_AFTER:.status.notAfter
```

### 8.2 数据库迁移

```bash
# 手动触发迁移（不通过 helm upgrade）
kubectl create job --from=cronjob/db-migrate \
  manual-migrate-$(date +%Y%m%d-%H%M) -n knowledge-prod

# 查看迁移日志
kubectl logs job/manual-migrate-xxx -n knowledge-prod

# 回滚迁移（helm hook）
helm rollback knowledge-system <revision> -n knowledge-prod
# post-rollback hook 会自动执行 alembic downgrade -1
```

### 8.3 重启 Pod（不触发 Helm 升级）

```bash
# 滚动重启 deployment
kubectl rollout restart deployment/knowledge-system-backend -n knowledge-prod

# 查看重启进度
kubectl rollout status deployment/knowledge-system-backend -n knowledge-prod
```

### 8.4 配置热更新（ConfigMap/Secret）

```bash
# 修改 Secret 后需手动重启关联 Pod
kubectl rollout restart deployment/knowledge-system-backend -n knowledge-prod
kubectl rollout restart deployment/knowledge-system-frontend -n knowledge-prod
```

### 8.5 清理完成的 Job

```bash
# 清理已完成的迁移 Job
kubectl delete jobs -n knowledge-prod --field-selector=status.successful=1

# 清理失败的 Job
kubectl delete jobs -n knowledge-prod --field-selector=status.failed=1
```

---

## 9. 卸载与清理

### 9.1 卸载 Chart（保留数据）

```bash
helm uninstall knowledge-system -n knowledge-prod

# 检查残留资源
kubectl get all -n knowledge-prod
kubectl get pvc -n knowledge-prod  # PVC 不会被 Helm 删除
```

### 9.2 完全清理（含数据，谨慎！）

```bash
# ⚠️ 警告：以下操作会删除所有数据，不可恢复！
# 操作前请确认已备份（见 BACKUP_RECOVERY.md）

# 1. 卸载 Chart
helm uninstall knowledge-system -n knowledge-prod

# 2. 删除 PVC（含数据）
kubectl delete pvc --all -n knowledge-prod

# 3. 删除命名空间（含所有资源）
kubectl delete namespace knowledge-prod

# 4. 删除备份存储（如有）
kubectl delete pvc -n knowledge-prod --all
```

### 9.3 清理 helm hook 资源

```bash
# Helm hook 创建的 Job 不会被自动清理
kubectl get jobs -n knowledge-prod
kubectl delete jobs -n knowledge-prod --all
```

---

## 10. 附录：常用 kubectl 速查

### 10.1 资源查看

```bash
# 概览
kubectl get all -n knowledge-prod
kubectl get pods,svc,ingress,pvc,hpa -n knowledge-prod

# 详细信息
kubectl describe pod <pod-name> -n knowledge-prod
kubectl describe deployment knowledge-system-backend -n knowledge-prod

# 资源使用
kubectl top pods -n knowledge-prod
kubectl top nodes
```

### 10.2 进入容器

```bash
# 进入 backend Pod
kubectl exec -it deployment/knowledge-system-backend -n knowledge-prod -- /bin/sh

# 进入 postgres Pod
kubectl exec -it statefulset/knowledge-system-postgres -n knowledge-prod -- psql -U postgres

# 进入 redis Pod
kubectl exec -it statefulset/knowledge-system-redis -n knowledge-prod -- redis-cli
```

### 10.3 端口转发（本地调试）

```bash
# 转发 backend 到本地 8000
kubectl port-forward svc/knowledge-system-backend 8000:8000 -n knowledge-prod

# 转发 postgres 到本地 5432
kubectl port-forward statefulset/knowledge-system-postgres 5432:5432 -n knowledge-prod
```

### 10.4 资源标签

```bash
# 查看资源标签
kubectl get pods -n knowledge-prod --show-labels

# 按 label 筛选
kubectl get pods -n knowledge-prod -l app.kubernetes.io/component=backend
kubectl get pods -n knowledge-prod -l deployment.slot=blue
```

### 10.5 Helm 速查

```bash
# 查看 release 历史
helm history knowledge-system -n knowledge-prod

# 查看 release 当前值
helm get values knowledge-system -n knowledge-prod
helm get values knowledge-system -n knowledge-prod --all

# 回滚到指定 revision
helm rollback knowledge-system <revision> -n knowledge-prod

# 查看渲染后的 manifest
helm get manifest knowledge-system -n knowledge-prod
```

### 10.6 故障排查命令组合

```bash
# Pod 异常：完整诊断
POD=<pod-name>
NS=knowledge-prod
kubectl describe pod $POD -n $NS
kubectl logs $POD -n $NS --previous --tail=100
kubectl get events -n $NS --field-selector involvedObject.name=$POD

# 节点异常
NODE=<node-name>
kubectl describe node $NODE
kubectl get pods -A --field-selector spec.nodeName=$NODE --no-headers | wc -l
```

---

## 相关文档

| 文档 | 说明 |
|---|---|
| [HELM_CHART_GUIDE.md](./HELM_CHART_GUIDE.md) | Helm Chart 完整参数说明 |
| [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) | 故障处理指南 |
| [RELEASE_SOP.md](./RELEASE_SOP.md) | 发布操作手册（蓝绿/金丝雀/回滚） |
| [BACKUP_RECOVERY.md](./BACKUP_RECOVERY.md) | 备份恢复手册 |
| [MONITORING_ALERTING.md](./MONITORING_ALERTING.md) | 监控告警手册 |
| [DR_RUNBOOK.md](../DR_RUNBOOK.md) | 灾难恢复演练手册 |
| [K8S_DEPLOYMENT_PLAN.md](../K8S_DEPLOYMENT_PLAN.md) | K8s 部署总体规划 |
