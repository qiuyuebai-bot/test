"""
培训项目域 ORM 模型
包含：培训项目、培训报名、培训计划
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Text, JSON, ForeignKey, Date, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class ProjectTypeEnum(enum.Enum):
    """培训项目类型枚举"""
    ONBOARD = "onboard"        # 入职培训
    TRANSFER = "transfer"      # 转岗培训
    UPSKILL = "upskill"        # 能力提升
    COMPLIANCE = "compliance"  # 合规培训


class ProjectStatusEnum(enum.Enum):
    """培训项目状态枚举"""
    DRAFT = "draft"            # 草稿
    ACTIVE = "active"          # 进行中
    COMPLETED = "completed"    # 已完成
    ARCHIVED = "archived"      # 已归档


class EnrollmentStatusEnum(enum.Enum):
    """报名状态枚举"""
    ENROLLED = "enrolled"        # 已报名
    IN_PROGRESS = "in_progress"  # 学习中
    COMPLETED = "completed"      # 已完成
    WITHDRAWN = "withdrawn"      # 已退出
    FAILED = "failed"            # 未通过


class PlanStatusEnum(enum.Enum):
    """培训计划状态枚举"""
    GENERATING = "generating"  # 生成中
    ACTIVE = "active"          # 进行中
    COMPLETED = "completed"    # 已完成
    FAILED = "failed"          # 生成失败


class TrainingProject(Base):
    """培训项目表"""

    __tablename__ = "training_projects"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="项目ID")
    name = Column(String(200), nullable=False, comment="项目名称")
    description = Column(Text, nullable=True, comment="项目描述")
    position_id = Column(Integer, ForeignKey("positions.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联岗位ID")
    certification_id = Column(Integer, ForeignKey("certifications.id", ondelete="SET NULL"), nullable=True, index=True, comment="关联认证ID")
    project_type = Column(String(20), nullable=True, comment="项目类型 onboard/transfer/upskill/compliance")
    enterprise_name = Column(String(100), nullable=True, comment="所属企业")
    status = Column(String(20), default=ProjectStatusEnum.DRAFT.value, comment="项目状态")
    start_date = Column(Date, nullable=True, comment="开始日期")
    end_date = Column(Date, nullable=True, comment="结束日期")
    config = Column(JSON, default=dict, comment="项目级配置")
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="创建人ID")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关联关系
    position = relationship("Position", backref="training_projects")
    certification = relationship("Certification", backref="training_projects")
    enrollments = relationship("TrainingEnrollment", back_populates="project", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<TrainingProject(id={self.id}, name={self.name})>"


class TrainingEnrollment(Base):
    """培训报名表"""

    __tablename__ = "training_enrollments"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_user"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True, comment="报名ID")
    project_id = Column(Integer, ForeignKey("training_projects.id", ondelete="CASCADE"), nullable=False, index=True, comment="项目ID")
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户ID")
    learner_id = Column(Integer, ForeignKey("learner_profiles.id", ondelete="SET NULL"), nullable=True, index=True, comment="学习者画像ID")
    status = Column(String(20), default=EnrollmentStatusEnum.ENROLLED.value, comment="报名状态")
    enrolled_at = Column(DateTime, server_default=func.now(), comment="报名时间")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")
    final_score = Column(Float, nullable=True, comment="最终得分")
    certification_record_id = Column(Integer, ForeignKey("certification_records.id", ondelete="SET NULL"), nullable=True, comment="认证记录ID")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关联关系
    project = relationship("TrainingProject", back_populates="enrollments")
    plans = relationship("TrainingPlan", back_populates="enrollment", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<TrainingEnrollment(id={self.id}, project_id={self.project_id}, user_id={self.user_id})>"


class TrainingPlan(Base):
    """培训计划表（学习路径）"""

    __tablename__ = "training_plans"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="计划ID")
    project_id = Column(Integer, ForeignKey("training_projects.id", ondelete="CASCADE"), nullable=False, index=True, comment="项目ID")
    enrollment_id = Column(Integer, ForeignKey("training_enrollments.id", ondelete="CASCADE"), nullable=False, index=True, comment="报名ID")
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户ID")
    learner_id = Column(Integer, ForeignKey("learner_profiles.id", ondelete="SET NULL"), nullable=True, comment="学习者画像ID")
    assessment_record_id = Column(Integer, ForeignKey("assessment_records.id", ondelete="SET NULL"), nullable=True, comment="关联评估记录ID")
    plan_content = Column(JSON, default=list, comment="学习计划内容 [{stage, title, competency_ids, resources, estimated_hours, target_level, deadline}]")
    total_stages = Column(Integer, default=0, comment="总阶段数")
    completed_stages = Column(Integer, default=0, comment="已完成阶段数")
    progress = Column(Float, default=0.0, comment="进度百分比")
    status = Column(String(20), default=PlanStatusEnum.GENERATING.value, comment="计划状态")
    generated_by_ai = Column(Boolean, default=True, comment="是否AI生成")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关联关系
    enrollment = relationship("TrainingEnrollment", back_populates="plans")

    def __repr__(self) -> str:
        return f"<TrainingPlan(id={self.id}, enrollment_id={self.enrollment_id}, progress={self.progress})>"


class TrainingTaskPackage(Base):
    """培训项目中的可交付任务包。"""

    __tablename__ = "training_task_packages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("training_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    sequence = Column(Integer, default=1)
    task_type = Column(String(30), default="practice")
    key_task_code = Column(String(80), nullable=True)
    learning_objectives = Column(JSON, default=list)
    resources = Column(JSON, default=list)
    submission_required = Column(Boolean, default=True)
    passing_score = Column(Float, default=60.0)
    is_mandatory = Column(Boolean, default=True)
    status = Column(String(20), default="active")
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    project = relationship("TrainingProject", backref="task_packages")
    rubrics = relationship("TrainingTaskRubric", back_populates="task_package", cascade="all, delete-orphan", order_by="TrainingTaskRubric.sequence")
    submissions = relationship("TrainingSubmission", back_populates="task_package", cascade="all, delete-orphan")


class TrainingTaskRubric(Base):
    """任务包教师评分标准。"""

    __tablename__ = "training_task_rubrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_package_id = Column(Integer, ForeignKey("training_task_packages.id", ondelete="CASCADE"), nullable=False, index=True)
    criterion = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    max_score = Column(Float, default=100.0)
    weight = Column(Float, default=1.0)
    sequence = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.now())

    task_package = relationship("TrainingTaskPackage", back_populates="rubrics")


class TrainingSubmission(Base):
    """学员实操任务提交及教师评审结果。"""

    __tablename__ = "training_submissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_package_id = Column(Integer, ForeignKey("training_task_packages.id", ondelete="CASCADE"), nullable=False, index=True)
    enrollment_id = Column(Integer, ForeignKey("training_enrollments.id", ondelete="CASCADE"), nullable=False, index=True)
    learner_id = Column(Integer, ForeignKey("learner_profiles.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    attempt_number = Column(Integer, default=1)
    content = Column(Text, nullable=True)
    attachments = Column(JSON, default=list)
    demo_url = Column(String(500), nullable=True)
    status = Column(String(20), default="submitted")
    overall_score = Column(Float, nullable=True)
    teacher_comment = Column(Text, nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    submitted_at = Column(DateTime, server_default=func.now())
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    task_package = relationship("TrainingTaskPackage", back_populates="submissions")
    enrollment = relationship("TrainingEnrollment", backref="submissions")
    scores = relationship("TrainingSubmissionScore", back_populates="submission", cascade="all, delete-orphan")


class TrainingSubmissionScore(Base):
    """提交记录按评分标准拆分的得分。"""

    __tablename__ = "training_submission_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    submission_id = Column(Integer, ForeignKey("training_submissions.id", ondelete="CASCADE"), nullable=False, index=True)
    rubric_id = Column(Integer, ForeignKey("training_task_rubrics.id", ondelete="CASCADE"), nullable=False, index=True)
    score = Column(Float, nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    submission = relationship("TrainingSubmission", back_populates="scores")
    rubric = relationship("TrainingTaskRubric")
