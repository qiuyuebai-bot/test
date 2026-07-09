#!/usr/bin/env bash
# ===========================================
# Phase 8.4: PVC 恢复脚本（Velero restore）
# 从 Velero 备份恢复 PVC 和关联资源
#
# 使用方式：
#   ./restore-pvc.sh --backup-name knowledge-backup-20260101 --namespace knowledge-prod
#   ./restore-pvc.sh --backup-name knowledge-backup-20260101 --namespace knowledge-prod --target-namespace knowledge-restored
#   ./restore-pvc.sh --list --namespace knowledge-prod
#
# 前置条件：
#   - 集群已安装 Velero controller
#   - 已有 Velero Backup（通过 Schedule 或手动创建）
#   - kubectl 和 velero CLI 已安装
# ===========================================
set -euo pipefail

# ===========================================
# 默认参数
# ===========================================
BACKUP_NAME=""
NAMESPACE=""
TARGET_NAMESPACE=""
LIST=false
INCLUDE_PVC=true
INCLUDE_SECRETS=true
INCLUDE_CONFIGMAPS=true
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
  --backup-name NAME    Velero Backup 名称
  --namespace NS        源命名空间

可选参数:
  --target-namespace NS  恢复到目标命名空间（默认与源相同）
  --list                列出可用 Velero Backup
  --no-pvc              不恢复 PVC
  --no-secrets          不恢复 Secret
  --no-configmaps       不恢复 ConfigMap
  --dry-run             仅打印将执行的命令
  -h, --help            显示帮助

示例:
  $0 --list --namespace knowledge-prod
  $0 --backup-name knowledge-backup-20260101 --namespace knowledge-prod
  $0 --backup-name knowledge-backup-20260101 --namespace knowledge-prod --target-namespace knowledge-restored
EOF
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --backup-name)       BACKUP_NAME="$2"; shift 2 ;;
        --namespace)         NAMESPACE="$2"; shift 2 ;;
        --target-namespace)  TARGET_NAMESPACE="$2"; shift 2 ;;
        --list)              LIST=true; shift ;;
        --no-pvc)            INCLUDE_PVC=false; shift ;;
        --no-secrets)        INCLUDE_SECRETS=false; shift ;;
        --no-configmaps)     INCLUDE_CONFIGMAPS=false; shift ;;
        --dry-run)           DRY_RUN=true; shift ;;
        -h|--help)           usage ;;
        *) log_error "未知参数: $1"; usage ;;
    esac
done

# ===========================================
# 前置检查：velero CLI 是否可用
# ===========================================
if ! command -v velero &>/dev/null; then
    log_error "未找到 velero CLI，请先安装: https://velero.io/docs/main/basic-install/"
    exit 1
fi

if ! command -v kubectl &>/dev/null; then
    log_error "未找到 kubectl CLI"
    exit 1
fi

# ===========================================
# --list 模式：列出可用备份
# ===========================================
if [[ "$LIST" == "true" ]]; then
    log_info "列出可用的 Velero Backup..."
    if [[ "$DRY_RUN" == "true" ]]; then
        echo "velero backup get"
        exit 0
    fi
    velero backup get
    exit 0
fi

# ===========================================
# 参数校验
# ===========================================
if [[ -z "$BACKUP_NAME" || -z "$NAMESPACE" ]]; then
    log_error "缺少必选参数: --backup-name 和 --namespace"
    usage
fi

# ===========================================
# 检查备份是否存在
# ===========================================
log_step "检查 Velero Backup ${BACKUP_NAME} 是否存在..."
if [[ "$DRY_RUN" == "true" ]]; then
    echo "velero backup get ${BACKUP_NAME}"
else
    if ! velero backup get "${BACKUP_NAME}" &>/dev/null; then
        log_error "Velero Backup ${BACKUP_NAME} 不存在"
        log_info "可用备份:"
        velero backup get
        exit 1
    fi

    # 检查备份状态
    BACKUP_STATUS=$(velero backup get "${BACKUP_NAME}" -o jsonpath='{.status.phase}' 2>/dev/null || echo "Unknown")
    if [[ "$BACKUP_STATUS" != "Completed" ]]; then
        log_error "备份状态为 ${BACKUP_STATUS}，仅 Completed 状态的备份可用于恢复"
        exit 1
    fi
    log_info "备份状态: ${BACKUP_STATUS}"
fi

# ===========================================
# 恢复前确认
# ===========================================
RESTORE_NAME="${BACKUP_NAME}-restore-$(date +%s)"
[[ -z "$TARGET_NAMESPACE" ]] && TARGET_NAMESPACE="$NAMESPACE"

