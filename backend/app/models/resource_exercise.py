"""
资源配套习题表 ORM 模型
存储资源中嵌入的分阶测试题、章节练习等
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float, JSON, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class ExerciseLevelEnum(enum.Enum):
    """习题难度枚举"""
    BASIC = "basic"            # 基础题
    INTERMEDIATE = "intermediate"  # 进阶题
    ADVANCED = "advanced"      # 挑战题
    COMPREHENSIVE = "comprehensive"  # 综合题


class ExerciseTypeEnum(enum.Enum):
    """习题类型枚举"""
    SINGLE_CHOICE = "single_choice"    # 单选题
    MULTI_CHOICE = "multi_choice"      # 多选题
    TRUE_FALSE = "true_false"          # 判断题
    FILL_BLANK = "fill_blank"          # 填空题
    SHORT_ANSWER = "short_answer"      # 简答题
    CODE = "code"                       # 编程题
    PRACTICAL = "practical"            # 实操题
    CASE_STUDY = "case_study"          # 案例分析题


class ResourceExercise(Base):
    """资源配套习题表"""
    
    __tablename__ = "resource_exercises"
    
    # ==================== 主键与关联 ====================
    id = Column(Integer, primary_key=True, autoincrement=True, comment="习题ID")
    resource_id = Column(Integer, ForeignKey("learning_resources.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联资源ID")
    section_id = Column(Integer, ForeignKey("resource_sections.id"), nullable=True, comment="关联章节ID")
    
    # ==================== 习题信息 ====================
    question_number = Column(Integer, default=0, comment="题号")
    question_title = Column(String(200), nullable=True, comment="题目简述")
    question_content = Column(Text, nullable=False, comment="题目内容")
    question_type = Column(String(20), nullable=False, comment="题目类型")
    difficulty_level = Column(String(20), default="basic", comment="难度等级")
    
    # ==================== 选项与答案 ====================
    options = Column(JSON, default=list, comment="选项列表（选择题专用）")
    correct_answer = Column(JSON, nullable=True, comment="正确答案")
    answer_explanation = Column(Text, nullable=True, comment="答案解析")
    answer_reference = Column(Text, nullable=True, comment="答案参考来源")
    
    # ==================== 代码题专用 ====================
    code_template = Column(Text, nullable=True, comment="代码模板")
    code_language = Column(String(20), nullable=True, comment="编程语言")
    test_cases = Column(JSON, default=list, comment="测试用例")
    expected_output = Column(Text, nullable=True, comment="预期输出")
    
    # ==================== 教学属性 ====================
    knowledge_points = Column(JSON, default=list, comment="考察知识点")
    score = Column(Float, default=10.0, comment="分值")
    estimated_minutes = Column(Integer, default=5, comment="预计用时(分钟)")
    hints = Column(JSON, default=list, comment="提示列表")
    
    # ==================== 知识溯源 ====================
    source_slice_ids = Column(JSON, default=list, comment="来源知识库切片ID")
    
    # ==================== 统计 ====================
    total_attempts = Column(Integer, default=0, comment="总答题次数")
    correct_count = Column(Integer, default=0, comment="正确次数")
    correct_rate = Column(Float, default=0.0, comment="正确率")
    average_time_ms = Column(Integer, default=0, comment="平均答题时间(毫秒)")
    
    # ==================== 状态 ====================
    is_active = Column(Boolean, default=True, comment="是否启用")
    sort_order = Column(Integer, default=0, comment="排序序号")
    
    # ==================== 时间字段 ====================
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    # ==================== 关联关系 ====================
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