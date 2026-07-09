#!/bin/bash
# ===========================================
# 数据库定时备份脚本（cron 调用）
# ===========================================
# 使用方式（Linux/Mac）：
#   1. 给脚本添加执行权限: chmod +x backend/scripts/cron_backup.sh
#   2. 编辑 crontab: crontab -e
#   3. 添加定时任务（每日凌晨 2 点执行备份）:
#      0 2 * * * /path/to/backend/scripts/cron_backup.sh
#   4. 备份文件位于 <project_root>/data/backups/
# ===========================================

# 切换到 backend 目录（脚本所在目录的上一级是 backend）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# 使用 venv 中的 Python（如果存在），否则使用系统 Python
if [ -f "./venv/bin/python" ]; then
    PYTHON="./venv/bin/python"
elif [ -f "./venv/Scripts/python.exe" ]; then
    PYTHON="./venv/Scripts/python.exe"
else
    PYTHON="python"
fi

# 执行备份脚本
$PYTHON scripts/backup_db.py

# 退出码与备份脚本一致
exit $?
