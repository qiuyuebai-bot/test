# 部署指南

> 本文档描述 CI/CD 自动部署到 Kubernetes 的完整流程、配置方法与故障排查。

---

## 一、分支策略与环境映射

| 分支 | 环境 | 命名空间 | 触发方式 | 审批 |
|---|---|---|---|---|
| `feature/**` | development | `knowledge-dev` | push 自动 | 否 |
| `develop` | staging | `knowledge-staging` | push 自动 | 否 |
| `main` | production | `knowledge-prod` | push 自动 | **是**（GitHub Environment required reviewers） |
| `v*.*.*` tag | production | `knowledge-prod` | tag 自动 | 是 |

**流程**：代码提交 → CI（lint/test/security）→ 镜像构建 + Trivy 扫描 → Helm 部署 → rollout 等待 → 冒烟测试 → Slack 通知。

---

## 二、首次部署前置配置

### 2.1 GitHub Secrets（按环境隔离）

在 Repo Settings → Secrets and variables → Actions → Secrets 中添加：

| Secret 名 | 说明 | 示例 |
|---|---|---|
| `KUBECONFIG_DEVELOPMENT` | dev 集群 kubeconfig（base64 编码） | `base64 -w0 ~/.kube/config-dev` |
| `KUBECONFIG_STAGING` | staging 集群 kubeconfig（base64 编码） | `base64 -w0 ~/.kube/config-staging` |
| `KUBECONFIG_PRODUCTION` | prod 集群 kubeconfig（base64 编码） | `base64 -w0 ~/.kube/config-prod` |
| `SLACK_WEBHOOK_URL` | 部署通知 Slack webhook URL | `https://hooks.slack.com/services/...` |
| `GHCR_BOT_TOKEN` | GHCR 镜像拉取 token（已有） | `ghp_xxx` |

**生成 kubeconfig base64**：
```bash
# Linux/macOS
base64 -w0 ~/.kube/config > kubeconfig-b64.txt

# Windows PowerShell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("$env:USERPROFILE\.kube\config")) > kubeconfig-b64.txt
```

### 2.2 GitHub Variables

在 Repo Settings → Secrets and variables → Actions → Variables 中添加：

| Variable 名 | 默认值 | 说明 |
|---|---|---|
| `COVERAGE_THRESHOLD` | `60` | 后端覆盖率门禁（渐进上调至 80） |
| `ARGOCD_API_URL` | （空） | ArgoCD API 地址（GitOps 模式可选） |
| `ARGOCD_APP_NAME` | `knowledge-system` | ArgoCD Application 名 |
| `COSIGN_ENABLED` | `false` | 是否启用镜像签名 |

### 2.3 GitHub Environments

在 Repo Settings → Environments 中创建：

| Environment | 部署分支 | Required reviewers | 等待时间 |
|---|---|---|---|
| `development` | `feature/**` | 无 | 0 |
| `staging` | `develop` | 无 | 0 |
| `production` | `main` | **配置 1-3 名审批人** | 可选配置等待时间 |

### 2.4 Required Status Checks

在 Repo Settings → Branches → Branch protection rules → `main` 中配置 required status checks：
- `Lint & Type Check`
- `Backend Tests`
- `Frontend Tests`
- `Security Scan`
- `Build & Push Frontend Image`
- `Build & Push Backend Image`

---

## 三、部署流程

### 3.1 自动部署（push 触发）

```
git push origin feature/new-function
  ↓
GitHub Actions 触发 docker-images.yml
  ↓
[并行] Build Frontend Image + Build Backend Image
  ↓
[并行] Trivy Scan Frontend + Trivy Scan Backend（HIGH/CRITICAL 阻断）
  ↓
Deploy to Kubernetes（调用 deploy.yml）
  ↓
[prod 阻塞] GitHub Environment 审批
  ↓
helm upgrade --install --atomic
  ↓
kubectl rollout status（backend + frontend）
  ↓
port-forward + smoke-test.sh（6 端点验证）
  ↓
Slack 通知（成功/失败）
  ↓
失败自动 helm rollback
```

### 3.2 手动构建（workflow_dispatch）

在 Actions → "Docker Images" → Run workflow 手动触发，不触发部署。

### 3.3 手动回滚（rollback.yml）

在 Actions → "Rollback Deployment" → Run workflow：
1. 选择 `environment`（development/staging/production）
2. 填写 `revision`（留空回滚到上一版本，填数字回滚到指定 revision）
3. 可选勾选 `skip-smoke-test`（紧急回滚跳过验证）
4. 运行 → 复用 `deploy/scripts/rollback.sh` → rollout 等待 → smoke-test → 通知

---

## 四、双模式说明

项目支持两种部署模式，**直推 Helm 为默认**，ArgoCD GitOps 为备选：

### 直推 Helm 模式（默认，所有分支）
- `deploy.yml` 直接执行 `helm upgrade --install`
- 无需 commit values，通过 `--set` 注入 image tag
- 部署快（无需 ArgoCD pull 延迟）
- 适用于：feature/develop/main 全部分支

### ArgoCD GitOps 模式（备选，仅 main）
- `update-helm-values` job 将 image tag commit 到 `deploy/helm/values.yaml`
- `notify-argocd` job 触发 ArgoCD refresh
- ArgoCD 拉取 Git 变更并 sync
- 适用于：需要 GitOps 审计追踪的生产环境
- **注意**：两者不冲突，main 分支同时触发两种模式，直推先完成，ArgoCD 作为兜底

