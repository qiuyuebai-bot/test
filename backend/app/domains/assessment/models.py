"""
评估域 ORM 模型
包含：评估模板、评估记录、胜任力评分明细
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Text, JSON, ForeignKey, UniqueConstraint, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class AssessmentStatusEnum(enum.Enum):
    """评估记录状态枚举"""
    DRAFT = "draft"              # 草稿（未开始）
    IN_PROGRESS = "in_progress"  # 进行中
    COMPLETED = "completed"      # 已完成
    EXPIRED = "expired"          # 已过期


class AssessmentMethodEnum(enum.Enum):
    """评估方式枚举"""
    QUIZ = "quiz"                # 测验
    SELF_REPORT = "self_report"  # 自评
    INTERVIEW = "interview"      # 面试
    PROJECT = "project"          # 项目


class AssessmentTemplate(Base):
    """评估模板表"""

    __tablename__ = "assessment_templates"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="模板ID")
    position_id = Column(Integer, ForeignKey("positions.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联岗位ID")
    name = Column(String(200), nullable=False, comment="模板名称")
    description = Column(Text, nullable=True, comment="模板描述")
    competency_configs = Column(JSON, default=list, comment="胜任力配置列表 [{competency_id, question_count, difficulty, assessment_method}]")
    pass_threshold = Column(Float, default=60.0, comment="通过分数线")
    duration_minutes = Column(Integer, nullable=True, comment="评估时长(分钟)")
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关联关系
    position = relationship("Position", backref="assessment_templates")
    records = relationship("AssessmentRecord", back_populates="template", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<AssessmentTemplate(id={self.id}, name={self.name})>"


class AssessmentRecord(Base):
    """评估记录表"""

    __tablename__ = "assessment_records"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="记录ID")
    template_id = Column(Integer, ForeignKey("assessment_templates.id", ondelete="CASCADE"), nullable=False, index=True, comment="模板ID")
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户ID")
    learner_id = Column(Integer, ForeignKey("learner_profiles.id", ondelete="SET NULL"), nullable=True, index=True, comment="学习者画像ID")
    position_id = Column(Integer, ForeignKey("positions.id", ondelete="CASCADE"), nullable=False, index=True, comment="岗位ID")
    status = Column(String(20), default=AssessmentStatusEnum.DRAFT.value, comment="评估状态")
    overall_score = Column(Float, nullable=True, comment="综合得分")
    overall_level = Column(Integer, nullable=True, comment="综合能力等级(1-5)")
    gap_summary = Column(JSON, default=list, comment="差距摘要 [{competency_id, competency_name, current_level, required_level, gap}]")
    ai_diagnosis = Column(Text, nullable=True, comment="AI生成的诊断报告")
    started_at = Column(DateTime, nullable=True, comment="开始时间")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关联关系
    template = relationship("AssessmentTemplate", back_populates="records")
    position = relationship("Position", backref="assessment_records")
    competency_scores = relationship("CompetencyScore", back_populates="record", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<AssessmentRecord(id={self.id}, status={self.status})>"


class CompetencyScore(Base):
    """胜任力评分明细表"""

    __tablename__ = "competency_scores"
    __table_args__ = (
        UniqueConstraint("assessment_record_id", "competency_id", name="uq_record_competency"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True, comment="评分ID")
    assessment_record_id = Column(Integer, ForeignKey("assessment_records.id", ondelete="CASCADE"), nullable=False, index=True, comment="评估记录ID")
    competency_id = Column(Integer, ForeignKey("competencies.id", ondelete="CASCADE"), nullable=False, index=True, comment="胜任力ID")
    current_level = Column(Integer, nullable=True, comment="当前等级(1-5)")
    current_score = Column(Float, nullable=True, comment="当前得分(0-100)")
    required_level = Column(Integer, nullable=False, comment="要求等级(1-5) 快照")
    gap = Column(Integer, nullable=True, comment="差距 = required_level - current_level")
    assessment_method = Column(String(20), nullable=True, comment="评估方式")
    evidence = Column(JSON, default=list, comment="评估依据(答题记录ID列表等)")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    # 关联关系
    record = relationship("AssessmentRecord", back_populates="competency_scores")
    competency = relationship("Competency")

    def __repr__(self) -> str:
        return f"<CompetencyScore(record_id={self.assessment_record_id}, competency_id={self.competency_id}, gap={self.gap})>"
