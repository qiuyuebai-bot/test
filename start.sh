#!/usr/bin/env bash
# ============================================================
# Unix/Linux/macOS 一键启动脚本
# 调用跨平台 Node.js 启动器 scripts/start.mjs
# ============================================================
set -e

# 切到脚本所在目录（项目根）
cd "$(dirname "$0")"

# 检测 Node.js
if ! command -v node >/dev/null 2>&1; then
    echo "[错误] 未检测到 Node.js，请先安装 Node.js 18+ 后再运行"
    echo "下载地址: https://nodejs.org/"
    exit 1
fi

# 传递所有参数给 Node 启动器
node scripts/start.mjs "$@"
