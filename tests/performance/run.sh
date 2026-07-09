#!/usr/bin/env bash
# k6 性能测试运行脚本 (Linux/macOS)
#
# 用法:
#   ./run.sh [scenario] [base_url] [--docker]
#
# 场景:
#   smoke   - 冒烟测试 (1 VU, 30s)
#   load    - 负载测试 (20 VU, 3min)
#   stress  - 压力测试 (10→200 VU, 6min)
#   spike   - 突发测试 (100 VU, 40s)
#   all     - 依次运行所有场景
#
# 示例:
#   ./run.sh smoke
#   ./run.sh load http://192.168.1.100:8000
#   ./run.sh stress --docker
#   ./run.sh all

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCENARIO="${1:-smoke}"
BASE_URL="${2:-http://localhost:8000}"
USE_DOCKER=false

if [[ "${3:-}" == "--docker" ]]; then
    USE_DOCKER=true
fi

if [[ "$SCENARIO" == "all" ]]; then
    SCENARIOS=("smoke" "load" "stress" "spike")
else
    SCENARIOS=("$SCENARIO")
fi

has_k6() {
    command -v k6 &>/dev/null
}

has_docker() {
    command -v docker &>/dev/null && docker info &>/dev/null
}

run_scenario() {
    local name="$1"
    local script="$SCRIPT_DIR/$name.js"

    if [[ ! -f "$script" ]]; then
        echo "ERROR: 场景脚本不存在: $script"
        return 1
    fi

    echo ""
    echo "========================================"
    echo "  场景: $name"
    echo "  目标: $BASE_URL"
    echo "========================================"

    if $USE_DOCKER; then
        if ! has_docker; then
            echo "ERROR: Docker 不可用"
            return 1
        fi
        cat "$script" | docker run --rm -i --network host \
            -e BASE_URL="$BASE_URL" \
            grafana/k6 run -
    elif has_k6; then
        BASE_URL="$BASE_URL" k6 run "$script"
    elif has_docker; then
        echo "未检测到本地 k6，使用 Docker 模式..."
        cat "$script" | docker run --rm -i --network host \
            -e BASE_URL="$BASE_URL" \
            grafana/k6 run -
    else
        echo "ERROR: 未检测到 k6 或 Docker"
        echo "  安装 k6:  https://k6.io/docs/get-started/installation/"
        echo "  或安装 Docker"
        return 1
    fi
}

for s in "${SCENARIOS[@]}"; do
    run_scenario "$s" || true
done
