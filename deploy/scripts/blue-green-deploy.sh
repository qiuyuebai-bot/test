#!/usr/bin/env bash
# ===========================================
# 蓝绿发布脚本
# 基于双 Helm release + router Service selector 切换
#
# 工作原理：
#   1. 部署两个并行的 Helm release：${RELEASE}-blue 和 ${RELEASE}-green
#   2. 一个 router Service（独立于 Helm，手动管理）通过 slot 标签指向当前活跃版本
#   3. 发布时部署到非活跃 slot → 等待就绪 → 冒烟测试 → 切换 router selector
#   4. 旧 slot 保留用于快速回退，手动确认后再清理
#
# 用法：
#   ./blue-green-deploy.sh --release knowledge --namespace default --chart ./helm --values values-prod.yaml
#
# 参数：
#   --release         Helm release 名称（必填）
#   --namespace       K8s 命名空间（必填）
#   --chart           Helm chart 路径（默认 ./helm）
#   --values          环境配置文件（可选，可多次指定）
#   --set             额外 helm set（可选，可多次指定）
#   --skip-wait       跳过等待 rollout 就绪
#   --skip-smoke      跳过冒烟测试
#   --cleanup-old     切换后立即清理旧 slot（默认保留）
#   --dry-run         仅打印命令不执行
#   --help            显示帮助
# ===========================================
set -euo pipefail

# ---- 默认参数 ----
RELEASE=""
NAMESPACE=""
CHART="./helm"
VALUES=()
SETS=()
SKIP_WAIT=false
SKIP_SMOKE=false
CLEANUP_OLD=false
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
        --chart)       CHART="$2"; shift 2 ;;
        --values)      VALUES+=("$2"); shift 2 ;;
        --set)         SETS+=("$2"); shift 2 ;;
        --skip-wait)   SKIP_WAIT=true; shift ;;
        --skip-smoke)  SKIP_SMOKE=true; shift ;;
        --cleanup-old) CLEANUP_OLD=true; shift ;;
        --dry-run)     DRY_RUN=true; shift ;;
        --help|-h)
            grep '^#' "$0" | sed 's/^# \?//'
            exit 0 ;;
        *) log_error "未知参数: $1"; exit 1 ;;
    esac
done

if [[ -z "$RELEASE" || -z "$NAMESPACE" ]]; then
    log_error "缺少必填参数 --release 或 --namespace"
    echo "示例: $0 --release knowledge --namespace default --chart ./helm --values values-prod.yaml"
    exit 1
fi

# ---- dry-run 前缀 ----
HELM_DRY=""
KUBECTL_DRY=""
if $DRY_RUN; then
    HELM_DRY="--dry-run"
    KUBECTL_DRY="--dry-run=client"
    log_warn "DRY-RUN 模式：仅打印命令，不实际执行"
fi

# ---- 构造 helm values 参数 ----
HELM_VALUES_ARGS=()
for v in "${VALUES[@]}"; do
    HELM_VALUES_ARGS+=(-f "$v")
done
for s in "${SETS[@]}"; do
    HELM_VALUES_ARGS+=(--set "$s")
done

# ===========================================
# 函数定义
# ===========================================

# 获取当前活跃 slot（blue 或 green）
# 通过检查 router service 的 selector 中的 slot 值
get_active_slot() {
    local slot
    slot=$(kubectl get svc "${RELEASE}-router" -n "$NAMESPACE" \
        -o jsonpath='{.spec.selector.slot}' 2>/dev/null || echo "")
    if [[ -z "$slot" ]]; then
        echo "blue"  # 默认从 blue 开始
    else
        echo "$slot"
    fi
}

# 获取非活跃 slot
get_inactive_slot() {
    local active="$1"
    if [[ "$active" == "blue" ]]; then
        echo "green"
    else
        echo "blue"
    fi
}

# 等待 rollout 就绪
wait_for_rollout() {
    local release_name="$1"
    local component="${2:-backend}"
    local deployment_name="${release_name}-${component}"

    if $SKIP_WAIT; then
        log_warn "跳过等待 rollout 就绪（--skip-wait）"
        return 0
    fi

    log_info "等待 ${deployment_name} rollout 就绪..."
    if kubectl rollout status deployment/"$deployment_name" \
        -n "$NAMESPACE" --timeout=300s; then
        log_ok "${deployment_name} rollout 就绪"
    else
        log_error "${deployment_name} rollout 超时或失败"
        return 1
    fi
}

# 运行冒烟测试（通过 port-forward 到新 slot 的 service）
run_smoke_test() {
    local slot="$1"
    local slot_release="${RELEASE}-${slot}"

    if $SKIP_SMOKE; then
        log_warn "跳过冒烟测试（--skip-smoke）"
        return 0
    fi

    local smoke_script
    smoke_script="$(dirname "$0")/smoke-test.sh"
    if [[ ! -f "$smoke_script" ]]; then
        log_warn "冒烟测试脚本不存在: $smoke_script，跳过"
        return 0
    fi

    log_info "对 slot=${slot} 运行冒烟测试..."
    # 通过 port-forward 临时访问新 slot 的 service
    local port=18080
    local pid
    kubectl port-forward svc/"${slot_release}-backend" "${port}:8000" -n "$NAMESPACE" >/dev/null 2>&1 &
    pid=$!

    # 等待 port-forward 就绪
    sleep 3

    if bash "$smoke_script" --host "http://127.0.0.1:${port}" --timeout 30; then
        log_ok "冒烟测试通过"
        kill "$pid" 2>/dev/null || true
        return 0
    else
        log_error "冒烟测试失败"
        kill "$pid" 2>/dev/null || true
        return 1
    fi
}

