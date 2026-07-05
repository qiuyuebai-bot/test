from datetime import datetime, timezone


def utcnow_naive() -> datetime:
    """返回 naive UTC datetime，等价于已弃用的 datetime.utcnow()。

    项目所有 SQLAlchemy DateTime 列均为 naive，禁止使用
    datetime.now(timezone.utc)（aware）以防比较时 TypeError。
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
