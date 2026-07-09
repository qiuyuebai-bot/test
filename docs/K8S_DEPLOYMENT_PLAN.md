# K8s 部署与自动化执行计划

> 版本：v1.0 · 编制日期：2026-07-07
> 适用项目：领域知识个性化生成与多智能体协同决策系统
> 当前部署方式：Docker Compose（7 个服务，见 `docker-compose.yml`）
> 目标部署方式：Kubernetes + Helm + ArgoCD GitOps
> 关联文档：`docs/REFACTORING_PLAN.md`（重构规划主文档）

---

## 目录

1. [目标与范围](#1-目标与范围)
2. [前置条件](#2-前置条件)
3. [架构设计](#3-架构设计)
4. [任务分解（WBS）](#4-任务分解wbs)
5. [依赖关系图](#5-依赖关系图)
6. [工时估算](#6-工时估算)
7. [里程碑](#7-里程碑)
8. [风险与应对](#8-风险与应对)
9. [验收标准](#9-验收标准)
10. [附录：技术选型理由](#10-附录技术选型理由)

---

## 1. 目标与范围

### 1.1 核心目标

将现有 docker-compose 部署方案迁移到 Kubernetes，实现：

1. **生产级高可用**：多副本、自动扩缩、故障自愈
2. **蓝绿/金丝雀发布**：零停机发布、秒级回滚
3. **GitOps 自动化**：声明式配置、自动同步、版本可追溯
4. **统一监控**：Prometheus + Grafana + AlertManager
5. **自我修复**：liveness/readiness probe 自动重启异常 Pod

### 1.2 范围边界

#### 包含

- 从 docker-compose 迁移到 K8s（7 个服务全部覆盖）
- Helm Chart 编写（含 dev/staging/prod 多环境 values）
- 蓝绿与金丝雀发布脚本
- 健康检查、资源限制、HPA 配置
- Prometheus 指标采集、Grafana Dashboard
- 数据库迁移 Job（Alembic）
- GitHub Actions CI 增强（镜像构建与推送）
- 运维手册与故障处理指南

#### 不包含

- K8s 集群本身的搭建（使用云厂商托管 K8s，如阿里云 ACK、腾讯云 TKE）
- Service Mesh（Istio/Linkerd）—— 后期单独评估
- 日志聚合系统（Loki/EFK）—— 后期单独评估
- 多集群容灾—— 后期单独评估

### 1.3 服务清单

| 服务 | 当前 compose 配置 | K8s 资源类型 | 备注 |
|---|---|---|---|
| frontend | Nginx 静态文件，80 端口 | Deployment + Service | 2 副本，HPA |
| backend | FastAPI，8000 端口 | Deployment + Service | 3 副本，HPA |
| postgres | postgres:16-alpine | StatefulSet + PVC | 生产用云 RDS 替代 |
| redis | redis:7-alpine | StatefulSet + PVC | 生产用云 Redis 替代 |
| celery-worker | celery worker | Deployment | 2 副本 |
| chroma | chromadb/chroma | StatefulSet + PVC | 可选，按需启用 |
| backup | python:3.11-slim，定时 | CronJob | 每日 02:00 |

---

## 2. 前置条件

### 2.1 基础设施

- [ ] K8s 集群（1.26+），kubectl 已配置
- [ ] 容器镜像仓库（阿里云 ACR / Docker Hub / 自建 Harbor）
- [ ] 域名 + DNS 解析
- [ ] TLS 证书（Let's Encrypt 或商业证书）

### 2.2 K8s 组件

- [ ] Helm 3.10+
- [ ] Ingress Controller（nginx-ingress 或 traefik）
- [ ] cert-manager（自动 TLS 证书）
- [ ] metrics-server（HPA 必需）
- [ ] Prometheus Operator（kube-prometheus-stack）
- [ ] ArgoCD（GitOps，可选但推荐）

### 2.3 代码侧准备

- [ ] 前后端 Dockerfile 已优化（多阶段构建、镜像大小 < 200MB）
- [ ] 后端 `health/live` 与 `health/ready` 端点可用（已有）
- [ ] `.env.example` 配置项齐全（已有 43 项）
- [ ] Alembic 迁移脚本可用（已有 P3-1）
- [ ] 备份脚本 `scripts/backup_db.py` 可用（已有 P3-2）

---

## 3. 架构设计

### 3.1 整体架构

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
            │   v1      │    │   v2      │    │   v3      │
            │ (blue)    │    │ (green)   │    │ (canary)  │
            └─────┬─────┘    └─────┬─────┘    └─────┬─────┘
                  │                 │                │
                  └─────────────────┼────────────────┘
                                    │
                            ┌───────▼───────┐
                            │    backend    │
                            │  (3 replicas) │
                            │      HPA      │
                            └───┬───┬───┬───┘
                                │   │   │
                ┌───────────────┘   │   └───────────────┐
                │                   │                   │
        ┌───────▼───────┐   ┌───────▼───────┐   ┌───────▼───────┐
        │   postgres    │   │     redis     │   │    chroma     │
        │  StatefulSet  │   │  StatefulSet  │   │  StatefulSet  │
        │     PVC       │   │     PVC       │   │     PVC       │
        └───────────────┘   └───────────────┘   └───────────────┘
                │
        ┌───────▼───────┐
        │ celery-worker │
        │  (2 replicas) │
        └───────────────┘
                │
        ┌───────▼───────┐
        │   backup      │
        │   CronJob     │
        └───────────────┘
```

### 3.2 命名空间规划

| 命名空间 | 用途 |
|---|---|
| `knowledge-dev` | 开发环境 |
| `knowledge-staging` | 预发布环境 |
| `knowledge-prod` | 生产环境 |
| `knowledge-infra` | 监控基础设施（Prometheus、Grafana） |

### 3.3 配置管理策略

- **非敏感配置**：ConfigMap（values.yaml 注入）
- **敏感配置**：Secret（base64 编码，生产用云 KMS 加密）
- **环境差异**：`values-dev.yaml`、`values-staging.yaml`、`values-prod.yaml`
- **密钥管理**：External Secrets Operator 对接云 KMS（生产环境）

### 3.4 数据持久化

| 服务 | 存储 | 备份策略 |
|---|---|---|
| postgres | PVC 50Gi（生产建议云 RDS） | 每日 02:00 全量 + WAL 持续归档 |
| redis | PVC 5Gi | 无需备份（缓存数据） |
| chroma | PVC 20Gi | 每周全量 |
| backend-data | PVC 10Gi（uploads、resources） | 每日增量 |
| backend-logs | PVC 5Gi | 7 天轮转 |

---

## 4. 任务分解（WBS）

### 阶段 1：Helm Chart 骨架与基础部署（WBS 1.x）

| 编号 | 任务 | 工时 | 依赖 |
|---|---|---|---|
| 1.1 | 创建 Helm Chart 目录结构 | 0.5d | - |
| 1.2 | 编写 `Chart.yaml`（版本、依赖声明） | 0.5d | 1.1 |
| 1.3 | 编写 `values.yaml`（默认配置） | 1d | 1.1 |
| 1.4 | 编写 frontend Deployment + Service 模板 | 0.5d | 1.3 |
| 1.5 | 编写 backend Deployment + Service 模板 | 1d | 1.3 |
| 1.6 | 编写 postgres StatefulSet + Service + PVC | 1d | 1.3 |
| 1.7 | 编写 redis StatefulSet + Service + PVC | 0.5d | 1.3 |
| 1.8 | 编写 celery-worker Deployment | 0.5d | 1.5 |
| 1.9 | 编写 chroma StatefulSet + Service + PVC | 0.5d | 1.3 |
| 1.10 | 编写 backup CronJob | 0.5d | 1.6 |
| 1.11 | 编写 ConfigMap 模板 | 0.5d | 1.3 |
| 1.12 | 编写 Secret 模板 | 0.5d | 1.3 |
| 1.13 | 编写 Ingress + TLS 配置 | 1d | 1.4, 1.5 |
| 1.14 | 编写 `_helpers.tpl`（命名、标签） | 0.5d | 1.1 |
| 1.15 | 编写 `values-dev.yaml` | 0.5d | 1.3 |
| 1.16 | 编写 `values-staging.yaml` | 0.5d | 1.3 |
| 1.17 | 编写 `values-prod.yaml` | 0.5d | 1.3 |
| 1.18 | 本地 k8s（minikube/kind）部署验证 | 1d | 1.1–1.17 |

**阶段 1 工时小计**：约 11 人天

### 阶段 2：生产级增强（WBS 2.x）

| 编号 | 任务 | 工时 | 依赖 |
|---|---|---|---|
| 2.1 | 配置 livenessProbe + readinessProbe（全部服务） | 1d | 阶段 1 |
| 2.2 | 配置 resources requests/limits | 0.5d | 阶段 1 |
| 2.3 | 配置 HPA（frontend、backend、celery-worker） | 1d | 2.2 |
| 2.4 | 配置 PodDisruptionBudget | 0.5d | 阶段 1 |
| 2.5 | 配置 NetworkPolicy（限制服务间通信） | 1d | 阶段 1 |
| 2.6 | 配置 Pod anti-affinity + topologySpreadConstraints | 0.5d | 阶段 1 |
| 2.7 | 配置 PriorityClass 与 QoS | 0.5d | 2.2 |
| 2.8 | 配置 PVC 存储类与动态供给 | 0.5d | 阶段 1 |
| 2.9 | 配置 Secret 加密（云 KMS / Sealed Secrets） | 1d | 阶段 1 |
| 2.10 | 配置 Pod Security Standards（restricted） | 0.5d | 阶段 1 |

**阶段 2 工时小计**：约 7 人天

### 阶段 3：数据库迁移 Job（WBS 3.x）

| 编号 | 任务 | 工时 | 依赖 |
|---|---|---|---|
| 3.1 | 编写 Alembic 迁移 Job 模板（helm hook: pre-install, pre-upgrade） | 1d | 阶段 1 |
| 3.2 | 编写种子数据初始化 Job（admin、培训、学习者） | 0.5d | 3.1 |
| 3.3 | 编写数据库回滚 Job（helm hook: post-rollback） | 0.5d | 3.1 |
| 3.4 | 验证迁移 Job 在 fresh 数据库上的行为 | 0.5d | 3.1, 3.2 |
| 3.5 | 验证迁移 Job 在已有数据上的兼容性 | 0.5d | 3.1 |

**阶段 3 工时小计**：约 3 人天

### 阶段 4：监控与告警（WBS 4.x）

| 编号 | 任务 | 工时 | 依赖 |
|---|---|---|---|
| 4.1 | 编写 Prometheus ServiceMonitor（backend metrics） | 0.5d | 阶段 1 |
| 4.2 | 编写 Grafana Dashboard ConfigMap | 1d | 4.1 |
| 4.3 | 编写 PrometheusRule（告警规则） | 1d | 4.1 |
| 4.4 | 配置 Alertmanager（钉钉/企业微信/邮件通知） | 1d | 4.3 |
| 4.5 | 编写核心指标仪表盘（API 延迟、错误率、QPS） | 1d | 4.2 |
| 4.6 | 编写业务指标仪表盘（LLM 调用、缓存命中、任务成功率） | 1d | 4.2 |
| 4.7 | 编写资源仪表盘（CPU、内存、磁盘、网络） | 0.5d | 4.2 |
| 4.8 | 配置日志采集（Loki + Promtail 或云日志服务） | 1d | 阶段 1 |

**阶段 4 工时小计**：约 7 人天

### 阶段 5：发布与回滚自动化（WBS 5.x）

| 编号 | 任务 | 工时 | 依赖 |
|---|---|---|---|
| 5.1 | 编写蓝绿发布脚本（基于 label + selector 切换） | 1.5d | 阶段 1 |
| 5.2 | 编写金丝雀发布脚本（基于 weight 流量切分） | 1.5d | 阶段 1, 5.1 |
| 5.3 | 编写回滚脚本（基于 Helm revision） | 0.5d | 阶段 1 |
| 5.4 | 配置 ArgoCD Application（GitOps 自动同步） | 1d | 阶段 1 |
| 5.5 | 配置 ArgoCD sync hook（pre-sync 数据库迁移、post-sync 健康检查） | 1d | 5.4, 3.1 |
| 5.6 | 编写发布前自动冒烟测试脚本 | 1d | 阶段 1 |
| 5.7 | 配置基于指标的自动回滚（Argo Rollouts） | 1.5d | 5.2, 4.3 |

**阶段 5 工时小计**：约 8 人天

### 阶段 6：CI/CD 管道增强（WBS 6.x）

| 编号 | 任务 | 工时 | 依赖 |
|---|---|---|---|
| 6.1 | GitHub Actions：构建并推送前端镜像 | 0.5d | - |
| 6.2 | GitHub Actions：构建并推送后端镜像 | 0.5d | - |
| 6.3 | GitHub Actions：镜像漏洞扫描（Trivy） | 0.5d | 6.1, 6.2 |
| 6.4 | GitHub Actions：自动更新 Helm values 中的 image tag | 0.5d | 6.1, 6.2 |
| 6.5 | GitHub Actions：自动触发 ArgoCD sync（PR 合并到 main） | 0.5d | 5.4 |
| 6.6 | 镜像缓存与层复用优化（多阶段构建、distroless 基础镜像） | 1d | 6.1, 6.2 |
| 6.7 | 镜像签名（cosign，可选） | 1d | 6.1, 6.2 |

**阶段 6 工时小计**：约 4.5 人天

### 阶段 7：自我修复与韧性（WBS 7.x）

| 编号 | 任务 | 工时 | 依赖 |
|---|---|---|---|
| 7.1 | 配置 livenessProbe 自动重启异常 Pod | 0.5d | 阶段 2 |
| 7.2 | 配置 OOM 处理（resources limits + restartPolicy） | 0.5d | 阶段 2 |
| 7.3 | 配置数据库连接池健康检查（SQLAlchemy pool_pre_ping） | 0.5d | 阶段 1 |
| 7.4 | 配置 LLM 调用熔断（circuit breaker，防止雪崩） | 1d | 阶段 1 |
| 7.5 | 配置 Celery 任务自动重试（已有，增强监控） | 0.5d | 阶段 1 |
| 7.6 | 配置 Pod disruption budget（保证最少副本数） | 0.5d | 阶段 2 |
| 7.7 | 配置优雅关闭（terminationGracePeriodSeconds + preStop hook） | 1d | 阶段 1 |

**阶段 7 工时小计**：约 4.5 人天

### 阶段 8：备份与灾难恢复（WBS 8.x）

| 编号 | 任务 | 工时 | 依赖 |
|---|---|---|---|
| 8.1 | 配置 PostgreSQL 定时备份 CronJob（已存在 backup_db.py） | 0.5d | 阶段 1 |
| 8.2 | 配置 PVC 快照备份（Velero） | 1d | 阶段 1 |
| 8.3 | 编写数据库恢复脚本（从备份恢复） | 1d | 8.1 |
| 8.4 | 编写 PVC 恢复脚本（Velero restore） | 0.5d | 8.2 |
| 8.5 | 编写灾难恢复演练手册（RTO/RPO 测试） | 1d | 8.1, 8.2 |
| 8.6 | 配置跨区域备份复制（生产环境） | 1d | 8.2 |

**阶段 8 工时小计**：约 5 人天

### 阶段 9：运维手册与文档（WBS 9.x）

| 编号 | 任务 | 工时 | 依赖 |
|---|---|---|---|
| 9.1 | 编写《K8s 部署运维手册》 | 1.5d | 阶段 1–7 |
| 9.2 | 编写《故障处理指南》（常见故障 + 排查步骤） | 1.5d | 阶段 1–7 |
| 9.3 | 编写《发布操作手册》（蓝绿、金丝雀、回滚 SOP） | 1d | 阶段 5 |
| 9.4 | 编写《备份恢复手册》 | 0.5d | 阶段 8 |
| 9.5 | 编写《监控告警手册》（指标含义、阈值、响应） | 1d | 阶段 4 |
| 9.6 | 编写《Helm Chart 使用文档》 | 0.5d | 阶段 1 |
| 9.7 | 更新 README.md 添加 K8s 部署章节 | 0.5d | 阶段 1 |

**阶段 9 工时小计**：约 7.5 人天

---

## 5. 依赖关系图

```
阶段 1 (Helm Chart 骨架)
  │
  ├──→ 阶段 2 (生产级增强)
  │       │
  │       └──→ 阶段 7 (自我修复)
  │
  ├──→ 阶段 3 (数据库迁移 Job)
  │       │
  │       └──→ 阶段 5 (发布自动化) ←─ 阶段 4 (监控告警)
  │
  ├──→ 阶段 6 (CI/CD 管道)
  │
  ├──→ 阶段 8 (备份恢复)
  │
  └──→ 阶段 9 (运维文档) ←── 依赖阶段 1–8 全部完成
```

**关键路径**：阶段 1 → 阶段 2 → 阶段 7 → 阶段 9
**可并行**：阶段 3、4、6、8 可在阶段 1 完成后并行推进

---

## 6. 工时估算

| 阶段 | 工时（人天） | 累计 |
|---|---|---|
| 阶段 1：Helm Chart 骨架 | 11.0 | 11.0 |
| 阶段 2：生产级增强 | 7.0 | 18.0 |
| 阶段 3：数据库迁移 Job | 3.0 | 21.0 |
| 阶段 4：监控告警 | 7.0 | 28.0 |
| 阶段 5：发布自动化 | 8.0 | 36.0 |
| 阶段 6：CI/CD 管道 | 4.5 | 40.5 |
| 阶段 7：自我修复 | 4.5 | 45.0 |
| 阶段 8：备份恢复 | 5.0 | 50.0 |
| 阶段 9：运维文档 | 7.5 | 57.5 |
| **总计** | **57.5 人天** | — |

**单人估算**：约 12 周（3 个月）
**双人估算**：约 6 周（1.5 个月，部分阶段可并行）
**推荐配置**：1 名 DevOps 工程师 + 1 名后端工程师，6 周完成

### 6.1 推荐实施顺序（双人并行）

| 周次 | 工程师 A（DevOps） | 工程师 B（后端） |
|---|---|---|
| W1 | 阶段 1.1–1.5（Chart 骨架、frontend、backend） | 阶段 1.6–1.10（postgres、redis、celery、chroma、backup） |
| W2 | 阶段 1.11–1.18（ConfigMap、Secret、Ingress、本地验证） | 阶段 3（数据库迁移 Job） |
| W3 | 阶段 2.1–2.5（probe、resources、HPA、PDB、NetworkPolicy） | 阶段 4.1–4.4（ServiceMonitor、Grafana、PrometheusRule、Alertmanager） |
| W4 | 阶段 2.6–2.10 + 阶段 7（anti-affinity、Secret、韧性） | 阶段 4.5–4.8（Dashboard、日志采集） |
| W5 | 阶段 5.1–5.4（蓝绿、金丝雀、回滚、ArgoCD） | 阶段 6（CI/CD 管道） |
| W6 | 阶段 5.5–5.7 + 阶段 8（sync hook、自动回滚、备份恢复） | 阶段 9（运维文档） |

---

## 7. 里程碑

| 里程碑 | 验收内容 | 预计完成 |
|---|---|---|
| M1：本地 K8s 部署跑通 | minikube/kind 部署成功，全部服务健康 | W2 末 |
| M2：staging 环境上线 | 部署到 staging，核心功能验证通过 | W4 末 |
| M3：监控告警就绪 | Grafana 可访问，告警规则生效 | W4 末 |
| M4：蓝绿发布能力 | 蓝绿发布脚本可用，回滚 < 30s | W5 末 |
| M5：GitOps 自动化 | PR 合并自动部署到 staging | W5 末 |
| M6：生产环境上线 | prod 环境部署，演练通过 | W6 末 |
| M7：运维手册交付 | 7 份文档完成 | W6 末 |

---

## 8. 风险与应对

| 风险 | 概率 | 影响 | 应对措施 |
|---|---|---|---|
| K8s 学习曲线陡峭 | 高 | 中 | 优先使用托管 K8s（ACK/TKE），减少集群运维 |
| Helm Chart 配置漂移 | 中 | 中 | values.yaml 严格版本管理 + ArgoCD 自动同步 |
| 数据库迁移在 K8s 中失败 | 中 | 高 | Job 使用 helm hook + 失败不阻塞 + 完整备份 |
| 镜像仓库不可用 | 低 | 高 | 多仓库镜像 + 本地缓存 |
| Ingress 配置错误导致服务不可达 | 中 | 高 | 先在 staging 验证 + 配置兜底 |
| PVC 数据丢失 | 低 | 极高 | Velero 定期备份 + 跨区域复制 |
| HPA 误判导致频繁扩缩 | 中 | 中 | 设置 stabilizationWindowSeconds |
| ArgoCD 配置漂移导致"误删" | 中 | 高 | 启用 auto-prune 前先在 staging 验证 |
| 监控指标过多导致 Prometheus 卡顿 | 中 | 中 | 使用 recording rules 预聚合 |
| 成本超支（K8s 节点费用） | 中 | 中 | HPA + 资源限制 + 抢占式实例 |

---

## 9. 验收标准

### 9.1 功能验收

- [ ] `helm install` 一键部署全部 7 个服务到 K8s
- [ ] 全部 Pod 进入 Running 状态，健康检查通过
- [ ] Ingress 可访问，TLS 证书有效
- [ ] 前端页面正常加载，API 调用成功
- [ ] 数据库迁移 Job 在部署时自动执行
- [ ] 备份 CronJob 按计划执行
- [ ] 日志可通过 `kubectl logs` 查看
- [ ] Prometheus 抓取到 backend metrics

### 9.2 非功能验收

- [ ] 蓝绿发布零停机（切换 < 5s）
- [ ] 金丝雀发布可按 10%/30%/50% 流量切分
- [ ] 回滚操作 < 30s
- [ ] HPA 在 CPU > 70% 时自动扩容
- [ ] Pod 异常自动重启（livenessProbe 生效）
- [ ] Grafana Dashboard 可访问，关键指标可见
- [ ] 告警规则触发后 5 分钟内通知到位
- [ ] ArgoCD 自动同步 PR 合并的变更
- [ ] 镜像构建 < 5 分钟，大小 < 200MB
- [ ] 全部 7 份运维文档完成

### 9.3 安全验收

- [ ] Secret 不在 Git 中明文存储
- [ ] Pod Security Standards 为 restricted 级别
- [ ] NetworkPolicy 限制非必要服务间通信
- [ ] 镜像漏洞扫描无高危项
- [ ] TLS 证书有效且自动续期

---

## 10. 附录：技术选型理由

### 10.1 为什么选 Helm 而非纯 Kustomize

| 维度 | Helm | Kustomize |
|---|---|---|
| 多环境管理 | values.yaml 切换 | overlay 目录 |
| 模板化 | 支持 | 不支持 |
| 版本管理 | Chart.yaml 版本号 | 无 |
| 依赖管理 | 支持（Chart 依赖） | 无 |
| 生态 | 丰富（Bitnami 等） | 一般 |

**结论**：项目有多环境（dev/staging/prod）+ 多服务依赖，Helm 更适合。

### 10.2 为什么选 ArgoCD 而非 Flux

| 维度 | ArgoCD | Flux |
|---|---|---|
| UI | 有 Web UI | 仅 CLI |
| 多 app 管理 | ApplicationSet 便捷 | 需配置 |
| sync hook | 支持 | 支持 |
| 社区活跃度 | 高 | 高 |
| 学习曲线 | 平缓 | 陡峭 |

**结论**：ArgoCD 的 UI 在演示场景下更友好，sync hook 与 Helm Chart 集成更顺。

### 10.3 为什么选 nginx-ingress 而非 traefik

| 维度 | nginx-ingress | traefik |
|---|---|---|
| 性能 | 高 | 高 |
| 配置灵活度 | 高 | 中 |
| 社区 | 大 | 中 |
| 蓝绿/金丝雀 | nginx-ingress 原生支持 | 需额外配置 |

**结论**：nginx-ingress 的 canary annotation（`nginx.ingress.kubernetes.io/canary-weight`）开箱即用。

### 10.4 为什么选 Velero 而非 Restic

| 维度 | Velero | Restic |
|---|---|---|
| K8s 原生 | 是 | 否 |
| PVC 快照 | 支持 | 仅文件级 |
| 跨 namespace 恢复 | 支持 | 不支持 |
| 集群迁移 | 支持 | 不支持 |

**结论**：Velero 是 K8s 备份事实标准。

### 10.5 为什么推荐云托管数据库（RDS）而非自建

| 维度 | 自建 PostgreSQL | 云 RDS |
|---|---|---|
| 运维成本 | 高 | 低 |
| 高可用 | 需自行配置 | 默认主从 |
| 备份 | 需自行配置 | 默认每日 |
| 性能监控 | 自建 | 内置 |
| 成本 | 低 | 中 |

**结论**：生产环境强烈建议用云 RDS，自建仅用于 dev/staging。

---

## 附录 A：Helm Chart 目录结构预览

```
deploy/helm/
├── Chart.yaml                    # Chart 元信息
├── values.yaml                   # 默认配置
├── values-dev.yaml               # 开发环境覆盖
├── values-staging.yaml            # 预发布环境覆盖
├── values-prod.yaml               # 生产环境覆盖
├── charts/                       # 子 Chart 依赖（如有）
├── templates/
│   ├── _helpers.tpl              # 命名、标签模板
│   ├── frontend/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   ├── hpa.yaml
│   │   └── pdb.yaml
│   ├── backend/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   ├── hpa.yaml
│   │   ├── pdb.yaml
│   │   └── servicemonitor.yaml
│   ├── postgres/
│   │   ├── statefulset.yaml
│   │   ├── service.yaml
│   │   └── pvc.yaml
│   ├── redis/
│   │   ├── statefulset.yaml
│   │   ├── service.yaml
│   │   └── pvc.yaml
│   ├── celery-worker/
│   │   └── deployment.yaml
│   ├── chroma/
│   │   ├── statefulset.yaml
│   │   ├── service.yaml
│   │   └── pvc.yaml
│   ├── backup/
│   │   └── cronjob.yaml
│   ├── jobs/
│   │   ├── db-migrate.yaml       # helm hook: pre-install, pre-upgrade
│   │   └── seed-data.yaml        # helm hook: post-install
│   ├── configmap.yaml
│   ├── secret.yaml
│   ├── ingress.yaml
│   ├── networkpolicy.yaml
│   └── NOTES.txt                  # 部署后提示
└── README.md
```

## 附录 B：运维文档清单

| 文档 | 路径 | 内容 |
|---|---|---|
| K8s 部署运维手册 | `docs/ops/k8s-deployment.md` | 集群准备、Helm 安装、升级、扩缩 |
| 故障处理指南 | `docs/ops/troubleshooting.md` | 常见故障 + 排查步骤 + 应急预案 |
| 发布操作手册 | `docs/ops/release-sop.md` | 蓝绿、金丝雀、回滚标准操作 |
| 备份恢复手册 | `docs/ops/backup-restore.md` | 备份策略、恢复演练、RTO/RPO |
| 监控告警手册 | `docs/ops/monitoring.md` | 指标含义、告警阈值、响应流程 |
| Helm Chart 使用文档 | `docs/ops/helm-usage.md` | 配置项说明、多环境切换 |
| CI/CD 管道文档 | `docs/ops/cicd.md` | 镜像构建、推送、部署流程 |

---

**文档维护者**：项目维护团队
**最后更新**：2026-07-07
**下次评审**：M1 里程碑完成后
