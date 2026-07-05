"""
学习者画像相关数据验证 Schema
"""
from pydantic import BaseModel, Field, model_validator, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime


# ===========================================
# 基础 Schema
# ===========================================

class LearnerProfileBase(BaseModel):
    """学习者画像基础信息"""
    real_name: Optional[str] = Field(None, max_length=50, description="真实姓名")
    education_level: Optional[str] = Field(None, description="学历层次")
    major: Optional[str] = Field(None, max_length=100, description="专业方向")
    graduation_year: Optional[int] = Field(None, ge=1980, le=2030, description="毕业年份")
    current_position: Optional[str] = Field(None, max_length=100, description="当前职位")
    learning_style: Optional[str] = Field("visual", description="学习风格")
    preferred_difficulty: Optional[int] = Field(3, ge=1, le=5, description="偏好难度等级")
    daily_study_time: Optional[int] = Field(60, ge=10, le=480, description="每日学习时间(分钟)")
    target_industry: Optional[str] = Field(None, max_length=50, description="目标行业")
    target_position: Optional[str] = Field(None, max_length=100, description="目标岗位")
    learning_goal: Optional[str] = Field(None, description="学习目标描述")


class LearnerProfileCreate(LearnerProfileBase):
    """创建学习者画像请求"""
    user_id: int = Field(..., description="关联用户ID")
    
    # 先验能力评估
    theoretical_foundation: float = Field(0.0, ge=0, le=100, description="理论基础")
    programming_ability: float = Field(0.0, ge=0, le=100, description="编程能力")
    algorithm_design: float = Field(0.0, ge=0, le=100, description="算法设计")
    system_architecture: float = Field(0.0, ge=0, le=100, description="系统架构")
    data_analysis: float = Field(0.0, ge=0, le=100, description="数据分析")
    engineering_practice: float = Field(0.0, ge=0, le=100, description="工程实践")
    
    # 知识盲区
    knowledge_blind_areas: List[str] = Field(default_factory=list, description="知识盲区标签")


class LearnerProfileUpdate(BaseModel):
    """更新学习者画像请求"""
    real_name: Optional[str] = None
    education_level: Optional[str] = None
    major: Optional[str] = None
    graduation_year: Optional[int] = None
    current_position: Optional[str] = None
    learning_style: Optional[str] = None
    preferred_difficulty: Optional[int] = None
    daily_study_time: Optional[int] = None
    target_industry: Optional[str] = None
    target_position: Optional[str] = None
    learning_goal: Optional[str] = None
    
    # 能力评估
    theoretical_foundation: Optional[float] = None
    programming_ability: Optional[float] = None
    algorithm_design: Optional[float] = None
    system_architecture: Optional[float] = None
    data_analysis: Optional[float] = None
    engineering_practice: Optional[float] = None
    
    # 知识盲区
    knowledge_blind_areas: Optional[List[str]] = None


class LearnerProfileResponse(BaseModel):
    """学习者画像响应"""
    id: int
    user_id: int
    real_name: Optional[str] = None
    education_level: Optional[str] = None
    major: Optional[str] = None
    graduation_year: Optional[int] = None
    current_position: Optional[str] = None
    learning_style: str
    preferred_difficulty: int
    daily_study_time: int
    target_industry: Optional[str] = None
    target_position: Optional[str] = None
    learning_goal: Optional[str] = None
    
    # 六维能力
    theoretical_foundation: float
    programming_ability: float
    algorithm_design: float
    system_architecture: float
    data_analysis: float
    engineering_practice: float
    
    average_ability: float
    knowledge_blind_areas: List[str] = []
    
    is_data_anonymized: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ===========================================
# 批量操作 Schema
# ===========================================

class LearnerBatchImportItem(BaseModel):
    """批量导入项"""
    user_id: Optional[int] = None
    real_name: Optional[str] = None
    education_level: str
    major: str
    learning_style: str = "visual"
    theoretical_foundation: float = 0
    programming_ability: float = 0
    algorithm_design: float = 0
    system_architecture: float = 0
    data_analysis: float = 0
    engineering_practice: float = 0
    knowledge_blind_areas: List[str] = []
    target_industry: Optional[str] = None


