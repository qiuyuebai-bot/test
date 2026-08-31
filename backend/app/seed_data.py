"""
种子数据初始化
默认管理员、学习者画像和领域知识库示例

CLI 用法：python -m app.seed_data [--admin-only] [--learners] [--career-training] [--knowledge]
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


def init_career_training_seed_data():
    """初始化岗位培训演示数据，按业务编码幂等补齐，不覆盖已有配置。"""
    from app.domains.assessment.models import AssessmentTemplate
    from app.domains.certification.models import Certification, CertificationRule
    from app.domains.position.models import Competency, Position, PositionCompetency
    from app.domains.training.models import TrainingProject
    from app.utils.seed_loader import load_seed_payload

    payload = load_seed_payload("career_training.json")
    db = SessionLocal()
    try:
        competencies = {}
        for item in payload.get("competencies", []):
            code = item.get("code")
            if not code or not item.get("name"):
                logger.warning("跳过字段不完整的胜任力种子记录: {}", item)
                continue
            competency = db.query(Competency).filter(Competency.code == code).first()
            if competency is None:
                competency = Competency(
                    code=code,
                    name=item["name"],
                    category=item.get("category"),
                    description=item.get("description"),
                    level_descriptions=item.get("level_descriptions") or {},
                    is_active=True,
                )
                db.add(competency)
                db.flush()
            competencies[code] = competency

        positions = {}
        for item in payload.get("positions", []):
            code = item.get("code")
            if not code or not item.get("name"):
                logger.warning("跳过字段不完整的岗位种子记录: {}", item)
                continue
            position = db.query(Position).filter(Position.code == code).first()
            if position is None:
                position = Position(
                    code=code,
                    name=item["name"],
                    category=item.get("category"),
                    industry=item.get("industry"),
                    level=item.get("level"),
                    description=item.get("description"),
                    responsibilities=item.get("responsibilities") or [],
                    key_tasks=item.get("key_tasks") or [],
                    prerequisites=item.get("prerequisites") or [],
                    career_path=item.get("career_path") or [],
                    is_active=True,
                )
                db.add(position)
                db.flush()
            elif not position.key_tasks and item.get("key_tasks"):
                position.key_tasks = item.get("key_tasks")
            positions[code] = position

            for requirement in item.get("competencies", []):
                competency = competencies.get(requirement.get("code"))
                if competency is None:
                    logger.warning("岗位 {} 引用了不存在的胜任力: {}", code, requirement.get("code"))
                    continue
                existing = db.query(PositionCompetency).filter(
                    PositionCompetency.position_id == position.id,
                    PositionCompetency.competency_id == competency.id,
                ).first()
                if existing is None:
                    db.add(PositionCompetency(
                        position_id=position.id,
                        competency_id=competency.id,
                        required_level=requirement.get("required_level", 3),
                        weight=requirement.get("weight", 1.0),
                        is_mandatory=requirement.get("is_mandatory", True),
                    ))

        db.flush()

        certifications = {}
        for item in payload.get("certifications", []):
            code = item.get("code")
            position = positions.get(item.get("position_code"))
            if not code or position is None or not item.get("name"):
                logger.warning("跳过字段不完整的认证种子记录: {}", item)
                continue
            certification = db.query(Certification).filter(Certification.code == code).first()
            if certification is None:
                certification = Certification(
                    position_id=position.id,
                    name=item["name"],
                    code=code,
                    level=item.get("level"),
                    description=item.get("description"),
                    validity_period_months=item.get("validity_period_months", 0),
                    issuer=item.get("issuer"),
                    is_active=True,
                )
                db.add(certification)
                db.flush()
            certifications[code] = certification

            existing_rules = db.query(CertificationRule).filter(
                CertificationRule.certification_id == certification.id,
            ).all()
            for rule_item in item.get("rules", []):
                rule_type = rule_item.get("rule_type")
                rule_config = dict(rule_item.get("rule_config") or {})
                competency_code = rule_config.pop("competency_code", None)
                if competency_code:
                    competency = competencies.get(competency_code)
                    if competency is None:
                        logger.warning("认证 {} 引用了不存在的胜任力: {}", code, competency_code)
                        continue
                    rule_config["competency_id"] = competency.id
                if not rule_type:
                    continue
                if not any(
                    rule.rule_type == rule_type and rule.rule_config == rule_config
                    for rule in existing_rules
                ):
                    new_rule = CertificationRule(
                        certification_id=certification.id,
                        rule_type=rule_type,
                        rule_config=rule_config,
                    )
                    db.add(new_rule)
                    existing_rules.append(new_rule)

        db.flush()

        for item in payload.get("assessment_templates", []):
            position = positions.get(item.get("position_code"))
            if position is None or not item.get("name"):
                logger.warning("跳过字段不完整的评估模板种子记录: {}", item)
                continue
            template = db.query(AssessmentTemplate).filter(
                AssessmentTemplate.position_id == position.id,
                AssessmentTemplate.name == item["name"],
            ).first()
            if template is None:
                configs = []
                for config in item.get("competencies", []):
                    competency = competencies.get(config.get("code"))
                    if competency is None:
                        logger.warning("评估模板 {} 引用了不存在的胜任力: {}", item["name"], config.get("code"))
                        continue
                    configs.append({
                        "competency_id": competency.id,
                        "question_count": config.get("question_count", 5),
                        "difficulty": config.get("difficulty", 3),
                        "assessment_method": config.get("assessment_method", "quiz"),
                    })
                db.add(AssessmentTemplate(
                    position_id=position.id,
                    name=item["name"],
                    description=item.get("description"),
                    competency_configs=configs,
                    pass_threshold=item.get("pass_threshold", 60),
                    duration_minutes=item.get("duration_minutes"),
                    is_active=True,
                ))

        db.flush()

        for item in payload.get("training_projects", []):
            position = positions.get(item.get("position_code"))
            certification = certifications.get(item.get("certification_code"))
            if position is None or not item.get("name"):
                logger.warning("跳过字段不完整的培训项目种子记录: {}", item)
                continue
            project = db.query(TrainingProject).filter(
                TrainingProject.position_id == position.id,
                TrainingProject.name == item["name"],
            ).first()
            if project is None:
                project = TrainingProject(
                    name=item["name"],
                    description=item.get("description"),
                    position_id=position.id,
                    certification_id=certification.id if certification else None,
                    project_type=item.get("project_type"),
                    enterprise_name=item.get("enterprise_name"),
                    status="active",
                    config=item.get("config") or {},
                    created_by=None,
                )
                db.add(project)
                db.flush()

            # 任务包按项目名称幂等补齐，便于旧数据库升级后获得可演示的实操闭环。
            from app.domains.training.models import TrainingTaskPackage
            for package_item in item.get("task_packages", []):
                package_name = package_item.get("name")
                if not package_name:
                    continue
                package = db.query(TrainingTaskPackage).filter(
                    TrainingTaskPackage.project_id == project.id,
                    TrainingTaskPackage.name == package_name,
                ).first()
                if package is None:
                    package = TrainingTaskPackage(
                        project_id=project.id,
                        name=package_name,
                        description=package_item.get("description"),
                        sequence=package_item.get("sequence", 1),
                        task_type=package_item.get("task_type", "practice"),
                        key_task_code=package_item.get("key_task_code"),
                        learning_objectives=package_item.get("learning_objectives") or [],
                        resources=package_item.get("resources") or [],
                        submission_required=package_item.get("submission_required", True),
                        passing_score=package_item.get("passing_score", 60),
                        is_mandatory=package_item.get("is_mandatory", True),
                        status="active",
                    )
                    db.add(package)
                    db.flush()
                    for index, rubric in enumerate(package_item.get("rubrics", []), 1):
                        criterion = rubric.get("criterion")
                        if criterion:
                            from app.domains.training.models import TrainingTaskRubric
                            db.add(TrainingTaskRubric(
                                task_package_id=package.id,
                                criterion=criterion,
                                description=rubric.get("description"),
                                max_score=rubric.get("max_score", 100),
                                weight=rubric.get("weight", 1),
                                sequence=rubric.get("sequence", index),
                            ))

        db.commit()
        logger.info(
            "岗位培训种子数据初始化完成: 岗位 {}，胜任力 {}，评估模板 {}，认证 {}，培训项目 {}",
            len(positions),
            len(competencies),
            len(payload.get("assessment_templates", [])),
            len(certifications),
            len(payload.get("training_projects", [])),
        )
    except Exception as e:
        logger.warning(f"初始化岗位培训种子数据失败: {e}")
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
    """初始化全部种子数据（管理员 + 学习者 + 岗位培训 + 知识库）"""
    init_default_admin()
    init_learner_seed_data()
    init_career_training_seed_data()
    init_knowledge_seed_data()
    init_metrics_seed_data()


if __name__ == "__main__":
    args = set(sys.argv[1:])
    if "--help" in args or "-h" in args:
        print("用法: python -m app.seed_data [选项]")
        print("  (无参数)   初始化全部种子数据")
        print("  --admin-only  仅初始化默认管理员")
        print("  --learners    仅初始化学习者画像数据")
        print("  --career-training  仅初始化岗位培训数据")
        print("  --knowledge   仅初始化默认知识库")
        print("  --metrics     根据当前事实生成标准指标快照")
        sys.exit(0)

    if "--admin-only" in args:
        init_default_admin()
    elif "--learners" in args:
        init_learner_seed_data()
    elif "--career-training" in args:
        init_career_training_seed_data()
    elif "--knowledge" in args:
        init_knowledge_seed_data()
    elif "--metrics" in args:
        init_metrics_seed_data()
    else:
        seed_all()

    logger.info("种子数据初始化 CLI 执行完成")
