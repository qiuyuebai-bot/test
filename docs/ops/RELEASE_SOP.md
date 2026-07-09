# 发布操作手册（SOP）

> 版本：v1.0 · 编制日期：2026-07-07
> 适用项目：领域知识个性化生成与多智能体协同决策系统
> 关联文档：[DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)、[TROUBLESHOOTING.md](./TROUBLESHOOTING.md)

本手册覆盖三种发布策略的标准化操作流程：**蓝绿发布**、**金丝雀发布**、**Helm 回滚**。每类发布包含前置检查清单、操作步骤、验证清单、回滚预案。

---

## 目录

1. [发布策略选择](#1-发布策略选择)
2. [发布前置检查](#2-发布前置检查)
3. [蓝绿发布 SOP](#3-蓝绿发布-sop)
4. [金丝雀发布 SOP](#4-金丝雀发布-sop)
5. [Helm 回滚 SOP](#5-helm-回滚-sop)
6. [Argo Rollouts 自动化发布](#6-argo-rollouts-自动化发布)
7. [冒烟测试](#7-冒烟测试)
8. [附录：发布决策树](#8-附录发布决策树)

---

## 1. 发布策略选择

| 策略 | 适用场景 | 切流速度 | 回滚速度 | 资源开销 | 复杂度 |
|---|---|---|---|---|---|
| **常规 Helm upgrade** | 日常小变更、配置调整 | 滚动更新（~30s） | helm rollback（~30s） | 低（滚动） | ★ |
| **蓝绿发布** | 重大版本升级、需要快速回退 | < 5s（router 切换） | < 5s（切回旧 slot） | 高（双倍资源） | ★★ |
| **金丝雀发布** | 风险较高、需观察指标 | 渐进（10→25→50→100%） | 调整 weight 到 0 | 中（1+N 副本） | ★★★ |
| **Argo Rollouts** | 自动化、指标驱动 | 自动渐进 | 自动回滚 | 中 | ★★★ |

### 选择建议

- **小变更（配置、文案、UI 调整）** → 常规 helm upgrade
- **中变更（新增 API、数据库迁移）** → 蓝绿发布
- **大变更（架构调整、新功能上线）** → 金丝雀发布
- **持续部署** → Argo Rollouts（CI/CD 集成）

---

## 2. 发布前置检查

每次发布前必须完成以下检查：

### 2.1 代码与 Chart 验证

```bash
# 1. 确认代码已合并到 main 分支
git checkout main && git pull origin main

# 2. Chart 语法检查
helm lint deploy/helm

# 3. 综合校验（16 项检查）
python deploy/helm/validate_chart.py

# 4. 模板渲染检查（确认无敏感信息泄漏）
helm template knowledge-system deploy/helm \
  -f deploy/helm/values-prod.yaml \
  -n knowledge-prod > /tmp/render-prod.yaml
grep -E "password|secret|key" /tmp/render-prod.yaml | head -20
```

### 2.2 镜像准备

```bash
# 1. 确认镜像已构建并推送
docker pull registry.cn-hangzhou.aliyuncs.com/knowledge-system/backend:1.1.0
docker pull registry.cn-hangzhou.aliyuncs.com/knowledge-system/frontend:1.1.0

# 2. 镜像漏洞扫描（Trivy）
trivy image registry.cn-hangzhou.aliyuncs.com/knowledge-system/backend:1.1.0
# 期望：无 HIGH/CRITICAL 漏洞
```

### 2.3 数据库备份（重要变更必做）

```bash
# 手动触发一次备份（不等待定时任务）
kubectl create job manual-backup-$(date +%Y%m%d-%H%M) \
  --from=cronjob/knowledge-system-backup -n knowledge-prod

# 监控备份完成
kubectl get jobs -n knowledge-prod -w
# 期望：COMPLETIONS=1/1

# 验证备份文件
kubectl logs job/manual-backup-xxx -n knowledge-prod | grep "备份成功"
```

### 2.4 当前状态快照

```bash
# 1. 当前 Pod 状态
kubectl get pods -n knowledge-prod -o wide > /tmp/pods-before-release.txt

# 2. 当前 release 历史
helm history knowledge-system -n knowledge-prod > /tmp/helm-history-before.txt

# 3. 当前 HPA 状态
kubectl get hpa -n knowledge-prod > /tmp/hpa-before.txt

# 4. 当前数据库迁移版本
kubectl exec statefulset/knowledge-system-postgres -n knowledge-prod -- \
  psql -U postgres -c "SELECT version_num FROM alembic_version;" > /tmp/alembic-version-before.txt
```

### 2.5 通知与窗口

- 在团队群通知发布计划（开始时间、预计时长、影响范围）
- 选择低峰时段（建议 22:00-02:00）
- 确认 On-Call 工程师在线

---

## 3. 蓝绿发布 SOP

### 3.1 原理

```
发布前：
  router Service → slot=blue → blue release（当前版本）

发布中（部署到 green slot）：
  blue release  → slot=blue  → 承接流量
  green release → slot=green → 等待就绪

切换后：
  router Service → slot=green → green release（新版本）
  blue release 保留用于回退
```

### 3.2 操作步骤

#### 步骤 1：确认当前活跃 slot

```bash
# 查看当前 router Service 指向哪个 slot
kubectl get svc knowledge-system-router -n knowledge-prod \
  -o jsonpath='{.spec.selector}'

# 输出示例：{"app.kubernetes.io/name":"knowledge-system","deployment.slot":"blue"}
# 当前活跃 slot = blue
```

#### 步骤 2：部署到非活跃 slot

```bash
# 假设当前活跃是 blue，部署到 green
bash deploy/scripts/blue-green-deploy.sh \
  --release knowledge-system \
  --namespace knowledge-prod \
  --chart ./deploy/helm \
  --values deploy/helm/values-prod.yaml \
  --set deployment.slot=green \
  --set images.backend.tag=1.1.0 \
  --set images.frontend.tag=1.1.0
```

脚本自动执行：
1. 部署 `knowledge-system-green` release（不影响流量）
2. 等待所有 Pod 就绪（默认等待 5 分钟）
3. 执行冒烟测试（6 个端点）
4. 如全部通过，提示用户确认切换

#### 步骤 3：确认新版本就绪

```bash
# 查看 green slot Pod 状态
kubectl get pods -n knowledge-prod -l deployment.slot=green

# 直接测试 green 版本（通过 port-forward）
kubectl port-forward svc/knowledge-system-green-backend 18000:8000 -n knowledge-prod
curl http://localhost:18000/health/ready
curl http://localhost:18000/api/v1/info
```

#### 步骤 4：切换流量到新版本

```bash
# 确认无误后，手动切换 router Service
kubectl patch svc knowledge-system-router -n knowledge-prod \
  --type json -p='[{"op":"replace","path":"/spec/selector/deployment.slot","value":"green"}]'

# 验证流量已切换
kubectl get svc knowledge-system-router -n knowledge-prod -o jsonpath='{.spec.selector}'
# 输出：{"deployment.slot":"green",...}

# 测试生产域名
curl https://knowledge-system.example.com/health/ready
curl https://knowledge-system.example.com/api/v1/info
```

#### 步骤 5：观察与清理

```bash
# 观察 5-10 分钟，确认无异常
kubectl get pods -n knowledge-prod -w
kubectl logs -l deployment.slot=green -n knowledge-prod --tail=50

# 确认稳定后清理旧 slot
bash deploy/scripts/blue-green-deploy.sh \
  --release knowledge-system \
  --namespace knowledge-prod \
  --cleanup-old
# 或手动 helm uninstall knowledge-system-blue -n knowledge-prod
```

### 3.3 验证清单

- [ ] green slot 所有 Pod Running 且 READY 1/1
- [ ] 冒烟测试 6 项全部通过
- [ ] router Service selector 已切换到 green
- [ ] 生产域名访问正常（/health/ready 返回 200）
- [ ] 监控指标正常（错误率 < 1%、P99 < 2s）
- [ ] 5-10 分钟观察期无异常告警

### 3.4 蓝绿回滚预案

如新版本异常，**5 秒内切回旧版本**：

```bash
# 立即切回 blue slot
kubectl patch svc knowledge-system-router -n knowledge-prod \
  --type json -p='[{"op":"replace","path":"/spec/selector/deployment.slot","value":"blue"}]'

# 验证
curl https://knowledge-system.example.com/health/ready
```

注意：数据库迁移若已执行，回滚后需检查兼容性。建议使用**向后兼容的迁移**（先加列后删列）。

---

## 4. 金丝雀发布 SOP

### 4.1 原理

```
主 Ingress     → 主 release     → 承载 (100% - weight) 流量
金丝雀 Ingress → 金丝雀 release → 承载 weight 流量

渐进切流：10% → 25% → 50% → 100%
每步观察指标：错误率 < 5%、P99 < 2s
```

### 4.2 操作步骤

#### 步骤 1：初始部署金丝雀（10% 流量）

```bash
bash deploy/scripts/canary-deploy.sh \
  --release knowledge-system \
  --namespace knowledge-prod \
  --chart ./deploy/helm \
  --values deploy/helm/values-prod.yaml \
  --set images.backend.tag=1.1.0 \
  --set images.frontend.tag=1.1.0 \
  --host knowledge-system.example.com \
  --weight 10
```

脚本自动：
1. 部署 `knowledge-system-canary` release（禁用数据库、Redis、备份等共享资源）
2. 创建金丝雀 Ingress（带 `nginx.ingress.kubernetes.io/canary-weight: "10"` 注解）
3. 等待 Pod 就绪
4. 10% 流量切到金丝雀

#### 步骤 2：观察指标（5-10 分钟）

```bash
# 1. 查看 Pod 状态
kubectl get pods -n knowledge-prod -l deployment.slot=canary

# 2. 查看金丝雀日志
kubectl logs -l deployment.slot=canary -n knowledge-prod --tail=30

# 3. 查看 Prometheus 指标
# 访问 Grafana，查看 ks-api Dashboard，关注：
#   - 5xx 错误率（金丝雀 vs 主版本）
#   - P99 延迟（金丝雀 vs 主版本）
#   - QPS（金丝雀 vs 主版本）

# 4. 用户反馈收集
# 关注客服群、用户反馈渠道
```

#### 步骤 3：推进金丝雀（10 → 25 → 50 → 100）

```bash
# 推进到 25%
bash deploy/scripts/canary-deploy.sh \
  --release knowledge-system \
  --namespace knowledge-prod \
  --weight 25 \
  --promote

# 观察 5-10 分钟...

# 推进到 50%
bash deploy/scripts/canary-deploy.sh \
  --release knowledge-system \
  --namespace knowledge-prod \
  --weight 50 \
  --promote

# 观察 5-10 分钟...

# 推进到 100%
bash deploy/scripts/canary-deploy.sh \
  --release knowledge-system \
  --namespace knowledge-prod \
  --weight 100 \
  --promote
```

#### 步骤 4：完成金丝雀（提升为主版本）

```bash
# 将金丝雀版本提升为主 release
bash deploy/scripts/canary-deploy.sh \
  --release knowledge-system \
  --namespace knowledge-prod \
  --promote \
  --finalize
```

脚本自动：
1. helm upgrade 主 release 到新版本
2. 等待主 release rollout 完成
3. 清理金丝雀 release 与 Ingress

#### 步骤 5：自动模式（可选）

```bash
# 自动渐进式推进（10→25→50→100，每步间隔 60 秒）
bash deploy/scripts/canary-deploy.sh \
  --release knowledge-system \
  --namespace knowledge-prod \
  --chart ./deploy/helm \
  --values deploy/helm/values-prod.yaml \
  --set images.backend.tag=1.1.0 \
  --host knowledge-system.example.com \
  --auto \
  --interval 60
```

### 4.3 验证清单

- [ ] 金丝雀 Pod Running 且 READY 1/1
- [ ] 金丝雀 Ingress 已创建（canary 注解正确）
- [ ] 流量切分比例符合预期（通过日志 QPS 验证）
- [ ] 每步观察期指标正常（错误率 < 5%、P99 < 2s）
- [ ] 最终 100% 切流后无异常
- [ ] 主 release 已升级到新版本
- [ ] 金丝雀资源已清理

### 4.4 金丝雀回滚预案

如某步骤指标异常，**立即回滚**：

```bash
# 立即将金丝雀流量降到 0
bash deploy/scripts/canary-deploy.sh \
  --release knowledge-system \
  --namespace knowledge-prod \
  --weight 0 \
  --promote

# 清理金丝雀资源
bash deploy/scripts/canary-deploy.sh \
  --release knowledge-system \
  --namespace knowledge-prod \
  --promote \
  --finalize
# 或手动：helm uninstall knowledge-system-canary -n knowledge-prod
```

---

## 5. Helm 回滚 SOP

### 5.1 适用场景

- 常规 helm upgrade 后发现问题
- 蓝绿/金丝雀不可用时的最后手段
- 配置回滚（无需镜像回滚）

### 5.2 操作步骤

#### 步骤 1：查看历史 revision

```bash
bash deploy/scripts/rollback.sh \
  --release knowledge-system \
  --namespace knowledge-prod \
  --list

# 或直接使用 helm 命令
helm history knowledge-system -n knowledge-prod
```

输出示例：
```
REVISION        UPDATED                         STATUS          CHART           APP VERSION    DESCRIPTION
1               Mon Jul  7 10:00:00 2026        superseded      knowledge-1.0.0  1.0.0          Install complete
2               Mon Jul  7 14:00:00 2026        superseded      knowledge-1.0.0  1.0.0          Upgrade complete
3               Mon Jul  7 18:00:00 2026        deployed        knowledge-1.0.0  1.0.0          Upgrade complete (当前)
```

#### 步骤 2：对比当前与目标 revision

```bash
# 查看当前 revision 的 values
helm get values knowledge-system -n knowledge-prod --revision 3

# 查看上一个 revision 的 values
helm get values knowledge-system -n knowledge-prod --revision 2

# diff 两个 revision
diff <(helm get values knowledge-system -n knowledge-prod --revision 2 --all) \
     <(helm get values knowledge-system -n knowledge-prod --revision 3 --all)
```

#### 步骤 3：执行回滚

```bash
# 方式 1：使用脚本（推荐，含等待与验证）
bash deploy/scripts/rollback.sh \
  --release knowledge-system \
  --namespace knowledge-prod \
  --revision 2

# 方式 2：直接使用 helm 命令
helm rollback knowledge-system 2 -n knowledge-prod
```

脚本自动：
1. 执行 `helm rollback`
2. 触发 post-rollback hook（执行 `alembic downgrade -1` 回滚数据库迁移）
3. 等待 Deployment rollout 完成（默认 300 秒）
4. 输出结果

#### 步骤 4：验证回滚

```bash
# 1. 确认 release 状态
helm history knowledge-system -n knowledge-prod | tail -3
# 期望：最新 revision 状态为 deployed

# 2. 确认 Pod 已切换
kubectl get pods -n knowledge-prod -w
# 期望：所有 Pod RollingUpdate 完成

# 3. 冒烟测试
bash deploy/scripts/smoke-test.sh \
  --host https://knowledge-system.example.com

# 4. 确认数据库迁移版本
kubectl exec statefulset/knowledge-system-postgres -n knowledge-prod -- \
  psql -U postgres -c "SELECT version_num FROM alembic_version;"
```

### 5.3 回滚注意事项

| 注意点 | 说明 |
|---|---|
| 数据库迁移 | post-rollback hook 会自动执行 `alembic downgrade -1`，仅回退一个版本 |
| 数据丢失风险 | 降级迁移若删列/删表会丢数据，迁移需向后兼容设计 |
| PVC 不会回滚 | 持久化数据保留，仅 Pod/Deployment 配置回滚 |
| 镜像 tag | helm rollback 会恢复 revision 对应的镜像 tag |
| helm hook 超时 | 如回滚 hook 卡住，见 [TROUBLESHOOTING.md §11](./TROUBLESHOOTING.md#11-helm-升级卡住) |

### 5.4 紧急回滚（无法等待 hook）

```bash
# 跳过 hook，强制回滚（数据库迁移不会自动回滚）
helm rollback knowledge-system 2 -n knowledge-prod --no-hooks

# ⚠️ 警告：使用此选项需手动处理数据库迁移
# 检查当前迁移版本与代码兼容性
kubectl exec deployment/knowledge-system-backend -n knowledge-prod -- \
  alembic current
```

---

## 6. Argo Rollouts 自动化发布

### 6.1 原理

使用 Argo Rollouts CRD 替代 backend Deployment，自动执行金丝雀发布并基于 Prometheus 指标自动回滚。

### 6.2 启用 Argo Rollouts

```yaml
# values-prod.yaml
rollouts:
  enabled: true
  strategy: canary
  canary:
    steps:
      - setWeight: 20
      - pause: { duration: 30s }
      - setWeight: 40
      - pause: { duration: 30s }
      - setWeight: 60
      - pause: { duration: 30s }
      - setWeight: 80
      - pause: { duration: 30s }
    analysis:
      enabled: true
      prometheusAddress: "http://prometheus-server.monitoring.svc.cluster.local:9090"
      metrics:
        - name: error-rate
          query: "sum(rate(http_requests_total{status_code=~\"5..\"}[2m])) / clamp_min(sum(rate(http_requests_total[2m])), 1)"
          threshold: "0.05"  # 5xx 错误率 > 5% 触发回滚
        - name: p99-latency
          query: "histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[2m])) by (le))"
          threshold: "2"  # P99 > 2s 触发回滚
```

### 6.3 发布操作

```bash
# 安装 Argo Rollouts kubectl 插件
curl -sLO https://github.com/argoproj/argo-rollouts/releases/latest/download/kubectl-argo-rollouts-linux-amd64
chmod +x kubectl-argo-rollouts-linux-amd64
mv kubectl-argo-rollouts-linux-amd64 /usr/local/bin/kubectl-argo-rollouts

# 查看当前 Rollout 状态
kubectl argo rollouts get rollout knowledge-system-backend -n knowledge-prod -w

# 触发发布（更新镜像）
kubectl argo rollouts set image knowledge-system-backend \
  backend=registry.cn-hangzhou.aliyuncs.com/knowledge-system/backend:1.1.0 \
  -n knowledge-prod

# 查看发布进度
kubectl argo rollouts get rollout knowledge-system-backend -n knowledge-prod -w

# 手动 promote（跳过当前 pause）
kubectl argo rollouts promote knowledge-system-backend -n knowledge-prod

# 手动 abort（回滚）
kubectl argo rollouts abort knowledge-system-backend -n knowledge-prod
```

### 6.4 自动回滚触发条件

- `error-rate > 5%` 持续 2 分钟
- `p99-latency > 2s` 持续 2 分钟
- 任一指标触发即自动回滚到上一个稳定版本

---

## 7. 冒烟测试

### 7.1 标准冒烟测试

每次发布后必须执行：

```bash
bash deploy/scripts/smoke-test.sh \
  --host https://knowledge-system.example.com \
  --retry 10 \
  --interval 6 \
  --verbose
```

测试项（6 项）：

| # | 端点 | 期望状态码 | 说明 |
|---|---|---|---|
| 1 | `/health/live` | 200 | 存活检查 |
| 2 | `/health/ready` | 200 | 就绪检查（DB + Chroma + 系统） |
| 3 | `/api/v1/info` | 200 | 系统信息（版本、配置） |
| 4 | `/api/v1/health` | 200 | API 层健康检查 |
| 5 | `/` | 200 | 前端根路径 |
| 6 | `/metrics` | 200 | Prometheus 指标端点 |

### 7.2 集群内冒烟测试（无外部访问时）

```bash
# 在集群内 Pod 中执行
kubectl run smoke-test --rm -it --restart=Never \
  --image=curlimages/curl:latest -- \
  curl -s -o /dev/null -w "%{http_code}" \
  http://knowledge-system-backend:8000/health/ready
```

### 7.3 冒烟测试失败处理

```bash
# 失败时脚本退出码非 0，会触发自动回滚（如配置了 Argo Rollouts）
# 手动回滚流程见 §5 Helm 回滚 SOP

# 查看具体失败项
bash deploy/scripts/smoke-test.sh \
  --host https://knowledge-system.example.com \
  --verbose 2>&1 | grep -E "FAIL|ERROR"
```

---

## 8. 附录：发布决策树

### 8.1 发布策略决策

```
发布需求
  │
  ├─ 小变更（配置、文案、UI 微调）？
  │    └─ 是 → 常规 helm upgrade（见 DEPLOYMENT_GUIDE.md §5.1）
  │
  ├─ 中变更（新增 API、表结构变更）？
  │    ├─ 向后兼容 → 蓝绿发布（§3）
  │    └─ 不兼容 → 金丝雀发布（§4）
  │
  ├─ 大变更（架构调整、核心功能上线）？
  │    └─ 金丝雀发布（§4）或 Argo Rollouts（§6）
  │
  └─ 紧急修复？
       └─ 蓝绿发布（最快回滚）
```

### 8.2 异常处理决策

```
发布后异常
  │
  ├─ 5xx 错误率 > 5%？
  │    └─ 立即回滚（蓝绿切回 / helm rollback）
  │
  ├─ P99 延迟 > 2s？
  │    ├─ 持续上升 → 回滚
  │    └─ 短暂峰值 → 观察是否回落
  │
  ├─ 用户反馈异常？
  │    └─ 评估影响范围，必要时回滚
  │
  └─ 数据库异常？
       └─ helm rollback + alembic downgrade
```

### 8.3 发布日历建议

| 时间段 | 建议 |
|---|---|
| 周一上午 | ❌ 避免（周末后流量回升） |
| 周五下午 | ❌ 避免（周末无人值守） |
| 节假日前 | ❌ 避免（节日流量高峰） |
| 工作日 22:00-02:00 | ✅ 推荐（低峰时段） |
| 周末（非节假日） | ✅ 推荐（流量低） |

---

## 相关文档

| 文档 | 说明 |
|---|---|
| [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) | 部署运维手册 |
| [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) | 故障处理指南 |
| [BACKUP_RECOVERY.md](./BACKUP_RECOVERY.md) | 备份恢复手册 |
| [MONITORING_ALERTING.md](./MONITORING_ALERTING.md) | 监控告警手册 |
| [HELM_CHART_GUIDE.md](./HELM_CHART_GUIDE.md) | Helm Chart 使用文档 |
| [K8S_DEPLOYMENT_PLAN.md](../K8S_DEPLOYMENT_PLAN.md) | K8s 部署总体规划 |