class LearnerBatchImportRequest(BaseModel):
    """批量导入请求"""
    learners: List[LearnerBatchImportItem] = Field(default_factory=list, max_length=100)
    items: Optional[List[LearnerBatchImportItem]] = Field(None, description="兼容旧版字段名")

    @model_validator(mode="after")
    def resolve_items(self):
        if self.items and not self.learners:
            self.learners = self.items
        return self


class LearnerBatchImportResponse(BaseModel):
    """批量导入响应"""
    total_count: int
    success_count: int
    failed_count: int
    created_ids: List[int] = []
    errors: List[Dict[str, Any]] = []


class LearnerBatchExportRequest(BaseModel):
    """批量导出请求"""
    learner_ids: Optional[List[int]] = Field(None, description="指定导出的学习者ID，为空则导出全部")
    export_format: str = Field("json", description="导出格式(json/csv)")
    include_sensitive: bool = Field(False, description="是否包含敏感数据")


class LearnerBatchExportResponse(BaseModel):
    """批量导出响应"""
    format: str
    total_count: int
    file_url: str
    download_url: str


# ===========================================
# 学情分析 Schema
# ===========================================

class LearningAnalysisRequest(BaseModel):
    """学情分析请求"""
    learner_id: int = Field(..., description="学习者ID")


class AbilityDimension(BaseModel):
    """能力维度"""
    name: str
    score: float
    level: str
    description: str


class LearningAnalysisResponse(BaseModel):
    """学情分析响应"""
    learner_id: int
    overall_score: float
    overall_level: str
    
    ability_dimensions: List[AbilityDimension]
    
    knowledge_strengths: List[str]
    knowledge_blind_areas: List[str]
    blind_area_details: List[Dict[str, Any]]
    
    test_history_summary: Dict[str, Any]
    learning_recommendations: List[str]
    
    analysis_date: datetime

    @property
    def strengths(self):
        return self.knowledge_strengths

    @property
    def blind_areas(self):
        return self.knowledge_blind_areas


# ===========================================
# 数据脱敏 Schema
# ===========================================

class AnonymizeRequest(BaseModel):
    """脱敏请求"""
    learner_id: Optional[int] = Field(None, description="学习者ID")
    fields: Optional[List[str]] = Field(None, description="指定脱敏字段，为空则脱敏所有敏感字段")


class AnonymizeResponse(BaseModel):
    """脱敏响应"""
    learner_id: int
    is_anonymized: bool
    anonymized_fields: List[str]
    
    before: Dict[str, Any]
    after: Dict[str, Any]
    
    record_id: int
    operation_time: datetime


# ===========================================
# 答题记录 Schema
# ===========================================

class AnswerRecordCreate(BaseModel):
    """创建答题记录请求"""
    learner_id: int
    user_id: Optional[int] = None
    question_type: str
    question_topic: str
    question_difficulty: int = 3
    question_content: Optional[str] = None
    user_answer: Any
    correct_answer: Any
    result: str
    score: float = 0
    time_spent_ms: int = 0


class AnswerRecordResponse(BaseModel):
    """答题记录响应"""
    id: int
    learner_id: int
    question_type: str
    question_topic: str
    question_difficulty: int
    result: str
    score: float
    time_spent_ms: int
    agent_decision: Optional[str] = None
    decision_reason: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ===========================================
# 列表查询 Schema
# ===========================================

class LearnerQueryParams(BaseModel):
    """学习者查询参数"""
    page: int = 1
    page_size: int = 10
    keyword: Optional[str] = None
    education_level: Optional[str] = None
    target_industry: Optional[str] = None
    learning_style: Optional[str] = None
    min_score: Optional[float] = None
    max_score: Optional[float] = None
    is_anonymized: Optional[bool] = None


class LearnerListResponse(BaseModel):
    """学习者列表响应"""
    items: List[LearnerProfileResponse]
    total: int
    page: int
    page_size: int
    total_pages: int