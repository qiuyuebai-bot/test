"""
知识库领域 ORM 模型
合并 knowledge_doc + knowledge_slice
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Text, Float, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class IndustryEnum(enum.Enum):
    """行业领域枚举"""
    MANUFACTURING = "智能制造"
    INDUSTRIAL_IOT = "工业互联网"
    SOFTWARE_DEV = "软件开发"
    AI_TRAINING = "人工智能训练"
    DATA_ANALYSIS = "数据分析"
    GENERAL = "通用"


class DocStatusEnum(enum.Enum):
    """文档状态枚举"""
    UPLOADING = "uploading"    # 上传中
    PROCESSING = "processing"  # 处理中
    READY = "ready"            # 已就绪
    ERROR = "error"            # 处理失败


class KnowledgeDoc(Base):
    """行业知识库文档表"""

    __tablename__ = "knowledge_docs"

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment="文档ID")

    # 基本信息
    title = Column(String(200), nullable=False, comment="文档标题")
    industry = Column(String(50), nullable=False, index=True, comment="所属行业领域")
    category = Column(String(100), nullable=True, comment="分类标签")

    # 文件信息
    file_name = Column(String(255), nullable=False, comment="原始文件名")
    file_path = Column(String(500), nullable=False, comment="文件存储路径")
    file_size = Column(Integer, nullable=True, comment="文件大小(字节)")
    file_type = Column(String(20), nullable=True, comment="文件类型(pdf/docx/md)")

    # 内容信息
    content_preview = Column(Text, nullable=True, comment="内容预览(前500字)")
    total_pages = Column(Integer, default=0, comment="总页数")
    word_count = Column(Integer, default=0, comment="字数统计")

    # 切片信息
    slice_count = Column(Integer, default=0, comment="切片数量")
    indexed_slice_count = Column(Integer, default=0, comment="已索引切片数量")

    # 状态
    status = Column(String(20), default="uploading", comment="文档状态")
    process_progress = Column(Float, default=0.0, comment="处理进度(0-100)")
    error_message = Column(Text, nullable=True, comment="错误信息")

    # 来源与版本
    source = Column(String(100), nullable=True, comment="文档来源")
    version = Column(String(20), default="1.0", comment="文档版本")
    author = Column(String(100), nullable=True, comment="作者")

    # 标签（JSON数组）
    tags = Column(JSON, default=list, comment="标签列表")

    # 是否启用
    is_enabled = Column(Boolean, default=True, comment="是否启用")

    # 时间字段
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    indexed_at = Column(DateTime, nullable=True, comment="索引完成时间")

    # 关联关系
    slices = relationship("KnowledgeSlice", back_populates="doc")

    def __repr__(self) -> str:
        return f"<KnowledgeDoc(id={self.id}, title={self.title}, industry={self.industry})>"

    @property
    def coverage_rate(self) -> float:
        """计算索引覆盖率"""
        if self.slice_count == 0:
            return 0.0
        return (self.indexed_slice_count / self.slice_count) * 100


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
