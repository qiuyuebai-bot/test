"""
学习资源领域 ORM 模型
合并 learning_resource + resource_section + resource_exercise + resource_media + resource_template + resource_version
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Float, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


# ===========================================
# 枚举定义
# ===========================================

class ResourceTypeEnum(enum.Enum):
    """资源类型枚举"""
    GUIDE = "guide"
    EXERCISE = "exercise"
    LECTURE = "lecture"


class ResourceDifficultyEnum(enum.Enum):
    """资源难度枚举"""
    BASIC = 1
    ELEMENTARY = 2
    INTERMEDIATE = 3
    ADVANCED = 4
    EXPERT = 5


class ResourceStatusEnum(enum.Enum):
    """资源状态枚举"""
    GENERATING = "generating"
    VALIDATING = "validating"
    READY = "ready"
    FAILED = "failed"
    ARCHIVED = "archived"


class ResourceFormatEnum(enum.Enum):
    """资源格式枚举"""
    MARKDOWN = "md"
    HTML = "html"
    PDF = "pdf"
    JSON = "json"


class SectionTypeEnum(enum.Enum):
    """章节类型枚举"""
    CHAPTER = "chapter"
    SECTION = "section"
    SUB_SECTION = "sub_section"
    STEP = "step"
    CODE_BLOCK = "code_block"
    DIAGRAM = "diagram"
    TABLE = "table"
    TIP = "tip"
    SUMMARY = "summary"
    EXERCISE = "exercise"


class ExerciseLevelEnum(enum.Enum):
    """习题难度枚举"""
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    COMPREHENSIVE = "comprehensive"


class ExerciseTypeEnum(enum.Enum):
    """习题类型枚举"""
    SINGLE_CHOICE = "single_choice"
    MULTI_CHOICE = "multi_choice"
    TRUE_FALSE = "true_false"
    FILL_BLANK = "fill_blank"
    SHORT_ANSWER = "short_answer"
    CODE = "code"
    PRACTICAL = "practical"
    CASE_STUDY = "case_study"


class MediaTypeEnum(enum.Enum):
    """媒体类型枚举"""
    IMAGE = "image"
    DIAGRAM = "diagram"
    CODE_SNIPPET = "code"
    FLOWCHART = "flowchart"
    TABLE = "table"
    VIDEO = "video"
    AUDIO = "audio"
    MATH = "math"
    MINDMAP = "mindmap"
    OTHER = "other"


class TemplateCategoryEnum(enum.Enum):
    """模板分类枚举"""
    GUIDE = "guide"
    EXERCISE = "exercise"
    LECTURE = "lecture"
    REPORT = "report"
    PATH = "path"


# ===========================================
# 模型定义
# ===========================================

class LearningResource(Base):
    """个性化学习资源表 - 核心资源存储"""

    __tablename__ = "learning_resources"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="资源ID")
    learner_id = Column(Integer, ForeignKey("learner_profiles.id"), nullable=False, index=True, comment="关联学习者ID")
    parent_resource_id = Column(Integer, ForeignKey("learning_resources.id"), nullable=True, comment="父资源ID（版本迭代）")
    template_id = Column(Integer, ForeignKey("resource_templates.id"), nullable=True, comment="使用的模板ID")

    title = Column(String(200), nullable=False, comment="资源标题")
    subtitle = Column(String(300), nullable=True, comment="副标题")
    resource_type = Column(String(20), nullable=False, index=True, comment="资源类型")
    format_type = Column(String(10), default="md", comment="内容格式")

    knowledge_topic = Column(String(100), nullable=True, comment="知识点主题")
    knowledge_subtopics = Column(JSON, default=list, comment="子知识点列表")
    industry = Column(String(50), nullable=True, index=True, comment="所属行业")
    keywords = Column(JSON, default=list, comment="搜索关键词")

    difficulty_level = Column(Integer, default=3, comment="难度等级(1-5)")
    estimated_duration = Column(Integer, default=0, comment="预计学习时长(分钟)")
    learning_objectives = Column(JSON, default=list, comment="学习目标列表")
    prerequisites = Column(JSON, default=list, comment="前置知识要求")
    target_audience = Column(String(500), nullable=True, comment="适用人群描述")

    content = Column(Text, nullable=False, comment="资源全文内容")
    content_json = Column(JSON, default=dict, comment="结构化内容(JSON)")
    summary = Column(Text, nullable=True, comment="资源摘要")
    cover_description = Column(Text, nullable=True, comment="封面描述")
    word_count = Column(Integer, default=0, comment="字数统计")
    section_count = Column(Integer, default=0, comment="章节数量")
    exercise_count = Column(Integer, default=0, comment="习题数量")
    media_count = Column(Integer, default=0, comment="媒体附件数")

    version = Column(String(20), default="1.0", comment="版本号")
    version_notes = Column(Text, nullable=True, comment="版本更新说明")
    is_latest = Column(Boolean, default=True, comment="是否最新版本")

    source_slice_ids = Column(JSON, default=list, comment="来源知识库切片ID列表")
    source_doc_ids = Column(JSON, default=list, comment="来源文档ID列表")
    reference_urls = Column(JSON, default=list, comment="参考链接")

    generated_by_agent = Column(String(20), nullable=True, comment="生成Agent类型")
    generation_task_id = Column(Integer, nullable=True, comment="生成任务ID")
    generation_method = Column(String(50), nullable=True, comment="生成方法")
    generation_prompt = Column(Text, nullable=True, comment="生成提示词")
    generation_duration_ms = Column(Integer, default=0, comment="生成耗时(毫秒)")

    is_validated = Column(Boolean, default=False, comment="是否已校验")
    validation_passed = Column(Boolean, default=False, comment="校验是否通过")
    validation_score = Column(Float, default=0.0, comment="校验评分")
    hallucination_detected = Column(Boolean, default=False, comment="是否检测到幻觉")
    validation_notes = Column(Text, nullable=True, comment="校验备注")

    match_score = Column(Float, default=0.0, comment="资源与学习者匹配度")
    ability_match = Column(Float, default=0.0, comment="能力匹配分")
    interest_match = Column(Float, default=0.0, comment="兴趣匹配分")
    goal_match = Column(Float, default=0.0, comment="目标匹配分")

    status = Column(String(20), default="generating", index=True, comment="资源状态")
    is_enabled = Column(Boolean, default=True, comment="是否启用")
    is_public = Column(Boolean, default=False, comment="是否公开")

    file_path = Column(String(500), nullable=True, comment="文件存储路径")
    file_type = Column(String(20), default="md", comment="文件类型")
    file_size = Column(Integer, default=0, comment="文件大小(字节)")

    view_count = Column(Integer, default=0, comment="查看次数")
    download_count = Column(Integer, default=0, comment="下载次数")
    completion_count = Column(Integer, default=0, comment="完成次数")
    average_rating = Column(Float, default=0.0, comment="平均评分")
    share_count = Column(Integer, default=0, comment="分享次数")
    bookmark_count = Column(Integer, default=0, comment="收藏次数")

    feedback_positive = Column(Integer, default=0, comment="正面反馈数")
    feedback_negative = Column(Integer, default=0, comment="负面反馈数")
    feedback_notes = Column(Text, nullable=True, comment="反馈备注")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    published_at = Column(DateTime, nullable=True, comment="发布时间")
    last_accessed_at = Column(DateTime, nullable=True, comment="最后访问时间")

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


class ResourceSection(Base):
    """资源章节/小节表"""

    __tablename__ = "resource_sections"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="章节ID")
    resource_id = Column(Integer, ForeignKey("learning_resources.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联资源ID")
    parent_section_id = Column(Integer, ForeignKey("resource_sections.id"), nullable=True, comment="父章节ID（层级结构）")

    title = Column(String(200), nullable=False, comment="章节标题")
    section_type = Column(String(20), default="section", comment="章节类型")
    sort_order = Column(Integer, default=0, comment="排序序号")
    level = Column(Integer, default=1, comment="层级深度(1-4)")
    section_number = Column(String(20), nullable=True, comment="章节编号(如1.2.3)")

    content = Column(Text, nullable=False, comment="章节正文内容")
    content_html = Column(Text, nullable=True, comment="HTML格式内容")
    content_summary = Column(Text, nullable=True, comment="内容摘要")
    word_count = Column(Integer, default=0, comment="字数统计")

    learning_points = Column(JSON, default=list, comment="本节知识点列表")
    key_concepts = Column(JSON, default=list, comment="关键概念")
    difficulty_hint = Column(String(20), nullable=True, comment="本节难度提示")
    estimated_minutes = Column(Integer, default=0, comment="预计学习时长(分钟)")

    language = Column(String(20), nullable=True, comment="编程语言")
    code_content = Column(Text, nullable=True, comment="代码内容")
    code_output = Column(Text, nullable=True, comment="代码预期输出")

    has_image = Column(Boolean, default=False, comment="是否含图片")
    has_table = Column(Boolean, default=False, comment="是否含表格")
    has_code = Column(Boolean, default=False, comment="是否含代码")
    media_refs = Column(JSON, default=list, comment="关联媒体ID列表")

    source_slice_ids = Column(JSON, default=list, comment="来源知识库切片ID")
    source_doc_ids = Column(JSON, default=list, comment="来源文档ID")

    is_required = Column(Boolean, default=True, comment="是否必学")
    is_completed = Column(Boolean, default=False, comment="是否已完成")
    is_published = Column(Boolean, default=True, comment="是否发布")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    resource = relationship("LearningResource", back_populates="sections")
    parent_section = relationship("ResourceSection", remote_side=[id], backref="children")

    def __repr__(self) -> str:
        return f"<ResourceSection(id={self.id}, title={self.title}, order={self.sort_order})>"


class ResourceExercise(Base):
    """资源配套习题表"""

    __tablename__ = "resource_exercises"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="习题ID")
    resource_id = Column(Integer, ForeignKey("learning_resources.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联资源ID")
    section_id = Column(Integer, ForeignKey("resource_sections.id"), nullable=True, comment="关联章节ID")

    question_number = Column(Integer, default=0, comment="题号")
    question_title = Column(String(200), nullable=True, comment="题目简述")
    question_content = Column(Text, nullable=False, comment="题目内容")
    question_type = Column(String(20), nullable=False, comment="题目类型")
    difficulty_level = Column(String(20), default="basic", comment="难度等级")

    options = Column(JSON, default=list, comment="选项列表（选择题专用）")
    correct_answer = Column(JSON, nullable=True, comment="正确答案")
    answer_explanation = Column(Text, nullable=True, comment="答案解析")
    answer_reference = Column(Text, nullable=True, comment="答案参考来源")

    code_template = Column(Text, nullable=True, comment="代码模板")
    code_language = Column(String(20), nullable=True, comment="编程语言")
    test_cases = Column(JSON, default=list, comment="测试用例")
    expected_output = Column(Text, nullable=True, comment="预期输出")

    knowledge_points = Column(JSON, default=list, comment="考察知识点")
    score = Column(Float, default=10.0, comment="分值")
    estimated_minutes = Column(Integer, default=5, comment="预计用时(分钟)")
    hints = Column(JSON, default=list, comment="提示列表")

    source_slice_ids = Column(JSON, default=list, comment="来源知识库切片ID")

    total_attempts = Column(Integer, default=0, comment="总答题次数")
    correct_count = Column(Integer, default=0, comment="正确次数")
    correct_rate = Column(Float, default=0.0, comment="正确率")
    average_time_ms = Column(Integer, default=0, comment="平均答题时间(毫秒)")

    is_active = Column(Boolean, default=True, comment="是否启用")
    sort_order = Column(Integer, default=0, comment="排序序号")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    resource = relationship("LearningResource", back_populates="exercises")

    @property
    def difficulty_label(self) -> str:
        labels = {"basic": "基础题", "intermediate": "进阶题", "advanced": "挑战题", "comprehensive": "综合题"}
        return labels.get(self.difficulty_level, "未知")

    @property
    def type_label(self) -> str:
        labels = {
            "single_choice": "单选题", "multi_choice": "多选题",
            "true_false": "判断题", "fill_blank": "填空题",
            "short_answer": "简答题", "code": "编程题",
            "practical": "实操题", "case_study": "案例分析题"
        }
        return labels.get(self.question_type, "未知")

    def __repr__(self) -> str:
        return f"<ResourceExercise(id={self.id}, q#{self.question_number}, type={self.question_type})>"


class ResourceMedia(Base):
    """资源媒体附件表"""

    __tablename__ = "resource_media"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="媒体ID")
    resource_id = Column(Integer, ForeignKey("learning_resources.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联资源ID")
    section_id = Column(Integer, ForeignKey("resource_sections.id"), nullable=True, comment="关联章节ID")

    media_name = Column(String(200), nullable=False, comment="媒体名称")
    media_type = Column(String(20), nullable=False, comment="媒体类型")
    media_format = Column(String(10), nullable=True, comment="文件格式(png/svg/jpg/mp4)")
    description = Column(Text, nullable=True, comment="媒体描述/Alt文本")
    caption = Column(String(500), nullable=True, comment="图注/说明文字")

    file_path = Column(String(500), nullable=True, comment="文件存储路径")
    file_url = Column(String(500), nullable=True, comment="文件访问URL")
    file_size = Column(Integer, default=0, comment="文件大小(字节)")
    width = Column(Integer, nullable=True, comment="宽度(px)")
    height = Column(Integer, nullable=True, comment="高度(px)")

    content_base64 = Column(Text, nullable=True, comment="Base64编码内容(小文件直接存储)")
    external_url = Column(String(500), nullable=True, comment="外部引用URL")
    source_attribution = Column(String(200), nullable=True, comment="来源标注")

    code_language = Column(String(20), nullable=True, comment="编程语言")
    code_highlight = Column(Boolean, default=False, comment="是否代码高亮")
    code_line_numbers = Column(Boolean, default=False, comment="是否显示行号")

    latex_content = Column(Text, nullable=True, comment="LaTeX公式内容")
    is_inline = Column(Boolean, default=False, comment="是否行内公式")

    sort_order = Column(Integer, default=0, comment="排序序号")
    is_cover = Column(Boolean, default=False, comment="是否封面图")
    is_active = Column(Boolean, default=True, comment="是否启用")

    source_slice_ids = Column(JSON, default=list, comment="来源知识库切片ID")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    resource = relationship("LearningResource", back_populates="media_items")

    def __repr__(self) -> str:
        return f"<ResourceMedia(id={self.id}, name={self.media_name}, type={self.media_type})>"


class ResourceTemplate(Base):
    """资源模板表"""

    __tablename__ = "resource_templates"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="模板ID")

    name = Column(String(100), nullable=False, comment="模板名称")
    template_code = Column(String(50), nullable=False, unique=True, comment="模板编码")
    category = Column(String(20), nullable=False, index=True, comment="模板分类")
    description = Column(Text, nullable=True, comment="模板描述")

    section_schema = Column(JSON, default=list, comment="章节结构定义")
    prompt_template = Column(Text, nullable=True, comment="生成提示词模板")
    output_format = Column(JSON, default=dict, comment="输出格式定义")

    default_difficulty = Column(Integer, default=3, comment="默认难度等级")
    estimated_sections = Column(Integer, default=5, comment="预计章节数")
    estimated_duration = Column(Integer, default=60, comment="预计学习时长(分钟)")

    style_config = Column(JSON, default=dict, comment="样式配置")

    is_builtin = Column(Boolean, default=False, comment="是否内置模板")
    is_active = Column(Boolean, default=True, comment="是否启用")
    version = Column(String(20), default="1.0", comment="模板版本号")
    usage_count = Column(Integer, default=0, comment="使用次数")

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


class ResourceVersion(Base):
    """资源版本历史表"""

    __tablename__ = "resource_versions"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="版本ID")
    resource_id = Column(Integer, ForeignKey("learning_resources.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联资源ID")

    version_number = Column(Integer, default=1, comment="版本序号")
    version_tag = Column(String(20), nullable=True, comment="版本标签(如v1.0, v2.1)")
    change_type = Column(String(20), nullable=True, comment="变更类型(create/update/correct/debate_fix)")
    change_summary = Column(Text, nullable=True, comment="变更摘要")
    change_detail = Column(JSON, default=dict, comment="变更详情")

    content_snapshot = Column(Text, nullable=True, comment="内容快照(全文)")
    content_hash = Column(String(64), nullable=True, comment="内容哈希(SHA256)")
    content_json_snapshot = Column(JSON, default=dict, comment="结构化内容快照")
    word_count = Column(Integer, default=0, comment="字数统计")

    generated_by = Column(String(50), nullable=True, comment="生成方式(agent/manual/corrected)")
    generation_task_id = Column(Integer, nullable=True, comment="关联任务ID")
    debate_record_id = Column(Integer, nullable=True, comment="关联辩论记录ID")

    validation_score = Column(Float, default=0.0, comment="校验评分")
    hallucination_count = Column(Integer, default=0, comment="幻觉检出数")
    corrected_count = Column(Integer, default=0, comment="修正数量")

    is_current = Column(Boolean, default=False, comment="是否当前版本")
    is_published = Column(Boolean, default=False, comment="是否发布")

    created_by = Column(String(100), nullable=True, comment="操作人")
    created_by_agent = Column(String(20), nullable=True, comment="操作Agent类型")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    resource = relationship("LearningResource", back_populates="versions")

    def __repr__(self) -> str:
        return f"<ResourceVersion(id={self.id}, resource={self.resource_id}, v{self.version_number})>"
