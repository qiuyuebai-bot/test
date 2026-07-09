# CI/CD 自动部署到 K8s 实施方案

> 编制日期：2026-07-08 · 深度优先策略 · 聚焦 CI/CD 自动部署闭环

---

## Context（背景与目标）

**问题**：项目已有完整的 CI（lint/test/security/coverage）与镜像构建流水线（docker-images.yml 构建推送 GHCR + Trivy 扫描 + Cosign 签名 + 更新 Helm values + 通知 ArgoCD），但**缺少从镜像构建到 K8s 实际部署的自动化衔接**——当前仅在 main 分支触发，依赖 ArgoCD GitOps 拉取，无 develop/feature 分支部署、无 prod 审批门禁、无独立回滚 workflow、无部署后健康验证。

**目标**：建立 `代码提交 → CI 门禁 → 镜像构建扫描 → Helm 部署 → 健康验证 → 通知` 的完整闭环，支持 dev/staging/prod 三环境，prod 需人工审批，失败自动回滚，支持手动回滚到任意历史版本。

**约束**：
- 不动 `deploy/helm/` Chart 结构（已冻结）
- 复用现有 `deploy/scripts/smoke-test.sh`（6 端点 + 重试）与 `rollback.sh`（Helm revision 回滚）
- 复用现有 `values-dev.yaml`/`values-staging.yaml`/`values-prod.yaml` 多环境覆盖
- 不破坏现有 ArgoCD GitOps 模式（保留为备选，新增直推 Helm 模式为默认）

---

## 现状基线（已核查）

| 项 | 状态 | 证据 |
|---|---|---|
| CI 流水线 | ✅ 完整 | `ci.yml`：lint、typecheck、pytest（cov-fail-under=60）、vitest、bandit、pip-audit、npm audit |
| 镜像构建 | ✅ 完整 | `docker-images.yml`：多平台构建、Trivy HIGH/CRITICAL 阻断、Cosign 签名 |
| Helm Chart | ✅ 完整 | `deploy/helm/`：frontend/backend/redis、HPA、CronJob 备份、3 套环境 values |
| 冒烟测试 | ✅ 可复用 | `smoke-test.sh --host` 参数化，6 端点 + 重试 + 退出码 |
| 回滚脚本 | ✅ 可复用 | `rollback.sh --release --namespace --revision`，支持 dry-run + 列版本 |
| ArgoCD 集成 | ✅ 已有 | `deploy/argocd/`，prod 禁用 auto-sync |
| **自动部署** | ❌ 缺失 | 无 `helm upgrade` 步骤，仅 commit values + 通知 ArgoCD |
| **多环境触发** | ❌ 缺失 | 仅 main 分支触发，无 develop/feature 分支部署 |
| **Prod 审批** | ❌ 缺失 | 无 GitHub environment 审批门禁 |
| **独立回滚 workflow** | ❌ 缺失 | 仅手动脚本，无 CI 触发 |

---

## 实施步骤

### 任务 1：新建 `.github/workflows/deploy.yml`（可复用部署 workflow）

**设计**：作为 `workflow_call` 被docker-images.yml 调用，接收 `image-tag` 与 `environment` 参数。

**Stage 设计**：
```
workflow_call inputs: image-tag, environment, image-digest
jobs:
  deploy:
    environment: ${{ inputs.environment }}   # prod 在此阻塞待审批
    runs-on: ubuntu-latest
    steps:
      1. checkout
      2. azure/setup-helm@v4, azure/setup-kubectl@v4
      3. 写 kubeconfig（从 secrets.KUBECONFIG_<ENV> base64 解码）
      4. 映射环境 → namespace：dev→knowledge-dev, staging→knowledge-staging, prod→knowledge-prod
      5. helm upgrade --install knowledge-system ./deploy/helm \
           -f deploy/helm/values.yaml -f deploy/helm/values-<env>.yaml \
           --set images.frontend.tag=${{ inputs.image-tag }} \
           --set images.backend.tag=${{ inputs.image-tag }} \
           -n knowledge-<env> --create-namespace --atomic --timeout 5m
      6. kubectl rollout status deploy/knowledge-system-backend -n knowledge-<env> --timeout=300s
      7. kubectl rollout status deploy/knowledge-system-frontend -n knowledge-<env> --timeout=300s
      8. kubectl port-forward svc/knowledge-system-backend 8000:8000 -n knowledge-<env> &
      9. ./deploy/scripts/smoke-test.sh --host http://localhost:8000 --retry 5 --interval 10
      10. 失败时 helm rollback knowledge-system -n knowledge-<env>（--atomic 已含自动回滚，此为兜底）
  notify:
    needs: deploy
    if: always()
    steps: Slack webhook 推送部署结果（成功/失败 + 环境 + 镜像 tag）
```

