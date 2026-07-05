"""
ORM 模型层统一导出
所有数据库模型在此统一管理
"""
from app.database import Base

# 用户相关模型
from app.models.user import User, UserRoleEnum
from app.models.learner_profile import LearnerProfile, EducationLevelEnum, LearningStyleEnum, LearningPhaseEnum

# 知识库相关模型
from app.models.knowledge_doc import KnowledgeDoc, IndustryEnum, DocStatusEnum
from app.models.knowledge_slice import KnowledgeSlice

# 智能体相关模型
from app.models.agent_task import AgentTask, AgentTypeEnum, TaskStatusEnum
from app.models.debate_record import DebateRecord, ConflictSeverityEnum, ResolutionStatusEnum

# 学习资源相关模型
from app.models.learning_resource import LearningResource, ResourceTypeEnum, ResourceDifficultyEnum, ResourceStatusEnum, ResourceFormatEnum
from app.models.resource_section import ResourceSection, SectionTypeEnum
from app.models.resource_exercise import ResourceExercise, ExerciseLevelEnum, ExerciseTypeEnum
from app.models.resource_media import ResourceMedia, MediaTypeEnum
from app.models.resource_template import ResourceTemplate, TemplateCategoryEnum
from app.models.resource_version import ResourceVersion
from app.models.answer_record import AnswerRecord, QuestionTypeEnum, AnswerResultEnum, AdaptiveDecisionEnum
from app.models.learning_path import LearningPath, PathNodeTypeEnum, NodeStatusEnum

# 企业培训相关模型
from app.models.enterprise_training import EnterpriseTraining, TrainingStatusEnum, TransferStatusEnum

# 系统统计相关模型
from app.models.test_metrics import TestMetrics

# 脱敏数据相关模型
from app.models.anonymized_data import AnonymizedData, AnonymizeMethodEnum, DataTypeEnum


# 所有模型列表（用于Alembic迁移）
__all__ = [
    "Base",
    # 用户相关
    "User",
    "UserRoleEnum",
    "LearnerProfile",
    "EducationLevelEnum",
    "LearningStyleEnum",
    "LearningPhaseEnum",
    # 知识库相关
    "KnowledgeDoc",
    "IndustryEnum",
    "DocStatusEnum",
    "KnowledgeSlice",
    # 智能体相关
    "AgentTask",
    "AgentTypeEnum",
    "TaskStatusEnum",
    "DebateRecord",
    "ConflictSeverityEnum",
    "ResolutionStatusEnum",
    # 学习资源相关
    "LearningResource",
    "ResourceTypeEnum",
    "ResourceDifficultyEnum",
    "ResourceStatusEnum",
    "ResourceFormatEnum",
    "ResourceSection",
    "SectionTypeEnum",
    "ResourceExercise",
    "ExerciseLevelEnum",
    "ExerciseTypeEnum",
    "ResourceMedia",
    "MediaTypeEnum",
    "ResourceTemplate",
    "TemplateCategoryEnum",
    "ResourceVersion",
    "AnswerRecord",
    "QuestionTypeEnum",
    "AnswerResultEnum",
    "AdaptiveDecisionEnum",
    "LearningPath",
    "PathNodeTypeEnum",
    "NodeStatusEnum",
    # 企业培训相关
    "EnterpriseTraining",
    "TrainingStatusEnum",
    "TransferStatusEnum",
    # 系统统计相关
    "TestMetrics",
    # 脱敏数据相关
    "AnonymizedData",
    "AnonymizeMethodEnum",
    "DataTypeEnum",
]