"""
资源媒体附件表 ORM 模型
存储资源中的图片、图表、代码截图、流程图等媒体内容
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class MediaTypeEnum(enum.Enum):
    """媒体类型枚举"""
    IMAGE = "image"            # 图片
    DIAGRAM = "diagram"        # 图表/架构图
    CODE_SNIPPET = "code"      # 代码截图
    FLOWCHART = "flowchart"    # 流程图
    TABLE = "table"            # 数据表格
    VIDEO = "video"            # 视频
    AUDIO = "audio"            # 音频
    MATH = "math"              # 数学公式
    MINDMAP = "mindmap"        # 思维导图
    OTHER = "other"            # 其他


class ResourceMedia(Base):
    """资源媒体附件表"""
    
    __tablename__ = "resource_media"
    
    # ==================== 主键与关联 ====================
    id = Column(Integer, primary_key=True, autoincrement=True, comment="媒体ID")
    resource_id = Column(Integer, ForeignKey("learning_resources.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联资源ID")
    section_id = Column(Integer, ForeignKey("resource_sections.id"), nullable=True, comment="关联章节ID")
    
    # ==================== 媒体信息 ====================
    media_name = Column(String(200), nullable=False, comment="媒体名称")
    media_type = Column(String(20), nullable=False, comment="媒体类型")
    media_format = Column(String(10), nullable=True, comment="文件格式(png/svg/jpg/mp4)")
    description = Column(Text, nullable=True, comment="媒体描述/Alt文本")
    caption = Column(String(500), nullable=True, comment="图注/说明文字")
    
    # ==================== 存储信息 ====================
    file_path = Column(String(500), nullable=True, comment="文件存储路径")
    file_url = Column(String(500), nullable=True, comment="文件访问URL")
    file_size = Column(Integer, default=0, comment="文件大小(字节)")
    width = Column(Integer, nullable=True, comment="宽度(px)")
    height = Column(Integer, nullable=True, comment="高度(px)")
    
    # ==================== 内容信息 ====================
    content_base64 = Column(Text, nullable=True, comment="Base64编码内容(小文件直接存储)")
    external_url = Column(String(500), nullable=True, comment="外部引用URL")
    source_attribution = Column(String(200), nullable=True, comment="来源标注")
    
    # ==================== 代码块专用 ====================
    code_language = Column(String(20), nullable=True, comment="编程语言")
    code_highlight = Column(Boolean, default=False, comment="是否代码高亮")
    code_line_numbers = Column(Boolean, default=False, comment="是否显示行号")
    
    # ==================== 数学公式专用 ====================
    latex_content = Column(Text, nullable=True, comment="LaTeX公式内容")
    is_inline = Column(Boolean, default=False, comment="是否行内公式")
    
    # ==================== 排序与状态 ====================
    sort_order = Column(Integer, default=0, comment="排序序号")
    is_cover = Column(Boolean, default=False, comment="是否封面图")
    is_active = Column(Boolean, default=True, comment="是否启用")
    
    # ==================== 知识溯源 ====================
    source_slice_ids = Column(JSON, default=list, comment="来源知识库切片ID")
    
    # ==================== 时间字段 ====================
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    # ==================== 关联关系 ====================
    resource = relationship("LearningResource", back_populates="media_items")
    
    def __repr__(self) -> str:
        return f"<ResourceMedia(id={self.id}, name={self.media_name}, type={self.media_type})>"