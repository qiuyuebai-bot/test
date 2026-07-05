"""
智能体执行任务记录表 ORM 模型
存储Agent任务执行记录与状态
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Float, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class AgentTypeEnum(enum.Enum):
    """智能体类型枚举"""
    DIAGNOSIS = "diagnosis"    # 学情诊断Agent
    GENERATION = "generation"  # 领域知识生成Agent
    JUDGE = "judge"            # 内容审核纠偏裁判Agent


class TaskStatusEnum(enum.Enum):
    """任务状态枚举"""
    PENDING = "pending"        # 待执行
    RUNNING = "running"        # 运行中
    COMPLETED = "completed"    # 已完成
    FAILED = "failed"          # 失败
    CANCELLED = "cancelled"    # 已取消


class AgentTask(Base):
    """智能体执行任务记录表"""
    
    __tablename__ = "agent_tasks"
    
    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment="任务ID")
    
    # 关联学习者
    learner_id = Column(Integer, ForeignKey("learner_profiles.id"), nullable=True, index=True, comment="关联学习者ID")
    
    # 任务基本信息
    task_name = Column(String(200), nullable=False, comment="任务名称")
    task_type = Column(String(50), nullable=False, index=True, comment="任务类型")
    agent_type = Column(String(20), nullable=False, comment="执行Agent类型")
    
    # 执行流程
    flow_stage = Column(String(50), default="init", comment="流程阶段(init/diagnosis/knowledge_retrieval/generation/judge_first/debate/final_revision/complete)")
    flow_description = Column(String(500), nullable=True, comment="流程描述")
    
    # 输入输出
    input_data = Column(JSON, default=dict, comment="输入数据")
    output_data = Column(JSON, default=dict, comment="输出数据")
    execution_logs = Column(JSON, default=list, comment="执行阶段日志列表，供前端可视化")
    
    # 执行状态
    status = Column(String(20), default="pending", index=True, comment="任务状态")
    progress = Column(Float, default=0.0, comment="执行进度(0-100)")
    
    # 执行信息
    started_at = Column(DateTime, nullable=True, comment="开始时间")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")
    duration_ms = Column(Integer, default=0, comment="执行耗时(毫秒)")
    
    # Token消耗
    prompt_tokens = Column(Integer, default=0, comment="Prompt Token数")
    completion_tokens = Column(Integer, default=0, comment="Completion Token数")
    total_tokens = Column(Integer, default=0, comment="总Token数")
    
    # 结果信息
    result_summary = Column(Text, nullable=True, comment="结果摘要")
    error_message = Column(Text, nullable=True, comment="错误信息")
    
    # 校验标记
    needs_validation = Column(Boolean, default=False, comment="是否需要校验")
    validated = Column(Boolean, default=False, comment="是否已校验")
    validation_passed = Column(Boolean, default=False, comment="校验是否通过")
    
    # 关联辩论记录
    debate_records = relationship("DebateRecord", back_populates="task")
    
    # 时间字段
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    def __repr__(self) -> str:
        return f"<AgentTask(id={self.id}, name={self.task_name}, status={self.status})>"