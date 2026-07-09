#!/usr/bin/env bash
# ===========================================
# 冒烟测试脚本
# 对部署后的服务执行关键 API 冒烟测试
# 返回非 0 退出码表示测试失败（触发回滚）
#
# 用法：
#   ./smoke-test.sh --host http://127.0.0.1:8000 --timeout 30
#   ./smoke-test.sh --host http://knowledge-backend:8000
#   curl ... | ./smoke-test.sh --host http://localhost:8000
#
# 测试项：
#   1. /health/live        - 存活检查
#   2. /health/ready       - 就绪检查（DB + Chroma + 系统）
#   3. /api/v1/info        - 系统信息
#   4. /api/v1/health       - API 健康检查
#   5. /                   - 根路径
#   6. /metrics            - Prometheus 指标端点
#
# 参数：
#   --host       目标服务 URL（必填，如 http://127.0.0.1:8000）
#   --timeout    单个请求超时秒数（默认 10）
#   --retry      失败重试次数（默认 3）
#   --interval   重试间隔秒数（默认 5）
#   --verbose    显示详细输出
#   --help       显示帮助
# ===========================================
set -euo pipefail

# ---- 默认参数 ----
HOST=""
TIMEOUT=10
RETRY=3
INTERVAL=5
VERBOSE=false

# ---- 颜色输出 ----
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[FAIL]${NC}  $*"; }

# ---- 参数解析 ----
while [[ $# -gt 0 ]]; do
    case $1 in
        --host)     HOST="$2"; shift 2 ;;
        --timeout)  TIMEOUT="$2"; shift 2 ;;
        --retry)     RETRY="$2"; shift 2 ;;
        --interval)  INTERVAL="$2"; shift 2 ;;
        --verbose)   VERBOSE=true; shift ;;
        --help|-h)
            grep '^#' "$0" | sed 's/^# \?//'
            exit 0 ;;
        *) log_error "未知参数: $1"; exit 1 ;;
    esac
done

if [[ -z "$HOST" ]]; then
    log_error "缺少必填参数 --host"
    echo "示例: $0 --host http://127.0.0.1:8000 --timeout 10"
    exit 1
fi

# 去除尾部斜杠
HOST="${HOST%/}"

# ---- 测试统计 ----
TOTAL=0
PASSED=0
FAILED=0

# ===========================================
# 函数定义
# ===========================================

# 单个 URL 测试（带重试）
# 参数: $1=测试名称 $2=路径 $3=期望状态码 $4=可选验证函数名
test_endpoint() {
    local name="$1"
    local path="$2"
    local expected_code="${3:-200}"
    local validate_fn="${4:-}"
    local url="${HOST}${path}"

    TOTAL=$((TOTAL + 1))
    log_info "测试 [$name]: GET ${path}（期望 HTTP ${expected_code}）"

    local attempt=0
    local http_code=0
    local response_body=""

    while [[ $attempt -lt $RETRY ]]; do
        attempt=$((attempt + 1))

        response_body=$(curl -sf --max-time "$TIMEOUT" \
            -o /tmp/smoke_response.json \
            -w "%{http_code}" \
            "$url" 2>/dev/null || echo "000")

        http_code="$response_body"

        if [[ "$http_code" == "$expected_code" ]]; then
            if [[ -n "$validate_fn" ]] && declare -f "$validate_fn" >/dev/null 2>&1; then
                if "$validate_fn" /tmp/smoke_response.json; then
                    log_ok "[$name] 通过（HTTP ${http_code}）"
                    PASSED=$((PASSED + 1))
                    return 0
                else
                    log_warn "[$name] HTTP ${http_code} 但验证失败（尝试 $attempt/$RETRY）"
                    $VERBOSE && cat /tmp/smoke_response.json 2>/dev/null
                fi
            else
                log_ok "[$name] 通过（HTTP ${http_code}）"
                PASSED=$((PASSED + 1))
                return 0
            fi
        else
            log_warn "[$name] HTTP ${http_code}（期望 ${expected_code}，尝试 $attempt/$RETRY）"
            $VERBOSE && cat /tmp/smoke_response.json 2>/dev/null
        fi

        if [[ $attempt -lt $RETRY ]]; then
            sleep "$INTERVAL"
        fi
    done

    log_error "[$name] 失败（重试 ${RETRY} 次后仍为 HTTP ${http_code}）"
    FAILED=$((FAILED + 1))
    return 1
}

