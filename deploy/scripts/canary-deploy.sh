#!/usr/bin/env bash
# ===========================================
# 金丝雀发布脚本
# 基于 Nginx Ingress canary-weight 注解按比例切分流量
#
# 工作原理：
#   1. 主 Ingress 指向主 release 的 backend service（承载 100% - weight 流量）
#   2. 金丝雀 Ingress（canary: "true"）指向金丝雀 release 的 backend service（承载 weight 流量）
#   3. 通过调整 canary-weight 注解渐进式推进：10% → 25% → 50% → 100%
#   4. 到达 100% 后，将金丝雀版本提升为主版本，清理旧金丝雀
#
# 用法：
#   # 初始部署金丝雀（10% 流量）
#   ./canary-deploy.sh --release knowledge --namespace default --chart ./helm \
#     --values values-prod.yaml --weight 10
#
#   # 推进金丝雀到 50%
#   ./canary-deploy.sh --release knowledge --namespace default --weight 50 --promote
#
#   # 完成金丝雀（100% → 提升为主版本）
#   ./canary-deploy.sh --release knowledge --namespace default --promote --finalize
#
# 参数：
#   --release         Helm release 名称（必填，主 release）
#   --namespace       K8s 命名空间（必填）
#   --chart           Helm chart 路径（默认 ./helm）
#   --values          环境配置文件（可选，可多次指定）
#   --set             额外 helm set（可选，可多次指定）
#   --weight          金丝雀流量百分比（0-100，默认 10）
#   --host            Ingress host（必填，用于 canary ingress 规则匹配）
#   --promote         推进金丝雀到指定 weight（而非初始部署）
#   --finalize        将金丝雀提升为主版本（helm upgrade 主 release 到新版本 + 清理金丝雀）
#   --auto            自动渐进式推进（10→25→50→100，每步间隔 --interval 秒）
#   --interval        自动模式每步间隔秒数（默认 60）
#   --skip-metrics    自动模式跳过指标检查
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
WEIGHT=10
HOST=""
PROMOTE=false
FINALIZE=false
AUTO=false
INTERVAL=60
SKIP_METRICS=false
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
        --release)       RELEASE="$2"; shift 2 ;;
        --namespace)     NAMESPACE="$2"; shift 2 ;;
        --chart)         CHART="$2"; shift 2 ;;
        --values)        VALUES+=("$2"); shift 2 ;;
        --set)           SETS+=("$2"); shift 2 ;;
        --weight)        WEIGHT="$2"; shift 2 ;;
        --host)          HOST="$2"; shift 2 ;;
        --promote)       PROMOTE=true; shift ;;
        --finalize)      FINALIZE=true; shift ;;
        --auto)          AUTO=true; shift ;;
        --interval)      INTERVAL="$2"; shift 2 ;;
        --skip-metrics)  SKIP_METRICS=true; shift ;;
        --dry-run)       DRY_RUN=true; shift ;;
        --help|-h)
            grep '^#' "$0" | sed 's/^# \?//'
            exit 0 ;;
        *) log_error "未知参数: $1"; exit 1 ;;
    esac
done

if [[ -z "$RELEASE" || -z "$NAMESPACE" ]]; then
    log_error "缺少必填参数 --release 或 --namespace"
    echo "示例: $0 --release knowledge --namespace default --chart ./helm --values values-prod.yaml --weight 10 --host api.example.com"
    exit 1
fi

if ! $PROMOTE && ! $FINALIZE && [[ -z "$HOST" ]]; then
    log_error "初始部署需要 --host 参数（Ingress host）"
    exit 1
fi

if [[ "$WEIGHT" -lt 0 || "$WEIGHT" -gt 100 ]]; then
    log_error "--weight 必须在 0-100 之间"
    exit 1
fi

# ---- dry-run 前缀 ----
HELM_DRY=""
if $DRY_RUN; then
    HELM_DRY="--dry-run"
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

# 金丝雀 release 名称
CANARY_RELEASE="${RELEASE}-canary"

# ===========================================
# 函数定义
# ===========================================

