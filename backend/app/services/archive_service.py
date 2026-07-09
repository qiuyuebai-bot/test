"""
数据归档服务
将旧数据从主表迁移到归档表，保持主表查询性能

使用方式（不自动执行，需手动调用或 cron 触发）：
    from app.services.archive_service import ArchiveService
    ArchiveService.archive_old_data(days=90)
    ArchiveService.get_archive_stats()

注意：
    归档表采用与主表相同的 schema，通过 CREATE TABLE IF NOT EXISTS ... AS SELECT 方式创建
    归档后主表对应行会被删除，请谨慎调用
"""
from datetime import datetime, timedelta
from typing import Dict, Any

from loguru import logger
from sqlalchemy import text

from app.database import get_db_context


class ArchiveService:
    """数据归档服务"""

    ARCHIVE_DAYS = 90  # 超过 90 天的数据归档

    @classmethod
    def archive_old_data(cls, days: int = None) -> Dict[str, int]:
        """
        归档旧数据到归档表

        Args:
            days: 归档阈值（天），默认 90

        Returns:
            各表归档条数
        """
        days = days or cls.ARCHIVE_DAYS
        cutoff_date = datetime.now() - timedelta(days=days)

        result = {
            "answer_records": 0,
            "agent_tasks": 0,
            "debate_records": 0,
        }

        with get_db_context() as db:
            # 创建归档表（如果不存在）
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS archived_answer_records AS
                SELECT * FROM answer_records WHERE 1=0
            """))

            # 统计待归档数量
            result["answer_records"] = db.execute(
                text("SELECT COUNT(*) FROM answer_records WHERE created_at < :cutoff"),
                {"cutoff": cutoff_date},
            ).scalar()

            # 归档答题记录
            db.execute(text("""
                INSERT INTO archived_answer_records
                SELECT * FROM answer_records WHERE created_at < :cutoff
            """), {"cutoff": cutoff_date})

            db.execute(text(
                "DELETE FROM answer_records WHERE created_at < :cutoff"
            ), {"cutoff": cutoff_date})

            db.commit()

        logger.info(f"[归档] 完成: {result}")
        return result

    @classmethod
    def get_archive_stats(cls) -> Dict[str, Any]:
        """获取归档统计"""
        with get_db_context() as db:
            stats: Dict[str, Any] = {}
            try:
                stats["archived_answer_records"] = db.execute(
                    text("SELECT COUNT(*) FROM archived_answer_records")
                ).scalar()
            except Exception:
                stats["archived_answer_records"] = 0

            return stats
