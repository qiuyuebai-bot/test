"""
智能体领域 ORM 模型
合并 agent_task + debate_record
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Float, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class AgentTypeEnum(enum.Enum):
    """智能体类型枚举"""
    DIAGNOSIS = "diagnosis"
    GENERATION = "generation"
    JUDGE = "judge"


class TaskStatusEnum(enum.Enum):
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ConflictSeverityEnum(enum.Enum):
    """冲突严重程度枚举"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ResolutionStatusEnum(enum.Enum):
    """解决状态枚举"""
    DETECTED = "detected"
    ANALYZING = "analyzing"
    RESOLVED = "resolved"
    ACCEPTED = "accepted"
    CORRECTED = "corrected"


class AgentTask(Base):
    """智能体执行任务记录表"""

    __tablename__ = "agent_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="任务ID")
    learner_id = Column(Integer, ForeignKey("learner_profiles.id"), nullable=True, index=True, comment="关联学习者ID")

    task_name = Column(String(200), nullable=False, comment="任务名称")
    task_type = Column(String(50), nullable=False, index=True, comment="任务类型")
    agent_type = Column(String(20), nullable=False, comment="执行Agent类型")

    flow_stage = Column(String(50), default="init", comment="流程阶段(init/diagnosis/knowledge_retrieval/generation/judge_first/debate/final_revision/complete)")
    flow_description = Column(String(500), nullable=True, comment="流程描述")

    input_data = Column(JSON, default=dict, comment="输入数据")
    output_data = Column(JSON, default=dict, comment="输出数据")
    execution_logs = Column(JSON, default=list, comment="执行阶段日志列表，供前端可视化")

    status = Column(String(20), default="pending", index=True, comment="任务状态")
    progress = Column(Float, default=0.0, comment="执行进度(0-100)")

    started_at = Column(DateTime, nullable=True, comment="开始时间")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")
    duration_ms = Column(Integer, default=0, comment="执行耗时(毫秒)")

    prompt_tokens = Column(Integer, default=0, comment="Prompt Token数")
    completion_tokens = Column(Integer, default=0, comment="Completion Token数")
    total_tokens = Column(Integer, default=0, comment="总Token数")

    result_summary = Column(Text, nullable=True, comment="结果摘要")
    error_message = Column(Text, nullable=True, comment="错误信息")

    needs_validation = Column(Boolean, default=False, comment="是否需要校验")
    validated = Column(Boolean, default=False, comment="是否已校验")
    validation_passed = Column(Boolean, default=False, comment="校验是否通过")

    debate_records = relationship("DebateRecord", back_populates="task")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def __repr__(self) -> str:
        return f"<AgentTask(id={self.id}, name={self.task_name}, status={self.status})>"


class DebateRecord(Base):
    """辩论校验冲突记录表"""

    __tablename__ = "debate_records"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="记录ID")
    task_id = Column(Integer, ForeignKey("agent_tasks.id"), nullable=False, index=True, comment="关联任务ID")

    debate_round = Column(Integer, default=1, comment="辩论轮次")
    debate_type = Column(String(50), default="cross_validation", comment="辩论类型")

    agent_diagnosis_view = Column(Text, nullable=True, comment="诊断Agent观点")
    agent_generation_view = Column(Text, nullable=True, comment="生成Agent观点")
    agent_judge_view = Column(Text, nullable=True, comment="裁判Agent裁决")

    original_content = Column(Text, nullable=False, comment="原始生成内容")
    reference_content = Column(Text, nullable=True, comment="知识库参考内容")
    comparison_summary = Column(Text, nullable=True, comment="对比分析摘要")

    has_conflict = Column(Boolean, default=False, comment="是否存在冲突")
    conflict_type = Column(String(50), nullable=True, comment="冲突类型")
    conflict_severity = Column(String(20), default="low", comment="冲突严重程度")
    conflict_description = Column(Text, nullable=True, comment="冲突描述")

    is_hallucination = Column(Boolean, default=False, comment="是否检测为幻觉")
    hallucination_type = Column(String(50), nullable=True, comment="幻觉类型")
    hallucination_keywords = Column(JSON, default=list, comment="幻觉关键词")
    hallucination_score = Column(Float, default=0.0, comment="幻觉评分(0-100)")

    resolution_status = Column(String(20), default="detected", comment="解决状态")
    corrected_content = Column(Text, nullable=True, comment="修正后内容")
    correction_reason = Column(Text, nullable=True, comment="修正原因")
    correction_source = Column(String(200), nullable=True, comment="修正来源(知识库切片ID)")

    judge_decision = Column(String(50), nullable=True, comment="裁判决策")
    judge_confidence = Column(Float, default=0.0, comment="裁判置信度")
    judge_notes = Column(Text, nullable=True, comment="裁判备注")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    resolved_at = Column(DateTime, nullable=True, comment="解决时间")

    task = relationship("AgentTask", back_populates="debate_records")

    def __repr__(self) -> str:
        return f"<DebateRecord(id={self.id}, task_id={self.task_id}, conflict={self.has_conflict})>"
