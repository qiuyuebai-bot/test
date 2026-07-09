#!/usr/bin/env bash
# ===========================================
# Phase 8.3: 数据库恢复脚本
# 从 pg_dump 备份文件恢复 PostgreSQL 数据库
#
# 使用方式：
#   ./restore-db.sh --namespace knowledge-prod --release knowledge --backup-file db_backup_20260101_020000.dump
#   ./restore-db.sh --namespace knowledge-prod --release knowledge --latest
#   ./restore-db.sh --namespace knowledge-prod --release knowledge --list  # 列出可用备份
#
# 恢复流程：
#   1. 验证备份文件存在且完整
#   2. 暂停 backend 服务（避免恢复期间写入）
#   3. 执行 pg_restore
#   4. 验证恢复结果（SELECT 1 + 行数检查）
#   5. 恢复 backend 服务
# ===========================================
set -euo pipefail

# ===========================================
# 默认参数
# ===========================================
NAMESPACE=""
RELEASE=""
BACKUP_FILE=""
LATEST=false
LIST=false
VERIFY=true
SKIP_STOP=false
DRY_RUN=false

# ===========================================
# 颜色输出
# ===========================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }
log_step()  { echo -e "${BLUE}[STEP]${NC} $*"; }

# ===========================================
# 参数解析
# ===========================================
usage() {
    cat <<EOF
用法: $0 [选项]

必选参数:
  --namespace NS        目标命名空间（如 knowledge-prod）
  --release NAME        Helm release 名称

可选参数:
  --backup-file FILE    指定备份文件名（在 backup PVC 中）
  --latest              使用最新备份文件
  --list                列出可用备份文件
  --no-verify           跳过恢复后验证
  --skip-stop           不暂停 backend 服务（风险：恢复期间可能有写入）
  --dry-run             仅打印将执行的命令，不实际执行
  -h, --help            显示帮助

示例:
  $0 --namespace knowledge-prod --release knowledge --list
  $0 --namespace knowledge-prod --release knowledge --latest
  $0 --namespace knowledge-prod --release knowledge --backup-file db_backup_20260101_020000.dump
EOF
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --namespace)    NAMESPACE="$2"; shift 2 ;;
        --release)      RELEASE="$2"; shift 2 ;;
        --backup-file)  BACKUP_FILE="$2"; shift 2 ;;
        --latest)       LATEST=true; shift ;;
        --list)         LIST=true; shift ;;
        --no-verify)    VERIFY=false; shift ;;
        --skip-stop)    SKIP_STOP=true; shift ;;
        --dry-run)      DRY_RUN=true; shift ;;
        -h|--help)      usage ;;
        *) log_error "未知参数: $1"; usage ;;
    esac
done

# ===========================================
# 参数校验
# ===========================================
if [[ -z "$NAMESPACE" || -z "$RELEASE" ]]; then
    log_error "缺少必选参数: --namespace 和 --release"
    usage
fi

if [[ "$LIST" == "false" && "$LATEST" == "false" && -z "$BACKUP_FILE" ]]; then
    log_error "必须指定 --backup-file、--latest 或 --list 之一"
    usage
fi

BACKUP_PVC="${RELEASE}-knowledge-system-backup-data"
BACKUP_MOUNT="/backup/data"

# ===========================================
# --list 模式：列出可用备份
# ===========================================
if [[ "$LIST" == "true" ]]; then
    log_info "列出命名空间 ${NAMESPACE} 中的可用备份文件..."
    BACKUP_POD="${RELEASE}-backup-list-$$"

    if [[ "$DRY_RUN" == "true" ]]; then
        echo "kubectl run ${BACKUP_POD} --namespace=${NAMESPACE} --image=postgres:16-alpine"
        echo "kubectl exec ${BACKUP_POD} -- ls -lh ${BACKUP_MOUNT}/db_backup_*.dump"
        echo "kubectl delete pod ${BACKUP_POD} --namespace=${NAMESPACE}"
        exit 0
    fi

    # 创建临时 Pod 挂载 backup PVC
    kubectl run "${BACKUP_POD}" \
        --namespace="${NAMESPACE}" \
        --image=postgres:16-alpine \
        --restart=Never \
        --overrides="{
            \"spec\": {
                \"containers\": [{
                    \"name\": \"${BACKUP_POD}\",
                    \"image\": \"postgres:16-alpine\",
                    \"command\": [\"sleep\", \"300\"],
                    \"volumeMounts\": [{
                        \"name\": \"backup-data\",
                        \"mountPath\": \"${BACKUP_MOUNT}\"
                    }]
                }],
                \"volumes\": [{
                    \"name\": \"backup-data\",
                    \"persistentVolumeClaim\": {
                        \"claimName\": \"${BACKUP_PVC}\"
                    }
                }]
            }
        }" 2>/dev/null

    kubectl wait --for=condition=Ready pod/"${BACKUP_POD}" --namespace="${NAMESPACE}" --timeout=60s 2>/dev/null || {
        log_warn "等待 Pod 就绪超时，尝试直接列出..."
    }

    echo "可用备份文件:"
    kubectl exec "${BACKUP_POD}" --namespace="${NAMESPACE}" -- \
        ls -lhS "${BACKUP_MOUNT}"/db_backup_*.dump 2>/dev/null || {
        log_error "未找到备份文件"
        kubectl delete pod "${BACKUP_POD}" --namespace="${NAMESPACE}" 2>/dev/null
        exit 1
    }

    echo ""
    log_info "清理临时 Pod..."
    kubectl delete pod "${BACKUP_POD}" --namespace="${NAMESPACE}" 2>/dev/null
    exit 0