echo ""
echo "========================================="
echo "  PVC 恢复操作确认"
echo "========================================="
echo "  Velero Backup:    ${BACKUP_NAME}"
echo "  源命名空间:       ${NAMESPACE}"
echo "  目标命名空间:     ${TARGET_NAMESPACE}"
echo "  恢复 PVC:         ${INCLUDE_PVC}"
echo "  恢复 Secret:      ${INCLUDE_SECRETS}"
echo "  恢复 ConfigMap:   ${INCLUDE_CONFIGMAPS}"
echo "  Restore 名称:     ${RESTORE_NAME}"
echo "  Dry run:          ${DRY_RUN}"
echo "========================================="
echo ""

if [[ "$NAMESPACE" == "$TARGET_NAMESPACE" ]]; then
    log_warn "目标命名空间与源相同，恢复将覆盖现有资源！"
fi

read -r -p "确认执行恢复？[y/N]: " response
if [[ ! "$response" =~ ^[yY]$ ]]; then
    log_warn "已取消"
    exit 0
fi

# ===========================================
# 构建 velero restore 命令
# ===========================================
log_step "执行 velero restore create..."

RESTORE_ARGS=(
    create "${RESTORE_NAME}"
    --from-backup "${BACKUP_NAME}"
    --namespace-mappings "${NAMESPACE}:${TARGET_NAMESPACE}"
)

if [[ "$INCLUDE_PVC" == "true" ]]; then
    RESTORE_ARGS+=(--include-resources persistentvolumeclaims,persistentvolumes)
fi

# velero restore 不支持 --exclude-resources 与 --include-resources 同时使用
# 如果需要排除某些资源，使用 --exclude-resources
if [[ "$INCLUDE_PVC" == "true" && "$INCLUDE_SECRETS" == "true" && "$INCLUDE_CONFIGMAPS" == "true" ]]; then
    # 恢复所有资源（不指定 --include-resources，恢复全部）
    :
elif [[ "$INCLUDE_PVC" == "true" ]]; then
    if [[ "$INCLUDE_SECRETS" == "false" ]]; then
        RESTORE_ARGS+=(--exclude-resources secrets)
    fi
    if [[ "$INCLUDE_CONFIGMAPS" == "false" ]]; then
        RESTORE_ARGS+=(--exclude-resources configmaps)
    fi
fi

if [[ "$DRY_RUN" == "true" ]]; then
    echo "velero ${RESTORE_ARGS[*]}"
    exit 0
fi

# 执行恢复
velero "${RESTORE_ARGS[@]}"

# ===========================================
# 等待恢复完成
# ===========================================
log_step "等待恢复完成..."
sleep 2

for i in $(seq 1 60); do
    RESTORE_STATUS=$(velero restore get "${RESTORE_NAME}" -o jsonpath='{.status.phase}' 2>/dev/null || echo "Unknown")
    if [[ "$RESTORE_STATUS" == "Completed" ]]; then
        log_info "恢复完成！"
        break
    elif [[ "$RESTORE_STATUS" == "Failed" || "$RESTORE_STATUS" == "PartiallyFailed" ]]; then
        log_warn "恢复状态: ${RESTORE_STATUS}"
        break
    fi
    echo "  当前状态: ${RESTORE_STATUS}（等待中... ${i}/60）"
    sleep 5
done

# ===========================================
# 恢复结果详情
# ===========================================
log_step "恢复详情:"
velero restore describe "${RESTORE_NAME}" --details 2>/dev/null || true

# ===========================================
# 验证恢复结果
# ===========================================
log_step "验证恢复结果..."

log_info "检查目标命名空间 ${TARGET_NAMESPACE} 中的 PVC..."
kubectl get pvc --namespace="${TARGET_NAMESPACE}" 2>/dev/null || {
    log_error "未找到 PVC"
    exit 1
}

log_info "检查目标命名空间中的 Pod..."
kubectl get pods --namespace="${TARGET_NAMESPACE}" 2>/dev/null || true

log_info "检查目标命名空间中的 Service..."
kubectl get svc --namespace="${TARGET_NAMESPACE}" 2>/dev/null || true

echo ""
log_info "PVC 恢复完成！"
log_info "Restore 名称: ${RESTORE_NAME}"
log_info ""
log_info "后续步骤:"
log_info "  1. 检查应用 Pod 是否正常启动: kubectl get pods --namespace=${TARGET_NAMESPACE}"
log_info "  2. 如需恢复数据库，请执行: ./restore-db.sh --namespace=${TARGET_NAMESPACE} --release <RELEASE>"
log_info "  3. 查看恢复日志: velero restore logs ${RESTORE_NAME}"
