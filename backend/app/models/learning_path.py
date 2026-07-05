"""
学习路径规划数据表 ORM 模型
存储个性化学习路径规划数据
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class PathNodeTypeEnum(enum.Enum):
    """路径节点类型枚举"""
    BASIC = "basic"        # 基础节点
    INTERMEDIATE = "intermediate"  # 进阶节点
    ADVANCED = "advanced"  # 高阶节点


class NodeStatusEnum(enum.Enum):
    """节点状态枚举"""
    LOCKED = "locked"      # 未解锁
    AVAILABLE = "available"  # 可学习
    IN_PROGRESS = "in_progress"  # 进行中
    COMPLETED = "completed"  # 已完成
    SKIPPED = "skipped"    # 已跳过


class LearningPath(Base):
    """学习路径规划数据表"""
    
    __tablename__ = "learning_paths"
    
    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment="路径ID")
    
    # 关联用户
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="关联用户ID")
    
    # 关联学习者画像
    learner_id = Column(Integer, ForeignKey("learner_profiles.id"), nullable=False, index=True, comment="关联学习者ID")
    
    # 路径基本信息
    path_name = Column(String(200), nullable=False, comment="路径名称")
    target_industry = Column(String(50), nullable=True, comment="目标行业")
    target_position = Column(String(100), nullable=True, comment="目标岗位")
    total_nodes = Column(Integer, default=0, comment="总节点数")
    total_duration = Column(Integer, default=0, comment="预计总时长(天)")
    
    # 路径内容（JSON结构）
    path_nodes = Column(JSON, default=list, comment="路径节点列表(JSON)")
    current_node_index = Column(Integer, default=0, comment="当前节点序号")
    
    # 进度信息
    completed_nodes = Column(Integer, default=0, comment="已完成节点数")
    progress_percentage = Column(Float, default=0.0, comment="完成百分比")
    
    # 评估信息
    estimated_completion_date = Column(DateTime, nullable=True, comment="预计完成日期")
    actual_started_date = Column(DateTime, nullable=True, comment="实际开始日期")
    actual_completion_date = Column(DateTime, nullable=True, comment="实际完成日期")
    
    # 路径生成信息
    generated_by_agent = Column(Boolean, default=True, comment="是否由Agent生成")
    generation_method = Column(String(50), nullable=True, comment="生成方法")
    
    # 自适应调整记录（JSON）
    adjustment_history = Column(JSON, default=list, comment="路径调整历史")
    
    # 状态
    is_active = Column(Boolean, default=True, comment="是否激活")
    is_completed = Column(Boolean, default=False, comment="是否已完成")
    
    # 效果评估
    knowledge_coverage_before = Column(Float, default=0.0, comment="学习前覆盖率")
    knowledge_coverage_after = Column(Float, default=0.0, comment="学习后覆盖率")
    skill_improvement_score = Column(Float, default=0.0, comment="技能提升分数")
    
    # 时间字段
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    # 关联关系
    user = relationship("User", back_populates="learning_paths")
    learner = relationship("LearnerProfile", back_populates="learning_paths")
    
    def __repr__(self) -> str:
        return f"<LearningPath(id={self.id}, name={self.path_name}, progress={self.progress_percentage}%)>"