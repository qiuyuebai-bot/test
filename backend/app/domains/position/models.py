"""
岗位与胜任力域 ORM 模型
包含：岗位定义、胜任力项、岗位-胜任力关联
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Text, JSON, ForeignKey, UniqueConstraint, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class PositionCategoryEnum(enum.Enum):
    """岗位类别枚举"""
    TECHNICAL = "technical"
    MANAGEMENT = "management"
    OPERATION = "operation"
    DESIGN = "design"
    OTHER = "other"


class PositionLevelEnum(enum.Enum):
    """岗位层级枚举"""
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    EXPERT = "expert"


class CompetencyCategoryEnum(enum.Enum):
    """胜任力类别枚举"""
    TECHNICAL = "technical"
    SOFT_SKILL = "soft_skill"
    DOMAIN_KNOWLEDGE = "domain"
    ENGINEERING = "engineering"


class Position(Base):
    """岗位定义表"""
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="岗位ID")
    code = Column(String(50), unique=True, nullable=False, index=True, comment="岗位编码")
    name = Column(String(100), nullable=False, index=True, comment="岗位名称")
    category = Column(String(50), nullable=True, index=True, comment="岗位类别")
    industry = Column(String(50), nullable=True, comment="所属行业")
    level = Column(String(20), nullable=True, comment="岗位层级")
    description = Column(Text, nullable=True, comment="岗位描述")
    responsibilities = Column(JSON, default=list, comment="岗位职责列表")
    key_tasks = Column(JSON, default=list, comment="关键任务列表，包含任务名称、产出物和验收标准")
    prerequisites = Column(JSON, default=list, comment="前置要求")
    career_path = Column(JSON, default=list, comment="职业发展路径")
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    competencies = relationship("PositionCompetency", back_populates="position", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Position(id={self.id}, code={self.code}, name={self.name})>"


class Competency(Base):
    """胜任力项表"""
    __tablename__ = "competencies"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="胜任力ID")
    code = Column(String(50), unique=True, nullable=False, index=True, comment="胜任力编码")
    name = Column(String(100), nullable=False, index=True, comment="胜任力名称")
    category = Column(String(50), nullable=True, index=True, comment="胜任力类别")
    description = Column(Text, nullable=True, comment="胜任力描述")
    level_descriptions = Column(JSON, default=dict, comment="各等级描述")
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    positions = relationship("PositionCompetency", back_populates="competency", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Competency(id={self.id}, code={self.code}, name={self.name})>"


class PositionCompetency(Base):
    """岗位-胜任力关联表"""
    __tablename__ = "position_competencies"
    __table_args__ = (
        UniqueConstraint("position_id", "competency_id", name="uq_position_competency"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True, comment="关联ID")
    position_id = Column(Integer, ForeignKey("positions.id", ondelete="CASCADE"), nullable=False, index=True, comment="岗位ID")
    competency_id = Column(Integer, ForeignKey("competencies.id", ondelete="CASCADE"), nullable=False, index=True, comment="胜任力ID")
    required_level = Column(Integer, nullable=False, comment="要求等级(1-5)")
    weight = Column(Float, default=1.0, comment="权重")
    is_mandatory = Column(Boolean, default=True, comment="是否必修")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    position = relationship("Position", back_populates="competencies")
    competency = relationship("Competency", back_populates="positions")

    def __repr__(self) -> str:
        return f"<PositionCompetency(position_id={self.position_id}, competency_id={self.competency_id}, level={self.required_level})>"
