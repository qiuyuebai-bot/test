"""
企业培训任务表 ORM 模型
存储企业标准化内训与员工转岗培训数据
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Float, JSON
from sqlalchemy.sql import func
from app.database import Base
import enum


class TrainingStatusEnum(enum.Enum):
    """培训状态枚举"""
    PLANNING = "planning"    # 规划中
    ONGOING = "ongoing"      # 进行中
    COMPLETED = "completed"  # 已完成
    CANCELLED = "cancelled"  # 已取消


class TransferStatusEnum(enum.Enum):
    """转岗状态枚举"""
    PENDING = "pending"      # 待开始
    IN_PROGRESS = "in_progress"  # 进行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"        # 未通过


class EnterpriseTraining(Base):
    """企业培训任务表"""
    
    __tablename__ = "enterprise_trainings"
    
    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment="培训ID")
    
    # 基本信息
    company_name = Column(String(100), nullable=False, index=True, comment="企业名称")
    training_name = Column(String(200), nullable=False, comment="培训名称")
    training_type = Column(String(50), default="standard", comment="培训类型(standard/transfer)")
    
    # 培训详情
    description = Column(Text, nullable=True, comment="培训描述")
    industry = Column(String(50), nullable=True, comment="所属行业")
    modules = Column(JSON, default=list, comment="培训模块列表")
    
    # 参与信息
    participant_count = Column(Integer, default=0, comment="参与人数")
    participants = Column(JSON, default=list, comment="参与学员ID列表")
    responsible_person = Column(String(50), nullable=True, comment="负责人")
    
    # 时间信息
    start_date = Column(DateTime, nullable=True, comment="开始日期")
    end_date = Column(DateTime, nullable=True, comment="结束日期")
    estimated_duration = Column(Integer, default=0, comment="预计时长(天)")
    
    # 进度信息
    status = Column(String(20), default="planning", index=True, comment="培训状态")
    progress_percentage = Column(Float, default=0.0, comment="进度百分比")
    completed_modules = Column(Integer, default=0, comment="已完成模块数")
    
    # 转岗信息（仅转岗培训）
    is_transfer_training = Column(Boolean, default=False, comment="是否转岗培训")
    transfer_from_position = Column(String(100), nullable=True, comment="原岗位")
    transfer_to_position = Column(String(100), nullable=True, comment="目标岗位")
    skill_gap_analysis = Column(JSON, default=dict, comment="技能差距分析")
    
    # 效果评估
    pass_rate = Column(Float, default=0.0, comment="通过率")
    average_score = Column(Float, default=0.0, comment="平均成绩")
    satisfaction_rate = Column(Float, default=0.0, comment="满意度")
    
    # 统计信息
    total_resources_used = Column(Integer, default=0, comment="使用资源数")
    total_tasks_completed = Column(Integer, default=0, comment="完成任务数")
    
    # 时间字段
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    def __repr__(self) -> str:
        return f"<EnterpriseTraining(id={self.id}, company={self.company_name}, name={self.training_name})>"