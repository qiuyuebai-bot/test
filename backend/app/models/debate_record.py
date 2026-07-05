"""
辩论校验冲突记录表 ORM 模型
存储Agent辩论交叉验证记录与幻觉检测结果
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Float, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class ConflictSeverityEnum(enum.Enum):
    """冲突严重程度枚举"""
    LOW = "low"        # 低严重度（轻微偏差）
    MEDIUM = "medium"  # 中等严重度（需要修正）
    HIGH = "high"      # 高严重度（可能幻觉）
    CRITICAL = "critical"  # 严重幻觉（必须纠偏）


class ResolutionStatusEnum(enum.Enum):
    """解决状态枚举"""
    DETECTED = "detected"      # 已检测
    ANALYZING = "analyzing"    # 分析中
    RESOLVED = "resolved"      # 已解决
    ACCEPTED = "accepted"      # 已接受（原内容）
    CORRECTED = "corrected"    # 已修正


class DebateRecord(Base):
    """辩论校验冲突记录表"""
    
    __tablename__ = "debate_records"
    
    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment="记录ID")
    
    # 关联任务
    task_id = Column(Integer, ForeignKey("agent_tasks.id"), nullable=False, index=True, comment="关联任务ID")
    
    # 辩论基本信息
    debate_round = Column(Integer, default=1, comment="辩论轮次")
    debate_type = Column(String(50), default="cross_validation", comment="辩论类型")
    
    # 参与Agent
    agent_diagnosis_view = Column(Text, nullable=True, comment="诊断Agent观点")
    agent_generation_view = Column(Text, nullable=True, comment="生成Agent观点")
    agent_judge_view = Column(Text, nullable=True, comment="裁判Agent裁决")
    
    # 对比内容
    original_content = Column(Text, nullable=False, comment="原始生成内容")
    reference_content = Column(Text, nullable=True, comment="知识库参考内容")
    comparison_summary = Column(Text, nullable=True, comment="对比分析摘要")
    
    # 冲突检测
    has_conflict = Column(Boolean, default=False, comment="是否存在冲突")
    conflict_type = Column(String(50), nullable=True, comment="冲突类型")
    conflict_severity = Column(String(20), default="low", comment="冲突严重程度")
    conflict_description = Column(Text, nullable=True, comment="冲突描述")
    
    # 幻觉检测
    is_hallucination = Column(Boolean, default=False, comment="是否检测为幻觉")
    hallucination_type = Column(String(50), nullable=True, comment="幻觉类型")
    hallucination_keywords = Column(JSON, default=list, comment="幻觉关键词")
    hallucination_score = Column(Float, default=0.0, comment="幻觉评分(0-100)")
    
    # 修正记录
    resolution_status = Column(String(20), default="detected", comment="解决状态")
    corrected_content = Column(Text, nullable=True, comment="修正后内容")
    correction_reason = Column(Text, nullable=True, comment="修正原因")
    correction_source = Column(String(200), nullable=True, comment="修正来源(知识库切片ID)")
    
    # 裁判决策
    judge_decision = Column(String(50), nullable=True, comment="裁判决策")
    judge_confidence = Column(Float, default=0.0, comment="裁判置信度")
    judge_notes = Column(Text, nullable=True, comment="裁判备注")
    
    # 时间字段
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    resolved_at = Column(DateTime, nullable=True, comment="解决时间")
    
    # 关联关系
    task = relationship("AgentTask", back_populates="debate_records")
    
    def __repr__(self) -> str:
        return f"<DebateRecord(id={self.id}, task_id={self.task_id}, conflict={self.has_conflict})>"