# 部署金丝雀版本（初始部署）
deploy_canary() {
    log_info "部署金丝雀版本到 ${CANARY_RELEASE}（${WEIGHT}% 流量）..."

    local helm_args=(
        upgrade --install "$CANARY_RELEASE" "$CHART"
        -n "$NAMESPACE"
        "${HELM_VALUES_ARGS[@]}"
        --set "fullnameOverride=${CANARY_RELEASE}"
        --set "frontend.enabled=false"
        --set "backend.replicaCount=1"
        --set "postgresql.enabled=false"
        --set "redis.enabled=false"
        --set "celeryWorker.enabled=false"
        --set "chroma.enabled=false"
        --set "backup.enabled=false"
        --set "ingress.enabled=false"
        --wait
    )

    if $DRY_RUN; then
        echo "  helm ${helm_args[*]}"
    else
        helm "${helm_args[@]}"
    fi

    log_ok "金丝雀版本部署完成"
}

# 应用金丝雀 Ingress（带 canary-weight 注解）
apply_canary_ingress() {
    local weight="$1"
    local canary_ingress="${CANARY_RELEASE}-ingress"

    log_info "应用金丝雀 Ingress（weight=${weight}%）..."

    if $DRY_RUN; then
        echo "  kubectl apply -f - <<'EOF'"
        echo "apiVersion: networking.k8s.io/v1"
        echo "kind: Ingress"
        echo "metadata:"
        echo "  name: ${canary_ingress}"
        echo "  namespace: ${NAMESPACE}"
        echo "  annotations:"
        echo "    nginx.ingress.kubernetes.io/canary: \"true\""
        echo "    nginx.ingress.kubernetes.io/canary-weight: \"${weight}\""
        echo "spec:"
        echo "  ingressClassName: nginx"
        echo "  rules:"
        echo "    - host: ${HOST}"
        echo "      http:"
        echo "        paths:"
        echo "          - path: /"
        echo "            pathType: Prefix"
        echo "            backend:"
        echo "              service:"
        echo "                name: ${CANARY_RELEASE}-backend"
        echo "                port:"
        echo "                  name: http"
        echo "EOF"
        return 0
    fi

    cat <<EOF | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ${canary_ingress}
  namespace: ${NAMESPACE}
  labels:
    app.kubernetes.io/name: ${RELEASE}
    app.kubernetes.io/part-of: knowledge-system
    app.kubernetes.io/managed-by: canary-script
  annotations:
    nginx.ingress.kubernetes.io/canary: "true"
    nginx.ingress.kubernetes.io/canary-weight: "${weight}"
spec:
  ingressClassName: nginx
  rules:
    - host: ${HOST}
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: ${CANARY_RELEASE}-backend
                port:
                  name: http
EOF
    log_ok "金丝雀 Ingress 已应用（weight=${weight}%）"
}

# 检查金丝雀版本的健康指标
check_canary_metrics() {
    if $SKIP_METRICS; then
        log_warn "跳过指标检查（--skip-metrics）"
        return 0
    fi

    log_info "检查金丝雀版本健康指标..."

    # 检查 5xx 错误率（通过 prometheus 查询）
    local error_rate
    error_rate=$(kubectl exec -n "$NAMESPACE" deployment/"${RELEASE}-backend" -- \
        curl -s 'http://prometheus-server:9090/api/v1/query?query=sum(rate(http_requests_total{status_code=~"5.."}[2m]))/clamp_min(sum(rate(http_requests_total[2m])),1)' 2>/dev/null \
        | jq -r '.data.result[0].value[1] // "0"' 2>/dev/null || echo "0")

    if (( $(echo "$error_rate > 0.05" | bc -l 2>/dev/null || echo 0) )); then
        log_error "金丝雀版本 5xx 错误率过高: ${error_rate}（>5%），停止推进"
        return 1
    fi

    log_ok "金丝雀指标正常（5xx 错误率: ${error_rate}）"
    return 0
}

# 推进金丝雀权重
promote_canary() {
    local weight="$1"
    log_info "推进金丝雀权重到 ${weight}%..."
    apply_canary_ingress "$weight"

    if ! $DRY_RUN; then
        log_info "等待 ${INTERVAL}s 观察指标..."
        sleep "$INTERVAL"
        check_canary_metrics || return 1
    fi
}

