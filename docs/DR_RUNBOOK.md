# 灾难恢复演练手册（DR Runbook）

> **版本**: 1.0  
> **更新日期**: 2026-07-07  
> **适用环境**: staging / production

## 1. 目标与范围

### 1.1 文档目标
本文档定义领域知识个性化生成与多智能体协同决策系统的灾难恢复策略，提供标准化的备份与恢复操作流程，确保在数据丢失、系统故障或区域级灾难时能够快速恢复服务。

### 1.2 适用范围
- PostgreSQL 数据库备份与恢复
- PVC 持久化存储备份与恢复
- 跨区域备份复制
- 灾难恢复演练流程

---

## 2. RTO/RPO 定义

| 指标 | 定义 | 目标 | 实现方式 |
|------|------|------|----------|
| **RPO** (Recovery Point Objective) | 数据丢失容忍上限 | **≤ 24 小时** | PostgreSQL 每日 02:00 全量备份 + Velero 每日 02:00 PVC 快照 |
| **RTO** (Recovery Time Objective) | 服务恢复时间上限 | **≤ 2 小时** | 自动化恢复脚本 + 标准化操作流程 |
| **RTO (PVC)** | PVC 恢复时间 | **≤ 30 分钟** | Velero restore 命令 |
| **RTO (DB)** | 数据库恢复时间 | **≤ 1 小时** | pg_restore + 验证脚本 |

### 2.1 备份策略

| 备份类型 | 频率 | 保留期 | 工具 | 存储位置 |
|----------|------|--------|------|----------|
| PostgreSQL 逻辑备份 | 每日 02:00 (UTC 18:00) | 7 天 | pg_dump (CronJob) | backup PVC |
| PVC 卷快照 | 每日 02:00 | 7 天 | Velero Schedule | 对象存储 + 云快照 |
| 跨区域复制 | 实时同步 | 30 天 | Velero BackupStorageLocation | 异地对象存储 |

---

## 3. 备份配置

### 3.1 启用 PostgreSQL 备份 CronJob

```bash
# 启用备份 CronJob
helm upgrade knowledge ./deploy/helm \
  --namespace knowledge-prod \
  --set backup.enabled=true \
  --set backup.schedule="0 18 * * *" \
  --set backup.retention.days=7
```

### 3.2 启用 Velero PVC 备份

```bash
# 启用 Velero（需要集群已安装 Velero controller）
helm upgrade knowledge ./deploy/helm \
  --namespace knowledge-prod \
  --set velero.enabled=true \
  --set velero.schedule="0 2 * * *" \
  --set velero.backupStorageLocation.bucket=your-bucket-name \
  --set velero.backupStorageLocation.region=cn-hangzhou \
  --set velero.backupStorageLocation.endpoint=https://oss-cn-hangzhou.aliyuncs.com \
  --set velero.backupStorageLocation.accessKey=YOUR_ACCESS_KEY \
  --set velero.backupStorageLocation.secretKey=YOUR_SECRET_KEY
```

### 3.3 启用跨区域备份复制

```bash
helm upgrade knowledge ./deploy/helm \
  --namespace knowledge-prod \
  --set velero.replication.enabled=true \
  --set velero.replication.bucket=your-replica-bucket \
  --set velero.replication.region=cn-shanghai \
  --set velero.replication.endpoint=https://oss-cn-shanghai.aliyuncs.com \
  --set velero.replication.accessKey=REPLICA_ACCESS_KEY \
  --set velero.replication.secretKey=REPLICA_SECRET_KEY
```

---

## 4. 恢复操作流程

### 4.1 PostgreSQL 数据库恢复

#### 4.1.1 列出可用备份

```bash
./deploy/scripts/restore-db.sh \
  --namespace knowledge-prod \
  --release knowledge \
  --list
```

#### 4.1.2 从最新备份恢复

```bash
./deploy/scripts/restore-db.sh \
  --namespace knowledge-prod \
  --release knowledge \
  --latest
```

#### 4.1.3 从指定备份恢复

```bash
./deploy/scripts/restore-db.sh \
  --namespace knowledge-prod \
  --release knowledge \
  --backup-file db_backup_20260101_020000.dump
```

#### 4.1.4 手动恢复步骤（如脚本不可用）

