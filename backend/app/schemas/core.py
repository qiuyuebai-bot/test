"""
核心业务模块 Pydantic Schema
包含：个性化资源生成、学情报告、自适应导学
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


# ========== 个性化资源生成 ==========

class GenerateResourcesRequest(BaseModel):
    """生成资源请求"""
    learner_id: int = Field(..., description="学习者ID", gt=0)
    target_topic: str = Field(..., description="目标主题", min_length=1)
    industry: Optional[str] = Field(None, description="行业领域")


class GeneratedResourceItem(BaseModel):
    """生成的资源项"""
    resource_type: str
    resource_type_name: str
    resource_title: str
    difficulty_level: int
    content: str
    content_json: Dict[str, Any]
    word_count: int
    match_score: float
    saved_resource_id: Optional[int] = None


class GenerateResourcesResponse(BaseModel):
    """生成资源响应"""
    success: bool
    learner_id: int
    target_topic: str
    industry: Optional[str] = None
    generated_resources: List[GeneratedResourceItem]
    resource_count: int
    avg_match_score: float
    diagnosis_summary: Dict[str, Any]
    knowledge_retrieved_count: int
    duration_ms: int


class ResourceListResponse(BaseModel):
    """资源列表响应"""
    resources: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int


class ResourceDetailResponse(BaseModel):
    """资源详情响应"""
    resource_id: int
    learner_id: int
    title: str
    resource_type: str
    resource_type_name: str
    difficulty_level: int
    knowledge_topic: str
    content: str
    content_json: Dict[str, Any]
    word_count: int
    match_score: float
    validation_score: float
    status: str
    view_count: int
    download_count: int
    created_at: Optional[str] = None


# ========== 学情可视化报告 ==========

class HeatmapDataItem(BaseModel):
    """热力图数据项"""
    dimension: str
    dimension_key: str
    severity: str
    severity_label: str
    value: float
    score: float
    is_blind: bool
    description: str


class BlindAreaHeatmapResponse(BaseModel):
    """盲区热力图响应"""
    labels: List[str]
    severity_levels: List[str]
    severity_labels: List[str]
    data: List[HeatmapDataItem]


class MatchCurveDataItem(BaseModel):
    """匹配曲线数据项"""
    name: str
    difficulty: int
    match_score: float
    learner_ability: float
    resource_id: int
    title: str


class DifficultyMatchCurveResponse(BaseModel):
    """难度匹配曲线响应"""
    labels: List[str]
    difficulty: List[int]
    match_score: List[float]
    learner_ability: List[float]
    data: List[MatchCurveDataItem]
    learner_ability_raw: float


class PathNode(BaseModel):
    """路径节点"""
    id: str
    name: str
    difficulty: int
    status: str
    estimated_time: str
    resources: List[Dict[str, Any]]
    description: str


class PathEdge(BaseModel):
    """路径边"""
    source: str
    target: str


class LearningPathTopologyResponse(BaseModel):
    """学习路径拓扑响应"""
    total_steps: int
    current_step: int
    progress: float
    estimated_total_time: str
    nodes: List[PathNode]
    edges: List[PathEdge]


class AbilityRadarDataItem(BaseModel):
    """能力雷达数据项"""
    dimension: str
    score: float
    fullMark: int


class AbilityRadarResponse(BaseModel):
    """能力雷达响应"""
    dimensions: List[str]
    data: List[AbilityRadarDataItem]
    average_score: float


class CoreMetricsResponse(BaseModel):
    """核心指标响应"""
    resource_match_accuracy: float
    knowledge_coverage_rate: float
    answer_accuracy: float


class LearnerReportResponse(BaseModel):
    """完整学情报告响应"""
    success: bool
    learner_id: int
    learner_info: Dict[str, Any]
    blind_area_heatmap: BlindAreaHeatmapResponse
    difficulty_match_curve: DifficultyMatchCurveResponse
    learning_path_topology: LearningPathTopologyResponse
    ability_radar: AbilityRadarResponse
    core_metrics: CoreMetricsResponse
    statistics: Dict[str, Any]


class SystemMetricsResponse(BaseModel):
    """系统指标响应"""
    hallucination_rate: float
    resource_match_accuracy: float
    knowledge_coverage_rate: float
    total_learners: int
    total_resources: int
    total_answers: int
    active_sessions: int
    avg_completion_time: str
    satisfaction_score: float
    trends: List[Dict[str, Any]]


# ========== 交互式自适应导学 ==========

class SubmitAnswerRequest(BaseModel):
    """提交答题请求"""
    learner_id: int = Field(..., description="学习者ID", gt=0)
    user_id: Optional[int] = Field(None, description="用户ID")
    question_id: Optional[str] = Field(None, description="题目ID")
    question_type: str = Field(..., description="题目类型")
    question_topic: str = Field(..., description="题目主题")
    question_difficulty: int = Field(..., description="题目难度", ge=1, le=5)
    question_content: str = Field(..., description="题目内容")
    user_answer: Any = Field(..., description="用户答案")
    correct_answer: Any = Field(..., description="正确答案")
    result: Optional[str] = Field(None, description="答题结果")
    score: float = Field(..., description="得分", ge=0, le=100)
    time_spent_ms: int = Field(..., description="答题耗时(毫秒)", ge=0)
    hints_used: int = Field(0, description="使用提示次数")


class SimplifiedExplanation(BaseModel):
    """简化解释内容"""
    type: str
    title: str
    original_question: str
    user_answer: str
    correct_answer: str
    simple_explanation: str
    analogy_explanation: str
    key_points: List[str]
    practice_tips: str
    suggested_resources: List[Dict[str, Any]]


class AdvancedChallenge(BaseModel):
    """进阶挑战内容"""
    type: str
    title: str
    current_difficulty: int
    advanced_difficulty: int
    challenge_description: str
    challenge_objectives: List[str]
    estimated_time: str
    bonus_points: int
    prerequisites: List[str]
    suggested_resources: List[Dict[str, Any]]


class AgentDecision(BaseModel):
    """Agent决策"""
    decision: str
    reason: str
    confidence: float


class NextAction(BaseModel):
    """下一步动作"""
    type: str
    description: str


class ProcessAnswerResponse(BaseModel):
    """处理答题响应"""
    success: bool
    learner_id: int
    answer_record_id: int
    is_correct: bool
    score: float
    accuracy_rate: float
    agent_decision: AgentDecision
    next_action: NextAction
    generated_content: Dict[str, Any]


class InteractionHistoryItem(BaseModel):
    """交互历史项"""
    record_id: int
    session_id: str
    sequence_index: int
    question_id: str
    question_type: str
    question_topic: str
    question_difficulty: int
    user_answer: str
    correct_answer: str
    result: str
    score: float
    time_spent_ms: int
    attempt_count: int
    hints_used: int
    agent_decision: str
    decision_reason: str
    decision_confidence: float
    next_action: str
    next_resource_id: Optional[int] = None
    next_question_difficulty: Optional[int] = None
    feedback_given: bool
    feedback_content: str
    decision_log: Dict[str, Any]
    created_at: Optional[str] = None


class InteractionHistoryResponse(BaseModel):
    """交互历史响应"""
    learner_id: int
    history: List[InteractionHistoryItem]
    total: int
    page: int
    page_size: int
