"""
资源版本历史表 ORM 模型
存储资源每次更新迭代的版本快照，支持版本回退与对比
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON, Boolean, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class ResourceVersion(Base):
    """资源版本历史表"""
    
    __tablename__ = "resource_versions"
    
    # ==================== 主键与关联 ====================
    id = Column(Integer, primary_key=True, autoincrement=True, comment="版本ID")
    resource_id = Column(Integer, ForeignKey("learning_resources.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联资源ID")
    
    # ==================== 版本信息 ====================
    version_number = Column(Integer, default=1, comment="版本序号")
    version_tag = Column(String(20), nullable=True, comment="版本标签(如v1.0, v2.1)")
    change_type = Column(String(20), nullable=True, comment="变更类型(create/update/correct/debate_fix)")
    change_summary = Column(Text, nullable=True, comment="变更摘要")
    change_detail = Column(JSON, default=dict, comment="变更详情")
    # 示例: {"added_sections": 2, "modified_sections": [1,3], "fixed_hallucinations": 3}
    
    # ==================== 内容快照 ====================
    content_snapshot = Column(Text, nullable=True, comment="内容快照(全文)")
    content_hash = Column(String(64), nullable=True, comment="内容哈希(SHA256)")
    content_json_snapshot = Column(JSON, default=dict, comment="结构化内容快照")
    word_count = Column(Integer, default=0, comment="字数统计")
    
    # ==================== 生成信息 ====================
    generated_by = Column(String(50), nullable=True, comment="生成方式(agent/manual/corrected)")
    generation_task_id = Column(Integer, nullable=True, comment="关联任务ID")
    debate_record_id = Column(Integer, nullable=True, comment="关联辩论记录ID")
    
    # ==================== 校验信息 ====================
    validation_score = Column(Float, default=0.0, comment="校验评分")
    hallucination_count = Column(Integer, default=0, comment="幻觉检出数")
    corrected_count = Column(Integer, default=0, comment="修正数量")
    
    # ==================== 状态 ====================
    is_current = Column(Boolean, default=False, comment="是否当前版本")
    is_published = Column(Boolean, default=False, comment="是否发布")
    
    # ==================== 操作人 ====================
    created_by = Column(String(100), nullable=True, comment="操作人")
    created_by_agent = Column(String(20), nullable=True, comment="操作Agent类型")
    
    # ==================== 时间字段 ====================
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    
    # ==================== 关联关系 ====================
    resource = relationship("LearningResource", back_populates="versions")
    
    def __repr__(self) -> str:
        return f"<ResourceVersion(id={self.id}, resource={self.resource_id}, v{self.version_number})>"