```bash
# 1. 找到 backup PVC
kubectl get pvc -n knowledge-prod | grep backup

# 2. 创建临时 Pod 挂载 backup PVC
kubectl run restore-temp --namespace=knowledge-prod \
  --image=postgres:16-alpine --restart=Never \
  --overrides='{"spec":{"containers":[{"name":"restore","image":"postgres:16-alpine","command":["sleep","600"],"volumeMounts":[{"name":"backup","mountPath":"/backup"}]}],"volumes":[{"name":"backup","persistentVolumeClaim":{"claimName":"knowledge-knowledge-system-backup-data"}}]}}'

# 3. 执行 pg_restore
kubectl exec restore-temp --namespace=knowledge-prod -- \
  sh -c 'pg_restore "${DATABASE_URL}" --clean --if-exists /backup/data/db_backup_xxx.dump'

# 4. 验证
kubectl exec knowledge-backend-xxx --namespace=knowledge-prod -- \
  python -c "from app.database import engine; from sqlalchemy import text; print(engine.connect().execute(text('SELECT count(*) FROM learners')).scalar())"

# 5. 清理临时 Pod
kubectl delete pod restore-temp --namespace=knowledge-prod
```

### 4.2 PVC 恢复（Velero）

#### 4.2.1 列出可用 Velero 备份

```bash
./deploy/scripts/restore-pvc.sh --list --namespace knowledge-prod
# 或直接使用 velero CLI
velero backup get
```

#### 4.2.2 从 Velero 备份恢复

```bash
./deploy/scripts/restore-pvc.sh \
  --backup-name knowledge-backup-20260101 \
  --namespace knowledge-prod
```

#### 4.2.3 恢复到新命名空间（用于测试）

```bash
./deploy/scripts/restore-pvc.sh \
  --backup-name knowledge-backup-20260101 \
  --namespace knowledge-prod \
  --target-namespace knowledge-restored
```

#### 4.2.4 手动恢复步骤

```bash
# 1. 创建 Restore
velero restore create knowledge-restore-001 \
  --from-backup knowledge-backup-20260101 \
  --namespace-mappings knowledge-prod:knowledge-restored

# 2. 查看恢复状态
velero restore get knowledge-restore-001

# 3. 查看恢复详情
velero restore describe knowledge-restore-001 --details

# 4. 查看恢复日志
velero restore logs knowledge-restore-001
```

### 4.3 全量恢复（数据库 + PVC）

当需要完整恢复整个系统时，按以下顺序执行：

```bash
# 步骤 1: 恢复 PVC（包括 backup PVC 中的数据库备份文件）
./deploy/scripts/restore-pvc.sh \
  --backup-name knowledge-backup-20260101 \
  --namespace knowledge-prod

# 步骤 2: 等待 PostgreSQL StatefulSet 启动
kubectl rollout status statefulset/knowledge-knowledge-system-postgres \
  --namespace=knowledge-prod --timeout=300s

# 步骤 3: 恢复数据库
./deploy/scripts/restore-db.sh \
  --namespace knowledge-prod \
  --release knowledge \
  --latest

# 步骤 4: 重启 backend 服务（加载最新数据）
kubectl rollout restart deployment/knowledge-knowledge-system-backend \
  --namespace=knowledge-prod

# 步骤 5: 验证服务
kubectl get pods --namespace=knowledge-prod
curl -s http://<LB_IP>/health/ready
```

---

## 5. 灾难恢复演练

### 5.1 演练计划

| 演练类型 | 频率 | 场景 | 负责人 |
|----------|------|------|--------|
| 数据库恢复 | 每月 | 从备份恢复数据库到测试环境 | DBA |
| PVC 恢复 | 每季度 | 从 Velero 备份恢复 PVC | 运维 |
| 全量恢复 | 每半年 | 完整恢复到新集群 | 运维 + 开发 |
| 跨区域故障切换 | 每年 | 模拟主区域故障，从异地恢复 | 运维 |

### 5.2 演练流程（数据库恢复）

#### 准备阶段
```bash
# 1. 创建演练命名空间
kubectl create namespace knowledge-dr-test

# 2. 部署空集群（仅数据库，无数据）
helm install knowledge-test ./deploy/helm \
  --namespace knowledge-dr-test \
  --set frontend.enabled=false \
  --set backend.enabled=false \
  --set backup.enabled=false

# 3. 等待数据库就绪
kubectl rollout status statefulset/knowledge-test-knowledge-system-postgres \
  --namespace=knowledge-dr-test
```

#### 执行阶段
```bash
# 4. 从生产备份恢复到演练环境
./deploy/scripts/restore-db.sh \
  --namespace knowledge-dr-test \
  --release knowledge-test \
  --backup-file db_backup_20260101_020000.dump

# 5. 记录 RTO
#    开始时间: _________
#    恢复完成: _________
#    RTO = 恢复完成 - 开始时间
```

