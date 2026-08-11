"""
ORM 模型层统一导出
所有数据库模型在此统一管理
"""
from app.database import Base

# 用户相关模型
from app.models.user import User, UserRoleEnum
from app.domains.learner.models import LearnerProfile, EducationLevelEnum, LearningStyleEnum, LearningPhaseEnum

# 岗位与胜任力相关模型
from app.domains.position.models import Position, PositionCategoryEnum, PositionLevelEnum
from app.domains.position.models import Competency, CompetencyCategoryEnum, PositionCompetency

# 评估相关模型
from app.domains.assessment.models import AssessmentTemplate, AssessmentRecord, CompetencyScore
from app.domains.assessment.models import AssessmentStatusEnum, AssessmentMethodEnum

# 认证发证相关模型
from app.domains.certification.models import Certification, CertificationRule, CertificationRecord
from app.domains.certification.models import CertificationLevelEnum, RuleTypeEnum, CertificationStatusEnum

# 培训项目相关模型
from app.domains.training.models import TrainingProject, TrainingEnrollment, TrainingPlan
from app.domains.training.models import ProjectTypeEnum, ProjectStatusEnum, EnrollmentStatusEnum, PlanStatusEnum

# 知识库相关模型
from app.domains.knowledge.models import KnowledgeDoc, IndustryEnum, DocStatusEnum
from app.domains.knowledge.models import KnowledgeSlice

# 智能体相关模型
from app.domains.agent.models import AgentTask, AgentTypeEnum, TaskStatusEnum
from app.domains.agent.models import DebateRecord, ConflictSeverityEnum, ResolutionStatusEnum

# 学习资源相关模型
from app.domains.resource.models import LearningResource, ResourceTypeEnum, ResourceDifficultyEnum, ResourceStatusEnum, ResourceFormatEnum
from app.domains.resource.models import ResourceSection, SectionTypeEnum
from app.domains.resource.models import ResourceExercise, ExerciseLevelEnum, ExerciseTypeEnum
from app.domains.resource.models import ResourceMedia, MediaTypeEnum
from app.domains.resource.models import ResourceTemplate, TemplateCategoryEnum
from app.domains.resource.models import ResourceVersion
from app.domains.learner.models import IssuedTutoringQuestion, AnswerRecord, QuestionTypeEnum, AnswerResultEnum, AdaptiveDecisionEnum
from app.domains.learner.models import LearningPath, PathNodeTypeEnum, NodeStatusEnum

# 系统统计相关模型
from app.models.test_metrics import TestMetrics

# 脱敏数据相关模型
from app.models.anonymized_data import AnonymizedData, AnonymizeMethodEnum, DataTypeEnum

# 审计日志相关模型
from app.models.audit_log import AuditLog


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
    # 岗位与胜任力相关
    "Position",
    "PositionCategoryEnum",
    "PositionLevelEnum",
    "Competency",
    "CompetencyCategoryEnum",
    "PositionCompetency",
    # 评估相关
    "AssessmentTemplate",
    "AssessmentRecord",
    "CompetencyScore",
    "AssessmentStatusEnum",
    "AssessmentMethodEnum",
    # 认证发证相关
    "Certification",
    "CertificationRule",
    "CertificationRecord",
    "CertificationLevelEnum",
    "RuleTypeEnum",
    "CertificationStatusEnum",
    # 培训项目相关
    "TrainingProject",
    "TrainingEnrollment",
    "TrainingPlan",
    "ProjectTypeEnum",
    "ProjectStatusEnum",
    "EnrollmentStatusEnum",
    "PlanStatusEnum",
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
    "IssuedTutoringQuestion",
    "AnswerRecord",
    "QuestionTypeEnum",
    "AnswerResultEnum",
    "AdaptiveDecisionEnum",
    "LearningPath",
    "PathNodeTypeEnum",
    "NodeStatusEnum",
    # 系统统计相关
    "TestMetrics",
    # 脱敏数据相关
    "AnonymizedData",
    "AnonymizeMethodEnum",
    "DataTypeEnum",
    # 审计日志相关
    "AuditLog",
]