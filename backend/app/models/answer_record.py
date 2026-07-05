"""
用户答题交互记录表 ORM 模型
存储用户答题交互与自适应导学决策记录
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Float, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class QuestionTypeEnum(enum.Enum):
    """题目类型枚举"""
    SINGLE_CHOICE = "single"      # 单选题
    MULTI_CHOICE = "multiple"     # 多选题
    FILL_BLANK = "fill"           # 填空题
    CODE = "code"                 # 代码题
    PRACTICAL = "practical"       # 实操题


class AnswerResultEnum(enum.Enum):
    """答题结果枚举"""
    CORRECT = "correct"           # 正确
    WRONG = "wrong"               # 错误
    PARTIAL = "partial"           # 部分正确
    SKIPPED = "skipped"           # 跳过


class AdaptiveDecisionEnum(enum.Enum):
    """自适应决策枚举"""
    ADVANCE = "advance"           # 进阶挑战
    MAINTAIN = "maintain"         # 维持难度
    SIMPLIFY = "simplify"         # 降维讲解
    REVIEW = "review"             # 回顾复习


class AnswerRecord(Base):
    """用户答题交互记录表"""
    
    __tablename__ = "answer_records"
    
    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment="记录ID")
    
    # 关联用户
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="关联用户ID")
    
    # 关联学习者画像
    learner_id = Column(Integer, ForeignKey("learner_profiles.id"), nullable=False, index=True, comment="关联学习者ID")
    
    # 答题基本信息
    question_id = Column(Integer, nullable=True, comment="题目ID")
    question_type = Column(SQLEnum(QuestionTypeEnum, values_callable=lambda e: [m.value for m in e]), nullable=False, comment="题目类型")
    question_topic = Column(String(100), nullable=True, comment="题目主题")
    question_difficulty = Column(Integer, default=3, comment="题目难度(1-5)")
    
    # 答题内容
    question_content = Column(Text, nullable=True, comment="题目内容")
    user_answer = Column(JSON, nullable=False, comment="用户答案")
    correct_answer = Column(JSON, nullable=True, comment="正确答案")
    
    # 答题结果
    result = Column(SQLEnum(AnswerResultEnum, values_callable=lambda e: [m.value for m in e]), nullable=False, index=True, comment="答题结果")
    score = Column(Float, default=0.0, comment="得分")
    time_spent_ms = Column(Integer, default=0, comment="答题耗时(毫秒)")
    
    # 答题统计
    attempt_count = Column(Integer, default=1, comment="尝试次数")
    hints_used = Column(Integer, default=0, comment="使用提示次数")
    
    # Agent决策记录
    agent_decision = Column(SQLEnum(AdaptiveDecisionEnum, values_callable=lambda e: [m.value for m in e]), nullable=True, comment="Agent自适应决策")
    decision_reason = Column(Text, nullable=True, comment="决策原因")
    decision_confidence = Column(Float, default=0.0, comment="决策置信度")
    
    # 决策过程日志（JSON）
    decision_log = Column(JSON, default=list, comment="Agent决策过程日志")
    
    # 后续动作
    next_action = Column(String(50), nullable=True, comment="后续动作")
    next_resource_id = Column(Integer, nullable=True, comment="推荐资源ID")
    next_question_difficulty = Column(Integer, nullable=True, comment="下一题难度")
    
    # 反馈信息
    feedback_given = Column(Boolean, default=False, comment="是否已反馈")
    feedback_content = Column(Text, nullable=True, comment="反馈内容")
    
    # 答题序列信息
    session_id = Column(String(100), nullable=True, comment="答题会话ID")
    sequence_index = Column(Integer, default=0, comment="题目序号")
    
    # 时间字段
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    # 关联关系
    user = relationship("User", back_populates="answer_records")
    learner = relationship("LearnerProfile", back_populates="answer_records")
    
    def __repr__(self) -> str:
        return f"<AnswerRecord(id={self.id}, result={self.result}, decision={self.agent_decision})>"