#### 验证阶段
```bash
# 6. 数据完整性验证
kubectl exec -n knowledge-dr-test knowledge-test-knowledge-system-postgres-0 -- \
  psql -U postgres -d knowledge_system -c "
    SELECT 'learners' AS table_name, count(*) FROM learners
    UNION ALL SELECT 'agent_tasks', count(*) FROM agent_tasks
    UNION ALL SELECT 'knowledge_documents', count(*) FROM knowledge_documents
    UNION ALL SELECT 'knowledge_slices', count(*) FROM knowledge_slices;
  "

# 7. 对比生产数据量
kubectl exec -n knowledge-prod knowledge-knowledge-system-postgres-0 -- \
  psql -U postgres -d knowledge_system -c "
    SELECT 'learners' AS table_name, count(*) FROM learners;
  "

# 8. 应用层验证（部署 backend 后）
kubectl scale deployment knowledge-test-knowledge-system-backend \
  --namespace=knowledge-dr-test --replicas=1
kubectl rollout status deployment/knowledge-test-knowledge-system-backend \
  --namespace=knowledge-dr-test
curl -s http://<test-lb>/health/ready
curl -s http://<test-lb>/api/v1/info
```

#### 清理阶段
```bash
# 9. 删除演练命名空间
kubectl delete namespace knowledge-dr-test
```

### 5.3 演练验证清单

- [ ] 备份文件存在且可读
- [ ] pg_restore 执行成功（无致命错误）
- [ ] 数据库连接验证通过（SELECT 1）
- [ ] 核心表行数与生产一致
- [ ] backend 服务启动成功
- [ ] /health/ready 返回 200
- [ ] /api/v1/info 返回正确版本
- [ ] 关键 API 功能正常（登录、查询学习者列表）
- [ ] RTO 在目标范围内（≤ 1 小时）
- [ ] RPO 在目标范围内（≤ 24 小时）

---

## 6. 故障排查

### 6.1 备份失败

```bash
# 查看 CronJob 执行历史
kubectl get jobs -n knowledge-prod | grep backup

# 查看最新失败的 Job 日志
kubectl logs job/knowledge-knowledge-system-backup-xxx -n knowledge-prod

# 常见原因:
# 1. DATABASE_URL 无法连接 → 检查 postgres StatefulSet 状态
# 2. backup PVC 空间不足 → kubectl exec ... -- df -h /backup/data
# 3. pg_dump 权限问题 → 检查 PGPASSWORD Secret
```

### 6.2 恢复失败

```bash
# 查看 restore Job 日志
kubectl logs job/knowledge-db-restore-xxx -n knowledge-prod

# 常见原因:
# 1. pg_restore --clean 报错（表不存在）→ 使用 --if-exists 或先创建表
# 2. 连接超时 → 检查 postgres StatefulSet 是否就绪
# 3. 备份文件损坏 → 尝试另一个备份
```

### 6.3 Velero 备份失败

```bash
# 查看 Velero 备份状态
velero backup get
velero backup describe <backup-name> --details

# 查看 Velero controller 日志
kubectl logs deployment/velero -n velero | tail -50

# 常见原因:
# 1. 对象存储凭证错误 → 检查 Secret
# 2. CSI 驱动不支持快照 → 检查 volumeSnapshotLocation 配置
# 3. 命名空间 label 不匹配 → 确保 app.kubernetes.io/part-of=knowledge-system
```

---

## 7. 附录

### 7.1 备份文件命名规则
```
db_backup_YYYYMMDD_HHMMSS.dump
```
- 格式：pg_dump 自定义格式（-Fc），支持压缩和选择性恢复
- 示例：`db_backup_20260101_020000.dump`

### 7.2 相关文件

| 文件 | 说明 |
|------|------|
| [deploy/helm/templates/backup/cronjob.yaml](file:///c:/Users/22602/Desktop/新建文件夹/deploy/helm/templates/backup/cronjob.yaml) | PostgreSQL 备份 CronJob |
| [deploy/helm/templates/backup/velero-backup.yaml](file:///c:/Users/22602/Desktop/新建文件夹/deploy/helm/templates/backup/velero-backup.yaml) | Velero 备份配置（BackupStorageLocation + Schedule） |
| [deploy/scripts/restore-db.sh](file:///c:/Users/22602/Desktop/新建文件夹/deploy/scripts/restore-db.sh) | 数据库恢复脚本 |
| [deploy/scripts/restore-pvc.sh](file:///c:/Users/22602/Desktop/新建文件夹/deploy/scripts/restore-pvc.sh) | PVC 恢复脚本 |
| [backend/scripts/backup_db.py](file:///c:/Users/22602/Desktop/新建文件夹/backend/scripts/backup_db.py) | 本地备份脚本（开发环境用） |

### 7.3 紧急联系人

| 角色 | 职责 | 联系方式 |
|------|------|----------|
| 运维负责人 | 备份恢复执行 | _________ |
| DBA | 数据库恢复 | _________ |
| 开发负责人 | 应用验证 | _________ |
| 安全负责人 | 审计与合规 | _________ |
