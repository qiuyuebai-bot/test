"""
学习者学情画像表 ORM 模型
存储学习者背景数据、能力评估、技能盲区、学习轨迹等信息
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON, ForeignKey, Text, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class EducationLevelEnum(enum.Enum):
    """学历层次枚举"""
    HIGH_SCHOOL = "高中"
    COLLEGE = "大专"
    BACHELOR = "本科"
    MASTER = "硕士"
    DOCTOR = "博士"


class LearningStyleEnum(enum.Enum):
    """学习风格枚举"""
    VISUAL = "visual"      # 视觉型
    AUDITORY = "auditory"  # 听觉型
    KINESTHETIC = "kinesthetic"  # 动觉型
    READING = "reading"    # 阅读型


class LearningPhaseEnum(enum.Enum):
    """学习阶段枚举"""
    ENTRY = "entry"            # 入门期
    FOUNDATION = "foundation"  # 基础期
    GROWTH = "growth"          # 成长期
    ADVANCED = "advanced"      # 进阶期
    EXPERT = "expert"          # 专家期


class LearnerProfile(Base):
    """学习者学情画像表"""

    __tablename__ = "learner_profiles"
    __table_args__ = (
        CheckConstraint("theoretical_foundation BETWEEN 0 AND 100", name="ck_theoretical_foundation_range"),
        CheckConstraint("programming_ability BETWEEN 0 AND 100", name="ck_programming_ability_range"),
        CheckConstraint("algorithm_design BETWEEN 0 AND 100", name="ck_algorithm_design_range"),
        CheckConstraint("system_architecture BETWEEN 0 AND 100", name="ck_system_architecture_range"),
        CheckConstraint("data_analysis BETWEEN 0 AND 100", name="ck_data_analysis_range"),
        CheckConstraint("engineering_practice BETWEEN 0 AND 100", name="ck_engineering_practice_range"),
        CheckConstraint("domain_knowledge BETWEEN 0 AND 100", name="ck_domain_knowledge_range"),
        CheckConstraint("problem_solving BETWEEN 0 AND 100", name="ck_problem_solving_range"),
        CheckConstraint("teamwork BETWEEN 0 AND 100", name="ck_teamwork_range"),
        CheckConstraint("communication BETWEEN 0 AND 100", name="ck_communication_range"),
    )

    # ==================== 主键与关联 ====================
    id = Column(Integer, primary_key=True, autoincrement=True, comment="画像ID")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, comment="关联用户ID")
    
    # ==================== 基本信息 ====================
    real_name = Column(String(50), nullable=True, comment="真实姓名(脱敏)")
    display_name = Column(String(50), nullable=True, comment="显示名称")
    education_level = Column(String(20), nullable=True, comment="学历层次")
    major = Column(String(100), nullable=True, comment="专业方向")
    minor = Column(String(100), nullable=True, comment="辅修方向")
    school = Column(String(200), nullable=True, comment="毕业院校")
    graduation_year = Column(Integer, nullable=True, comment="毕业年份")
    current_position = Column(String(100), nullable=True, comment="当前职位")
    years_of_experience = Column(Integer, default=0, comment="工作年限")
    
    # ==================== 学习偏好 ====================
    learning_style = Column(String(20), default="visual", comment="学习风格")
    preferred_difficulty = Column(Integer, default=3, comment="偏好难度等级(1-5)")
    daily_study_time = Column(Integer, default=60, comment="每日学习时间(分钟)")
    preferred_language = Column(String(10), default="zh-CN", comment="偏好语言")
    preferred_formats = Column(JSON, default=list, comment="偏好资源格式")
    study_peak_hours = Column(JSON, default=list, comment="最佳学习时段")
    # 示例: ["morning", "evening"] 或 ["09:00-11:00", "19:00-21:00"]
    
    # ==================== 先验能力评估（六级维度） ====================
    theoretical_foundation = Column(Float, default=0.0, comment="理论基础(0-100)")
    programming_ability = Column(Float, default=0.0, comment="编程能力(0-100)")
    algorithm_design = Column(Float, default=0.0, comment="算法设计(0-100)")
    system_architecture = Column(Float, default=0.0, comment="系统架构(0-100)")
    data_analysis = Column(Float, default=0.0, comment="数据分析(0-100)")
    engineering_practice = Column(Float, default=0.0, comment="工程实践(0-100)")
    
    # 扩展能力维度
    domain_knowledge = Column(Float, default=0.0, comment="领域知识(0-100)")
    problem_solving = Column(Float, default=0.0, comment="问题解决能力(0-100)")
    teamwork = Column(Float, default=0.0, comment="团队协作(0-100)")
    communication = Column(Float, default=0.0, comment="沟通表达(0-100)")
    
    # ==================== 知识盲区与强项 ====================
    knowledge_blind_areas = Column(JSON, default=list, comment="知识盲区标签列表")
    knowledge_strengths = Column(JSON, default=list, comment="知识强项标签列表")
    knowledge_interests = Column(JSON, default=list, comment="兴趣知识点列表")
    
    # ==================== 历史测试成绩 ====================
    historical_test_scores = Column(JSON, default=dict, comment="历史测试成绩记录")
    # 示例: {"2024-Q1": {"avg_score": 78, "tests": 5, "topics": ["ML", "DL"]}}
    total_questions_answered = Column(Integer, default=0, comment="总答题数")
    total_correct_rate = Column(Float, default=0.0, comment="总正确率")
    recent_correct_rate = Column(Float, default=0.0, comment="近期正确率(近30天)")
    
    # ==================== 学习阶段 ====================
    learning_phase = Column(String(20), default="entry", comment="当前学习阶段")
    learning_phase_score = Column(Float, default=0.0, comment="阶段评估分数")
    consecutive_study_days = Column(Integer, default=0, comment="连续学习天数")
    total_study_hours = Column(Float, default=0.0, comment="累计学习时长(小时)")
    
    # ==================== 学习目标 ====================
    learning_goal = Column(Text, nullable=True, comment="学习目标描述")
    learning_goal_short = Column(Text, nullable=True, comment="短期目标(1-3月)")
    learning_goal_long = Column(Text, nullable=True, comment="长期目标")
    target_industry = Column(String(50), nullable=True, comment="目标行业")
    target_position = Column(String(100), nullable=True, comment="目标岗位")
    target_skills = Column(JSON, default=list, comment="目标技能列表")
    certification_goals = Column(JSON, default=list, comment="认证目标")
    
    # ==================== 行业背景 ====================
    previous_industries = Column(JSON, default=list, comment="过往行业经验")
    technical_stack = Column(JSON, default=list, comment="技术栈")
    tools_familiar = Column(JSON, default=list, comment="熟练工具")
    certifications = Column(JSON, default=list, comment="已获认证")
    
    # ==================== 学习行为 ====================
    avg_session_duration = Column(Integer, default=0, comment="平均每次学习时长(分钟)")
    completion_rate = Column(Float, default=0.0, comment="资源完成率")
    feedback_engagement = Column(Float, default=0.0, comment="反馈参与度")
    preferred_topics = Column(JSON, default=list, comment="最常学习主题Top5")
    
    # ==================== 数据权限 ====================
    data_permission_level = Column(String(20), default="learner", comment="数据权限级别")
    # learner: 仅自己可见, enterprise_admin: 企业管理员可见, admin: 系统管理员可见
    is_data_anonymized = Column(Boolean, default=False, comment="数据是否已脱敏")
    anonymized_fields = Column(JSON, default=list, comment="已脱敏字段列表")
    data_retention_days = Column(Integer, default=365, comment="数据保留天数")
    
    # ==================== 时间字段 ====================
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    last_active_at = Column(DateTime, nullable=True, comment="最后活跃时间")
    last_report_at = Column(DateTime, nullable=True, comment="最后报告生成时间")
    
    # ==================== 关联关系 ====================
    user = relationship("User", back_populates="learner_profile")
    learning_resources = relationship("LearningResource", back_populates="learner")
    answer_records = relationship("AnswerRecord", back_populates="learner")
    learning_paths = relationship("LearningPath", back_populates="learner")
    
    def __repr__(self) -> str:
        return f"<LearnerProfile(id={self.id}, user_id={self.user_id}, education={self.education_level})>"
    
    @property
    def average_ability(self) -> float:
        """计算平均能力分数（6维核心能力）"""
        scores = [
            self.theoretical_foundation or 0,
            self.programming_ability or 0,
            self.algorithm_design or 0,
            self.system_architecture or 0,
            self.data_analysis or 0,
            self.engineering_practice or 0,
        ]
        return sum(scores) / len(scores)

    @property
    def comprehensive_ability(self) -> float:
        """计算综合能力分（含扩展维度）"""
        scores = [
            self.theoretical_foundation or 0,
            self.programming_ability or 0,
            self.algorithm_design or 0,
            self.system_architecture or 0,
            self.data_analysis or 0,
            self.engineering_practice or 0,
            self.domain_knowledge or 0,
            self.problem_solving or 0,
        ]
        return sum(scores) / len(scores)
    
    @property
    def ability_profile(self) -> dict:
        """返回完整能力画像字典"""
        return {
            "theoretical_foundation": self.theoretical_foundation,
            "programming_ability": self.programming_ability,
            "algorithm_design": self.algorithm_design,
            "system_architecture": self.system_architecture,
            "data_analysis": self.data_analysis,
            "engineering_practice": self.engineering_practice,
            "domain_knowledge": self.domain_knowledge,
            "problem_solving": self.problem_solving,
            "average": self.average_ability,
            "comprehensive": self.comprehensive_ability,
        }
    
    @property
    def learning_phase_label(self) -> str:
        labels = {
            "entry": "入门期", "foundation": "基础期",
            "growth": "成长期", "advanced": "进阶期", "expert": "专家期"
        }
        return labels.get(self.learning_phase, "未知")