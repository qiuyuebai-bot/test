"""
知识库切片向量表 ORM 模型
存储知识库切片内容与向量索引信息
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Float, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class KnowledgeSlice(Base):
    """知识库切片向量表"""
    
    __tablename__ = "knowledge_slices"
    
    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment="切片ID")
    
    # 关联文档
    doc_id = Column(Integer, ForeignKey("knowledge_docs.id"), nullable=False, index=True, comment="关联文档ID")
    
    # 切片基本信息
    slice_index = Column(Integer, nullable=False, comment="切片序号(文档内)")
    slice_type = Column(String(20), default="paragraph", comment="切片类型(paragraph/section/table)")
    
    # 内容信息
    content = Column(Text, nullable=False, comment="切片内容")
    content_hash = Column(String(64), nullable=True, comment="内容哈希值(MD5)")
    word_count = Column(Integer, default=0, comment="字数统计")
    
    # 上下文信息
    title = Column(String(200), nullable=True, comment="切片标题/章节标题")
    parent_section = Column(String(200), nullable=True, comment="父级章节")
    context_before = Column(Text, nullable=True, comment="前文上下文")
    context_after = Column(Text, nullable=True, comment="后文上下文")
    
    # 向量索引信息
    vector_id = Column(String(100), nullable=True, unique=True, comment="Chroma向量ID")
    embedding_model = Column(String(50), nullable=True, comment="Embedding模型名称")
    is_indexed = Column(Boolean, default=False, comment="是否已索引")
    
    # 元数据
    slice_metadata = Column("slice_metadata", JSON, default=dict, comment="切片元数据")
    keywords = Column(JSON, default=list, comment="关键词列表")
    
    # 质量评分
    quality_score = Column(Float, default=0.0, comment="切片质量评分")
    relevance_score = Column(Float, default=0.0, comment="相关性评分")
    
    # 使用统计
    reference_count = Column(Integer, default=0, comment="引用次数")
    last_referenced_at = Column(DateTime, nullable=True, comment="最后引用时间")
    
    # 时间字段
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    # 关联关系
    doc = relationship("KnowledgeDoc", back_populates="slices")
    
    def __repr__(self) -> str:
        return f"<KnowledgeSlice(id={self.id}, doc_id={self.doc_id}, index={self.slice_index})>"