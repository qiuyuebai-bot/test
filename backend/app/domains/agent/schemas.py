"""
Agent 相关 Pydantic Schema
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


# ========== 状态相关 ==========

class AgentStatusResponse(BaseModel):
    """Agent状态响应"""
    agent_type: str = Field(..., description="Agent类型")
    agent_name: str = Field(..., description="Agent名称")
    status: str = Field(..., description="状态: idle/running/validating/error")
    current_task_id: Optional[int] = Field(None, description="当前任务ID")
    last_error: Optional[str] = Field(None, description="最后错误信息")


# ========== 任务相关 ==========

class CreateAgentTaskRequest(BaseModel):
    """创建Agent任务请求"""
    learner_id: int = Field(..., description="学习者ID", gt=0)
    task_name: str = Field(..., description="任务名称", min_length=1, max_length=200)
    task_type: str = Field(..., description="任务类型: learner_diagnosis/resource_generation/full_pipeline")
    target_topic: Optional[str] = Field(None, description="目标主题")
    resource_type: Optional[str] = Field("guide", description="资源类型: guide/exercise/lecture")
    industry: Optional[str] = Field(None, description="行业领域")
    input_data: Optional[Dict[str, Any]] = Field(None, description="额外输入数据")


class TaskStatusResponse(BaseModel):
    """任务状态响应"""
    task_id: int
    task_name: Optional[str] = None
    status: Optional[str] = None
    progress: Optional[int] = None
    stage: Optional[str] = None
    description: Optional[str] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None


class TaskLogEntry(BaseModel):
    """任务日志条目"""
    stage: str
    progress: int
    description: str
    timestamp: str


# ========== 诊断相关 ==========

class DiagnosisRequest(BaseModel):
    """学情诊断请求"""
    learner_id: int = Field(..., description="学习者ID", gt=0)


class AbilityDimension(BaseModel):
    """能力维度"""
    name: str
    score: float
    level: str
    description: str


class BlindArea(BaseModel):
    """知识盲区"""
    name: str
    type: str
    severity: str
    source: str
    score: Optional[float] = None


class DiagnosisResultResponse(BaseModel):
    """诊断结果响应"""
    learner_id: int
    ability_scores: Dict[str, float]
    ability_levels: Dict[str, AbilityDimension]
    overall_score: float
    overall_level: str
    knowledge_blind_areas: List[BlindArea]
    knowledge_strengths: List[Dict[str, Any]]
    recommended_difficulty: Dict[str, Any]
    recommendations: List[str]


# ========== 资源生成相关 ==========

class GenerationRequest(BaseModel):
    """资源生成请求"""
    learner_id: int = Field(..., description="学习者ID", gt=0)
    target_topic: str = Field(..., description="目标主题", min_length=1)
    resource_type: str = Field("guide", description="资源类型: guide/exercise/lecture")
    industry: Optional[str] = Field(None, description="行业领域")


# ========== 审核校验相关 ==========

class AuditIssue(BaseModel):
    """审核问题"""
    type: str
    severity: str
    description: str
    details: Optional[Any] = None


class CorrectionItem(BaseModel):
    """修正项"""
    issue_type: str
    severity: str
    description: str
    suggested_fix: str
    confidence: str


class AuditResultResponse(BaseModel):
    """审核结果响应"""
    passed: bool
    overall_score: float
    issue_count: int
    hallucination_detected: bool
    hallucination_score: float
    consistency_score: float
    standard_score: float
    issues: List[AuditIssue]
    corrections: List[CorrectionItem]


# ========== 辩论记录相关 ==========

class DebateRecordItem(BaseModel):
    """辩论记录"""
    round: int
    judge_standpoint: Dict[str, Any]
    generation_counterargument: Dict[str, Any]
    final_decision: str
    conflict_points: List[Dict[str, Any]]
    corrections: List[Dict[str, Any]]
    debate_ended: Optional[bool] = None


# ========== 指标统计相关 ==========

class MetricsResponse(BaseModel):
    """指标统计响应"""
    total_count: int
    hallucination_count: int
    hallucination_rate: float
    avg_score: float
    pass_rate: float
