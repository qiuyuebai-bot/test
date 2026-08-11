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