# 切换 router service selector 到新 slot
switch_traffic() {
    local new_slot="$1"
    local router="${RELEASE}-router"

    log_info "切换 router service ${router} → slot=${new_slot}"

    if $DRY_RUN; then
        echo "  kubectl patch svc ${router} -n ${NAMESPACE} \\"
        echo "    --type=json -p='[{\"op\":\"replace\",\"path\":\"/spec/selector/slot\",\"value\":\"${new_slot}\"}]'"
        return 0
    fi

    kubectl patch svc "$router" -n "$NAMESPACE" \
        --type=json \
        -p="[{\"op\":\"replace\",\"path\":\"/spec/selector/slot\",\"value\":\"${new_slot}\"}]"

    log_ok "流量已切换到 slot=${new_slot}"
}

# 清理旧 slot
cleanup_old_slot() {
    local old_slot="$1"
    local old_release="${RELEASE}-${old_slot}"

    if ! $CLEANUP_OLD; then
        log_info "保留旧 slot ${old_slot} 用于回退（使用 --cleanup-old 自动清理）"
        log_info "手动清理: helm uninstall ${old_release} -n ${NAMESPACE}"
        return 0
    fi

    log_warn "清理旧 slot: ${old_slot}"
    helm uninstall "$old_release" -n "$NAMESPACE" $HELM_DRY
    log_ok "旧 slot ${old_slot} 已清理"
}

# 确保 router service 存在
ensure_router_service() {
    local active_slot="$1"
    local router="${RELEASE}-router"

    if kubectl get svc "$router" -n "$NAMESPACE" >/dev/null 2>&1; then
        log_info "router service 已存在"
        return 0
    fi

    log_info "创建 router service ${router}（初始指向 slot=${active_slot}）"
    if $DRY_RUN; then
        echo "  kubectl apply -f - <<'EOF'"
        echo "apiVersion: v1"
        echo "kind: Service"
        echo "metadata:"
        echo "  name: ${router}"
        echo "  namespace: ${NAMESPACE}"
        echo "spec:"
        echo "  type: ClusterIP"
        echo "  ports:"
        echo "    - port: 8000"
        echo "      targetPort: 8000"
        echo "      name: http"
        echo "  selector:"
        echo "    app.kubernetes.io/part-of: knowledge-system"
        echo "    app.kubernetes.io/component: backend"
        echo "    slot: ${active_slot}"
        echo "EOF"
        return 0
    fi

    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Service
metadata:
  name: ${router}
  namespace: ${NAMESPACE}
  labels:
    app.kubernetes.io/name: ${RELEASE}
    app.kubernetes.io/part-of: knowledge-system
    app.kubernetes.io/managed-by: blue-green-script
spec:
  type: ClusterIP
  ports:
    - port: 8000
      targetPort: 8000
      name: http
  selector:
    app.kubernetes.io/part-of: knowledge-system
    app.kubernetes.io/component: backend
    slot: ${active_slot}
EOF
    log_ok "router service ${router} 已创建"
}

# ===========================================
# 主流程
# ===========================================
main() {
    local active_slot inactive_slot new_release

    active_slot=$(get_active_slot)
    inactive_slot=$(get_inactive_slot "$active_slot")
    new_release="${RELEASE}-${inactive_slot}"

    echo ""
    echo "=========================================="
    echo "  蓝绿发布"
    echo "=========================================="
    log_info "Release 前缀  : ${RELEASE}"
    log_info "命名空间      : ${NAMESPACE}"
    log_info "Chart 路径    : ${CHART}"
    log_info "当前活跃 slot : ${active_slot}"
    log_info "新版本 slot   : ${inactive_slot}"
    log_info "新 release 名 : ${new_release}"
    echo "=========================================="
    echo ""

    # 1. 确保 router service 存在
    ensure_router_service "$active_slot"

    # 2. 部署新版本到非活跃 slot
    log_info "部署新版本到 slot=${inactive_slot}..."
    local helm_args=(
        upgrade --install "$new_release" "$CHART"
        -n "$NAMESPACE"
        "${HELM_VALUES_ARGS[@]}"
        --set "fullnameOverride=${new_release}"
        --set "deployment.slot=${inactive_slot}"
        --wait
    )

    if $DRY_RUN; then
        echo "  helm ${helm_args[*]}"
    else
        helm "${helm_args[@]}"
    fi

    # 3. 等待 rollout 就绪
    wait_for_rollout "$new_release" "backend"
    wait_for_rollout "$new_release" "frontend"

    # 4. 冒烟测试
    if ! run_smoke_test "$inactive_slot"; then
        log_error "冒烟测试失败，停止发布，旧 slot=${active_slot} 仍承载流量"
        log_info "如需回滚新版本: helm uninstall ${new_release} -n ${NAMESPACE}"
        exit 1
    fi

    # 5. 切换流量
    switch_traffic "$inactive_slot"

    # 6. 清理旧 slot（可选）
    cleanup_old_slot "$active_slot"

    echo ""
    echo "=========================================="
    log_ok "蓝绿发布完成！"
    echo "=========================================="
    log_info "当前活跃 slot : ${inactive_slot}"
    log_info "旧 slot       : ${active_slot}（已保留）"
    log_info "回滚命令      : bash $(basename "$0") --release ${RELEASE} --namespace ${NAMESPACE} --chart ${CHART}"
    echo ""
}

main
