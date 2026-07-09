"""
学习者域 ORM 模型
合并 LearnerProfile、AnswerRecord、LearningPath 三个模型
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON, ForeignKey, Text, CheckConstraint, Enum as SQLEnum
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

    id = Column(Integer, primary_key=True, autoincrement=True, comment="画像ID")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, comment="关联用户ID")

    real_name = Column(String(50), nullable=True, index=True, comment="真实姓名(脱敏)")
    display_name = Column(String(50), nullable=True, comment="显示名称")
    education_level = Column(String(20), nullable=True, index=True, comment="学历层次")
    major = Column(String(100), nullable=True, comment="专业方向")
    minor = Column(String(100), nullable=True, comment="辅修方向")
    school = Column(String(200), nullable=True, comment="毕业院校")
    graduation_year = Column(Integer, nullable=True, comment="毕业年份")
    current_position = Column(String(100), nullable=True, comment="当前职位")
    years_of_experience = Column(Integer, default=0, comment="工作年限")

    learning_style = Column(String(20), default="visual", comment="学习风格")
    preferred_difficulty = Column(Integer, default=3, comment="偏好难度等级(1-5)")
    daily_study_time = Column(Integer, default=60, comment="每日学习时间(分钟)")
    preferred_language = Column(String(10), default="zh-CN", comment="偏好语言")
    preferred_formats = Column(JSON, default=list, comment="偏好资源格式")
    study_peak_hours = Column(JSON, default=list, comment="最佳学习时段")

    theoretical_foundation = Column(Float, default=0.0, comment="理论基础(0-100)")
    programming_ability = Column(Float, default=0.0, comment="编程能力(0-100)")
    algorithm_design = Column(Float, default=0.0, comment="算法设计(0-100)")
    system_architecture = Column(Float, default=0.0, comment="系统架构(0-100)")
    data_analysis = Column(Float, default=0.0, comment="数据分析(0-100)")
    engineering_practice = Column(Float, default=0.0, comment="工程实践(0-100)")

    domain_knowledge = Column(Float, default=0.0, comment="领域知识(0-100)")
    problem_solving = Column(Float, default=0.0, comment="问题解决能力(0-100)")
    teamwork = Column(Float, default=0.0, comment="团队协作(0-100)")
    communication = Column(Float, default=0.0, comment="沟通表达(0-100)")

    knowledge_blind_areas = Column(JSON, default=list, comment="知识盲区标签列表")
    knowledge_strengths = Column(JSON, default=list, comment="知识强项标签列表")
    knowledge_interests = Column(JSON, default=list, comment="兴趣知识点列表")

    historical_test_scores = Column(JSON, default=dict, comment="历史测试成绩记录")
    total_questions_answered = Column(Integer, default=0, comment="总答题数")
    total_correct_rate = Column(Float, default=0.0, comment="总正确率")
    recent_correct_rate = Column(Float, default=0.0, comment="近期正确率(近30天)")

    learning_phase = Column(String(20), default="entry", index=True, comment="当前学习阶段")
    learning_phase_score = Column(Float, default=0.0, comment="阶段评估分数")
    consecutive_study_days = Column(Integer, default=0, comment="连续学习天数")
    total_study_hours = Column(Float, default=0.0, comment="累计学习时长(小时)")

    learning_goal = Column(Text, nullable=True, comment="学习目标描述")
    learning_goal_short = Column(Text, nullable=True, comment="短期目标(1-3月)")
    learning_goal_long = Column(Text, nullable=True, comment="长期目标")
    target_industry = Column(String(50), nullable=True, index=True, comment="目标行业")
    target_position = Column(String(100), nullable=True, comment="目标岗位")
    target_skills = Column(JSON, default=list, comment="目标技能列表")
    certification_goals = Column(JSON, default=list, comment="认证目标")

    previous_industries = Column(JSON, default=list, comment="过往行业经验")
    technical_stack = Column(JSON, default=list, comment="技术栈")
    tools_familiar = Column(JSON, default=list, comment="熟练工具")
    certifications = Column(JSON, default=list, comment="已获认证")

    avg_session_duration = Column(Integer, default=0, comment="平均每次学习时长(分钟)")
    completion_rate = Column(Float, default=0.0, comment="资源完成率")
    feedback_engagement = Column(Float, default=0.0, comment="反馈参与度")
    preferred_topics = Column(JSON, default=list, comment="最常学习主题Top5")

    data_permission_level = Column(String(20), default="learner", comment="数据权限级别")
    is_data_anonymized = Column(Boolean, default=False, comment="数据是否已脱敏")
    anonymized_fields = Column(JSON, default=list, comment="已脱敏字段列表")
    data_retention_days = Column(Integer, default=365, comment="数据保留天数")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    last_active_at = Column(DateTime, nullable=True, comment="最后活跃时间")
    last_report_at = Column(DateTime, nullable=True, comment="最后报告生成时间")

    user = relationship("User", back_populates="learner_profile")
    learning_resources = relationship("LearningResource", back_populates="learner")
    answer_records = relationship("AnswerRecord", back_populates="learner")
    learning_paths = relationship("LearningPath", back_populates="learner")

    def __repr__(self) -> str:
        return f"<LearnerProfile(id={self.id}, user_id={self.user_id}, education={self.education_level})>"

    @property
    def average_ability(self) -> float:
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


class QuestionTypeEnum(enum.Enum):
    """题目类型枚举"""
    SINGLE_CHOICE = "single"
    MULTI_CHOICE = "multiple"
    FILL_BLANK = "fill"
    CODE = "code"
    PRACTICAL = "practical"


class AnswerResultEnum(enum.Enum):
    """答题结果枚举"""
    CORRECT = "correct"
    WRONG = "wrong"
    PARTIAL = "partial"
    SKIPPED = "skipped"


class AdaptiveDecisionEnum(enum.Enum):
    """自适应决策枚举"""
    ADVANCE = "advance"
    MAINTAIN = "maintain"
    SIMPLIFY = "simplify"
    REVIEW = "review"


class AnswerRecord(Base):
    """用户答题交互记录表"""

    __tablename__ = "answer_records"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="记录ID")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="关联用户ID")
    learner_id = Column(Integer, ForeignKey("learner_profiles.id"), nullable=False, index=True, comment="关联学习者ID")

    question_id = Column(Integer, nullable=True, comment="题目ID")
    question_type = Column(SQLEnum(QuestionTypeEnum, values_callable=lambda e: [m.value for m in e]), nullable=False, comment="题目类型")
    question_topic = Column(String(100), nullable=True, comment="题目主题")
    question_difficulty = Column(Integer, default=3, comment="题目难度(1-5)")

    question_content = Column(Text, nullable=True, comment="题目内容")
    user_answer = Column(JSON, nullable=False, comment="用户答案")
    correct_answer = Column(JSON, nullable=True, comment="正确答案")

    result = Column(SQLEnum(AnswerResultEnum, values_callable=lambda e: [m.value for m in e]), nullable=False, index=True, comment="答题结果")
    score = Column(Float, default=0.0, comment="得分")
    time_spent_ms = Column(Integer, default=0, comment="答题耗时(毫秒)")

    attempt_count = Column(Integer, default=1, comment="尝试次数")
    hints_used = Column(Integer, default=0, comment="使用提示次数")

    agent_decision = Column(SQLEnum(AdaptiveDecisionEnum, values_callable=lambda e: [m.value for m in e]), nullable=True, comment="Agent自适应决策")
    decision_reason = Column(Text, nullable=True, comment="决策原因")
    decision_confidence = Column(Float, default=0.0, comment="决策置信度")

    decision_log = Column(JSON, default=list, comment="Agent决策过程日志")

    next_action = Column(String(50), nullable=True, comment="后续动作")
    next_resource_id = Column(Integer, nullable=True, comment="推荐资源ID")
    next_question_difficulty = Column(Integer, nullable=True, comment="下一题难度")

    feedback_given = Column(Boolean, default=False, comment="是否已反馈")
    feedback_content = Column(Text, nullable=True, comment="反馈内容")

    session_id = Column(String(100), nullable=True, comment="答题会话ID")
    sequence_index = Column(Integer, default=0, comment="题目序号")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    user = relationship("User", back_populates="answer_records")
    learner = relationship("LearnerProfile", back_populates="answer_records")

    def __repr__(self) -> str:
        return f"<AnswerRecord(id={self.id}, result={self.result}, decision={self.agent_decision})>"


class PathNodeTypeEnum(enum.Enum):
    """路径节点类型枚举"""
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class NodeStatusEnum(enum.Enum):
    """节点状态枚举"""
    LOCKED = "locked"
    AVAILABLE = "available"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class LearningPath(Base):
    """学习路径规划数据表"""

    __tablename__ = "learning_paths"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="路径ID")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="关联用户ID")
    learner_id = Column(Integer, ForeignKey("learner_profiles.id"), nullable=False, index=True, comment="关联学习者ID")

    path_name = Column(String(200), nullable=False, comment="路径名称")
    target_industry = Column(String(50), nullable=True, comment="目标行业")
    target_position = Column(String(100), nullable=True, comment="目标岗位")
    total_nodes = Column(Integer, default=0, comment="总节点数")
    total_duration = Column(Integer, default=0, comment="预计总时长(天)")

    path_nodes = Column(JSON, default=list, comment="路径节点列表(JSON)")
    current_node_index = Column(Integer, default=0, comment="当前节点序号")

    completed_nodes = Column(Integer, default=0, comment="已完成节点数")
    progress_percentage = Column(Float, default=0.0, comment="完成百分比")

    estimated_completion_date = Column(DateTime, nullable=True, comment="预计完成日期")
    actual_started_date = Column(DateTime, nullable=True, comment="实际开始日期")
    actual_completion_date = Column(DateTime, nullable=True, comment="实际完成日期")

    generated_by_agent = Column(Boolean, default=True, comment="是否由Agent生成")
    generation_method = Column(String(50), nullable=True, comment="生成方法")

    adjustment_history = Column(JSON, default=list, comment="路径调整历史")

    is_active = Column(Boolean, default=True, comment="是否激活")
    is_completed = Column(Boolean, default=False, comment="是否已完成")

    knowledge_coverage_before = Column(Float, default=0.0, comment="学习前覆盖率")
    knowledge_coverage_after = Column(Float, default=0.0, comment="学习后覆盖率")
    skill_improvement_score = Column(Float, default=0.0, comment="技能提升分数")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    user = relationship("User", back_populates="learning_paths")
    learner = relationship("LearnerProfile", back_populates="learning_paths")

    def __repr__(self) -> str:
        return f"<LearningPath(id={self.id}, name={self.path_name}, progress={self.progress_percentage}%)>"
