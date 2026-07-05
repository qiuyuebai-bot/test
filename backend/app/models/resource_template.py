"""
资源模板表 ORM 模型
存储预定义的资源生成模板，用于规范三类资源的输出格式
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Boolean
from sqlalchemy.sql import func
from app.database import Base
import enum


class TemplateCategoryEnum(enum.Enum):
    """模板分类枚举"""
    GUIDE = "guide"            # 实操指南模板
    EXERCISE = "exercise"      # 测试题模板
    LECTURE = "lecture"        # 知识讲义模板
    REPORT = "report"          # 学情报告模板
    PATH = "path"              # 学习路径模板


class ResourceTemplate(Base):
    """资源模板表"""
    
    __tablename__ = "resource_templates"
    
    # ==================== 主键 ====================
    id = Column(Integer, primary_key=True, autoincrement=True, comment="模板ID")
    
    # ==================== 基本信息 ====================
    name = Column(String(100), nullable=False, comment="模板名称")
    template_code = Column(String(50), nullable=False, unique=True, comment="模板编码")
    category = Column(String(20), nullable=False, index=True, comment="模板分类")
    description = Column(Text, nullable=True, comment="模板描述")
    
    # ==================== 模板结构 ====================
    section_schema = Column(JSON, default=list, comment="章节结构定义")
    # 示例: [
    #   {"name": "概述", "type": "section", "required": true, "order": 1},
    #   {"name": "核心概念", "type": "section", "required": true, "order": 2},
    #   {"name": "实操步骤", "type": "step", "required": true, "order": 3},
    #   {"name": "注意事项", "type": "tip", "required": false, "order": 4},
    #   {"name": "本章小结", "type": "summary", "required": true, "order": 5},
    # ]
    
    prompt_template = Column(Text, nullable=True, comment="生成提示词模板")
    # 使用 {learner_name}, {difficulty}, {topic}, {industry} 等占位符
    
    output_format = Column(JSON, default=dict, comment="输出格式定义")
    # 示例: {"structure": "markdown", "code_style": "github", "include_toc": true}
    
    # ==================== 教学配置 ====================
    default_difficulty = Column(Integer, default=3, comment="默认难度等级")
    estimated_sections = Column(Integer, default=5, comment="预计章节数")
    estimated_duration = Column(Integer, default=60, comment="预计学习时长(分钟)")
    
    # ==================== 样式配置 ====================
    style_config = Column(JSON, default=dict, comment="样式配置")
    # 示例: {"font_size": "14px", "line_height": "1.8", "code_theme": "github"}
    
    # ==================== 状态 ====================
    is_builtin = Column(Boolean, default=False, comment="是否内置模板")
    is_active = Column(Boolean, default=True, comment="是否启用")
    version = Column(String(20), default="1.0", comment="模板版本号")
    usage_count = Column(Integer, default=0, comment="使用次数")
    
    # ==================== 时间字段 ====================
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    @property
    def category_label(self) -> str:
        labels = {
            "guide": "实操指南模板", "exercise": "测试题模板",
            "lecture": "知识讲义模板", "report": "学情报告模板",
            "path": "学习路径模板"
        }
        return labels.get(self.category, "未知")
    
    def __repr__(self) -> str:
        return f"<ResourceTemplate(id={self.id}, name={self.name}, category={self.category})>"