"""
核心业务模块 Pydantic Schema
包含：个性化资源生成、学情报告、自适应导学
"""
from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel, Field, field_validator


# ========== 个性化资源生成 ==========

class GenerateResourcesRequest(BaseModel):
    """生成资源请求"""
    learner_id: int = Field(..., description="学习者ID", gt=0)
    target_topic: str = Field(..., description="目标主题", min_length=1)
    industry: Optional[str] = Field(None, description="行业领域")

    @field_validator("target_topic")
    @classmethod
    def normalize_target_topic(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("目标主题不能为空")
        return value


class GeneratedResourceItem(BaseModel):
    """生成的资源项"""
    resource_type: str
    resource_type_name: str
    resource_title: str
    difficulty_level: int
    content: str
    content_json: Dict[str, Any]
    word_count: int
    match_score: Optional[float] = None
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
    match_score: Optional[float] = None
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
    match_score: Optional[float] = None
    learner_ability: float
    resource_id: int
    title: str


class DifficultyMatchCurveResponse(BaseModel):
    """难度匹配曲线响应"""
    labels: List[str]
    difficulty: List[int]
    match_score: List[Optional[float]]
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
    resource_match_accuracy: Optional[float] = None
    knowledge_coverage_rate: Optional[float] = None
    answer_accuracy: Optional[float] = None


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
    hallucination_rate: Optional[float] = None
    total_checks: int = 0
    evaluated_checks: int = 0
    pending_checks: int = 0
    confirmed_hallucinations: int = 0
    evidence_gaps: int = 0
    state_counts: Dict[str, int] = Field(default_factory=dict)
    invalid_records: int = 0
    high_risk_checks: int = 0
    high_risk_reviewed: int = 0
    high_risk_review_coverage: Optional[float] = None
    pass_rate: Optional[float] = None
    has_sufficient_sample: bool = False
    minimum_sample_size: int = 10
    formal_minimum_sample_size: int = 60
    target_percent: float = 5.0
    operator: str = "<"
    policy_version: str = "hallucination-rate-v1"
    rolling_30d: Optional[Dict[str, Any]] = None
    resource_match_accuracy: Optional[float] = None
    knowledge_coverage_rate: Optional[float] = None
    knowledge_index_coverage_rate: Optional[float] = None
    learning_blind_spot_coverage_rate: Optional[float] = None
    metrics_status: str = "no_data"
    metrics_source: str = "realtime"
    snapshot_available: bool = False
    calculated_at: Optional[str] = None
    total_learners: int
    total_resources: int
    total_answers: int
    active_sessions: int
    avg_completion_time: str
    satisfaction_score: float
    trends: List[Dict[str, Any]]


# ========== 交互式自适应导学 ==========

class GenerateTutoringQuestionsRequest(BaseModel):
    """Request an ungraded, dynamically generated practice set."""
    learner_id: int = Field(..., description="学习者ID", gt=0)
    topic: Optional[str] = Field(None, description="目标知识点；为空时使用最近的分阶测试题主题", max_length=200)
    difficulty: Optional[int] = Field(None, description="题目难度；为空时使用学习者推荐难度", ge=1, le=5)
    question_count: int = Field(10, description="question count", ge=1, le=10)
    replace_pending: bool = Field(False, description="是否替换该主题下尚未作答的旧题")


    assessment_mode: Literal["practice", "batch_practice"] = Field("practice", description="assessment mode")
    session_id: Optional[str] = Field(None, description="batch session id", max_length=100)
    training_context: Optional[Dict[str, Any]] = Field(None, description="岗位培训阶段上下文")


class SubmitAnswerRequest(BaseModel):
    """提交答题请求。动态题由服务端根据 question_id 判分。"""
    learner_id: int = Field(..., description="学习者ID", gt=0)
    question_id: Optional[str] = Field(None, description="题目ID")
    user_answer: Any = Field(..., description="用户答案")
    time_spent_ms: int = Field(..., description="答题耗时(毫秒)", ge=0)
    hints_used: int = Field(0, description="使用提示次数")
    session_id: Optional[str] = Field(None, description="自适应导学会话ID", max_length=100)
    sequence_index: Optional[int] = Field(None, description="会话内题目序号", ge=1)

    # Legacy seed-bank fields remain optional while clients migrate. They are ignored for server-issued questions.
    question_type: Optional[str] = Field(None, description="题目类型")
    question_topic: Optional[str] = Field(None, description="题目主题")
    question_difficulty: Optional[int] = Field(None, description="题目难度", ge=1, le=5)
    question_content: Optional[str] = Field(None, description="题目内容")
    correct_answer: Optional[Any] = Field(None, description="旧题库答案")
    score: Optional[float] = Field(None, description="旧题库得分", ge=0, le=100)


class BatchAnswerItem(BaseModel):
    question_id: str = Field(..., min_length=1, max_length=64)
    user_answer: Any = Field(...)
    sequence_index: int = Field(..., ge=1)


class SubmitBatchRequest(BaseModel):
    learner_id: int = Field(..., gt=0)
    session_id: str = Field(..., min_length=1, max_length=100)
    answers: List[BatchAnswerItem] = Field(..., min_length=1, max_length=10)


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
