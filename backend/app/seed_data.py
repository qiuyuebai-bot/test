"""
种子数据初始化
默认管理员 + 企业培训 + 学习者画像

CLI 用法：python -m app.seed_data [--admin-only] [--training] [--learners]
"""
import sys
from loguru import logger

from app.config import settings
from app.database import SessionLocal
from app.utils.auth import hash_password


def init_default_admin():
    """初始化默认管理员账户"""
    from app.models.user import User, UserRoleEnum

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                password_hash=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
                email="admin@knowledge-system.com",
                role=UserRoleEnum.ADMIN,
                is_active=True,
                is_verified=True,
            )
            db.add(admin)
            db.commit()
            logger.info("默认管理员账户已创建（密码来自 DEFAULT_ADMIN_PASSWORD 配置）")
        else:
            logger.debug("默认管理员账户已存在")
    except Exception as e:
        logger.warning(f"初始化默认管理员失败: {e}")
        db.rollback()
    finally:
        db.close()


def init_training_seed_data():
    """初始化企业培训种子数据"""
    from app.domains.training.service import TrainingService

    db = SessionLocal()
    try:
        TrainingService.init_seed_data(db)
    except Exception as e:
        logger.warning(f"初始化培训种子数据失败: {e}")
        db.rollback()
    finally:
        db.close()


def init_learner_seed_data():
    """初始化学习者画像种子数据（从 JSON 配置文件读取，避免硬编码）"""
    from app.models.user import User, UserRoleEnum
    from app.domains.learner.models import LearnerProfile
    from app.utils.seed_loader import load_seed_data, load_seed_meta

    db = SessionLocal()
    try:
        existing = db.query(LearnerProfile).count()
        if existing > 0:
            logger.debug("学习者种子数据已存在，跳过初始化")
            return

        meta = load_seed_meta("learners.json")
        default_password = meta.get("default_password", "learner123")
        default_role = meta.get("default_role", "learner")
        try:
            role_enum = UserRoleEnum(default_role)
        except ValueError:
            logger.warning(f"未知角色 {default_role}，回退为 LEARNER")
            role_enum = UserRoleEnum.LEARNER

        records = load_seed_data("learners.json")
        for record in records:
            username = record.pop("username", None)
            if not username:
                logger.warning(f"跳过缺少 username 的学习者记录: {record}")
                continue
            user = User(
                username=username,
                password_hash=hash_password(default_password),
                role=role_enum,
                is_active=True,
                is_verified=True,
            )
            db.add(user)
            db.flush()
            profile = LearnerProfile(user_id=user.id, **record)
            db.add(profile)
        db.commit()
        logger.info(f"学习者种子数据已初始化: {len(records)} 条 (默认密码已配置)")
    except Exception as e:
        logger.warning(f"初始化学习者种子数据失败: {e}")
        db.rollback()
    finally:
        db.close()


def seed_all():
    """初始化全部种子数据（管理员 + 培训 + 学习者）"""
    init_default_admin()
    init_training_seed_data()
    init_learner_seed_data()


if __name__ == "__main__":
    args = set(sys.argv[1:])
    if "--help" in args or "-h" in args:
        print("用法: python -m app.seed_data [选项]")
        print("  (无参数)   初始化全部种子数据")
        print("  --admin-only  仅初始化默认管理员")
        print("  --training    仅初始化企业培训数据")
        print("  --learners    仅初始化学习者画像数据")
        sys.exit(0)

    if "--admin-only" in args:
        init_default_admin()
    elif "--training" in args:
        init_training_seed_data()
    elif "--learners" in args:
        init_learner_seed_data()
    else:
        seed_all()

    logger.info("种子数据初始化 CLI 执行完成")