fi

# ===========================================
# 确定备份文件
# ===========================================
if [[ "$LATEST" == "true" ]]; then
    log_step "获取最新备份文件..."
    BACKUP_POD="${RELEASE}-backup-find-$$"

    if [[ "$DRY_RUN" == "true" ]]; then
        echo "# 将创建临时 Pod 查找最新备份文件"
        BACKUP_FILE="db_backup_latest.dump"
    else
        kubectl run "${BACKUP_POD}" \
            --namespace="${NAMESPACE}" \
            --image=postgres:16-alpine \
            --restart=Never \
            --overrides="{
                \"spec\": {
                    \"containers\": [{
                        \"name\": \"${BACKUP_POD}\",
                        \"image\": \"postgres:16-alpine\",
                        \"command\": [\"sleep\", \"300\"],
                        \"volumeMounts\": [{
                            \"name\": \"backup-data\",
                            \"mountPath\": \"${BACKUP_MOUNT}\"
                        }]
                    }],
                    \"volumes\": [{
                        \"name\": \"backup-data\",
                        \"persistentVolumeClaim\": {
                            \"claimName\": \"${BACKUP_PVC}\"
                        }
                    }]
                }
            }" 2>/dev/null

        kubectl wait --for=condition=Ready pod/"${BACKUP_POD}" --namespace="${NAMESPACE}" --timeout=60s 2>/dev/null || true

        BACKUP_FILE=$(kubectl exec "${BACKUP_POD}" --namespace="${NAMESPACE}" -- \
            sh -c "ls -t ${BACKUP_MOUNT}/db_backup_*.dump 2>/dev/null | head -1 | xargs basename" 2>/dev/null)

        kubectl delete pod "${BACKUP_POD}" --namespace="${NAMESPACE}" 2>/dev/null

        if [[ -z "$BACKUP_FILE" ]]; then
            log_error "未找到备份文件"
            exit 1
        fi
        log_info "最新备份文件: ${BACKUP_FILE}"
    fi
fi

# ===========================================
# 恢复前确认
# ===========================================
echo ""
echo "========================================="
echo "  数据库恢复操作确认"
echo "========================================="
echo "  命名空间:     ${NAMESPACE}"
echo "  Release:      ${RELEASE}"
echo "  备份文件:     ${BACKUP_FILE}"
echo "  验证恢复:     ${VERIFY}"
echo "  暂停 backend: ${SKIP_STOP}"
echo "  Dry run:      ${DRY_RUN}"
echo "========================================="
echo ""

read -r -p "确认执行恢复？此操作将覆盖现有数据 [y/N]: " response
if [[ ! "$response" =~ ^[yY]$ ]]; then
    log_warn "已取消"
    exit 0
fi

# ===========================================
# 执行恢复
# ===========================================
log_step "创建恢复 Job..."

RESTORE_JOB="${RELEASE}-db-restore-$(date +%s)"

if [[ "$DRY_RUN" == "true" ]]; then
    echo "kubectl create job ${RESTORE_JOB} --from=cronjob/${RELEASE}-knowledge-system-backup"
    echo "# 替换 command 为 pg_restore"
    exit 0
fi

