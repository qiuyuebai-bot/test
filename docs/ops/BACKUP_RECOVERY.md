# 备份恢复手册

> 版本：v1.0 · 编制日期：2026-07-07
> 适用项目：领域知识个性化生成与多智能体协同决策系统
> 关联文档：[DR_RUNBOOK.md](../DR_RUNBOOK.md)（灾难恢复演练）、[DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)

本手册覆盖日常备份策略、备份验证、恢复操作、定期演练全流程。灾难恢复演练详见 [DR_RUNBOOK.md](../DR_RUNBOOK.md)。

---

## 目录

1. [备份架构总览](#1-备份架构总览)
2. [备份策略](#2-备份策略)
3. [启用备份](#3-启用备份)
4. [备份验证](#4-备份验证)
5. [数据库恢复操作](#5-数据库恢复操作)
6. [PVC 恢复操作](#6-pvc-恢复操作)
7. [全量恢复流程](#7-全量恢复流程)
8. [备份监控](#8-备份监控)
9. [备份清理](#9-备份清理)
10. [常见问题](#10-常见问题)

---

## 1. 备份架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                    K8s 集群（knowledge-prod）              │
│                                                             │
│  ┌──────────────┐         ┌──────────────┐                  │
│  │  postgres    │         │  PVC         │                  │
│  │  StatefulSet │         │  (uploads/   │                  │
│  │              │         │   chroma)    │                  │
│  └──────┬───────┘         └──────┬───────┘                  │
│         │                        │                          │
│         │ pg_dump                │ snapshot                 │
│         ▼                        ▼                          │
│  ┌──────────────┐         ┌──────────────┐                  │
│  │  backup      │         │  Velero      │                  │
│  │  CronJob     │         │  Schedule    │                  │
│  │  (每日 02:00)│         │  (每日 02:00)│                  │
│  └──────┬───────┘         └──────┬───────┘                  │
│         │                        │                          │
└─────────┼────────────────────────┼──────────────────────────┘
          │                        │
          ▼                        ▼
   ┌──────────────┐         ┌──────────────┐
   │  backup PVC  │         │  对象存储     │
   │  (集群内)    │         │  (OSS/S3)    │
   │              │         │              │
   │  db_backup_  │         │  -           │
   │  *.dump      │         │  VolumeSnap  │
   │              │         │   shots       │
   │              │         │  -           │
   │              │         │  BackupMeta  │
   │              │         │    data      │
   └──────────────┘         └──────┬───────┘
                                   │
                           ┌───────┴────────┐
                           │ 跨区域复制      │
                           │ (cn-shanghai)  │
                           │ - replica BSL  │
                           └────────────────┘
```

### 备份组件清单

| 组件 | 工具 | 频率 | 保留期 | 存储位置 |
|---|---|---|---|---|
| PostgreSQL 逻辑备份 | pg_dump -Fc | 每日 02:00 | 7-30 天 | backup PVC |
| PVC 卷快照 | Velero Schedule | 每日 02:00 | 7 天（168h） | 对象存储 + 云快照 |
| 跨区域备份复制 | Velero replica BSL | 实时 | 30 天 | 异地对象存储 |

---

## 2. 备份策略

### 2.1 RPO/RTO 目标

| 指标 | 目标 | 实现方式 |
|---|---|---|
| RPO（数据丢失上限） | ≤ 24 小时 | 每日 02:00 全量备份 |
| RTO（恢复时间上限） | ≤ 2 小时 | 自动化脚本 + 标准流程 |
| RTO（数据库） | ≤ 1 小时 | pg_restore + 验证 |
| RTO（PVC） | ≤ 30 分钟 | Velero restore |

### 2.2 多环境备份策略

| 环境 | DB 备份 | Velero 备份 | 跨区域 | 保留期 |
|---|---|---|---|---|
| dev | ❌ | ❌ | ❌ | - |
| staging | ✅ 每日 | ✅ 每日 | ❌ | 14 天 |
| prod | ✅ 每日 | ✅ 每日 | ✅ | 30 天 |

### 2.3 备份内容

**PostgreSQL 逻辑备份包含：**
- 所有业务表（users、knowledge_topics、knowledge_slices、learners、enterprises、training_records、agent_tasks 等）
- Alembic 迁移版本表（alembic_version）
- 系统配置表

**PVC 卷快照包含：**
- postgres 数据卷（如未使用云 RDS）
- redis 数据卷（持久化 AOF）
- chroma 向量库卷
- backend uploads / resources / logs 卷

**不包含：**
- 镜像（在镜像仓库中管理）
- Helm Chart 配置（在 Git 中管理）
- Secrets（建议单独备份到云 KMS）

---

## 3. 启用备份

### 3.1 启用 PostgreSQL 备份 CronJob

```yaml
# values-prod.yaml
backup:
  enabled: true
  schedule: "0 18 * * *"  # UTC 18:00 = 北京时间 02:00
  retention:
    days: 30  # 保留 30 天
  persistence:
    enabled: true
    size: 100Gi  # 根据数据量调整
  resources:
    requests:
      cpu: 50m
      memory: 128Mi
    limits:
      cpu: 200m
      memory: 256Mi
```

```bash
helm upgrade knowledge-system ./deploy/helm \
  -f deploy/helm/values-prod.yaml -n knowledge-prod
```

### 3.2 启用 Velero PVC 备份

**前置：安装 Velero 控制器**

```bash
# 1. 安装 Velero（含 S3/OSS 凭证）
velero install \
  --provider aws \
  --bucket your-backup-bucket \
  --backup-location-config region=cn-hangzhou,s3ForcePathStyle=false \
  --snapshot-location-config region=cn-hangzhou \
  --secret-file credentials-velero \
  --namespace velero

# 2. 等待 Velero 就绪
kubectl get pods -n velero -w
```

**启用 Chart 中的 Velero 配置：**

```yaml
# values-prod.yaml
velero:
  enabled: true
  schedule: "0 2 * * *"  # 每日 02:00
  ttl: "168h"  # 保留 7 天

  backupStorageLocation:
    provider: aws
    bucket: "your-backup-bucket"
    prefix: "knowledge-system"
    region: "cn-hangzhou"
    endpoint: "https://oss-cn-hangzhou.aliyuncs.com"
    accessKey: "${OSS_ACCESS_KEY}"  # 通过 --set 注入
    secretKey: "${OSS_SECRET_KEY}"

  volumeSnapshotLocation:
    provider: aws
    region: "cn-hangzhou"
    enabled: true
```

```bash
helm upgrade knowledge-system ./deploy/helm \
  -f deploy/helm/values-prod.yaml \
  --set velero.backupStorageLocation.accessKey=$OSS_ACCESS_KEY \
  --set velero.backupStorageLocation.secretKey=$OSS_SECRET_KEY \
  -n knowledge-prod
```

### 3.3 启用跨区域备份复制（生产推荐）

```yaml
# values-prod.yaml
velero:
  enabled: true
  replication:
    enabled: true
    provider: aws
    bucket: "your-backup-bucket-replica"
    prefix: "knowledge-system-replica"
    region: "cn-shanghai"  # 异地（与主 cn-hangzhou 不同）
    endpoint: "https://oss-cn-shanghai.aliyuncs.com"
    accessKey: "${OSS_REPLICA_ACCESS_KEY}"
    secretKey: "${OSS_REPLICA_SECRET_KEY}"
```

---

## 4. 备份验证

### 4.1 验证 CronJob 执行状态

```bash
# 1. 查看 CronJob 状态
kubectl get cronjob -n knowledge-prod

# 2. 查看历史 Job
kubectl get jobs -n knowledge-prod --sort-by='.metadata.creationTimestamp' | tail -10

# 3. 查看最近一次备份日志
kubectl logs job/knowledge-system-backup-$(date -u +%Y%m%d) -n knowledge-prod

# 期望日志包含：
# [Backup Job] 开始 PostgreSQL 数据库备份...
# [Backup Job] 执行 pg_dump: /backup/data/db_backup_YYYYMMDD_HHMMSS.dump
# [Backup Job] 备份成功: /backup/data/db_backup_YYYYMMDD_HHMMSS.dump (xxx bytes)
# [Backup Job] 清理完成
# [Backup Job] 备份任务完成
```

### 4.2 验证备份文件完整性

```bash
# 1. 列出所有备份文件
kubectl exec job/knowledge-system-backup-xxx -n knowledge-prod -- \
  ls -lh /backup/data/

# 期望输出（按时间倒序）：
# -rw-r--r-- 1 1000 1000 5.2M Jul 7 18:00 db_backup_20260707_180000.dump
# -rw-r--r-- 1 1000 1000 5.1M Jul 6 18:00 db_backup_20260706_180000.dump
# ...

# 2. 验证备份文件可读（pg_restore --list）
kubectl exec job/knowledge-system-backup-xxx -n knowledge-prod -- \
  pg_restore --list /backup/data/db_backup_20260707_180000.dump | head -20

# 期望输出：表清单（users、knowledge_topics、...）
```

### 4.3 验证 Velero 备份状态

```bash
# 1. 查看 Velero 备份列表
velero backup get

# 期望输出：
# NAME                              STATUS      ERRORS   WARNINGS   CREATED
# knowledge-system-backup-20260707  Completed   0        0          2026-07-07 02:00:00
# knowledge-system-backup-20260706  Completed   0        0          2026-07-06 02:00:00

# 2. 查看备份详情
velero backup describe knowledge-system-backup-20260707 --details

# 3. 查看备份存储位置
velero backup-location get
```

### 4.4 自动化验证（建议接入 CI）

```bash
# 创建验证脚本 scripts/verify-backup.sh
#!/bin/bash
set -e

LATEST_BACKUP=$(kubectl exec job/knowledge-system-backup-xxx -n knowledge-prod -- \
  ls -t /backup/data/db_backup_*.dump | head -1)

BACKUP_SIZE=$(kubectl exec job/knowledge-system-backup-xxx -n knowledge-prod -- \
  wc -c < "$LATEST_BACKUP")

if [ "$BACKUP_SIZE" -lt 1024 ]; then
  echo "FAIL: 备份文件过小 ($BACKUP_SIZE bytes)"
  exit 1
fi

echo "OK: 备份文件大小 $BACKUP_SIZE bytes"
```

---

## 5. 数据库恢复操作

使用 [restore-db.sh](../../deploy/scripts/restore-db.sh) 脚本。

### 5.1 查看可用备份

```bash
bash deploy/scripts/restore-db.sh \
  --release knowledge-system \
  --namespace knowledge-prod \
  --list
```

输出示例：
```
[INFO] 可用备份列表：
  /backup/data/db_backup_20260707_180000.dump  (5.2M)
  /backup/data/db_backup_20260706_180000.dump  (5.1M)
  /backup/data/db_backup_20260705_180000.dump  (5.1M)
  ...
```

### 5.2 方式 1：从指定备份文件恢复

```bash
bash deploy/scripts/restore-db.sh \
  --release knowledge-system \
  --namespace knowledge-prod \
  --backup-file /backup/data/db_backup_20260707_180000.dump
```

脚本流程：
1. 创建临时恢复 Pod（挂载 backup PVC）
2. 等待数据库就绪
3. 执行 `pg_restore --clean --if-exists`
4. 验证 `SELECT 1` 与表数量
5. 清理临时 Pod

### 5.3 方式 2：从最新备份恢复

```bash
bash deploy/scripts/restore-db.sh \
  --release knowledge-system \
  --namespace knowledge-prod \
  --latest
```

### 5.4 方式 3：Dry-Run 预览

```bash
bash deploy/scripts/restore-db.sh \
  --release knowledge-system \
  --namespace knowledge-prod \
  --latest \
  --dry-run
```

### 5.5 方式 4：跳过验证（紧急恢复）

```bash
bash deploy/scripts/restore-db.sh \
  --release knowledge-system \
  --namespace knowledge-prod \
  --latest \
  --no-verify \
  --skip-stop
```

### 5.6 恢复后验证

```bash
# 1. 检查表数量
kubectl exec statefulset/knowledge-system-postgres -n knowledge-prod -- \
  psql -U postgres -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';"

# 2. 检查关键表数据
kubectl exec statefulset/knowledge-system-postgres -n knowledge-prod -- \
  psql -U postgres -c "SELECT count(*) FROM users;"

# 3. 检查 alembic 版本
kubectl exec statefulset/knowledge-system-postgres -n knowledge-prod -- \
  psql -U postgres -c "SELECT version_num FROM alembic_version;"

# 4. 冒烟测试 backend
bash deploy/scripts/smoke-test.sh \
  --host http://knowledge-system-backend:8000
```

---

## 6. PVC 恢复操作

使用 [restore-pvc.sh](../../deploy/scripts/restore-pvc.sh) 脚本。

### 6.1 查看可用 Velero 备份

```bash
bash deploy/scripts/restore-pvc.sh \
  --list
```

输出示例：
```
[INFO] 可用 Velero 备份：
  knowledge-system-backup-20260707  Completed   2026-07-07 02:00:00
  knowledge-system-backup-20260706  Completed   2026-07-06 02:00:00
  ...
```

### 6.2 恢复到原命名空间

```bash
bash deploy/scripts/restore-pvc.sh \
  --backup-name knowledge-system-backup-20260707 \
  --namespace knowledge-prod
```

### 6.3 恢复到新命名空间（灾难恢复）

```bash
bash deploy/scripts/restore-pvc.sh \
  --backup-name knowledge-system-backup-20260707 \
  --namespace knowledge-prod \
  --target-namespace knowledge-prod-recovered
```

### 6.4 选择性恢复（仅 PVC，不含 Secret/ConfigMap）

```bash
bash deploy/scripts/restore-pvc.sh \
  --backup-name knowledge-system-backup-20260707 \
  --namespace knowledge-prod \
  --no-secrets \
  --no-configmaps
```

### 6.5 恢复后验证

```bash
# 1. 查看 PVC 状态
kubectl get pvc -n knowledge-prod

# 2. 查看 Pod 是否挂载成功
kubectl get pods -n knowledge-prod -o wide

# 3. 进入 Pod 检查数据
kubectl exec deployment/knowledge-system-backend -n knowledge-prod -- \
  ls -la /app/data/uploads
```

---

## 7. 全量恢复流程

适用于灾难场景：集群丢失、区域故障、数据完全损坏。

### 7.1 全量恢复步骤

```
Step 1: 准备新集群（或新命名空间）
  │
Step 2: 部署基础设施（postgres/redis StatefulSet 空实例）
  │
Step 3: 从 Velero 恢复 PVC（postgres 数据卷 + uploads 卷）
  │  └─ 如 Velero 不可用，从 pg_dump 恢复数据库
  │
Step 4: 部署应用（backend/frontend/celery-worker）
  │
Step 5: 验证服务（冒烟测试）
  │
Step 6: 切换流量（DNS / Ingress）
```

### 7.2 详细操作

详见 [DR_RUNBOOK.md](../DR_RUNBOOK.md) §4 全量恢复流程。

### 7.3 恢复演练

建议每季度执行一次灾难恢复演练，详见 [DR_RUNBOOK.md](../DR_RUNBOOK.md) §5 演练流程。

---

## 8. 备份监控

### 8.1 监控指标

| 指标 | 阈值 | 告警动作 |
|---|---|---|
| 备份 Job 失败 | 连续 1 次失败 | 立即通知 On-Call |
| 备份文件大小 < 1KB | 异常 | 立即通知 |
| 最近一次备份 > 26 小时前 | 错过备份窗口 | 立即通知 |
| backup PVC 使用率 > 85% | 空间不足 | 通知扩容 |
| Velero 备份失败 | PartiallyFailed | 通知排查 |

### 8.2 告警配置

备份相关告警已在 [prometheusrules.yaml](../../deploy/helm/templates/monitoring/prometheusrules.yaml) 中配置：

- `KnowledgeSystemPVCDiskRunningFull`：PVC 使用率 > 85%
- `KnowledgeSystemBackupJobFailed`：backup CronJob 失败（自定义规则）

### 8.3 日常检查脚本

```bash
#!/bin/bash
# scripts/check-backup-health.sh
NS=knowledge-prod

echo "===== 1. 最近备份 Job 状态 ====="
kubectl get jobs -n $NS -l app.kubernetes.io/component=backup --sort-by='.metadata.creationTimestamp' | tail -5

echo ""
echo "===== 2. 最近备份文件 ====="
kubectl exec job/knowledge-system-backup-xxx -n $NS -- \
  ls -lh /backup/data/ | tail -5

echo ""
echo "===== 3. backup PVC 使用率 ====="
kubectl exec job/knowledge-system-backup-xxx -n $NS -- df -h /backup/data

echo ""
echo "===== 4. Velero 备份状态 ====="
velero backup get | tail -5
```

---

## 9. 备份清理

### 9.1 自动清理（已配置）

- **PostgreSQL 备份**：CronJob 内 `find -mtime +N -delete` 自动清理（见 [cronjob.yaml](../../deploy/helm/templates/backup/cronjob.yaml) L66）
- **Velero 备份**：`ttl: 168h` 自动过期（见 [values.yaml](../../deploy/helm/values.yaml) L311）

### 9.2 手动清理

```bash
# 1. 清理过期 pg_dump 备份
kubectl exec job/knowledge-system-backup-xxx -n knowledge-prod -- \
  find /backup/data -name "db_backup_*.dump" -mtime +30 -delete

# 2. 清理过期 Velero 备份
velero backup delete --older-than 720h --confirm

# 3. 清理已完成的备份 Job
kubectl delete jobs -n knowledge-prod --field-selector status.successful=1
```

### 9.3 灾难场景：备份空间不足

```bash
# 紧急扩容 backup PVC
kubectl patch pvc knowledge-system-backup-data -n knowledge-prod \
  -p '{"spec":{"resources":{"requests":{"storage":"200Gi"}}}}'

# 或清理旧备份释放空间
kubectl exec job/knowledge-system-backup-xxx -n knowledge-prod -- \
  find /backup/data -name "db_backup_*.dump" -mtime +7 -delete
```

---

## 10. 常见问题

### 10.1 备份 Job 失败

```bash
# 查看失败原因
kubectl logs job/knowledge-system-backup-xxx -n knowledge-prod

# 常见错误：
# 1. pg_dump: connection refused
#    → 数据库未就绪，检查 postgres Pod 状态
# 2. 备份文件过小 (xxx bytes)
#    → 数据库为空 / pg_dump 异常退出
# 3. No space left on device
#    → backup PVC 空间不足，扩容或清理
# 4. pg_dump: server version mismatch
#    → backup Pod 镜像与 DB 版本不匹配（应使用 postgres:16-alpine）
```

### 10.2 恢复失败

```bash
# 查看恢复脚本详细日志
bash deploy/scripts/restore-db.sh --latest --verbose

# 常见错误：
# 1. pg_restore: error: could not execute query
#    → SQL 冲突（如重复对象），加 --clean --if-exists
# 2. CREATE DATABASE permission denied
#    → 数据库用户权限不足，使用超级用户
# 3. database "knowledge_system" is being accessed by other users
#    → 先停止 backend Pod，再恢复
```

### 10.3 Velero 备份失败

```bash
# 查看详情
velero backup describe knowledge-system-backup-xxx --details

# 常见错误：
# 1. PartiallyFailed
#    → 部分 PVC 快照失败，查看 Failure Reason
# 2. BackupStorageLocation unavailable
#    → 对象存储不可达，检查网络与凭证
# 3. VolumeSnapshot failure
#    → 云厂商 CSI 驱动不支持，检查 volumeSnapshotLocation 配置
```

### 10.4 跨区域复制失败

```bash
# 查看 replica BackupStorageLocation 状态
velero backup-location get

# 期望：replica 可用
# 如不可用，检查：
# 1. 异地 OSS bucket 是否存在
# 2. 凭证是否正确
# 3. 跨区域网络是否通
```

---

## 相关文档

| 文档 | 说明 |
|---|---|
| [DR_RUNBOOK.md](../DR_RUNBOOK.md) | 灾难恢复演练手册（RTO/RPO 测试） |
| [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) | 部署运维手册 |
| [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) | 故障处理指南（§10 备份任务失败） |
| [MONITORING_ALERTING.md](./MONITORING_ALERTING.md) | 监控告警手册 |
| [HELM_CHART_GUIDE.md](./HELM_CHART_GUIDE.md) | Helm Chart 使用文档（备份参数说明） |