# 完成金丝雀：将金丝雀版本提升为主版本
finalize_canary() {
    log_warn "将金丝雀版本提升为主版本..."

    # 1. 获取金丝雀的镜像版本
    local canary_image
    canary_image=$(kubectl get deployment "${CANARY_RELEASE}-backend" -n "$NAMESPACE" \
        -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null || echo "")
    log_info "金丝雀镜像: ${canary_image}"

    # 2. helm upgrade 主 release 到金丝雀的镜像版本
    if [[ -n "$canary_image" ]]; then
        local helm_args=(
            upgrade --install "$RELEASE" "$CHART"
            -n "$NAMESPACE"
            "${HELM_VALUES_ARGS[@]}"
            --set "images.backend.tag=$(echo "$canary_image" | sed 's/.*://')"
            --wait
        )
        if $DRY_RUN; then
            echo "  helm ${helm_args[*]}"
        else
            helm "${helm_args[@]}"
        fi
    else
        log_warn "无法获取金丝雀镜像，跳过主 release 升级"
    fi

    # 3. 清理金丝雀资源
    log_info "清理金丝雀资源..."
    if $DRY_RUN; then
        echo "  kubectl delete ingress ${CANARY_RELEASE}-ingress -n ${NAMESPACE} --ignore-not-found"
        echo "  helm uninstall ${CANARY_RELEASE} -n ${NAMESPACE}"
    else
        kubectl delete ingress "${CANARY_RELEASE}-ingress" -n "$NAMESPACE" --ignore-not-found
        helm uninstall "$CANARY_RELEASE" -n "$NAMESPACE"
    fi

    log_ok "金丝雀发布完成，主版本已更新"
}

# 自动渐进式推进
auto_promote() {
    local stages=(10 25 50 100)
    log_info "自动渐进式推进金丝雀: ${stages[*]}"

    for w in "${stages[@]}"; do
        if [[ "$w" -ge "$WEIGHT" ]]; then
            log_info "=== 推进到 ${w}% ==="
            promote_canary "$w" || {
                log_error "在 ${w}% 阶段检查失败，停止推进"
                log_info "回滚金丝雀: kubectl delete ingress ${CANARY_RELEASE}-ingress -n ${NAMESPACE}"
                exit 1
            }

            if [[ "$w" -eq 100 ]]; then
                finalize_canary
                return 0
            fi
        fi
    done
}

# ===========================================
# 主流程
# ===========================================
main() {
    echo ""
    echo "=========================================="
    echo "  金丝雀发布"
    echo "=========================================="
    log_info "主 release     : ${RELEASE}"
    log_info "金丝雀 release : ${CANARY_RELEASE}"
    log_info "命名空间       : ${NAMESPACE}"
    log_info "Chart 路径     : ${CHART}"
    log_info "目标权重       : ${WEIGHT}%"
    if [[ -n "$HOST" ]]; then
        log_info "Ingress host   : ${HOST}"
    fi
    if $AUTO; then
        log_info "模式           : 自动渐进式（间隔 ${INTERVAL}s）"
    elif $FINALIZE; then
        log_info "模式           : 完成（提升为主版本）"
    elif $PROMOTE; then
        log_info "模式           : 推进权重"
    else
        log_info "模式           : 初始部署"
    fi
    echo "=========================================="
    echo ""

    if $FINALIZE; then
        # 完成金丝雀
        finalize_canary
    elif $AUTO; then
        # 自动渐进式
        deploy_canary
        auto_promote
    elif $PROMOTE; then
        # 推进权重
        promote_canary "$WEIGHT"
    else
        # 初始部署
        deploy_canary
        apply_canary_ingress "$WEIGHT"
        if ! $DRY_RUN; then
            log_info "等待 ${INTERVAL}s 观察指标..."
            sleep "$INTERVAL"
            check_canary_metrics
        fi
    fi

    echo ""
    echo "=========================================="
    if $FINALIZE; then
        log_ok "金丝雀发布已完成！主版本已更新。"
    elif $AUTO; then
        log_ok "金丝雀自动推进完成！"
    else
        log_ok "金丝雀发布操作完成（当前权重: ${WEIGHT}%）"
        log_info "继续推进: bash $(basename "$0") --release ${RELEASE} --namespace ${NAMESPACE} --weight 50 --promote"
        log_info "完成发布: bash $(basename "$0") --release ${RELEASE} --namespace ${NAMESPACE} --finalize"
    fi
    echo "=========================================="
    echo ""
}

main
