"""
种子数据初始化
默认管理员、学习者画像和领域知识库示例

CLI 用法：python -m app.seed_data [--admin-only] [--learners] [--knowledge]
"""
import hashlib
import sys
from pathlib import Path

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


def init_metrics_seed_data():
    """Materialize a standard snapshot from the current demo facts."""
    from app.services.metric_service import MetricService

    db = SessionLocal()
    try:
        results = MetricService.calculate_metrics(db, scope="global")
        MetricService.persist_daily_snapshot(db, results)
        logger.info("Metric demo snapshot initialized")
    except Exception as e:
        logger.warning(f"Metric demo snapshot initialization failed: {e}")
        db.rollback()
    finally:
        db.close()


def normalize_demo_data_paths():
    """Resolve filesystem placeholders in the bundled demo database."""
    if not settings.is_desktop:
        return
    from app.domains.knowledge.models import KnowledgeDoc

    token = "__DEMO_DATA_DIR__"
    data_dir = Path(settings.APP_DATA_DIR).resolve()
    db = SessionLocal()
    try:
        changed = 0
        for document in db.query(KnowledgeDoc).filter(KnowledgeDoc.file_path.like(f"{token}%")):
            suffix = str(document.file_path)[len(token):].lstrip("/\\")
            document.file_path = str(data_dir / suffix)
            changed += 1
        if changed:
            db.commit()
            logger.info("桌面演示数据文件路径已解析: {} 条", changed)
    except Exception as e:
        logger.warning(f"解析演示数据文件路径失败: {e}")
        db.rollback()
    finally:
        db.close()


def init_knowledge_seed_data():
    """初始化默认知识库文档和数据库切片。

    默认种子使用数据库关键词检索即可工作，不在启动阶段强制下载向量模型。
    管理员后续可通过知识库页面重新索引，启用向量检索。
    """
    from app.domains.knowledge.models import KnowledgeDoc, KnowledgeSlice
    from app.utils.seed_loader import load_seed_payload

    payload = load_seed_payload("knowledge.json")
    db = SessionLocal()
    created_files = []
    try:
        created_docs = 0
        updated_docs = 0
        created_slices = 0
        doc_dir = Path(settings.KNOWLEDGE_DOC_DIR)
        doc_dir.mkdir(parents=True, exist_ok=True)

        for item in payload.get("records", []):
            file_name = item.get("file_name")
            slices = item.get("slices") or []
            if not file_name or not item.get("title") or not item.get("industry") or not slices:
                logger.warning("跳过字段不完整的知识库种子记录: {}", item.get("code"))
                continue

            existing = db.query(KnowledgeDoc).filter(
                KnowledgeDoc.file_name == file_name,
            ).first()
            if existing is not None:
                if existing.origin_type != "seed":
                    continue
                existing_slices = db.query(KnowledgeSlice).filter(
                    KnowledgeSlice.doc_id == existing.id,
                ).all()
                existing_titles = {slice_item.title for slice_item in existing_slices}
                existing_hashes = {slice_item.content_hash for slice_item in existing_slices}
                pending_slices = [
                    slice_item for slice_item in slices
                    if slice_item.get("title") not in existing_titles
                    and hashlib.sha256(
                        str(slice_item.get("content") or "").strip().encode("utf-8")
                    ).hexdigest() not in existing_hashes
                ]
                if not pending_slices:
                    continue
                doc = existing
                slice_start = max(
                    (slice_item.slice_index for slice_item in existing_slices),
                    default=-1,
                ) + 1
                doc.slice_count = len(existing_slices) + len(pending_slices)
                doc.indexed_slice_count = sum(
                    1 for slice_item in existing_slices if slice_item.is_indexed
                )
                updated_docs += 1
            else:
                content = "\n\n".join(
                    f"## {slice_item.get('title', '')}\n{slice_item.get('content', '')}"
                    for slice_item in slices
                )
                file_path = doc_dir / file_name
                if not file_path.exists():
                    file_path.write_text(
                        f"# {item['title']}\n\n{content}\n",
                        encoding="utf-8",
                    )
                    created_files.append(file_path)

                doc = KnowledgeDoc(
                    title=item["title"],
                    industry=item["industry"],
                    category=item.get("category"),
                    file_name=file_name,
                    file_path=str(file_path),
                    file_size=file_path.stat().st_size,
                    file_type="md",
                    content_preview=content[:500],
                    total_pages=1,
                    word_count=len(content),
                    slice_count=len(slices),
                    indexed_slice_count=0,
                    status="ready",
                    process_progress=100,
                    source=item.get("source"),
                    origin_type="seed",
                    version=str(payload.get("_meta", {}).get("version", "1.0")),
                    author=item.get("author"),
                    tags=item.get("tags") or [],
                    is_enabled=True,
                )
                db.add(doc)
                db.flush()
                pending_slices = slices
                slice_start = 0

            for index, slice_item in enumerate(pending_slices, start=slice_start):
                slice_content = str(slice_item.get("content") or "").strip()
                if not slice_content:
                    continue
                db.add(KnowledgeSlice(
                    doc_id=doc.id,
                    slice_index=index,
                    slice_type="paragraph",
                    content=slice_content,
                    content_hash=hashlib.sha256(slice_content.encode("utf-8")).hexdigest(),
                    word_count=len(slice_content),
                    title=slice_item.get("title"),
                    is_indexed=False,
                    slice_metadata={"seed": True, "source_code": item.get("code")},
                    keywords=slice_item.get("keywords") or [],
                    quality_score=1.0,
                    relevance_score=1.0,
                ))
                created_slices += 1
            created_docs += 1

        db.commit()
        logger.info(
            "知识库种子数据初始化完成: 文档新增 {}，文档补齐 {}，切片新增 {}（数据库关键词检索可用）",
            created_docs,
            updated_docs,
            created_slices,
        )
    except Exception as exc:
        logger.warning(f"初始化知识库种子数据失败: {exc}")
        db.rollback()
        for file_path in created_files:
            try:
                file_path.unlink(missing_ok=True)
            except OSError:
                logger.warning(f"清理未提交的知识文档失败: {file_path}")
    finally:
        db.close()


def seed_all():
    """初始化全部种子数据（管理员 + 学习者 + 知识库）"""
    init_default_admin()
    init_learner_seed_data()
    init_knowledge_seed_data()
    init_metrics_seed_data()


if __name__ == "__main__":
    args = set(sys.argv[1:])
    if "--help" in args or "-h" in args:
        print("用法: python -m app.seed_data [选项]")
        print("  (无参数)   初始化全部种子数据")
        print("  --admin-only  仅初始化默认管理员")
        print("  --learners    仅初始化学习者画像数据")
        print("  --knowledge   仅初始化默认知识库")
        print("  --metrics     根据当前事实生成标准指标快照")
        sys.exit(0)

    if "--admin-only" in args:
        init_default_admin()
    elif "--learners" in args:
        init_learner_seed_data()
    elif "--knowledge" in args:
        init_knowledge_seed_data()
    elif "--metrics" in args:
        init_metrics_seed_data()
    else:
        seed_all()

    logger.info("种子数据初始化 CLI 执行完成")
