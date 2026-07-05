"""
学习者画像服务层
实现画像管理、学情分析、数据脱敏、批量导入导出等业务逻辑
"""
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import or_
from loguru import logger

from app.constants import BLIND_AREA_CRITICAL_THRESHOLD, BLIND_AREA_WARNING_THRESHOLD
from app.models import (
    LearnerProfile,
    AnswerRecord,
    User,
    AnonymizedData,
    UserRoleEnum,
)
from app.schemas.learner import (
    LearnerProfileCreate,
    LearnerProfileUpdate,
    LearnerBatchImportRequest,
    LearnerBatchImportResponse,
    LearnerBatchExportRequest,
    LearningAnalysisResponse,
    AbilityDimension,
    AnonymizeRequest,
    AnonymizeResponse,
    AnswerRecordCreate,
)
from app.utils.anonymize import AnonymizeUtil


class LearnerService:
    """学习者画像服务类"""
    
    # 能力维度配置
    ABILITY_DIMENSIONS = [
        ("theoretical_foundation", "理论基础"),
        ("programming_ability", "编程能力"),
        ("algorithm_design", "算法设计"),
        ("system_architecture", "系统架构"),
        ("data_analysis", "数据分析"),
        ("engineering_practice", "工程实践"),
    ]
    
    @staticmethod
    def create_learner(db: Session, learner_data: LearnerProfileCreate) -> Optional[LearnerProfile]:
        """
        创建学习者画像
        
        Args:
            db: 数据库会话
            learner_data: 学习者创建数据
            
        Returns:
            学习者画像对象，已存在则返回None
        """
        existing = db.query(LearnerProfile).filter(
            LearnerProfile.user_id == learner_data.user_id
        ).first()
        if existing:
            logger.warning(f"用户已存在学习者画像: user_id={learner_data.user_id}")
            return None
        
        learner = LearnerProfile(
            user_id=learner_data.user_id,
            real_name=learner_data.real_name,
            education_level=learner_data.education_level,
            major=learner_data.major,
            graduation_year=learner_data.graduation_year,
            current_position=learner_data.current_position,
            learning_style=learner_data.learning_style,
            preferred_difficulty=learner_data.preferred_difficulty,
            daily_study_time=learner_data.daily_study_time,
            target_industry=learner_data.target_industry,
            target_position=learner_data.target_position,
            learning_goal=learner_data.learning_goal,
            theoretical_foundation=learner_data.theoretical_foundation,
            programming_ability=learner_data.programming_ability,
            algorithm_design=learner_data.algorithm_design,
            system_architecture=learner_data.system_architecture,
            data_analysis=learner_data.data_analysis,
            engineering_practice=learner_data.engineering_practice,
            knowledge_blind_areas=learner_data.knowledge_blind_areas,
        )
        
        db.add(learner)
        db.commit()
        db.refresh(learner)
        
        logger.info(f"创建学习者画像: id={learner.id}, user_id={learner.user_id}")
        
        return learner
    
    @staticmethod
    def get_learner_list(
        db: Session,
        page: int = 1,
        page_size: int = 10,
        keyword: Optional[str] = None,
        education_level: Optional[str] = None,
        target_industry: Optional[str] = None,
        learning_style: Optional[str] = None,
        is_anonymized: Optional[bool] = None,
    ) -> Tuple[List[LearnerProfile], int]:
        """
        获取学习者列表
        
        Args:
            db: 数据库会话
            page: 页码
            page_size: 每页数量
            keyword: 关键词搜索
            education_level: 学历过滤
            target_industry: 目标行业过滤
            learning_style: 学习风格过滤
            is_anonymized: 是否脱敏过滤
            
        Returns:
            Tuple[学习者列表, 总数]
        """
        query = db.query(LearnerProfile)
        
        # 关键词搜索
        if keyword:
            escaped_keyword = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            query = query.filter(
                or_(
                    LearnerProfile.real_name.like(f"%{escaped_keyword}%", escape="\\"),
                    LearnerProfile.major.like(f"%{escaped_keyword}%", escape="\\"),
                    LearnerProfile.current_position.like(f"%{escaped_keyword}%", escape="\\"),
                )
            )
        
        # 学历过滤
        if education_level:
            query = query.filter(LearnerProfile.education_level == education_level)
        
        # 行业过滤
        if target_industry:
            query = query.filter(LearnerProfile.target_industry == target_industry)
        
        # 学习风格过滤
        if learning_style:
            query = query.filter(LearnerProfile.learning_style == learning_style)
        
        # 脱敏状态过滤
        if is_anonymized is not None:
            query = query.filter(LearnerProfile.is_data_anonymized == is_anonymized)
        
        # 计算总数
        total = query.count()
        
        # 分页
        items = query.order_by(LearnerProfile.created_at.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        
        return items, total
    
    @staticmethod
    def get_learner_by_id(db: Session, learner_id: int) -> Optional[LearnerProfile]:
        """
        根据ID获取学习者
        
        Args:
            db: 数据库会话
            learner_id: 学习者ID
            
        Returns:
            学习者对象或None
        """
        return db.query(LearnerProfile).filter(LearnerProfile.id == learner_id).first()
    
    @staticmethod
    def get_learner_by_user_id(db: Session, user_id: int) -> Optional[LearnerProfile]:
        """
        根据用户ID获取学习者
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            
        Returns:
            学习者对象或None
        """
        return db.query(LearnerProfile).filter(LearnerProfile.user_id == user_id).first()
    
    @staticmethod
    def update_learner(
        db: Session,
        learner_id: int,
        update_data: LearnerProfileUpdate,
    ) -> Optional[LearnerProfile]:
        """
        更新学习者画像
        
        Args:
            db: 数据库会话
            learner_id: 学习者ID
            update_data: 更新数据
            
        Returns:
            更新后的学习者对象或None
        """
        learner = db.query(LearnerProfile).filter(
            LearnerProfile.id == learner_id
        ).first()
        
        if not learner:
            return None
        
        # 更新基本信息
        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            if hasattr(learner, key):
                setattr(learner, key, value)
        
        db.commit()
        db.refresh(learner)
        
        logger.info(f"更新学习者画像: id={learner_id}")
        
        return learner
    
    @staticmethod
    def delete_learner(db: Session, learner_id: int) -> bool:
        """
        删除学习者画像
        
        Args:
            db: 数据库会话
            learner_id: 学习者ID
            
        Returns:
            是否删除成功
        """
        learner = db.query(LearnerProfile).filter(
            LearnerProfile.id == learner_id
        ).first()
        
        if not learner:
            return False
        
        db.delete(learner)
        db.commit()
        
        logger.info(f"删除学习者画像: id={learner_id}")
        
        return True
    
    @staticmethod
    def batch_import(
        db: Session,
        import_data: LearnerBatchImportRequest,
    ) -> LearnerBatchImportResponse:
        """
        批量导入学习者
        
        Args:
            db: 数据库会话
            import_data: 导入数据
            
        Returns:
            导入结果
        """
        success_count = 0
        failed_count = 0
        created_ids = []
        errors = []
        
        for idx, learner_data in enumerate(import_data.learners):
            try:
                learner = LearnerProfile(
                    user_id=learner_data.user_id,
                    real_name=learner_data.real_name,
                    education_level=learner_data.education_level,
                    major=learner_data.major,
                    learning_style=learner_data.learning_style,
                    theoretical_foundation=learner_data.theoretical_foundation,
                    programming_ability=learner_data.programming_ability,
                    algorithm_design=learner_data.algorithm_design,
                    system_architecture=learner_data.system_architecture,
                    data_analysis=learner_data.data_analysis,
                    engineering_practice=learner_data.engineering_practice,
                    knowledge_blind_areas=learner_data.knowledge_blind_areas,
                    target_industry=learner_data.target_industry,
                )
                
                db.add(learner)
                db.flush()
                created_ids.append(learner.id)
                success_count += 1
                
            except Exception as e:
                db.rollback()
                failed_count += 1
                errors.append({
                    "index": idx,
                    "name": learner_data.real_name,
                    "error": str(e),
                })
                logger.error(f"批量导入失败: index={idx}, error={e}")
        
        db.commit()
        
        logger.info(f"批量导入: total={len(import_data.learners)}, success={success_count}, failed={failed_count}")
        
        return LearnerBatchImportResponse(
            total_count=len(import_data.learners),
            success_count=success_count,
            failed_count=failed_count,
            created_ids=created_ids,
            errors=errors,
        )
    
    @staticmethod
    def batch_export(
        db: Session,
        export_request: LearnerBatchExportRequest,
    ) -> List[Dict[str, Any]]:
        """
        批量导出学习者
        
        Args:
            db: 数据库会话
            export_request: 导出请求
            
        Returns:
            导出数据列表
        """
        query = db.query(LearnerProfile)
        
        if export_request.learner_ids:
            query = query.filter(LearnerProfile.id.in_(export_request.learner_ids))
        
        learners = query.all()
        
        export_data = []
        for learner in learners:
            item = {
                "id": learner.id,
                "real_name": learner.real_name if export_request.include_sensitive else AnonymizeUtil.anonymize_name(learner.real_name or ""),
                "education_level": learner.education_level,
                "major": learner.major,
                "learning_style": learner.learning_style,
                "theoretical_foundation": learner.theoretical_foundation,
                "programming_ability": learner.programming_ability,
                "algorithm_design": learner.algorithm_design,
                "system_architecture": learner.system_architecture,
                "data_analysis": learner.data_analysis,
                "engineering_practice": learner.engineering_practice,
                "average_ability": learner.average_ability,
                "knowledge_blind_areas": learner.knowledge_blind_areas,
                "target_industry": learner.target_industry,
            }
            export_data.append(item)
        
        logger.info(f"批量导出: count={len(export_data)}, format={export_request.export_format}")
        
        return export_data
    
    @staticmethod
    def analyze_learning(
        db: Session,
        learner_id: int,
    ) -> Optional[LearningAnalysisResponse]:
        """
        学情分析：自动解析测试记录，提取强项、盲区
        
        Args:
            db: 数据库会话
            learner_id: 学习者ID
            
        Returns:
            分析结果或None
        """
        learner = db.query(LearnerProfile).filter(
            LearnerProfile.id == learner_id
        ).first()
        
        if not learner:
            return None
        
        # 计算各维度能力等级
        ability_scores = {
            "theoretical_foundation": learner.theoretical_foundation,
            "programming_ability": learner.programming_ability,
            "algorithm_design": learner.algorithm_design,
            "system_architecture": learner.system_architecture,
            "data_analysis": learner.data_analysis,
            "engineering_practice": learner.engineering_practice,
        }
        
        strengths = []
        blind_areas = []
        blind_area_details = []
        
        for field_key, field_name in LearnerService.ABILITY_DIMENSIONS:
            score = ability_scores.get(field_key, 0)
            
            # 能力等级判定
            if score >= 90:
                level = "精通"
                strengths.append(field_name)
            elif score >= 75:
                level = "熟练"
                strengths.append(field_name)
            elif score >= BLIND_AREA_WARNING_THRESHOLD:
                level = "掌握"
            elif score >= BLIND_AREA_CRITICAL_THRESHOLD:
                level = "了解"
                blind_areas.append(field_name)
                blind_area_details.append({
                    "dimension": field_name,
                    "score": score,
                    "level": level,
                    "gap": 60 - score,
                })
            else:
                level = "薄弱"
                blind_areas.append(field_name)
                blind_area_details.append({
                    "dimension": field_name,
                    "score": score,
                    "level": level,
                    "gap": 60 - score,
                })
        
        # 计算总体评分
        overall_score = learner.average_ability
        if overall_score >= 85:
            overall_level = "优秀"
        elif overall_score >= 70:
            overall_level = "良好"
        elif overall_score >= 55:
            overall_level = "中等"
        else:
            overall_level = "待提升"
        
        # 获取答题历史统计
        answer_count = db.query(AnswerRecord).filter(
            AnswerRecord.learner_id == learner_id
        ).count()
        
        correct_count = db.query(AnswerRecord).filter(
            AnswerRecord.learner_id == learner_id,
            AnswerRecord.result == "correct",
        ).count()
        
        accuracy_rate = (correct_count / answer_count * 100) if answer_count > 0 else 0
        
        # 生成学习建议
        recommendations = []
        if len(blind_areas) > 0:
            top_blind = blind_area_details[0] if blind_area_details else None
            if top_blind:
                recommendations.append(f"重点提升「{top_blind['dimension']}」能力，当前分数 {top_blind['score']} 分")
                recommendations.append("建议从基础概念开始，循序渐进")
        
        if overall_score < 60:
            recommendations.append("整体基础偏弱，建议从入门级资源开始学习")
        elif overall_score < 80:
            recommendations.append("能力中等，可尝试进阶难度的学习资源")
        else:
            recommendations.append("基础扎实，建议挑战高阶实战项目")
        
        logger.info(f"学情分析: learner_id={learner_id}, overall_score={overall_score}")
        
        return LearningAnalysisResponse(
            learner_id=learner.id,
            overall_score=round(overall_score, 1),
            overall_level=overall_level,
            ability_dimensions=[
                AbilityDimension(
                    name=field_name,
                    score=ability_scores.get(field_key, 0),
                    level=("精通" if ability_scores.get(field_key, 0) >= 90
                           else "熟练" if ability_scores.get(field_key, 0) >= 75
                           else "掌握" if ability_scores.get(field_key, 0) >= BLIND_AREA_WARNING_THRESHOLD
                           else "了解" if ability_scores.get(field_key, 0) >= BLIND_AREA_CRITICAL_THRESHOLD
                           else "薄弱"),
                    description=LearnerService._get_ability_description(field_key, ability_scores.get(field_key, 0)),
                )
                for field_key, field_name in LearnerService.ABILITY_DIMENSIONS
            ],
            knowledge_strengths=strengths,
            knowledge_blind_areas=learner.knowledge_blind_areas or [],
            blind_area_details=blind_area_details,
            test_history_summary={
                "total_tests": answer_count,
                "correct_count": correct_count,
                "accuracy_rate": round(accuracy_rate, 2),
            },
            learning_recommendations=recommendations,
            analysis_date=datetime.now(),
        )
    
    @staticmethod
    def _get_ability_description(dimension: str, score: float) -> str:
        """获取能力维度描述"""
        descriptions = {
            "theoretical_foundation": "理论基础是学习的根基，决定对概念的理解深度",
            "programming_ability": "编程能力直接影响实践操作和代码实现质量",
            "algorithm_design": "算法设计能力反映问题分析和解决的思维水平",
            "system_architecture": "系统架构能力体现整体设计和宏观把控能力",
            "data_analysis": "数据分析能力是从数据中提取价值的关键",
            "engineering_practice": "工程实践能力决定实际项目的交付质量",
        }
        return descriptions.get(dimension, "")
    
    @staticmethod
    def anonymize_learner(
        db: Session,
        anonymize_request: AnonymizeRequest,
    ) -> Optional[AnonymizeResponse]:
        """
        数据脱敏：对学习者敏感信息进行掩码处理
        
        Args:
            db: 数据库会话
            anonymize_request: 脱敏请求
            
        Returns:
            脱敏结果或None
        """
        learner = db.query(LearnerProfile).filter(
            LearnerProfile.id == anonymize_request.learner_id
        ).first()
        
        if not learner:
            return None
        
        # 脱敏前数据
        before_data = {
            "real_name": learner.real_name,
            "current_position": learner.current_position,
        }
        
        # 执行脱敏
        anonymized_fields = []
        anonymized_record_id = 0

        # 姓名脱敏
        if (not anonymize_request.fields or "real_name" in anonymize_request.fields) and learner.real_name:
            original_name = learner.real_name
            learner.real_name = AnonymizeUtil.anonymize_name(original_name)
            anonymized_fields.append("real_name")

            # 记录脱敏记录
            record = AnonymizedData(
                data_type="name",
                field_name="real_name",
                user_id=learner.user_id,
                source_table="learner_profiles",
                source_record_id=learner.id,
                original_data_hash=AnonymizeUtil.hash_data(original_name),
                anonymized_data=learner.real_name,
                anonymize_method="partial_mask",
                original_example=original_name[:3] + "***" if len(original_name) > 3 else original_name + "***",
                anonymized_example=learner.real_name,
            )
            db.add(record)
            db.flush()
            anonymized_record_id = record.id
        
        # 位置脱敏
        if (not anonymize_request.fields or "current_position" in anonymize_request.fields) and learner.current_position:
            original_pos = learner.current_position
            learner.current_position = AnonymizeUtil.anonymize_company(original_pos, 4)
            anonymized_fields.append("current_position")
        
        # 标记为已脱敏
        learner.is_data_anonymized = True
        
        # 脱敏后数据
        after_data = {
            "real_name": learner.real_name,
            "current_position": learner.current_position,
        }
        
        db.commit()
        db.refresh(learner)
        
        logger.info(f"数据脱敏: learner_id={learner.id}, fields={anonymized_fields}")
        
        return AnonymizeResponse(
            learner_id=learner.id,
            is_anonymized=True,
            anonymized_fields=anonymized_fields,
            before=before_data,
            after=after_data,
            record_id=anonymized_record_id,
            operation_time=datetime.now(),
        )
    
    @staticmethod
    def check_data_permission(
        db: Session,
        user_id: int,
        learner_id: int,
    ) -> bool:
        """
        检查数据权限
        
        Args:
            db: 数据库会话
            user_id: 当前用户ID
            learner_id: 要访问的学习者ID
            
        Returns:
            是否有权限
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        
        # 管理员权限：查看全部
        if user.role == UserRoleEnum.ADMIN:
            return True
        
        # 企业管理员：查看本企业
        if user.role == UserRoleEnum.ENTERPRISE:
            learner = db.query(LearnerProfile).filter(
                LearnerProfile.id == learner_id
            ).first()
            if learner:
                # 简化处理：企业管理员可查看所有
                return True
            return False
        
        # 普通学习者：查看自己
        learner = db.query(LearnerProfile).filter(
            LearnerProfile.id == learner_id,
            LearnerProfile.user_id == user_id,
        ).first()
        
        return learner is not None
    
    @staticmethod
    def add_answer_record(
        db: Session,
        answer_data: AnswerRecordCreate,
    ) -> AnswerRecord:
        """
        添加答题记录
        
        Args:
            db: 数据库会话
            answer_data: 答题数据
            
        Returns:
            答题记录对象
        """
        record = AnswerRecord(
            user_id=answer_data.user_id,
            learner_id=answer_data.learner_id,
            question_type=answer_data.question_type,
            question_topic=answer_data.question_topic,
            question_difficulty=answer_data.question_difficulty,
            question_content=answer_data.question_content,
            user_answer=answer_data.user_answer,
            correct_answer=answer_data.correct_answer,
            result=answer_data.result,
            score=answer_data.score,
            time_spent_ms=answer_data.time_spent_ms,
        )
        
        db.add(record)
        db.commit()
        db.refresh(record)
        
        logger.info(f"添加答题记录: id={record.id}, learner_id={answer_data.learner_id}")
        
        return record
    
    @staticmethod
    def get_answer_records(
        db: Session,
        learner_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[AnswerRecord], int]:
        """
        获取答题记录列表
        
        Args:
            db: 数据库会话
            learner_id: 学习者ID
            page: 页码
            page_size: 每页数量
            
        Returns:
            Tuple[记录列表, 总数]
        """
        query = db.query(AnswerRecord).filter(
            AnswerRecord.learner_id == learner_id
        )
        
        total = query.count()
        
        records = query.order_by(AnswerRecord.created_at.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        
        return records, total