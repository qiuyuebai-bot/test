# 监控告警手册

> 版本：v1.0 · 编制日期：2026-07-07
> 适用项目：领域知识个性化生成与多智能体协同决策系统
> 关联文档：[DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)、[TROUBLESHOOTING.md](./TROUBLESHOOTING.md)

本手册覆盖监控架构、指标体系、10 个告警规则、3 个 Grafana Dashboard、告警通知渠道配置、日常监控指标解读。

---

## 目录

1. [监控架构](#1-监控架构)
2. [启用监控](#2-启用监控)
3. [指标体系](#3-指标体系)
4. [告警规则](#4-告警规则)
5. [Grafana Dashboards](#5-grafana-dashboards)
6. [告警通知配置](#6-告警通知配置)
7. [日常监控指标解读](#7-日常监控指标解读)
8. [容量规划](#8-容量规划)

---

## 1. 监控架构

```
┌────────────────────────────────────────────────────────────┐
│                    K8s 集群                                 │
│                                                            │
│  ┌──────────────┐    /metrics    ┌──────────────────┐       │
│  │   backend    │ ────────────► │   ServiceMonitor  │      │
│  │  (FastAPI)   │                │   (CRD)           │      │
│  └──────────────┘                └─────────┬─────────┘      │
│                                            │                │
│  ┌──────────────────┐                      ▼                │
│  │  kube-state-     │ ────► Prometheus ◄───┘               │
│  │  metrics (KSM)   │ ◄───                                │
│  └──────────────────┘ ────►                                │
│                                                            │
│  ┌──────────────────┐    cAdvisor   ────►                  │
│  │  node-exporter   │ ◄─────────────────                  │
│  └──────────────────┘                       │              │
│                                            │              │
└────────────────────────────────────────────┼──────────────┘
                                             │
                            ┌────────────────┼──────────────┐
                            │                │              │
                            ▼                ▼              ▼
                    ┌────────────┐  ┌──────────────┐  ┌──────────┐
                    │ Prometheus │  │   Grafana    │  │ AlertMgr │
                    │   (存储)   │  │ (可视化)    │  │ (通知)   │
                    └────────────┘  └──────────────┘  └────┬─────┘
                                                            │
                                                  ┌─────────┴─────────┐
                                                  ▼                   ▼
                                          ┌──────────────┐    ┌──────────────┐
                                          │ 钉钉/企业微信 │    │ 邮件/Slack   │
                                          └──────────────┘    └──────────────┘
```

### 组件清单

| 组件 | 作用 | 部署方式 |
|---|---|---|
| Prometheus | 指标采集与存储 | kube-prometheus-stack |
| Grafana | 可视化面板 | kube-prometheus-stack |
| Alertmanager | 告警路由与通知 | kube-prometheus-stack |
| ServiceMonitor | 自动发现 backend /metrics | Helm Chart 创建 |
| PrometheusRule | 告警规则（7 条） | Helm Chart 创建 |
| Grafana Dashboard ConfigMap | 3 个 Dashboard | Helm Chart 创建 |
| Alertmanager Config Secret | 通知渠道配置 | Helm Chart 创建 |
| kube-state-metrics | K8s 资源指标 | kube-prometheus-stack |
| node-exporter | 节点指标 | kube-prometheus-stack |

---

## 2. 启用监控

### 2.1 安装 kube-prometheus-stack

```bash
# 1. 添加 Helm 仓库
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# 2. 安装 kube-prometheus-stack（含 Prometheus + Grafana + Alertmanager）
helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace \
  --set grafana.adminPassword=admin \
  --set grafana.service.type=LoadBalancer  # 生产用 Ingress 替代

# 3. 等待就绪
kubectl get pods -n monitoring -w
```

### 2.2 启用 Chart 内置监控

```yaml
# values-prod.yaml
monitoring:
  serviceMonitor:
    enabled: true
    namespace: monitoring
    interval: 30s
    scrapeTimeout: 10s
    path: /metrics

  prometheusRule:
    enabled: true
    namespace: monitoring

  grafanaDashboard:
    enabled: true
    namespace: monitoring

  alertmanager:
    enabled: true
    namespace: monitoring
    channel: dingtalk  # dingtalk | wechat | slack | email
    webhookUrl: "https://oapi.dingtalk.com/robot/send?access_token=xxx"
```

```bash
helm upgrade knowledge-system ./deploy/helm \
  -f deploy/helm/values-prod.yaml -n knowledge-prod
```

### 2.3 验证监控就绪

```bash
# 1. 验证 ServiceMonitor 被识别
kubectl get servicemonitor -n monitoring
# 期望看到 knowledge-system ServiceMonitor

# 2. 验证 Prometheus 已抓取目标
kubectl port-forward svc/kube-prometheus-stack-prometheus 9090:9090 -n monitoring
# 访问 http://localhost:9090/targets，确认 knowledge-system backend 已被抓取

# 3. 验证 PrometheusRule 已加载
kubectl get prometheusrule -n monitoring
# 期望看到 knowledge-system-alerts 规则

# 4. 验证 Grafana Dashboard 已加载
kubectl get configmap -n monitoring -l grafana_dashboard=1
# 期望看到 knowledge-system-grafana-dashboards ConfigMap

# 5. 验证 Alertmanager 配置
kubectl get secret -n monitoring -l app.kubernetes.io/component=alertmanager
```

### 2.4 访问 Grafana

```bash
# 获取 Grafana 密码（如未在安装时指定）
kubectl get secret kube-prometheus-stack-grafana -n monitoring \
  -o jsonpath="{.data.admin-password}" | base64 --decode ; echo

# 端口转发访问
kubectl port-forward svc/kube-prometheus-stack-grafana 3000:80 -n monitoring
# 访问 http://localhost:3000（用户名：admin，密码：上一步获取）
```

---

## 3. 指标体系

### 3.1 指标分类

| 类别 | 来源 | 关键指标 |
|---|---|---|
| API 核心 | backend `/metrics` | http_requests_total、http_request_duration_seconds、http_requests_in_progress |
| LLM 业务 | backend `/metrics` | llm_calls_total、llm_call_duration_seconds、llm_cache_hits |
| Agent 业务 | backend `/metrics` | agent_tasks_total、agent_task_duration |
| 数据库 | backend `/metrics` | db_connections_active、db_query_duration |
| 资源 | cAdvisor/KSM | container_cpu_usage、container_memory_working_set_bytes |
| 节点 | node-exporter | node_cpu_seconds、node_memory_MemAvailable |
| K8s | kube-state-metrics | kube_pod_status_phase、kube_pvc_* |

### 3.2 backend 暴露的指标端点

backend 通过 `/metrics` 暴露 Prometheus 格式指标：

```bash
# 验证指标端点
kubectl port-forward svc/knowledge-system-backend 8000:8000 -n knowledge-prod
curl http://localhost:8000/metrics | head -30

# 关键指标示例：
# http_requests_total{method="GET",path="/api/v1/info",status_code="200"} 1234
# http_request_duration_seconds_bucket{le="0.1",method="GET",path="/api/v1/info"} 1100
# http_requests_in_progress 5
# llm_calls_total{model="gpt-4-turbo-preview",status="success"} 234
# llm_call_duration_seconds_bucket{le="10",model="gpt-4-turbo-preview"} 200
# db_connections_active 8
```

### 3.3 常用 PromQL 查询

```promql
# 1. 当前 QPS
sum(rate(http_requests_total[1m]))

# 2. 5xx 错误率
sum(rate(http_requests_total{status_code=~"5.."}[5m]))
/
clamp_min(sum(rate(http_requests_total[5m])), 1)

# 3. P99 延迟
histogram_quantile(0.99,
  sum(rate(http_request_duration_seconds_bucket[5m])) by (le)
)

# 4. LLM 调用成功率
1 - (
  sum(rate(llm_calls_total{status="error"}[10m]))
  /
  clamp_min(sum(rate(llm_calls_total[10m])), 1)
)

# 5. 当前数据库连接数
db_connections_active

# 6. 容器 CPU 使用率（占 limit 比例）
sum(rate(container_cpu_usage_seconds_total{namespace="knowledge-prod",container!="POD",container!=""}[5m])) by (pod)
/
sum(container_spec_cpu_quota{namespace="knowledge-prod",container!=""}/container_spec_cpu_period{namespace="knowledge-prod",container!=""}) by (pod)

# 7. PVC 使用率
kubelet_volume_stats_used_bytes / kubelet_volume_stats_capacity_bytes

# 8. Pod 重启次数
increase(kube_pod_container_status_restarts_total{namespace=~"knowledge-.*"}[1h])
```

---

## 4. 告警规则

共 10 条告警规则，分 3 组：API（3 条）、LLM（2 条）、基础设施（5 条）。

### 4.1 API 健康与性能告警（3 条）

#### KnowledgeSystemHighErrorRate

| 属性 | 值 |
|---|---|
| 告警名 | KnowledgeSystemHighErrorRate |
| 表达式 | `5xx 错误率 > 5% 持续 5 分钟` |
| 严重级别 | critical |
| PromQL | `sum(rate(http_requests_total{status_code=~"5.."}`[5m])) by (namespace, service) / clamp_min(sum(rate(http_requests_total[5m])) by (namespace, service), 1) > 0.05` |
| 触发条件 | 5xx 错误率 > 5% 持续 5 分钟 |
| 响应动作 | 1. 查看 backend 日志定位错误 2. 检查依赖（DB/Redis）状态 3. 必要时回滚 |
| 排查指引 | [TROUBLESHOOTING.md §1 CrashLoopBackOff](./TROUBLESHOOTING.md#1-pod-crashloopbackoff) |

#### KnowledgeSystemHighLatency

| 属性 | 值 |
|---|---|
| 告警名 | KnowledgeSystemHighLatency |
| 表达式 | `HTTP P99 延迟 > 2s 持续 5 分钟` |
| 严重级别 | warning |
| 触发条件 | P99 延迟 > 2 秒持续 5 分钟 |
| 响应动作 | 1. 检查 HPA 是否触发扩容 2. 排查慢查询 3. 检查 LLM 调用是否阻塞 |
| 排查指引 | [TROUBLESHOOTING.md §7 HPA 不触发扩容](./TROUBLESHOOTING.md#7-hpa-不触发扩容) |

#### KnowledgeSystemHighInProgress

| 属性 | 值 |
|---|---|
| 告警名 | KnowledgeSystemHighInProgress |
| 表达式 | `当前在处理请求数 > 100 持续 10 分钟` |
| 严重级别 | warning |
| 触发条件 | http_requests_in_progress > 100 持续 10 分钟 |
| 响应动作 | 1. 扩容 backend 2. 检查是否有 LLM 长响应阻塞 3. 排查慢请求 |

### 4.2 LLM 调用告警（2 条）

#### KnowledgeSystemLLMHighErrorRate

| 属性 | 值 |
|---|---|
| 告警名 | KnowledgeSystemLLMHighErrorRate |
| 表达式 | `LLM 调用错误率 > 30% 持续 10 分钟` |
| 严重级别 | critical |
| 触发条件 | LLM 错误率 > 30% 持续 10 分钟 |
| 响应动作 | 1. 检查 API Key 是否失效 2. 检查 LLM 服务可用性 3. 检查熔断器状态 |
| 排查指引 | [TROUBLESHOOTING.md §8 LLM 调用熔断](./TROUBLESHOOTING.md#8-llm-调用熔断) |

#### KnowledgeSystemLLMHighLatency

| 属性 | 值 |
|---|---|
| 告警名 | KnowledgeSystemLLMHighLatency |
| 表达式 | `LLM P99 延迟 > 30s 持续 10 分钟` |
| 严重级别 | warning |
| 触发条件 | LLM 调用 P99 > 30 秒持续 10 分钟 |
| 响应动作 | 1. 检查 LLM 服务状态 2. 检查网络延迟 3. 考虑切换模型 |

### 4.3 基础设施告警（5 条）

#### KnowledgeSystemDBConnectionsHigh

| 属性 | 值 |
|---|---|
| 告警名 | KnowledgeSystemDBConnectionsHigh |
| 表达式 | `数据库活跃连接数 > 25 持续 5 分钟` |
| 严重级别 | warning |
| 触发条件 | db_connections_active > 25 持续 5 分钟 |
| 响应动作 | 1. 检查连接池配置 2. 排查连接泄漏 3. 扩容数据库或 backend |
| 排查指引 | [TROUBLESHOOTING.md §4 数据库连接失败](./TROUBLESHOOTING.md#4-数据库连接失败) |

#### KnowledgeSystemPodCrashLooping

| 属性 | 值 |
|---|---|
| 告警名 | KnowledgeSystemPodCrashLooping |
| 表达式 | `Pod 10 分钟内重启 > 5 次持续 5 分钟` |
| 严重级别 | critical |
| 触发条件 | increase(kube_pod_container_status_restarts_total[10m]) > 5 持续 5 分钟 |
| 响应动作 | 1. 查看崩溃日志 2. 检查 OOM/配置错误 3. 必要时回滚 |
| 排查指引 | [TROUBLESHOOTING.md §1 Pod CrashLoopBackOff](./TROUBLESHOOTING.md#1-pod-crashloopbackoff) |

#### KnowledgeSystemPodNotReady

| 属性 | 值 |
|---|---|
| 告警名 | KnowledgeSystemPodNotReady |
| 表达式 | `Pod 未就绪持续 10 分钟` |
| 严重级别 | warning |
| 触发条件 | Pod ready=0 持续 10 分钟 |
| 响应动作 | 1. 查看 Pod 事件 2. 检查 readinessProbe 失败原因 |

#### KnowledgeSystemPVCDiskRunningFull

| 属性 | 值 |
|---|---|
| 告警名 | KnowledgeSystemPVCDiskRunningFull |
| 表达式 | `PVC 磁盘使用率 > 85% 持续 10 分钟` |
| 严重级别 | warning |
| 触发条件 | PVC 使用率 > 85% 持续 10 分钟 |
| 响应动作 | 1. 扩容 PVC 2. 清理旧数据 3. 检查备份清理策略 |
| 排查指引 | [TROUBLESHOOTING.md §6 PVC 磁盘满](./TROUBLESHOOTING.md#6-pvc-磁盘满) |

#### KnowledgeSystemContainerMemoryHigh

| 属性 | 值 |
|---|---|
| 告警名 | KnowledgeSystemContainerMemoryHigh |
| 表达式 | `容器内存使用率 > 85% 持续 5 分钟` |
| 严重级别 | warning |
| 触发条件 | container_memory_working_set_bytes / container_spec_memory_limit_bytes > 0.85 持续 5 分钟 |
| 响应动作 | 1. 扩容容器内存 2. 排查内存泄漏 3. 扩容副本 |
| 排查指引 | [TROUBLESHOOTING.md §2 Pod OOMKilled](./TROUBLESHOOTING.md#2-pod-oomkilled) |

### 4.4 告警级别与响应时效

| 级别 | 响应时效 | 通知间隔 | 通知渠道 |
|---|---|---|---|
| critical | 立即响应（< 5 分钟） | 每 1 小时重复 | 钉钉 + 邮件 + 电话 |
| warning | 30 分钟内响应 | 每 4 小时重复 | 钉钉 + 邮件 |

**抑制规则**：同 namespace + service 下，critical 触发时自动抑制 warning。

---

## 5. Grafana Dashboards

### 5.1 Dashboard 概览

| Dashboard | UID | 名称 | 关注指标 |
|---|---|---|---|
| 1 | ks-api | 知识系统 - API 核心指标 | QPS、错误率、延迟、状态码分布 |
| 2 | ks-biz | 知识系统 - 业务指标 | LLM 调用、Agent 任务、知识库 |
| 3 | ks-infra | 知识系统 - 资源与基础设施 | CPU、内存、PVC、DB 连接 |

### 5.2 访问 Dashboard

```bash
# 端口转发 Grafana
kubectl port-forward svc/kube-prometheus-stack-grafana 3000:80 -n monitoring

# 访问 http://localhost:3000
# 用户名：admin
# 密码：见部署时配置，或运行：
kubectl get secret kube-prometheus-stack-grafana -n monitoring \
  -o jsonpath="{.data.admin-password}" | base64 --decode ; echo
```

### 5.3 Dashboard 1：API 核心指标（ks-api）

**包含面板：**
1. QPS（每秒请求数）— stat
2. 5xx 错误率 — gauge
3. P99/P95/P50 延迟 — graph
4. HTTP 状态码分布 — pie chart
5. 在处理请求数 — stat
6. 各端点 QPS Top 10 — bar gauge

**关键指标解读：**
- QPS 反映流量水平
- 5xx 错误率 < 1% 为正常
- P99 < 2s 为正常
- 在处理请求数 < 50 为正常

### 5.4 Dashboard 2：业务指标（ks-biz）

**包含面板：**
1. LLM 调用 QPS — graph
2. LLM 错误率 — gauge
3. LLM P99 延迟 — graph
4. LLM 缓存命中率 — gauge
5. Agent 任务执行数 — graph
6. Agent 任务成功率 — gauge
7. 知识库切片数 — stat

### 5.5 Dashboard 3：资源与基础设施（ks-infra）

**包含面板：**
1. Pod CPU 使用率 — graph（按 Pod）
2. Pod 内存使用率 — graph（按 Pod）
3. PVC 使用率 — bar gauge
4. 数据库连接数 — gauge
5. 节点资源概览 — stat
6. Pod 重启次数 — stat

---

## 6. 告警通知配置

### 6.1 通知渠道

| 渠道 | 配置方式 | 适用场景 |
|---|---|---|
| 钉钉机器人 | webhook URL | 国内首选 |
| 企业微信 | webhook URL | 企业微信用户 |
| Slack | api_url + channel | 国际团队 |
| 邮件 | SMTP 配置 | 备用渠道 |

### 6.2 钉钉机器人配置

```yaml
# values-prod.yaml
monitoring:
  alertmanager:
    enabled: true
    channel: dingtalk
    webhookUrl: "https://oapi.dingtalk.com/robot/send?access_token=xxx"
```

**创建钉钉机器人：**
1. 钉钉群 → 群设置 → 智能群助手 → 添加机器人
2. 选择"自定义"机器人
3. 安全设置：自定义关键词 `knowledge-system` 或 IP 白名单
4. 复制 webhook URL，填入 values-prod.yaml

### 6.3 邮件配置

```yaml
# values-prod.yaml
monitoring:
  alertmanager:
    enabled: true
    channel: email
    smtp:
      from: "alerts@knowledge-system.com"
      smarthost: "smtp.exmail.qq.com:465"
      authUsername: "alerts@knowledge-system.com"
      authPassword: "your-smtp-password"
```

### 6.4 多渠道并行通知

如需同时发送钉钉 + 邮件，修改 [alertmanager-config.yaml](../../deploy/helm/templates/monitoring/alertmanager-config.yaml) 添加多个 receiver：

```yaml
receivers:
  - name: 'default'
    webhook_configs:
      - url: 'https://oapi.dingtalk.com/robot/send?access_token=xxx'
        send_resolved: true
    email_configs:
      - to: 'alerts@knowledge-system.com'
        from: 'alerts@knowledge-system.com'
        smarthost: 'smtp.exmail.qq.com:465'
        auth_username: 'alerts@knowledge-system.com'
        auth_password: 'xxx'
        send_resolved: true
```

### 6.5 告警分组与抑制

**分组规则：** 按 `alertname + namespace + service` 分组，同一组告警合并发送。

**抑制规则：** critical 触发时，同 namespace + service 的 warning 自动抑制（避免告警风暴）。

**重发间隔：**
- critical：每 1 小时重复
- warning：每 4 小时重复
- resolved（恢复）：自动发送恢复通知

---

## 7. 日常监控指标解读

### 7.1 健康度评估清单

| 指标 | 健康范围 | 警戒范围 | 危险范围 |
|---|---|---|---|
| API 5xx 错误率 | < 1% | 1-5% | > 5% |
| P99 延迟 | < 1s | 1-2s | > 2s |
| 在处理请求数 | < 30 | 30-100 | > 100 |
| LLM 错误率 | < 5% | 5-30% | > 30% |
| LLM P99 延迟 | < 10s | 10-30s | > 30s |
| DB 连接数 | < 15 | 15-25 | > 25 |
| 容器内存使用率 | < 70% | 70-85% | > 85% |
| PVC 使用率 | < 70% | 70-85% | > 85% |

### 7.2 趋势分析

```bash
# 通过 Grafana 查看趋势：
# 1. QPS 周环比（识别流量增长）
# 2. P99 延迟 7 天趋势（识别性能退化）
# 3. 内存使用率 24 小时趋势（识别内存泄漏）
# 4. PVC 增长率（预测何时扩容）
```

### 7.3 容量预测

**PVC 增长率预测：**

```promql
# 过去 7 天 PVC 日均增长率
deriv(kubelet_volume_stats_used_bytes[7d]) * 86400

# 预计 N 天后用尽
(kubelet_volume_stats_capacity_bytes - kubelet_volume_stats_used_bytes)
/
deriv(kubelet_volume_stats_used_bytes[7d]) / 86400
```

---

## 8. 容量规划

### 8.1 资源基线

| 服务 | CPU 请求 | CPU 上限 | 内存请求 | 内存上限 | 副本 |
|---|---|---|---|---|---|
| frontend | 50-100m | 200-300m | 64-128Mi | 128-256Mi | 2-3 |
| backend | 100-500m | 500-2000m | 256Mi-1Gi | 1-2Gi | 2-4 |
| celery-worker | 100-300m | 500-1000m | 256-512Mi | 512Mi-1Gi | 2-3 |
| postgres | 100-200m | 500-1000m | 256-512Mi | 1-2Gi | 1 |
| redis | 50m | 200m | 64-128Mi | 64-256Mi | 1 |
| chroma | 100-200m | 500-1000m | 256-512Mi | 1-2Gi | 1 |

### 8.2 容量评估公式

```bash
# 1. 计算当前资源利用率
utilization = requests_usage / requests_limit

# 2. 评估所需副本数
required_replicas = current_replicas * (current_utilization / target_utilization)

# 例：backend 4 副本，CPU 利用率 80%，目标 65%
# required = 4 * (80/65) = 4.92 → 5 副本
```

### 8.3 扩容决策树

```
资源瓶颈
  │
  ├─ CPU 瓶颈（利用率 > 70%）？
  │    ├─ HPA 已启用 → 自动扩容
  │    └─ HPA 未启用 → 手动 kubectl scale
  │
  ├─ 内存瓶颈（利用率 > 85%）？
  │    ├─ 突发流量 → 扩容副本
  │    └─ 持续高 → 调高 memory limit
  │
  └─ PVC 瓶颈（使用率 > 85%）？
       ├─ 临时数据 → 清理
       └─ 业务数据 → 扩容 PVC
```

### 8.4 监控数据来源

| 决策 | 数据来源 | 查询示例 |
|---|---|---|
| 扩容副本 | HPA 历史决策 | `kubectl describe hpa` |
| 扩容 PVC | PVC 7 天增长率 | 见 §7.3 PromQL |
| 调整资源 limit | 容器 CPU/内存趋势 | Grafana ks-infra Dashboard |
| 节点扩容 | 节点资源使用率 | `kubectl top nodes` |

---

## 相关文档

| 文档 | 说明 |
|---|---|
| [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) | 部署运维手册 |
| [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) | 故障处理指南（告警对应排查） |
| [RELEASE_SOP.md](./RELEASE_SOP.md) | 发布操作手册（监控验证） |
| [BACKUP_RECOVERY.md](./BACKUP_RECOVERY.md) | 备份恢复手册 |
| [HELM_CHART_GUIDE.md](./HELM_CHART_GUIDE.md) | Helm Chart 使用文档（监控参数） |
| [K8S_DEPLOYMENT_PLAN.md](../K8S_DEPLOYMENT_PLAN.md) | K8s 部署总体规划 |
