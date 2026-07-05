"""
企业培训任务相关数据验证 Schema
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class TrainingBase(BaseModel):
    """培训任务基础信息"""
    company_name: str = Field(..., max_length=100, description="企业名称")
    training_name: str = Field(..., max_length=200, description="培训名称")
    training_type: str = Field("standard", description="培训类型(standard/transfer)")
    description: Optional[str] = Field(None, description="培训描述")
    industry: Optional[str] = Field(None, max_length=50, description="所属行业")
    modules: List[str] = Field(default_factory=list, description="培训模块列表")
    participant_count: int = Field(0, ge=0, description="参与人数")
    participants: List[int] = Field(default_factory=list, description="参与学员ID列表")
    responsible_person: Optional[str] = Field(None, max_length=50, description="负责人")
    start_date: Optional[datetime] = Field(None, description="开始日期")
    end_date: Optional[datetime] = Field(None, description="结束日期")
    estimated_duration: int = Field(0, ge=0, description="预计时长(天)")
    is_transfer_training: bool = Field(False, description="是否转岗培训")
    transfer_from_position: Optional[str] = Field(None, max_length=100, description="原岗位")
    transfer_to_position: Optional[str] = Field(None, max_length=100, description="目标岗位")
    skill_gap_analysis: Dict[str, Any] = Field(default_factory=dict, description="技能差距分析")


class TrainingCreate(TrainingBase):
    """创建培训任务"""
    pass


class TrainingUpdate(BaseModel):
    """更新培训任务"""
    training_name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    industry: Optional[str] = None
    modules: Optional[List[str]] = None
    participant_count: Optional[int] = Field(None, ge=0)
    participants: Optional[List[int]] = None
    responsible_person: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    estimated_duration: Optional[int] = Field(None, ge=0)
    status: Optional[str] = Field(None, pattern="^(planning|ongoing|completed|cancelled)$")
    progress_percentage: Optional[float] = Field(None, ge=0, le=100)
    completed_modules: Optional[int] = Field(None, ge=0)
    is_transfer_training: Optional[bool] = None
    transfer_from_position: Optional[str] = None
    transfer_to_position: Optional[str] = None
    skill_gap_analysis: Optional[Dict[str, Any]] = None
    pass_rate: Optional[float] = Field(None, ge=0, le=100)
    average_score: Optional[float] = Field(None, ge=0, le=100)
    satisfaction_rate: Optional[float] = Field(None, ge=0, le=100)


class TrainingResponse(BaseModel):
    """培训任务响应"""
    id: int
    company_name: str
    training_name: str
    training_type: str
    description: Optional[str] = None
    industry: Optional[str] = None
    modules: List[str] = []
    participant_count: int
    participants: List[int] = []
    responsible_person: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    estimated_duration: int
    status: str
    progress_percentage: float
    completed_modules: int
    is_transfer_training: bool
    transfer_from_position: Optional[str] = None
    transfer_to_position: Optional[str] = None
    skill_gap_analysis: Dict[str, Any] = {}
    pass_rate: float
    average_score: float
    satisfaction_rate: float
    total_resources_used: int
    total_tasks_completed: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TrainingStatsResponse(BaseModel):
    """培训统计响应"""
    companies: int = 0
    learners: int = 0
    pass_rate: float = 0.0
    avg_score: float = 0.0
    total_trainings: int = 0
    ongoing_trainings: int = 0
    completed_trainings: int = 0


class TransferRecord(BaseModel):
    """转岗记录"""
    id: int
    name: str
    from_position: str
    to_position: str
    company: str
    completion: float
    skill_gap: float


class SkillGapItem(BaseModel):
    """技能差距项"""
    skill: str
    current: float
    required: float
    gap: float


class TrainingBatchImportItem(BaseModel):
    """批量导入单条"""
    company_name: str
    training_name: str
    training_type: str = "standard"
    industry: Optional[str] = None
    participant_count: int = 0
    responsible_person: Optional[str] = None


class TrainingBatchImportRequest(BaseModel):
    """批量导入请求"""
    trainings: List[TrainingBatchImportItem]
