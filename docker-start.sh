#!/usr/bin/env bash
# ============================================================
# 领域知识个性化生成与多智能体协同决策系统
# Docker 一键启动脚本（Linux / macOS）
# 用法: ./docker-start.sh
# ============================================================
set -e

cd "$(dirname "$0")"

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}[OK]${NC} $1"; }
warn() { echo -e "  ${YELLOW}[!]${NC}  $1"; }
err()  { echo -e "  ${RED}[X]${NC} $1"; }

echo ""
echo "  ╔═══════════════════════════════════════════════════════════╗"
echo "  ║     领域知识个性化生成与多智能体协同决策系统               ║"
echo "  ║     Docker 一键部署                                        ║"
echo "  ╚═══════════════════════════════════════════════════════════╝"
echo ""

# ---- 检测 Docker ----
if ! command -v docker >/dev/null 2>&1; then
    err "未检测到 Docker，请先安装 Docker"
    echo "    下载地址: https://docs.docker.com/get-docker/"
    exit 1
fi
ok "已检测到 Docker"

# ---- 检测 Docker 引擎运行状态 ----
if ! docker info >/dev/null 2>&1; then
    err "Docker 引擎未运行，请启动 Docker 服务后重试"
    echo "    Linux: sudo systemctl start docker"
    echo "    macOS: 启动 Docker Desktop"
    exit 1
fi
ok "Docker 引擎运行中"

# ---- 创建 .env（如不存在）----
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        ok "已从 .env.example 创建 .env 配置文件"
    else
        warn "未找到 .env.example，将使用默认配置"
    fi
else
    ok ".env 配置文件已存在"
fi

# ---- 构建并启动容器 ----
echo ""
echo "  ── 正在构建并启动容器（首次构建约需 3-8 分钟）──"
echo ""

docker compose up -d --build

# ---- 等待后端就绪 ----
echo ""
echo "  ── 等待后端服务就绪 ──"
tries=0
max_tries=40
while [ $tries -lt $max_tries ]; do
    tries=$((tries + 1))
    sleep 3
    if curl -sf -o /dev/null http://localhost:8000/health 2>/dev/null; then
        ok "后端服务已就绪"
        break
    fi
    echo "  · 等待中... 第 $tries 次尝试"
    if [ $tries -eq $max_tries ]; then
        warn "服务启动超时，请检查日志: docker compose logs backend"
    fi
done

# ---- 显示信息 ----
echo ""
echo "  ════════════════════════════════════════════════════════════"
echo ""
echo "    系统已启动！"
echo ""
echo "    前端页面:  http://localhost"
echo "    后端 API:  http://localhost:8000"
echo "    API 文档:  http://localhost:8000/docs"
echo ""
echo "    默认登录:  用户名 admin  密码 admin123"
echo ""
echo "    停止系统:  ./docker-stop.sh"
echo "    查看日志:  docker compose logs -f"
echo ""
echo "    提示: 如需 AI 生成功能，请在 .env 中设置 OPENAI_API_KEY"
echo "          修改后执行: docker compose up -d 重新生效"
echo ""
echo "  ════════════════════════════════════════════════════════════"
echo ""

# ---- 尝试打开浏览器 ----
if command -v xdg-open >/dev/null 2>&1; then
    xdg-open http://localhost >/dev/null 2>&1 || true
elif command -v open >/dev/null 2>&1; then
    open http://localhost >/dev/null 2>&1 || true
fi