### 切换到纯 ArgoCD 模式
如需禁用直推、仅用 ArgoCD：
1. 在 `docker-images.yml` 的 deploy job 添加 `if: false`
2. 确保 `ARGOCD_API_URL` 和 `ARGOCD_TOKEN` 已配置
3. ArgoCD Application 配置 auto-sync（prod 仍建议 manual sync）

---

## 五、故障排查

### 5.1 部署失败：Helm upgrade 超时

**症状**：`helm upgrade --atomic --timeout 5m` 超时

**排查**：
```bash
# 查看 release 历史
helm history knowledge-system -n knowledge-<env>

# 查看 pod 状态
kubectl get pods -n knowledge-<env>
kubectl describe pod <pod-name> -n knowledge-<env>

# 查看事件
kubectl get events -n knowledge-<env> --sort-by='.lastTimestamp'
```

**常见原因**：
- 镜像拉取失败（检查 imagePullSecrets）
- 资源不足（检查 requests/limits）
- 健康检查失败（检查 readinessProbe）

### 5.2 部署失败：rollout status 超时

**症状**：`kubectl rollout status` 超时（300s）

**排查**：
```bash
# 查看 rollout 状态
kubectl rollout status deploy/knowledge-system-backend -n knowledge-<env>

# 查看 ReplicaSet
kubectl get rs -n knowledge-<env>

# 查看新 pod 日志
kubectl logs <new-pod> -n knowledge-<env> --tail=100
```

### 5.3 冒烟测试失败

**症状**：`smoke-test.sh` 返回非 0

**排查**：
```bash
# 手动执行冒烟测试
./deploy/scripts/smoke-test.sh --host http://localhost:8000 --verbose

# 检查 backend 日志
kubectl logs deploy/knowledge-system-backend -n knowledge-<env> --tail=200

# 检查数据库连接
kubectl exec -it deploy/knowledge-system-backend -n knowledge-<env> -- python -c "from app.database import engine; print(engine.url)"
```

**自动回滚**：smoke-test 失败后 deploy.yml 的 `Rollback on failure` step 自动执行 `helm rollback`。

### 5.4 kubeconfig 认证失败

**症状**：`Unable to connect to the server: dial tcp`

**排查**：
- 确认 `KUBECONFIG_<ENV>` secret 已配置且为 base64 编码
- 确认集群 API server 可达（GitHub Actions runner 需网络可达）
- 确认 ServiceAccount 有 cluster-admin 或命名空间 admin 权限

### 5.5 prod 审批未触发

**症状**：main 分支推送后部署未在审批处阻塞

**排查**：
- 确认 `production` environment 已在 Repo Settings 创建
- 确认 required reviewers 已配置
- 确认 deployment branch 限制为 `main`

---

## 六、回滚操作

### 6.1 通过 CI/CD 回滚（推荐）

1. 进入 Actions → "Rollback Deployment"
2. 点击 "Run workflow"
3. 选择环境、填写 revision（可选）
4. 运行并等待 smoke-test 验证

### 6.2 手动回滚（集群内）

```bash
# 查看历史 revision
helm history knowledge-system -n knowledge-prod

# 回滚到上一版本
helm rollback knowledge-system -n knowledge-prod

# 回滚到指定版本
helm rollback knowledge-system 5 -n knowledge-prod

# 等待 rollout
kubectl rollout status deploy/knowledge-system-backend -n knowledge-prod
kubectl rollout status deploy/knowledge-system-frontend -n knowledge-prod

# 冒烟测试
./deploy/scripts/smoke-test.sh --host http://<prod-ingress>
```

### 6.3 回滚到指定镜像 tag

```bash
helm upgrade --install knowledge-system ./deploy/helm \
  -f deploy/helm/values.yaml -f deploy/helm/values-prod.yaml \
  --set images.frontend.tag=<旧tag> \
  --set images.backend.tag=<旧tag> \
  -n knowledge-prod --atomic --timeout 5m
```

---

## 七、监控与可观测性

部署后可通过以下方式监控：

- **Prometheus 指标**：`/metrics` 端点（Prometheus middleware）
- **健康检查**：`/health/live`（存活）、`/health/ready`（就绪）
- **系统信息**：`/api/v1/info`（版本、uptime）
- **Sentry**：前端错误聚合（DSN 配置后启用）
- **K8s HPA**：`kubectl get hpa -n knowledge-<env>`
- **Pod 日志**：`kubectl logs -n knowledge-<env> -l app.kubernetes.io/name=knowledge-system`

---

## 八、相关文件

| 文件 | 说明 |
|---|---|
| `.github/workflows/ci.yml` | CI 流水线（lint/test/security/coverage） |
| `.github/workflows/docker-images.yml` | 镜像构建 + 扫描 + 部署触发 |
| `.github/workflows/deploy.yml` | 可复用部署 workflow（helm upgrade + smoke-test） |
| `.github/workflows/rollback.yml` | 手动回滚 workflow |
| `deploy/helm/` | Helm Chart（冻结不动） |
| `deploy/helm/values-{dev,staging,prod}.yaml` | 多环境 values 覆盖 |
| `deploy/scripts/smoke-test.sh` | 冒烟测试脚本（6 端点 + 重试） |
| `deploy/scripts/rollback.sh` | Helm 回滚脚本（revision + dry-run） |
| `deploy/argocd/` | ArgoCD Application（GitOps 备选模式） |
