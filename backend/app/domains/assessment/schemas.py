"""
评估域 Pydantic Schemas
"""
from typing import Optional, List, Any
from datetime import datetime
from pydantic import BaseModel, Field


# ===========================================
# 评估模板 Schemas
# ===========================================

class CompetencyConfig(BaseModel):
    """胜任力配置项（模板内的元素）"""
    competency_id: int = Field(..., description="胜任力ID")
    question_count: int = Field(5, ge=1, description="题目数量")
    difficulty: int = Field(3, ge=1, le=5, description="难度等级(1-5)")
    assessment_method: str = Field("quiz", description="评估方式: quiz/self_report/interview/project")


class AssessmentTemplateBase(BaseModel):
    position_id: int = Field(..., description="关联岗位ID")
    name: str = Field(..., max_length=200, description="模板名称")
    description: Optional[str] = None
    competency_configs: List[CompetencyConfig] = Field(default_factory=list, description="胜任力配置列表")
    pass_threshold: float = Field(60.0, ge=0, le=100, description="通过分数线")
    duration_minutes: Optional[int] = Field(None, ge=1, description="评估时长(分钟)")


class AssessmentTemplateCreate(AssessmentTemplateBase):
    pass


class AssessmentTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    competency_configs: Optional[List[CompetencyConfig]] = None
    pass_threshold: Optional[float] = Field(None, ge=0, le=100)
    duration_minutes: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None


class AssessmentTemplateResponse(AssessmentTemplateBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ===========================================
# 胜任力评分 Schemas
# ===========================================

class CompetencyScoreResponse(BaseModel):
    id: int
    assessment_record_id: int
    competency_id: int
    competency_name: Optional[str] = None
    competency_code: Optional[str] = None
    current_level: Optional[int] = None
    current_score: Optional[float] = None
    required_level: int
    gap: Optional[int] = None
    assessment_method: Optional[str] = None
    evidence: Optional[List[Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ===========================================
# 评估记录 Schemas
# ===========================================

class AssessmentStartRequest(BaseModel):
    """开始评估请求"""
    template_id: int = Field(..., description="评估模板ID")
    learner_id: int = Field(..., description="学习者画像ID")


class AssessmentSubmitRequest(BaseModel):
    """提交评估请求"""
    scores: List[dict] = Field(..., description="评分列表 [{competency_id, current_level, current_score, assessment_method, evidence}]")


class AssessmentRecordResponse(BaseModel):
    id: int
    template_id: int
    user_id: int
    learner_id: Optional[int] = None
    position_id: int
    status: str
    overall_score: Optional[float] = None
    overall_level: Optional[int] = None
    gap_summary: Optional[List[dict]] = None
    ai_diagnosis: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AssessmentRecordDetailResponse(AssessmentRecordResponse):
    """评估记录详情（含评分明细和模板信息）"""
    competency_scores: List[CompetencyScoreResponse] = Field(default_factory=list)
    template_name: Optional[str] = None
    position_name: Optional[str] = None


# ===========================================
# 差距分析响应
# ===========================================

class GapItem(BaseModel):
    """单项差距"""
    competency_id: int
    competency_name: str
    competency_code: Optional[str] = None
    current_level: Optional[int] = None
    required_level: int
    gap: int
    is_met: bool


class GapAnalysisResponse(BaseModel):
    """差距分析响应"""
    record_id: int
    overall_score: Optional[float] = None
    overall_level: Optional[int] = None
    pass_threshold: float
    is_passed: bool
    total_competencies: int
    met_count: int
    gap_count: int
    gaps: List[GapItem]
