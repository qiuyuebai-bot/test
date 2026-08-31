"""
认证发证域 ORM 模型
包含：认证定义、发证规则、认证记录
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class CertificationLevelEnum(enum.Enum):
    """认证级别枚举"""
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"


class RuleTypeEnum(enum.Enum):
    """发证规则类型枚举"""
    OVERALL_SCORE = "overall_score"              # 综合得分达标
    COMPETENCY_LEVEL = "competency_level"        # 特定胜任力等级达标
    ALL_MANDATORY_MET = "all_mandatory_met"      # 所有必修项达标
    TRAINING_COMPLETION = "training_completion"  # 培训项目完成度达标
    MANDATORY_TASKS_PASSED = "mandatory_tasks_passed"  # 必修任务通过数
    TASK_SCORE = "task_score"                    # 指定任务得分达标


class CertificationStatusEnum(enum.Enum):
    """认证记录状态枚举"""
    PENDING = "pending"      # 待审核
    APPROVED = "approved"    # 已通过
    REJECTED = "rejected"    # 已拒绝
    EXPIRED = "expired"      # 已过期
    REVOKED = "revoked"      # 已撤销


class Certification(Base):
    """认证定义表"""

    __tablename__ = "certifications"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="认证ID")
    position_id = Column(Integer, ForeignKey("positions.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联岗位ID")
    name = Column(String(200), nullable=False, comment="认证名称")
    code = Column(String(50), unique=True, nullable=False, index=True, comment="认证编码")
    level = Column(String(20), nullable=True, comment="认证级别 junior/mid/senior")
    description = Column(Text, nullable=True, comment="认证描述")
    validity_period_months = Column(Integer, default=0, comment="有效期(月)，0表示永久")
    issuer = Column(String(100), nullable=True, comment="发证机构")
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关联关系
    position = relationship("Position", backref="certifications")
    rules = relationship("CertificationRule", back_populates="certification", cascade="all, delete-orphan")
    records = relationship("CertificationRecord", back_populates="certification", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Certification(id={self.id}, name={self.name})>"


class CertificationRule(Base):
    """发证规则表"""

    __tablename__ = "certification_rules"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="规则ID")
    certification_id = Column(Integer, ForeignKey("certifications.id", ondelete="CASCADE"), nullable=False, index=True, comment="认证ID")
    rule_type = Column(String(30), nullable=False, comment="规则类型 overall_score/competency_level/all_mandatory_met")
    rule_config = Column(JSON, default=dict, comment="规则配置")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    # 关联关系
    certification = relationship("Certification", back_populates="rules")

    def __repr__(self) -> str:
        return f"<CertificationRule(id={self.id}, type={self.rule_type})>"


class CertificationRecord(Base):
    """认证记录表"""

    __tablename__ = "certification_records"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="记录ID")
    certification_id = Column(Integer, ForeignKey("certifications.id", ondelete="CASCADE"), nullable=False, index=True, comment="认证ID")
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户ID")
    learner_id = Column(Integer, ForeignKey("learner_profiles.id", ondelete="SET NULL"), nullable=True, index=True, comment="学习者画像ID")
    assessment_record_id = Column(Integer, ForeignKey("assessment_records.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联评估记录ID")
    status = Column(String(20), default=CertificationStatusEnum.PENDING.value, comment="认证状态")
    certificate_number = Column(String(100), unique=True, nullable=True, index=True, comment="证书编号")
    rule_evaluation = Column(JSON, nullable=True, comment="规则评估结果")
    issued_at = Column(DateTime, nullable=True, comment="发证时间")
    expires_at = Column(DateTime, nullable=True, comment="过期时间")
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="审核人ID")
    review_comment = Column(Text, nullable=True, comment="审核意见")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关联关系
    certification = relationship("Certification", back_populates="records")

    def __repr__(self) -> str:
        return f"<CertificationRecord(id={self.id}, status={self.status})>"