# 验证 /health/ready 返回的 JSON 包含 status: ready
validate_health_ready() {
    local body_file="$1"
    local status
    status=$(python -c "
import json, sys
try:
    data = json.load(open('$body_file'))
    print(data.get('data', {}).get('status', data.get('message', 'unknown')))
except:
    print('parse_error')
" 2>/dev/null || echo "parse_error")

    if [[ "$status" == "ready" ]]; then
        return 0
    else
        log_warn "health/ready 状态: ${status}（期望 ready）"
        return 1
    fi
}

# 验证 /api/v1/info 返回有效 JSON
validate_api_info() {
    local body_file="$1"
    local version
    version=$(python -c "
import json
try:
    data = json.load(open('$body_file'))
    print(data.get('data', {}).get('version', ''))
except:
    print('')
" 2>/dev/null || echo "")

    if [[ -n "$version" ]]; then
        $VERBOSE && log_info "应用版本: ${version}"
        return 0
    else
        log_warn "api/v1/info 未返回版本信息"
        return 1
    fi
}

# 验证 /metrics 返回 Prometheus 格式
validate_metrics() {
    local body_file="$1"
    if grep -q "^# TYPE" "$body_file" 2>/dev/null && grep -q "http_requests_total" "$body_file" 2>/dev/null; then
        return 0
    else
        log_warn "metrics 响应未包含 Prometheus 格式指标"
        return 1
    fi
}

# ===========================================
# 主流程
# ===========================================
main() {
    echo ""
    echo "=========================================="
    echo "  冒烟测试"
    echo "=========================================="
    log_info "目标地址  : ${HOST}"
    log_info "超时      : ${TIMEOUT}s"
    log_info "重试      : ${RETRY} 次（间隔 ${INTERVAL}s）"
    echo "=========================================="
    echo ""

    local all_passed=true

    # 1. 存活检查
    test_endpoint "Liveness" "/health/live" 200 || all_passed=false
    echo ""

    # 2. 就绪检查（含 DB + Chroma + 系统资源）
    test_endpoint "Readiness" "/health/ready" 200 validate_health_ready || all_passed=false
    echo ""

    # 3. 系统信息
    test_endpoint "API Info" "/api/v1/info" 200 validate_api_info || all_passed=false
    echo ""

    # 4. API 健康检查（别名）
    test_endpoint "API Health" "/api/v1/health" 200 || all_passed=false
    echo ""

    # 5. 根路径
    test_endpoint "Root" "/" 200 || all_passed=false
    echo ""

    # 6. Prometheus 指标端点
    test_endpoint "Metrics" "/metrics" 200 validate_metrics || all_passed=false
    echo ""

    # ---- 汇总 ----
    echo "=========================================="
    echo "  冒烟测试汇总"
    echo "=========================================="
    echo "  总计: ${TOTAL}"
    echo -e "  ${GREEN}通过: ${PASSED}${NC}"
    if [[ $FAILED -gt 0 ]]; then
        echo -e "  ${RED}失败: ${FAILED}${NC}"
    else
        echo -e "  失败: 0"
    fi
    echo "=========================================="

    if $all_passed; then
        echo -e "${GREEN}所有冒烟测试通过！${NC}"
        exit 0
    else
        echo -e "${RED}冒烟测试存在失败项！${NC}"
        exit 1
    fi
}

main
