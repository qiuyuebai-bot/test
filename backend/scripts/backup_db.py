#!/usr/bin/env python3
"""数据库备份脚本，支持 SQLite 和 PostgreSQL

使用方式：
    python scripts/backup_db.py

环境变量：
    DATABASE_URL：数据库连接字符串
        - SQLite:     sqlite:///./data/app.db
        - PostgreSQL: postgresql://user:pass@host:port/dbname

输出：
    备份文件位于 <project_root>/data/backups/ 目录下
    - SQLite:     app_db_<timestamp>.db
    - PostgreSQL: app_db_<timestamp>.sql

清理策略：
    默认保留 30 天，超过自动删除（BACKUP_RETENTION_DAYS 控制）
"""
import os
import sys
import shutil
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402

BACKUP_DIR = Path(settings.LOG_DIR).resolve().parent / "backups"
BACKUP_RETENTION_DAYS = 30


def backup_sqlite() -> bool:
    """备份 SQLite 数据库"""
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    if not os.path.exists(db_path):
        print(f"数据库文件不存在: {db_path}")
        return False

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_path = BACKUP_DIR / f"app_db_{timestamp}.db"

    shutil.copy2(db_path, backup_path)
    print(f"SQLite 备份完成: {backup_path}")
    return True


def backup_postgresql() -> bool:
    """备份 PostgreSQL 数据库"""
    import subprocess

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_path = BACKUP_DIR / f"app_db_{timestamp}.sql"

    env = os.environ.copy()
    cmd = ["pg_dump", settings.DATABASE_URL, "-f", str(backup_path)]
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"PostgreSQL 备份完成: {backup_path}")
        return True
    else:
        print(f"PostgreSQL 备份失败: {result.stderr}")
        return False


def cleanup_old_backups() -> None:
    """清理超过保留期的备份"""
    if not BACKUP_DIR.exists():
        return

    cutoff = datetime.now().timestamp() - BACKUP_RETENTION_DAYS * 86400

    for f in BACKUP_DIR.iterdir():
        if f.is_file() and f.stat().st_mtime < cutoff:
            f.unlink()
            print(f"已清理过期备份: {f.name}")


def main() -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    if settings.DATABASE_URL.startswith("sqlite"):
        backup_sqlite()
    else:
        backup_postgresql()

    cleanup_old_backups()
    print("备份任务完成")


if __name__ == "__main__":
    main()