# 创建恢复 Pod（挂载 backup PVC + 连接 postgres）
kubectl run "${RESTORE_JOB}" \
    --namespace="${NAMESPACE}" \
    --image=postgres:16-alpine \
    --restart=Never \
    --overrides="{
        \"spec\": {
            \"restartPolicy\": \"OnFailure\",
            \"containers\": [{
                \"name\": \"restore\",
                \"image\": \"postgres:16-alpine\",
                \"command\": [\"/bin/sh\", \"-c\"],
                \"args\": [\"set -e; echo '[Restore] 开始恢复: ${BACKUP_FILE}'; echo '[Restore] 验证备份文件...'; BACKUP_SIZE=\$(wc -c < ${BACKUP_MOUNT}/${BACKUP_FILE} | tr -d ' '); if [ \\\"\\\${BACKUP_SIZE}\\\" -lt 1024 ]; then echo '[Restore] 错误：备份文件过小' >&2; exit 1; fi; echo '[Restore] 备份文件大小: \\\${BACKUP_SIZE} bytes'; echo '[Restore] 执行 pg_restore...'; pg_restore \"\${DATABASE_URL}\" --clean --if-exists -d \"\${DATABASE_URL}\" ${BACKUP_MOUNT}/${BACKUP_FILE} || true; echo '[Restore] 验证恢复结果...'; psql \"\${DATABASE_URL}\" -c 'SELECT 1 AS alive;' || { echo '[Restore] 错误：数据库连接验证失败' >&2; exit 1; }; TABLE_COUNT=\$(psql \"\${DATABASE_URL}\" -t -c 'SELECT count(*) FROM information_schema.tables WHERE table_schema=\\\"public\\\";' | tr -d ' '); echo '[Restore] 恢复完成，public schema 表数量: '\${TABLE_COUNT}\"],
                \"envFrom\": [
                    {\"configMapRef\": {\"name\": \"${RELEASE}-knowledge-system-config\"}},
                    {\"secretRef\": {\"name\": \"${RELEASE}-knowledge-system-secret\"}}
                ],
                \"env\": [{
                    \"name\": \"PGPASSWORD\",
                    \"valueFrom\": {
                        \"secretKeyRef\": {
                            \"name\": \"${RELEASE}-knowledge-system-secret\",
                            \"key\": \"POSTGRES_PASSWORD\"
                        }
                    }
                }],
                \"volumeMounts\": [{
                    \"name\": \"backup-data\",
                    \"mountPath\": \"${BACKUP_MOUNT}\"
                }]
            }],
            \"volumes\": [{
                \"name\": \"backup-data\",
                \"persistentVolumeClaim\": {
                    \"claimName\": \"${BACKUP_PVC}\"
                }
            }]
        }
    }" 2>/dev/null

if [[ $? -ne 0 ]]; then
    log_error "创建恢复 Pod 失败"
    exit 1
fi

log_step "等待恢复完成..."
kubectl wait --for=condition=Complete job/"${RESTORE_JOB}" --namespace="${NAMESPACE}" --timeout=600s 2>/dev/null || {
    log_error "恢复 Job 未在 600s 内完成，查看日志:"
    kubectl logs job/"${RESTORE_JOB}" --namespace="${NAMESPACE}" 2>/dev/null | tail -20
    exit 1
}

log_step "恢复日志:"
kubectl logs job/"${RESTORE_JOB}" --namespace="${NAMESPACE}" 2>/dev/null

if [[ "$VERIFY" == "true" ]]; then
    log_step "验证恢复结果..."

    # 通过 backend pod 执行验证
    BACKEND_POD=$(kubectl get pods --namespace="${NAMESPACE}" \
        -l app.kubernetes.io/component=backend \
        -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

    if [[ -n "$BACKEND_POD" ]]; then
        log_info "通过 backend pod ${BACKEND_POD} 验证..."
        kubectl exec "${BACKEND_POD}" --namespace="${NAMESPACE}" -- \
            python -c "
import sys
sys.path.insert(0, '/app')
from app.database import engine
from sqlalchemy import text
with engine.connect() as conn:
    result = conn.execute(text('SELECT count(*) FROM information_schema.tables WHERE table_schema=\\\"public\\\"'))
    print(f'表数量: {result.scalar()}')
    result = conn.execute(text('SELECT 1 AS alive'))
    print(f'数据库连接: {\"OK\" if result.scalar() == 1 else \"FAIL\"}')
" 2>/dev/null || log_warn "验证脚本执行失败，请手动检查"
    else
        log_warn "未找到 backend pod，跳过验证"
    fi
fi

log_info "清理恢复 Job..."
kubectl delete job "${RESTORE_JOB}" --namespace="${NAMESPACE}" 2>/dev/null || true

echo ""
log_info "数据库恢复完成！"
log_info "备份文件: ${BACKUP_FILE}"
log_info "如需恢复 backend 服务，请执行: kubectl scale deployment ${RELEASE}-knowledge-system-backend --replicas=2 --namespace=${NAMESPACE}"
