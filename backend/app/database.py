"""
数据库连接与会话管理
统一从 config.settings 读取 DATABASE_URL，根据数据库类型自动适配连接参数：
- SQLite：单线程模式（check_same_thread=False），不使用连接池
- PostgreSQL：使用连接池（pool_size + max_overflow），pool_pre_ping 保活
"""
from pathlib import Path
import sqlite3
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from typing import Generator
from contextlib import contextmanager
from loguru import logger
from fastapi import HTTPException

from app.config import settings
from app.desktop_runtime import bundle_path, desktop_data_dir


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

    Alembic 是已存在数据库的 schema source of truth。只有没有版本表的首次
    启动才使用 ``create_all`` 建立初始基线；有版本记录的数据库必须只通过
    Alembic 演进，避免 ORM 模型提前创建后续迁移中的表而产生 schema drift。
    """
    import app.models as models
    import warnings

    logger.info(f"正在初始化数据库（已注册 {len(models.__all__)} 个模型，APP_ENV={settings.APP_ENV}）...")

    is_production = settings.APP_ENV == "production" or settings.is_desktop

    alembic_ini_path = bundle_path("alembic.ini")
    if not alembic_ini_path.exists():
        if is_production:
            logger.error(f"生产环境未找到 alembic.ini: {alembic_ini_path}")
            raise RuntimeError(f"生产环境必须配置 alembic.ini: {alembic_ini_path}")
        Base.metadata.create_all(bind=engine)
        logger.warning(f"未找到 alembic.ini: {alembic_ini_path}，跳过 alembic 迁移")
    else:
        table_names = set(inspect(engine).get_table_names())
        has_version_table = "alembic_version" in table_names
        user_tables = table_names - {"alembic_version"}
        is_fresh_schema = not has_version_table and not user_tables

        # 初始迁移是历史基线（不创建表），所以新数据库需要先建立 ORM
        # 基线；后续启动一律跳过 create_all，让迁移文件管理 schema。
        if is_fresh_schema:
            Base.metadata.create_all(bind=engine)
            logger.info("create_all 完成（全新数据库的初始基线）")
        else:
            logger.info("检测到 Alembic 版本表，跳过 create_all，按迁移链升级")

        # 运行 alembic 迁移（确保 schema 最新）
        try:
            from alembic.config import Config
            from alembic import command

            alembic_cfg = Config(str(alembic_ini_path))
            # Alembic otherwise resolves ``script_location = alembic`` from
            # the process working directory.  Keep migrations reliable when
            # the backend is launched from the project root (for tests) too.
            alembic_cfg.set_main_option("script_location", str(bundle_path("alembic")))
            # 显式从 settings 注入 DATABASE_URL，避免 alembic.ini 配置漂移
            alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
            if is_fresh_schema:
                # ORM 已按当前模型建立完整结构。全新库继续执行历史 ALTER
                # 迁移会重复添加已存在的列，因此只写入当前迁移版本标记。
                command.stamp(alembic_cfg, "head")
                logger.info("全新数据库已标记为 Alembic 最新版本")
            else:
                _backup_desktop_sqlite_before_upgrade()
                command.upgrade(alembic_cfg, "head")
                logger.info("Alembic 迁移完成")
        except Exception as e:
            if is_production:
                logger.error(f"生产环境 Alembic 迁移失败: {e}")
                raise
            warnings.warn(f"Alembic 迁移失败（不影响 create_all）: {e}")

    logger.info("数据库初始化完成")


def _backup_desktop_sqlite_before_upgrade() -> None:
    """桌面更新迁移前保留一份 SQLite 备份，避免安装升级损伤用户数据。"""
    if not settings.is_desktop or not settings.is_sqlite:
        return
    raw_path = settings.DATABASE_URL[len("sqlite:///"):]
    database_path = Path(raw_path)
    if not database_path.exists():
        return
    backup_dir = desktop_data_dir() / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"pre-upgrade-{settings.APP_VERSION}.db"
    if backup_path.exists():
        return
    with sqlite3.connect(database_path) as source, sqlite3.connect(backup_path) as target:
        source.backup(target)
    logger.info("桌面数据库升级前备份已创建: {}", backup_path)


def drop_database() -> None:
    """
    删除所有表结构（仅用于测试环境）
    """
    logger.warning("正在删除数据库所有表...")
    Base.metadata.drop_all(bind=engine)
    logger.warning("数据库表已全部删除")
