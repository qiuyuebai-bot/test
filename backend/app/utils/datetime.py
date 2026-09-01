from datetime import datetime, timedelta, timezone

# Celery beat 与产品用户均按 Asia/Shanghai 运行。每日快照的日界若沿用
# UTC，凌晨生成的快照会归属到前一天，导致趋势图横坐标整体偏移一天。
LOCAL_TZ = timezone(timedelta(hours=8))


def utcnow_naive() -> datetime:
    """返回 naive UTC datetime，等价于已弃用的 datetime.utcnow()。

    项目所有 SQLAlchemy DateTime 列均为 naive，禁止使用
    datetime.now(timezone.utc)（aware）以防比较时 TypeError。
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def local_now_naive() -> datetime:
    """返回北京时间（Asia/Shanghai）的 naive datetime。

    仅用于每日快照的日界划分与面向用户的展示时间；涉及新鲜度、
    跨模块比较的时间仍统一使用 utcnow_naive()。
    """
    return datetime.now(LOCAL_TZ).replace(tzinfo=None)
