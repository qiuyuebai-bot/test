"""
资源章节/小节表 ORM 模型
存储实操指南、知识讲义等资源的结构化章节内容
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class SectionTypeEnum(enum.Enum):
    """章节类型枚举"""
    CHAPTER = "chapter"            # 章
    SECTION = "section"            # 节
    SUB_SECTION = "sub_section"    # 小节
    STEP = "step"                  # 操作步骤
    CODE_BLOCK = "code_block"      # 代码块
    DIAGRAM = "diagram"            # 图表说明
    TABLE = "table"                # 表格
    TIP = "tip"                    # 提示/注意
    SUMMARY = "summary"            # 章节总结
    EXERCISE = "exercise"          # 章节练习


class ResourceSection(Base):
    """资源章节/小节表"""
    
    __tablename__ = "resource_sections"
    
    # ==================== 主键与关联 ====================
    id = Column(Integer, primary_key=True, autoincrement=True, comment="章节ID")
    resource_id = Column(Integer, ForeignKey("learning_resources.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联资源ID")
    parent_section_id = Column(Integer, ForeignKey("resource_sections.id"), nullable=True, comment="父章节ID（层级结构）")
    
    # ==================== 章节信息 ====================
    title = Column(String(200), nullable=False, comment="章节标题")
    section_type = Column(String(20), default="section", comment="章节类型")
    sort_order = Column(Integer, default=0, comment="排序序号")
    level = Column(Integer, default=1, comment="层级深度(1-4)")
    section_number = Column(String(20), nullable=True, comment="章节编号(如1.2.3)")
    
    # ==================== 内容 ====================
    content = Column(Text, nullable=False, comment="章节正文内容")
    content_html = Column(Text, nullable=True, comment="HTML格式内容")
    content_summary = Column(Text, nullable=True, comment="内容摘要")
    word_count = Column(Integer, default=0, comment="字数统计")
    
    # ==================== 教学属性 ====================
    learning_points = Column(JSON, default=list, comment="本节知识点列表")
    key_concepts = Column(JSON, default=list, comment="关键概念")
    difficulty_hint = Column(String(20), nullable=True, comment="本节难度提示")
    estimated_minutes = Column(Integer, default=0, comment="预计学习时长(分钟)")
    
    # ==================== 代码块专用 ====================
    language = Column(String(20), nullable=True, comment="编程语言")
    code_content = Column(Text, nullable=True, comment="代码内容")
    code_output = Column(Text, nullable=True, comment="代码预期输出")
    
    # ==================== 媒体 ====================
    has_image = Column(Boolean, default=False, comment="是否含图片")
    has_table = Column(Boolean, default=False, comment="是否含表格")
    has_code = Column(Boolean, default=False, comment="是否含代码")
    media_refs = Column(JSON, default=list, comment="关联媒体ID列表")
    
    # ==================== 知识溯源 ====================
    source_slice_ids = Column(JSON, default=list, comment="来源知识库切片ID")
    source_doc_ids = Column(JSON, default=list, comment="来源文档ID")
    
    # ==================== 状态 ====================
    is_required = Column(Boolean, default=True, comment="是否必学")
    is_completed = Column(Boolean, default=False, comment="是否已完成")
    is_published = Column(Boolean, default=True, comment="是否发布")
    
    # ==================== 时间字段 ====================
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    # ==================== 关联关系 ====================
    resource = relationship("LearningResource", back_populates="sections")
    parent_section = relationship("ResourceSection", remote_side=[id], backref="children")
    
    def __repr__(self) -> str:
        return f"<ResourceSection(id={self.id}, title={self.title}, order={self.sort_order})>"