"""
培训项目域 Pydantic Schemas
"""
from typing import Optional, List, Any, Dict
from datetime import date, datetime
from pydantic import BaseModel, Field


# ===========================================
# 培训项目 Schemas
# ===========================================

class TrainingProjectCreate(BaseModel):
    """创建培训项目"""
    name: str = Field(..., max_length=200, description="项目名称")
    description: Optional[str] = None
    position_id: int = Field(..., description="关联岗位ID")
    certification_id: Optional[int] = Field(None, description="关联认证ID")
    project_type: Optional[str] = Field(None, description="项目类型: onboard/transfer/upskill/compliance")
    enterprise_name: Optional[str] = Field(None, max_length=100, description="所属企业")
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    config: Dict[str, Any] = Field(default_factory=dict, description="项目级配置")


class TrainingProjectUpdate(BaseModel):
    """更新培训项目"""
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    certification_id: Optional[int] = None
    project_type: Optional[str] = None
    enterprise_name: Optional[str] = Field(None, max_length=100)
    status: Optional[str] = Field(None, description="项目状态: draft/active/completed/archived")
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    config: Optional[Dict[str, Any]] = None


# ===========================================
# 报名 Schemas
# ===========================================

class EnrollRequest(BaseModel):
    """报名请求"""
    learner_id: Optional[int] = Field(None, description="学习者画像ID")


# ===========================================
# 培训计划 Schemas
# ===========================================

class GeneratePlanRequest(BaseModel):
    """生成学习计划请求"""
    assessment_record_id: int = Field(..., description="基于哪次评估记录生成计划")


class UpdateProgressRequest(BaseModel):
    """更新学习进度请求"""
    completed_stages: int = Field(..., ge=0, description="已完成阶段数")


class TaskPackageCreate(BaseModel):
    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    sequence: int = Field(1, ge=1)
    task_type: str = Field("practice", max_length=30)
    key_task_code: Optional[str] = Field(None, max_length=80)
    learning_objectives: List[Any] = Field(default_factory=list)
    resources: List[Any] = Field(default_factory=list)
    submission_required: bool = True
    passing_score: float = Field(60, ge=0, le=100)
    is_mandatory: bool = True
    status: str = Field("active", max_length=20)
    rubrics: List[Dict[str, Any]] = Field(default_factory=list)


class TaskPackageUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    sequence: Optional[int] = Field(None, ge=1)
    task_type: Optional[str] = Field(None, max_length=30)
    key_task_code: Optional[str] = Field(None, max_length=80)
    learning_objectives: Optional[List[Any]] = None
    resources: Optional[List[Any]] = None
    submission_required: Optional[bool] = None
    passing_score: Optional[float] = Field(None, ge=0, le=100)
    is_mandatory: Optional[bool] = None
    status: Optional[str] = Field(None, max_length=20)
    rubrics: Optional[List[Dict[str, Any]]] = None


class SubmissionCreate(BaseModel):
    enrollment_id: Optional[int] = None
    content: Optional[str] = None
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    demo_url: Optional[str] = Field(None, max_length=500)


class SubmissionReview(BaseModel):
    scores: List[Dict[str, Any]] = Field(default_factory=list)
    teacher_comment: Optional[str] = None
    status: str = Field("passed", pattern="^(passed|revision_requested|failed)$")


class SubmissionResponse(BaseModel):
    id: int
    task_package_id: int
    enrollment_id: int
    learner_id: Optional[int] = None
    user_id: int
    attempt_number: int
    content: Optional[str] = None
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    demo_url: Optional[str] = None
    status: str
    overall_score: Optional[float] = None
    teacher_comment: Optional[str] = None
    reviewed_by: Optional[int] = None
    submitted_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    scores: List[Dict[str, Any]] = Field(default_factory=list)
