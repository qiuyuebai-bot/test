"""
数据库连接与会话管理
统一从 config.settings 读取 DATABASE_URL，根据数据库类型自动适配连接参数：
- SQLite：单线程模式（check_same_thread=False），不使用连接池
- PostgreSQL：使用连接池（pool_size + max_overflow），pool_pre_ping 保活
"""
from pathlib import Path
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
    初始化数据库：运行 alembic 迁移

    策略：
    - 生产环境（APP_ENV=production）：仅运行 alembic upgrade head，迁移失败即报错
    - 开发/预发布环境：先用 create_all 保证最低可用性，再运行 alembic upgrade head
    """
    import app.models as models
    import warnings

    logger.info(f"正在初始化数据库（已注册 {len(models.__all__)} 个模型，APP_ENV={settings.APP_ENV}）...")

    is_production = settings.APP_ENV == "production"

    # 开发环境保留 create_all 作为 fallback，保证首次启动开箱即用
    if not is_production:
        Base.metadata.create_all(bind=engine)
        logger.info("create_all 完成（开发环境 fallback）")

    # 运行 alembic 迁移（确保 schema 最新）
    alembic_ini_path = Path(__file__).resolve().parent.parent / "alembic.ini"
    if not alembic_ini_path.exists():
        if is_production:
            logger.error(f"生产环境未找到 alembic.ini: {alembic_ini_path}")
            raise RuntimeError(f"生产环境必须配置 alembic.ini: {alembic_ini_path}")
        logger.warning(f"未找到 alembic.ini: {alembic_ini_path}，跳过 alembic 迁移")
    else:
        try:
            from alembic.config import Config
            from alembic import command

            alembic_cfg = Config(str(alembic_ini_path))
            # 显式从 settings 注入 DATABASE_URL，避免 alembic.ini 配置漂移
            alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
            command.upgrade(alembic_cfg, "head")
            logger.info("Alembic 迁移完成")
        except Exception as e:
            if is_production:
                logger.error(f"生产环境 Alembic 迁移失败: {e}")
                raise
            warnings.warn(f"Alembic 迁移失败（不影响 create_all）: {e}")

    logger.info("数据库初始化完成")


def drop_database() -> None:
    """
    删除所有表结构（仅用于测试环境）
    """
    logger.warning("正在删除数据库所有表...")
    Base.metadata.drop_all(bind=engine)
    logger.warning("数据库表已全部删除")
