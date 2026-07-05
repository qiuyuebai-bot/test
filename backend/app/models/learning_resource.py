"""
个性化学习资源表 ORM 模型
存储系统生成的三类个性化资源：实操指南、分阶测试题、专属知识讲义
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Float, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class ResourceTypeEnum(enum.Enum):
    """资源类型枚举"""
    GUIDE = "guide"            # 实操指南
    EXERCISE = "exercise"      # 分阶测试题
    LECTURE = "lecture"        # 专属知识讲义


class ResourceDifficultyEnum(enum.Enum):
    """资源难度枚举"""
    BASIC = 1       # 入门级
    ELEMENTARY = 2  # 基础级
    INTERMEDIATE = 3  # 进阶级
    ADVANCED = 4    # 精通级
    EXPERT = 5      # 专家级


class ResourceStatusEnum(enum.Enum):
    """资源状态枚举"""
    GENERATING = "generating"  # 生成中
    VALIDATING = "validating"  # 校验中
    READY = "ready"            # 已就绪
    FAILED = "failed"          # 生成失败
    ARCHIVED = "archived"      # 已归档


class ResourceFormatEnum(enum.Enum):
    """资源格式枚举"""
    MARKDOWN = "md"
    HTML = "html"
    PDF = "pdf"
    JSON = "json"


class LearningResource(Base):
    """个性化学习资源表 - 核心资源存储"""
    
    __tablename__ = "learning_resources"
    
    # ==================== 主键与关联 ====================
    id = Column(Integer, primary_key=True, autoincrement=True, comment="资源ID")
    learner_id = Column(Integer, ForeignKey("learner_profiles.id"), nullable=False, index=True, comment="关联学习者ID")
    
    # 资源版本链（支持迭代优化）
    parent_resource_id = Column(Integer, ForeignKey("learning_resources.id"), nullable=True, comment="父资源ID（版本迭代）")
    template_id = Column(Integer, ForeignKey("resource_templates.id"), nullable=True, comment="使用的模板ID")
    
    # ==================== 基本信息 ====================
    title = Column(String(200), nullable=False, comment="资源标题")
    subtitle = Column(String(300), nullable=True, comment="副标题")
    resource_type = Column(String(20), nullable=False, index=True, comment="资源类型")
    format_type = Column(String(10), default="md", comment="内容格式")
    
    # 知识领域
    knowledge_topic = Column(String(100), nullable=True, comment="知识点主题")
    knowledge_subtopics = Column(JSON, default=list, comment="子知识点列表")
    industry = Column(String(50), nullable=True, index=True, comment="所属行业")
    keywords = Column(JSON, default=list, comment="搜索关键词")
    
    # ==================== 教学属性 ====================
    difficulty_level = Column(Integer, default=3, comment="难度等级(1-5)")
    estimated_duration = Column(Integer, default=0, comment="预计学习时长(分钟)")
    learning_objectives = Column(JSON, default=list, comment="学习目标列表")
    prerequisites = Column(JSON, default=list, comment="前置知识要求")
    target_audience = Column(String(500), nullable=True, comment="适用人群描述")
    
    # ==================== 内容信息 ====================
    content = Column(Text, nullable=False, comment="资源全文内容")
    content_json = Column(JSON, default=dict, comment="结构化内容(JSON)")
    summary = Column(Text, nullable=True, comment="资源摘要")
    cover_description = Column(Text, nullable=True, comment="封面描述")
    word_count = Column(Integer, default=0, comment="字数统计")
    section_count = Column(Integer, default=0, comment="章节数量")
    exercise_count = Column(Integer, default=0, comment="习题数量")
    media_count = Column(Integer, default=0, comment="媒体附件数")
    
    # ==================== 版本管理 ====================
    version = Column(String(20), default="1.0", comment="版本号")
    version_notes = Column(Text, nullable=True, comment="版本更新说明")
    is_latest = Column(Boolean, default=True, comment="是否最新版本")
    
    # ==================== 知识溯源 ====================
    source_slice_ids = Column(JSON, default=list, comment="来源知识库切片ID列表")
    source_doc_ids = Column(JSON, default=list, comment="来源文档ID列表")
    reference_urls = Column(JSON, default=list, comment="参考链接")
    
    # ==================== 生成信息 ====================
    generated_by_agent = Column(String(20), nullable=True, comment="生成Agent类型")
    generation_task_id = Column(Integer, nullable=True, comment="生成任务ID")
    generation_method = Column(String(50), nullable=True, comment="生成方法")
    generation_prompt = Column(Text, nullable=True, comment="生成提示词")
    generation_duration_ms = Column(Integer, default=0, comment="生成耗时(毫秒)")
    
    # ==================== 校验信息 ====================
    is_validated = Column(Boolean, default=False, comment="是否已校验")
    validation_passed = Column(Boolean, default=False, comment="校验是否通过")
    validation_score = Column(Float, default=0.0, comment="校验评分")
    hallucination_detected = Column(Boolean, default=False, comment="是否检测到幻觉")
    validation_notes = Column(Text, nullable=True, comment="校验备注")
    
    # ==================== 匹配度 ====================
    match_score = Column(Float, default=0.0, comment="资源与学习者匹配度")
    ability_match = Column(Float, default=0.0, comment="能力匹配分")
    interest_match = Column(Float, default=0.0, comment="兴趣匹配分")
    goal_match = Column(Float, default=0.0, comment="目标匹配分")
    
    # ==================== 状态 ====================
    status = Column(String(20), default="generating", index=True, comment="资源状态")
    is_enabled = Column(Boolean, default=True, comment="是否启用")
    is_public = Column(Boolean, default=False, comment="是否公开")
    
    # ==================== 文件信息 ====================
    file_path = Column(String(500), nullable=True, comment="文件存储路径")
    file_type = Column(String(20), default="md", comment="文件类型")
    file_size = Column(Integer, default=0, comment="文件大小(字节)")
    
    # ==================== 使用统计 ====================
    view_count = Column(Integer, default=0, comment="查看次数")
    download_count = Column(Integer, default=0, comment="下载次数")
    completion_count = Column(Integer, default=0, comment="完成次数")
    average_rating = Column(Float, default=0.0, comment="平均评分")
    share_count = Column(Integer, default=0, comment="分享次数")
    bookmark_count = Column(Integer, default=0, comment="收藏次数")
    
    # ==================== 用户反馈 ====================
    feedback_positive = Column(Integer, default=0, comment="正面反馈数")
    feedback_negative = Column(Integer, default=0, comment="负面反馈数")
    feedback_notes = Column(Text, nullable=True, comment="反馈备注")
    
    # ==================== 时间字段 ====================
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    published_at = Column(DateTime, nullable=True, comment="发布时间")
    last_accessed_at = Column(DateTime, nullable=True, comment="最后访问时间")
    
    # ==================== 关联关系 ====================
    learner = relationship("LearnerProfile", back_populates="learning_resources")
    sections = relationship("ResourceSection", back_populates="resource", cascade="all, delete-orphan", order_by="ResourceSection.sort_order")
    exercises = relationship("ResourceExercise", back_populates="resource", cascade="all, delete-orphan")
    media_items = relationship("ResourceMedia", back_populates="resource", cascade="all, delete-orphan")
    versions = relationship("ResourceVersion", back_populates="resource", cascade="all, delete-orphan", order_by="ResourceVersion.version_number.desc()")
    
    @property
    def difficulty_label(self) -> str:
        labels = {1: "入门级", 2: "基础级", 3: "进阶级", 4: "精通级", 5: "专家级"}
        return labels.get(self.difficulty_level, "未知")
    
    @property
    def resource_type_label(self) -> str:
        labels = {"guide": "实操指南", "exercise": "分阶测试题", "lecture": "专属知识讲义"}
        return labels.get(self.resource_type, "未知")
    
    def __repr__(self) -> str:
        return f"<LearningResource(id={self.id}, title={self.title}, type={self.resource_type})>"