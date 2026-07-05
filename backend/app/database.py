"""
数据库连接与会话管理
统一从 config.settings 读取 DATABASE_URL，根据数据库类型自动适配连接参数：
- SQLite：单线程模式（check_same_thread=False），不使用连接池
- PostgreSQL：使用连接池（pool_size + max_overflow），pool_pre_ping 保活
"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from typing import Generator
from contextlib import contextmanager
from loguru import logger
from fastapi import HTTPException

from app.config import settings


def _build_engine():
    database_url = settings.DATABASE_URL

    if settings.is_sqlite:
        connect_args = {"check_same_thread": False}
        engine = create_engine(
            database_url,
            connect_args=connect_args,
            echo=False,
        )

        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        logger.info(f"数据库引擎已创建（SQLite）: {database_url}")
    elif settings.is_postgresql:
        engine = create_engine(
            database_url,
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_MAX_OVERFLOW,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False,
        )
        logger.info(f"数据库引擎已创建（PostgreSQL）: pool_size={settings.DATABASE_POOL_SIZE}")
    else:
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False,
        )
        logger.info(f"数据库引擎已创建: {database_url}")

    return engine


engine = _build_engine()

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    bind=engine
)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI依赖注入使用的数据库会话获取函数
    每次请求自动创建会话，请求结束后自动关闭
    """
    db = SessionLocal()
    try:
        yield db
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        logger.error(f"数据库会话异常: {e}")
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    非请求场景下使用的数据库会话上下文管理器
    用于Celery任务、后台处理、初始化脚本等场景
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        logger.error(f"数据库操作异常: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def init_database() -> None:
    """
    初始化数据库
    创建所有表结构
    """
    import app.models as models

    logger.info(f"正在初始化数据库（已注册 {len(models.__all__)} 个模型）...")
    Base.metadata.create_all(bind=engine)
    logger.info("数据库初始化完成")


def drop_database() -> None:
    """
    删除所有表结构（仅用于测试环境）
    """
    logger.warning("正在删除数据库所有表...")
    Base.metadata.drop_all(bind=engine)
    logger.warning("数据库表已全部删除")
