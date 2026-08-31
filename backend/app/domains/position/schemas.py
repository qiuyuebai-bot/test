"""
岗位与胜任力域 Pydantic Schemas
"""
from typing import Optional, List, Any
from datetime import datetime
from pydantic import BaseModel, Field


# ===========================================
# Competency Schemas
# ===========================================

class CompetencyBase(BaseModel):
    code: str = Field(..., max_length=50, description="胜任力编码")
    name: str = Field(..., max_length=100, description="胜任力名称")
    category: Optional[str] = Field(None, description="胜任力类别")
    description: Optional[str] = None
    level_descriptions: Optional[dict] = Field(None, description="各等级描述")

class CompetencyCreate(CompetencyBase):
    pass

class CompetencyUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    category: Optional[str] = None
    description: Optional[str] = None
    level_descriptions: Optional[dict] = None
    is_active: Optional[bool] = None

class CompetencyResponse(CompetencyBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ===========================================
# Position Schemas
# ===========================================

class PositionBase(BaseModel):
    code: str = Field(..., max_length=50, description="岗位编码")
    name: str = Field(..., max_length=100, description="岗位名称")
    category: Optional[str] = Field(None, description="岗位类别")
    industry: Optional[str] = None
    level: Optional[str] = None
    description: Optional[str] = None
    responsibilities: Optional[List[Any]] = Field(default_factory=list)
    key_tasks: Optional[List[dict]] = Field(default_factory=list, description="关键任务")
    prerequisites: Optional[List[str]] = Field(default_factory=list)
    career_path: Optional[List[str]] = Field(default_factory=list)

class PositionCreate(PositionBase):
    pass

class PositionUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    category: Optional[str] = None
    industry: Optional[str] = None
    level: Optional[str] = None
    description: Optional[str] = None
    responsibilities: Optional[List[Any]] = None
    key_tasks: Optional[List[dict]] = None
    prerequisites: Optional[List[str]] = None
    career_path: Optional[List[str]] = None
    is_active: Optional[bool] = None

class PositionResponse(PositionBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ===========================================
# PositionCompetency Schemas
# ===========================================

class PositionCompetencyCreate(BaseModel):
    competency_id: int = Field(..., description="胜任力ID")
    required_level: int = Field(..., ge=1, le=5, description="要求等级(1-5)")
    weight: float = Field(1.0, description="权重")
    is_mandatory: bool = Field(True, description="是否必修")

class PositionCompetencyUpdate(BaseModel):
    required_level: Optional[int] = Field(None, ge=1, le=5)
    weight: Optional[float] = None
    is_mandatory: Optional[bool] = None

class PositionCompetencyResponse(BaseModel):
    id: int
    position_id: int
    competency_id: int
    competency_name: Optional[str] = None
    competency_code: Optional[str] = None
    competency_category: Optional[str] = None
    required_level: int
    weight: float
    is_mandatory: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ===========================================
# 带胜任力矩阵的岗位详情
# ===========================================

class PositionDetailResponse(PositionResponse):
    competencies: List[PositionCompetencyResponse] = Field(default_factory=list)