**关键设计点**：
- `--atomic` 参数：Helm 部署失败自动回滚到上一 revision
- `--set` 注入 tag：避免 commit values 产生 git 噪音（与现有 update-helm-values job 互斥，仅 main 用 ArgoCD 模式时保留 commit）
- `environment` 关键字：GitHub 原生审批门禁，prod 在 Repo Settings 配置 required reviewers
- smoke-test 失败即整个 job 失败，触发 `--atomic` 回滚

### 任务 2：改造 `.github/workflows/docker-images.yml`

**改动点**：
1. **扩展触发分支**：`branches: [main]` → `branches: [main, develop, 'feature/**']`
2. **末尾新增 deploy job**：`needs: [build-frontend, build-backend, scan-frontend, scan-backend]`（Trivy 失败即阻断部署），根据 `github.ref` 映射 environment 后 `uses: ./.github/workflows/deploy.yml`

**分支 → 环境映射逻辑**（在 deploy job 中）：
```yaml
- name: Map branch to environment
  id: env
  run: |
    if [[ "${{ github.ref }}" == "refs/heads/main" ]]; then
      echo "environment=production" >> $GITHUB_OUTPUT
    elif [[ "${{ github.ref }}" == "refs/heads/develop" ]]; then
      echo "environment=staging" >> $GITHUB_OUTPUT
    else
      echo "environment=development" >> $GITHUB_OUTPUT
    fi
```

3. **保留现有 update-helm-values + notify-argocd**：仅在 main 分支运行（ArgoCD GitOps 模式作为备选），新增的 deploy job 在所有分支运行（直推 Helm 模式为默认）。两者不冲突——main 分支同时触发 ArgoCD 模式与直推模式，直推更快（无需 commit + ArgoCD pull）。

### 任务 3：新建 `.github/workflows/rollback.yml`（手动回滚）

**设计**：`workflow_dispatch` 触发，支持回滚到指定环境的历史 revision。

```
workflow_dispatch inputs: environment, revision(可选)
jobs:
  rollback:
    environment: ${{ inputs.environment }}   # prod 回滚也需审批
    steps:
      1. checkout
      2. setup helm + kubectl
      3. 写 kubeconfig
      4. 若指定 revision：./deploy/scripts/rollback.sh --release knowledge-system --namespace knowledge-<env> --revision <N>
         否则：./deploy/scripts/rollback.sh --release knowledge-system --namespace knowledge-<env>（回滚到上一版本）
      5. kubectl rollout status 验证
      6. port-forward + smoke-test 验证
  notify: 推送回滚结果
```

### 任务 4：GitHub Repo 配置清单（文档化）

在方案文档中明确列出需在 GitHub Repo Settings 配置的项：

**Secrets（按环境隔离）**：
- `KUBECONFIG_DEVELOPMENT` — dev 集群 kubeconfig（base64）
- `KUBECONFIG_STAGING` — staging 集群 kubeconfig（base64）
- `KUBECONFIG_PRODUCTION` — prod 集群 kubeconfig（base64）
- `SLACK_WEBHOOK_URL` — 部署通知 webhook
- `GHCR_BOT_TOKEN` — 已有，镜像拉取

**Variables**：
- `COVERAGE_THRESHOLD` — 覆盖率门禁阈值（默认 60，渐进上调）
- `ARGOCD_API_URL` / `ARGOCD_APP_NAME` — 已有
- `COSIGN_ENABLED` — 已有

