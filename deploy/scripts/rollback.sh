#!/usr/bin/env bash
# ===========================================
# 回滚脚本
# 基于 Helm revision 回滚到历史版本
#
# 功能：
#   1. 列出当前 release 的历史 revision
#   2. 回滚到指定 revision（默认上一个 revision）
#   3. 回滚后等待 rollout 就绪
#   4. 支持仅预览不执行（--dry-run）
#   5. 支持回滚所有组件（backend + frontend）
#
# 用法：
#   # 列出历史 revision
#   ./rollback.sh --release knowledge --namespace default --list
#
#   # 回滚到上一个 revision
#   ./rollback.sh --release knowledge --namespace default
#
#   # 回滚到指定 revision
#   ./rollback.sh --release knowledge --namespace default --revision 5
#
#   # 仅预览不执行
#   ./rollback.sh --release knowledge --namespace default --dry-run
#
# 参数：
#   --release         Helm release 名称（必填）
#   --namespace       K8s 命名空间（必填）
#   --revision        目标 revision 号（默认回滚到上一个）
#   --list            仅列出历史 revision
#   --skip-wait       跳过等待 rollout 就绪
#   --timeout         rollout 等待超时秒数（默认 300）
#   --dry-run         仅预览不执行
#   --help            显示帮助
# ===========================================
set -euo pipefail

# ---- 默认参数 ----
RELEASE=""
NAMESPACE=""
REVISION=""
LIST_ONLY=false
SKIP_WAIT=false
TIMEOUT=300
DRY_RUN=false

# ---- 颜色输出 ----
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ---- 参数解析 ----
while [[ $# -gt 0 ]]; do
    case $1 in
        --release)     RELEASE="$2"; shift 2 ;;
        --namespace)   NAMESPACE="$2"; shift 2 ;;
        --revision)    REVISION="$2"; shift 2 ;;
        --list)        LIST_ONLY=true; shift ;;
        --skip-wait)   SKIP_WAIT=true; shift ;;
        --timeout)     TIMEOUT="$2"; shift 2 ;;
        --dry-run)     DRY_RUN=true; shift ;;
        --help|-h)
            grep '^#' "$0" | sed 's/^# \?//'
            exit 0 ;;
        *) log_error "未知参数: $1"; exit 1 ;;
    esac
done

if [[ -z "$RELEASE" || -z "$NAMESPACE" ]]; then
    log_error "缺少必填参数 --release 或 --namespace"
    echo "示例: $0 --release knowledge --namespace default"
    exit 1
fi

# ===========================================
# 函数定义
# ===========================================

# 列出 helm history
list_history() {
    log_info "Helm release '${RELEASE}' 的历史 revision："
    echo ""
    helm history "$RELEASE" -n "$NAMESPACE" -o table 2>/dev/null || {
        log_error "无法获取 release '${RELEASE}' 的历史，可能 release 不存在"
        exit 1
    }
    echo ""
    log_info "提示：REVISION 标记 * 的是当前版本，回滚将回退到指定 revision"
}

# 获取当前 revision
get_current_revision() {
    helm history "$RELEASE" -n "$NAMESPACE" -o json 2>/dev/null \
        | jq '[.[] | select(.status == "deployed")] | .[0].revision' 2>/dev/null || echo ""
}

# 获取上一个 revision
get_previous_revision() {
    local current
    current=$(get_current_revision)
    if [[ -z "$current" ]]; then
        echo ""
        return
    fi
    echo $((current - 1))
}

# 等待 rollout 就绪
wait_for_rollout() {
    if $SKIP_WAIT; then
        log_warn "跳过等待 rollout 就绪（--skip-wait）"
        return 0
    fi

    local component
    for component in backend frontend; do
        local deployment="${RELEASE}-${component}"
        log_info "等待 ${deployment} rollout 就绪..."
        if kubectl rollout status deployment/"$deployment" \
            -n "$NAMESPACE" --timeout="${TIMEOUT}s"; then
            log_ok "${deployment} rollout 就绪"
        else
            log_error "${deployment} rollout 超时或失败"
            log_warn "回滚已执行但 rollout 未完成，请手动检查: kubectl get pods -n ${NAMESPACE}"
            return 1
        fi
    done
}

# 执行回滚
perform_rollback() {
    local target_revision="$1"

    if $DRY_RUN; then
        log_warn "DRY-RUN 模式：以下命令将执行但不实际运行"
        echo "  helm rollback ${RELEASE} ${target_revision} -n ${NAMESPACE}"
        echo ""
        log_info "回滚后部署将恢复到 revision ${target_revision} 的状态"
        return 0
    fi

    log_warn "执行 helm rollback ${RELEASE} → revision ${target_revision}..."
    if helm rollback "$RELEASE" "$target_revision" -n "$NAMESPACE"; then
        log_ok "Helm rollback 命令执行成功"
    else
        log_error "Helm rollback 命令执行失败"
        exit 1
    fi
}

# ===========================================
# 主流程
# ===========================================
main() {
    echo ""
    echo "=========================================="
    echo "  Helm 回滚"
    echo "=========================================="
    log_info "Release    : ${RELEASE}"
    log_info "命名空间   : ${NAMESPACE}"
    echo "=========================================="
    echo ""

    # 仅列出历史
    if $LIST_ONLY; then
        list_history
        exit 0
    fi

    # 确定目标 revision
    local target_revision
    if [[ -n "$REVISION" ]]; then
        target_revision="$REVISION"
        log_info "目标 revision: ${target_revision}（指定）"
    else
        target_revision=$(get_previous_revision)
        if [[ -z "$target_revision" || "$target_revision" -le 0 ]]; then
            log_error "无法确定回滚目标 revision，请用 --list 查看历史并使用 --revision 指定"
            list_history
            exit 1
        fi
        log_info "目标 revision: ${target_revision}（上一个）"
    fi

    # 显示当前与目标对比
    local current_revision
    current_revision=$(get_current_revision)
    log_info "当前 revision: ${current_revision}"
    log_info "目标 revision: ${target_revision}"
    echo ""

    # 确认提示
    if ! $DRY_RUN; then
        read -rp "确认回滚到 revision ${target_revision}? (y/N): " confirm
        if [[ "${confirm,,}" != "y" ]]; then
            log_warn "已取消回滚"
            exit 0
        fi
    fi

    # 执行回滚
    perform_rollback "$target_revision"

    # 等待 rollout
    wait_for_rollout

    echo ""
    echo "=========================================="
    log_ok "回滚完成！"
    echo "=========================================="
    log_info "当前 revision: ${target_revision}"
    log_info "验证命令: kubectl get pods -n ${NAMESPACE}"
    log_info "查看历史: bash $(basename "$0") --release ${RELEASE} --namespace ${NAMESPACE} --list"
    echo ""
}

main
