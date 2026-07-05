"""
企业培训任务业务逻辑层
"""
from typing import Optional, List, Tuple, Dict, Any
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy import func, case

from app.models.enterprise_training import EnterpriseTraining
from app.schemas.training import (
    TrainingCreate,
    TrainingUpdate,
    TrainingResponse,
    TrainingStatsResponse,
    TrainingBatchImportRequest,
)


class TrainingService:
    """企业培训任务服务"""

    @staticmethod
    def _to_response(training: EnterpriseTraining) -> TrainingResponse:
        """ORM 对象转响应模型"""
        return TrainingResponse(
            id=training.id,
            company_name=training.company_name,
            training_name=training.training_name,
            training_type=training.training_type,
            description=training.description,
            industry=training.industry,
            modules=training.modules or [],
            participant_count=training.participant_count,
            participants=training.participants or [],
            responsible_person=training.responsible_person,
            start_date=training.start_date,
            end_date=training.end_date,
            estimated_duration=training.estimated_duration,
            status=training.status,
            progress_percentage=training.progress_percentage,
            completed_modules=training.completed_modules,
            is_transfer_training=training.is_transfer_training,
            transfer_from_position=training.transfer_from_position,
            transfer_to_position=training.transfer_to_position,
            skill_gap_analysis=training.skill_gap_analysis or {},
            pass_rate=training.pass_rate,
            average_score=training.average_score,
            satisfaction_rate=training.satisfaction_rate,
            total_resources_used=training.total_resources_used,
            total_tasks_completed=training.total_tasks_completed,
            created_at=training.created_at,
            updated_at=training.updated_at,
        )

    @staticmethod
    def get_training_list(
        db: Session,
        page: int = 1,
        page_size: int = 10,
        keyword: Optional[str] = None,
        status: Optional[str] = None,
        training_type: Optional[str] = None,
    ) -> Tuple[List[TrainingResponse], int]:
        """获取培训任务列表"""
        query = db.query(EnterpriseTraining)

        if keyword:
            query = query.filter(
                (EnterpriseTraining.training_name.contains(keyword))
                | (EnterpriseTraining.company_name.contains(keyword))
            )
        if status:
            query = query.filter(EnterpriseTraining.status == status)
        if training_type:
            query = query.filter(EnterpriseTraining.training_type == training_type)

        total = query.count()
        items = (
            query.order_by(EnterpriseTraining.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return [TrainingService._to_response(t) for t in items], total

    @staticmethod
    def get_training_by_id(db: Session, training_id: int) -> Optional[TrainingResponse]:
        """获取培训任务详情"""
        training = db.query(EnterpriseTraining).filter(
            EnterpriseTraining.id == training_id
        ).first()
        if not training:
            return None
        return TrainingService._to_response(training)

    @staticmethod
    def create_training(db: Session, data: TrainingCreate) -> EnterpriseTraining:
        """创建培训任务"""
        training = EnterpriseTraining(
            company_name=data.company_name,
            training_name=data.training_name,
            training_type=data.training_type,
            description=data.description,
            industry=data.industry,
            modules=data.modules,
            participant_count=data.participant_count,
            participants=data.participants,
            responsible_person=data.responsible_person,
            start_date=data.start_date,
            end_date=data.end_date,
            estimated_duration=data.estimated_duration,
            status="planning",
            progress_percentage=0.0,
            completed_modules=0,
            is_transfer_training=data.is_transfer_training,
            transfer_from_position=data.transfer_from_position,
            transfer_to_position=data.transfer_to_position,
            skill_gap_analysis=data.skill_gap_analysis,
        )
        db.add(training)
        db.commit()
        db.refresh(training)
        logger.info(f"创建培训任务: {training.id} - {training.training_name}")
        return training

    @staticmethod
    def update_training(
        db: Session, training_id: int, data: TrainingUpdate
    ) -> Optional[EnterpriseTraining]:
        """更新培训任务"""
        training = db.query(EnterpriseTraining).filter(
            EnterpriseTraining.id == training_id
        ).first()
        if not training:
            return None

        update_fields = data.model_dump(exclude_unset=True)
        for field, value in update_fields.items():
            setattr(training, field, value)

        # 自动同步 completed_modules 与 modules 数量
        if training.modules and training.progress_percentage > 0:
            total_modules = len(training.modules)
            if total_modules > 0:
                training.completed_modules = min(
                    int(total_modules * training.progress_percentage / 100),
                    total_modules,
                )

        db.commit()
        db.refresh(training)
        logger.info(f"更新培训任务: {training_id}")
        return training

    @staticmethod
    def delete_training(db: Session, training_id: int) -> bool:
        """删除培训任务"""
        training = db.query(EnterpriseTraining).filter(
            EnterpriseTraining.id == training_id
        ).first()
        if not training:
            return False
        db.delete(training)
        db.commit()
        logger.info(f"删除培训任务: {training_id}")
        return True

    @staticmethod
    def get_stats(db: Session) -> TrainingStatsResponse:
        """获取培训统计"""
        total = db.query(func.count(EnterpriseTraining.id)).scalar() or 0
        ongoing = db.query(func.count(EnterpriseTraining.id)).filter(
            EnterpriseTraining.status == "ongoing"
        ).scalar() or 0
        completed = db.query(func.count(EnterpriseTraining.id)).filter(
            EnterpriseTraining.status == "completed"
        ).scalar() or 0

        companies = db.query(
            func.count(func.distinct(EnterpriseTraining.company_name))
        ).scalar() or 0

        learners = db.query(
            func.coalesce(func.sum(EnterpriseTraining.participant_count), 0)
        ).scalar() or 0

        avg_pass = db.query(
            func.avg(
                case(
                    (EnterpriseTraining.pass_rate > 0, EnterpriseTraining.pass_rate),
                    else_=None,
                )
            )
        ).scalar()
        avg_score = db.query(
            func.avg(
                case(
                    (EnterpriseTraining.average_score > 0, EnterpriseTraining.average_score),
                    else_=None,
                )
            )
        ).scalar()

        return TrainingStatsResponse(
            companies=companies,
            learners=int(learners),
            pass_rate=round(float(avg_pass or 0), 1),
            avg_score=round(float(avg_score or 0), 1),
            total_trainings=total,
            ongoing_trainings=ongoing,
            completed_trainings=completed,
        )

    @staticmethod
    def get_transfers(db: Session) -> List[Dict[str, Any]]:
        """获取转岗培训列表（前端适配格式）"""
        trainings = db.query(EnterpriseTraining).filter(
            EnterpriseTraining.is_transfer_training == True
        ).order_by(EnterpriseTraining.created_at.desc()).all()

        result = []
        for t in trainings:
            gap_data = t.skill_gap_analysis or {}
            result.append({
                "id": t.id,
                "name": t.responsible_person or "未命名",
                "from": t.transfer_from_position or "-",
                "to": t.transfer_to_position or "-",
                "company": t.company_name,
                "completion": t.progress_percentage,
                "skill_gap": gap_data.get("overall_gap", 0),
            })
        return result

    @staticmethod
    def get_skill_gaps(db: Session, training_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取技能差距分析"""
        query = db.query(EnterpriseTraining).filter(
            EnterpriseTraining.is_transfer_training == True,
            EnterpriseTraining.skill_gap_analysis.isnot(None),
        )
        if training_id:
            query = query.filter(EnterpriseTraining.id == training_id)

        trainings = query.all()
        all_skills: Dict[str, Dict[str, float]] = {}

        for t in trainings:
            skills = (t.skill_gap_analysis or {}).get("skills", [])
            for s in skills:
                name = s.get("skill", "")
                if name:
                    if name not in all_skills:
                        all_skills[name] = {"current": 0, "required": 0, "count": 0}
                    all_skills[name]["current"] += s.get("current", 0)
                    all_skills[name]["required"] += s.get("required", 0)
                    all_skills[name]["count"] += 1

        result = []
        for name, vals in all_skills.items():
            cnt = max(vals["count"], 1)
            current = round(vals["current"] / cnt, 1)
            required = round(vals["required"] / cnt, 1)
            result.append({
                "skill": name,
                "current": current,
                "required": required,
                "gap": round(max(required - current, 0), 1),
            })
        return result

    @staticmethod
    def batch_import(db: Session, request: TrainingBatchImportRequest) -> Dict[str, Any]:
        """批量导入培训任务"""
        success_count = 0
        failed_count = 0
        for item in request.trainings:
            try:
                training = EnterpriseTraining(
                    company_name=item.company_name,
                    training_name=item.training_name,
                    training_type=item.training_type,
                    industry=item.industry,
                    participant_count=item.participant_count,
                    responsible_person=item.responsible_person,
                    status="planning",
                )
                db.add(training)
                db.flush()
                success_count += 1
            except Exception as e:
                db.rollback()
                logger.warning(f"导入培训任务失败: {e}")
                failed_count += 1
        db.commit()
        return {"success_count": success_count, "failed_count": failed_count}

    @staticmethod
    def init_seed_data(db: Session):
        """初始化种子数据（从 JSON 配置文件读取，避免硬编码）"""
        from app.utils.seed_loader import load_seed_data

        existing = db.query(EnterpriseTraining).count()
        if existing > 0:
            return

        records = load_seed_data("trainings.json")
        for record in records:
            db.add(EnterpriseTraining(**record))
        db.commit()
        logger.info(f"企业培训种子数据已初始化: {len(records)} 条")
