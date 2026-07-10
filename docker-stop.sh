#!/usr/bin/env bash
# ============================================================
# 领域知识个性化生成与多智能体协同决策系统
# Docker 一键停止脚本（Linux / macOS）
# 用法: ./docker-stop.sh
# ============================================================
set -e

cd "$(dirname "$0")"

GREEN='\033[0;32m'
NC='\033[0m'

echo ""
echo "  正在停止所有 Docker 容器..."
echo ""

docker compose down

echo ""
echo -e "  ${GREEN}[OK]${NC} 所有服务已停止，数据已保留在 Docker 卷中"
echo "       下次执行 ./docker-start.sh 即可重新启动"
echo ""