**Repo Settings**：
- `production` environment：required reviewers + deployment branch=main
- `staging` environment：deployment branch=develop
- `development` environment：无审批
- Required status checks：`lint`、`backend-test`、`frontend-test`、`security`、`build-frontend`、`build-backend`

### 任务 5：新建 `.github/DEPLOYMENT.md` 部署指南文档

涵盖：
- 分支策略与环境映射表
- 首次部署前置（GitHub Secrets/Variables/Environment 配置）
- 部署流程图（提交→CI→构建→扫描→部署→验证→通知）
- 手动回滚操作（workflow_dispatch 触发）
- ArgoCD GitOps vs 直推 Helm 双模式说明
- 故障排查（smoke-test 失败、rollout 超时、镜像拉取失败）

---

## 关键文件清单

| 文件 | 操作 | 说明 |
|---|---|---|
| `.github/workflows/deploy.yml` | **新建** | 可复用部署 workflow（workflow_call） |
| `.github/workflows/rollback.yml` | **新建** | 手动回滚 workflow（workflow_dispatch） |
| `.github/workflows/docker-images.yml` | **改造** | 扩展触发分支 + 末尾调用 deploy.yml |
| `.github/workflows/ci.yml` | **微调** | 覆盖率阈值参数化（读 Variables） |
| `.github/DEPLOYMENT.md` | **新建** | 部署指南文档 |

**复用的现有文件（不修改）**：
- `deploy/scripts/smoke-test.sh` — 冒烟测试（6 端点 + 重试）
- `deploy/scripts/rollback.sh` — Helm 回滚（revision + dry-run + rollout wait）
- `deploy/helm/values-{dev,staging,prod}.yaml` — 多环境 values 覆盖
- `deploy/helm/` Chart 结构 — 全程冻结不动

---

## 验收标准

1. **feature 分支提交** → CI 全绿 + 镜像构建扫描通过 → 5 分钟内 dev 自动部署 + smoke-test 通过
2. **develop 合并** → staging 自动部署，`kubectl rollout status` 通过
3. **main 合并** → prod 部署阻塞待审批，审批后部署 + `/health/ready` 返回 200
4. **smoke-test 失败** → 自动 `helm rollback` + Slack 告警
5. **手动触发 rollback.yml** → 3 分钟内回退到指定 revision + smoke-test 验证
6. **覆盖率 < 60% 或 Trivy HIGH/CRITICAL** → 部署被阻断（上游 job 失败）
7. **prod 部署** → 必须经过 `production` environment required reviewers 审批

---

## 验证方法

1. **dry-run 验证**：在 deploy.yml 的 helm upgrade 步骤加 `--dry-run` 标志先验证模板渲染
2. **dev 环境实测**：提交 feature 分支，观察 GitHub Actions 部署日志 + dev 集群 `kubectl get pods`
3. **smoke-test 验证**：部署后手动执行 `./deploy/scripts/smoke-test.sh --host http://<dev-ingress>`
4. **回滚验证**：触发 rollback.yml，验证 revision 回退 + smoke-test 通过
5. **审批门禁验证**：main 分支提交，确认 prod 部署在 GitHub environment 审批处阻塞

---

## 风险与应对

| 风险 | 应对 |
|---|---|
| kubeconfig 泄露 | 按环境隔离 Secret，使用短效 token 或 OIDC provider（进阶） |
| prod 部署误操作 | `production` environment required reviewers + `--atomic` 自动回滚 |
| ArgoCD 与直推模式冲突 | main 分支优先直推（更快），ArgoCD 作为 GitOps 观察备选，不强制 sync |
| Helm 部署超时 | `--timeout 5m` + rollout `--timeout=300s` + smoke-test `--retry 5` |
| 镜像拉取失败 | GHCR imagePullSecrets 在 values-prod.yaml 已配置 |

---

*本方案聚焦 CI/CD 自动部署闭环，深度实施至生产可用。其他工程化维度（性能压测、审计日志、API 文档导出）按用户选择暂不纳入本轮，可后续按需扩展。*
