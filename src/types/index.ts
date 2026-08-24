export type UserRole = 'admin' | 'teacher' | 'learner' | 'enterprise'

export interface UserInfo {
  userId: number
  username: string
  email?: string
  phone?: string
  role: UserRole
  isActive: boolean
  isVerified: boolean
  enterpriseName?: string
  lastLoginAt?: string
  createdAt?: string
}

export interface LoginRequest {
  username: string
  password: string
}

export interface AbilityAssessment {
  status: 'estimated' | 'insufficient_evidence' | string
  estimatedScore: number | null
  confidence: number
  answeredCount: number
  manualAdjustment?: number
  lastAssessedAt?: string
}

export interface LoginResponse {
  userId: number
  username: string
  role: UserRole
  accessToken: string
  refreshToken: string
  tokenType: string
}

export interface LearnerProfile {
  id: number
  userId?: number
  realName: string
  educationLevel: string
  major: string
  graduationYear?: number
  currentPosition?: string
  learningStyle?: string
  preferredDifficulty?: number
  dailyStudyTime?: number
  targetIndustry?: string
  targetPosition?: string
  learningGoal?: string
  theoreticalFoundation: number
  programmingAbility: number
  algorithmDesign: number
  systemArchitecture: number
  dataAnalysis: number
  engineeringPractice: number
  averageAbility: number
  abilityAssessments?: Record<string, AbilityAssessment>
  diagnosticStatus?: 'not_started' | 'in_progress' | 'completed' | 'failed' | string
  diagnosticCompletedAt?: string
  knowledgeBlindAreas: string[]
  isDataAnonymized: boolean
  createdAt?: string
  updatedAt?: string
}

export interface KnowledgeDoc {
  id: number
  title: string
  domain: string
  category: string
  totalSlices: number
  indexedSlices: number
  status: 'indexed' | 'pending' | 'error'
  source?: string
  uploadTime: string
  fileType?: string
  fileSize?: number
  version: string
  fileName?: string
  industry?: string
  coverageRate?: number
  tags?: string[]
  author?: string
  isEnabled?: boolean
  contentPreview?: string
  createdAt?: string
  updatedAt?: string
  indexedAt?: string
  errorMessage?: string
}

export interface KnowledgeSlice {
  id: number
  docId: number
  sliceIndex: number
  content: string
  contentType?: string
  sliceType?: string
  title?: string
  tokens?: number
  wordCount?: number
  keywords: string[]
  isIndexed?: boolean
  qualityScore?: number
  referenceCount?: number
  createdAt?: string
}

export interface KnowledgeSearchResult {
  sliceId: number
  docId: number
  docTitle: string
  industry?: string
  title?: string
  sliceIndex: number
  content: string
  contentType?: string
  similarity: number
  keywords: string[]
  highlightedContent?: string
  originType?: string
  originResourceId?: number
  isKeyPoint?: boolean
}

export interface KnowledgeSearchResponse {
  query: string
  totalResults: number
  results: KnowledgeSearchResult[]
  searchDurationMs: number
}

export type AgentType = 'diagnosis' | 'generation' | 'review'
export type AgentState = 'idle' | 'running' | 'waiting' | 'completed' | 'failed' | 'error'
export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
export type TaskType =
  | 'diagnosis'
  | 'generation'
  | 'review'
  | 'full_flow'
  | 'learner_diagnosis'
  | 'resource_generation'
  | 'full_pipeline'

export interface AgentStatus {
  agentType: AgentType
  agentName: string
  state: AgentState
  currentTaskId?: number
  totalTasksHandled: number
  successCount: number
  failureCount: number
  avgLatencyMs?: number
  lastHeartbeat?: string
  description?: string
}

export interface AgentTask {
  taskId: number
  taskName: string
  taskType: TaskType
  status: TaskStatus
  flowStage: string
  progress: number
  assignedAgentId?: string
  learnerId: number
  resourceId?: number
  createdAt?: string
  updatedAt?: string
  completedAt?: string
  errorMessage?: string
  metadata?: Record<string, unknown>
}

export interface TaskLog {
  stage: string
  progress: number
  description: string
  timestamp: string
}

export interface DebateRecord {
  round: number
  debateType: string
  hasConflict: boolean
  conflictType?: string
  conflictSeverity?: string
  isHallucination: boolean
  hallucinationType?: string
  hallucinationScore?: number
  judgeStandpoint: Record<string, unknown>
  generationCounterargument: Record<string, unknown>
  conflictPoints: string[]
  corrections: string[]
  resolutionStatus: string
  judgeDecision?: string
  judgeConfidence?: number
  createdAt?: string
  resolvedAt?: string
}

export type EvidenceDecision = 'approved' | 'revised_approved' | 'rejected' | 'insufficient_evidence'

export interface EvidenceConfidenceBreakdown {
  key: string
  label: string
  weight: number
  score: number
}

export interface TaskEvidenceDebate {
  round: number
  debateType?: string
  hasConflict: boolean
  conflictType?: string
  conflictSeverity?: string
  isHallucination: boolean
  hallucinationScore?: number
  judgeStandpoint: Record<string, unknown>
  generationCounterargument: Record<string, unknown>
  conflictPoints: Array<string | Record<string, unknown>>
  corrections: Array<string | Record<string, unknown>>
  resolutionStatus?: string
  judgeDecision?: string
  judgeConfidence?: number
  originalContent?: string
  correctedContent?: string
  correctionReason?: string
  createdAt?: string
  resolvedAt?: string
}

export interface TaskEvidence {
  task: AgentTask & { resourceId?: number }
  learner: {
    id?: number
    name?: string | null
    diagnosis?: Record<string, unknown> | null
  }
  summary: {
    finalDecision: EvidenceDecision
    confidence: number | null
    credibility?: string
    hasSufficientEvidence: boolean
    stats: {
      debateRounds: number
      issuesFound: number
      correctionsApplied: number
      sourceCount: number
    }
    keyCorrection?: {
      original: string
      revised: string
      description: string
      reason: string
    } | null
    confidenceBreakdown: EvidenceConfidenceBreakdown[]
  }
  timeline: Array<{
    stage: string
    label: string
    status: 'completed' | 'active' | 'pending'
    progress: number
    description?: string
    timestamp?: string
  }>
  debateRecords: TaskEvidenceDebate[]
  knowledgeEvidence: Array<{
    sliceId: number
    docId: number
    docTitle: string
    title?: string
    content: string
    sliceIndex: number
    similarity?: number | null
    qualityScore?: number | null
    relation: string
  }>
  sourceDocuments: Array<{
    id: number
    title: string
    industry?: string
    source?: string
    version?: string
    status?: string
    isEnabled?: boolean
  }>
  initialGeneration: { content: string }
  finalGeneration: { content: string; title?: string | null; resourceType?: string | null }
  revisionComparison: {
    originalContent: string
    finalContent: string
    corrections: Array<string | Record<string, unknown>>
    hasChanges: boolean
  }
  decision: {
    releaseReason: string
    unresolvedRisks: string[]
    reviewRules: string[]
  }
}

export interface LearningResource {
  id: number
  title: string
  resourceType: 'guide' | 'exercise' | 'lecture' | 'case' | 'quiz' | 'roadmap'
  targetLearnerId: number
  contentSummary: string
  contentPath?: string
  contentType: 'pdf' | 'html' | 'video' | 'text'
  formatType?: 'md' | 'text' | 'html' | 'json'
  qualityScore: number | null
  hallucinationDetected: boolean
  validationPassed?: boolean
  reviewStatus: 'pending' | 'approved' | 'rejected' | 'revised'
  versionNumber: number
  generatedByAgent: string
  generationMethod?: string
  createdByAgent?: string
  generationTime: string
  metaData?: Record<string, unknown>
  difficultyLevel?: number
  knowledgeTopic?: string
  targetTopic?: string
  content?: string
  contentJson?: Record<string, unknown>
  createdAt?: string
  status?: string
  matchScore?: number | null
  hasHallucination?: boolean
  sourceSliceIds?: number[]
  summary?: string
  learnerId?: number
  version?: string | number
  isLatest?: boolean
}

export interface DiagnosisResult {
  learnerId: number
  abilityScores: Record<string, number>
  blindAreas: BlindArea[]
  difficultyRecommendation: number
  learningSuggestions: string[]
  summary: string
}

export interface BlindArea {
  area: string
  level: 'critical' | 'important' | 'normal'
  score: number
  description: string
}

export interface LearnerReport {
  success: boolean
  learnerId: number
  learnerInfo: LearnerReportInfo
  blindAreaHeatmap: BlindAreaHeatmap
  difficultyMatchCurve: DifficultyMatchCurve
  learningPathTopology: LearningPathTopology
  abilityRadar: AbilityRadar
  coreMetrics: LearnerReportCoreMetrics
  statistics: LearnerReportStatistics
  hallucinationReport?: import('../lib/hallucinationEvidence').HallucinationReport
}

export interface LearnerReportInfo {
  id: number
  name: string
  education: string
  major: string
  learningStyle: string
  targetIndustry: string
  targetPosition: string
}

export interface BlindAreaHeatmap {
  labels: string[]
  severityLevels: string[]
  severityLabels: string[]
  data: LearnerReportHeatmapItem[]
}

export interface LearnerReportHeatmapItem {
  dimension: string
  dimensionKey: string
  severity: string
  severityLabel: string
  value: number
  score: number
  isBlind: boolean
  description: string
}

export interface DifficultyMatchCurve {
  labels: string[]
  difficulty: number[]
  matchScore: Array<number | null>
  learnerAbility: number[]
  data: LearnerReportMatchCurveItem[]
  learnerAbilityRaw: number
}

export interface LearnerReportMatchCurveItem {
  name: string
  difficulty: number
  matchScore: number | null
  learnerAbility: number
  resourceId: number
  title: string
}

export interface LearningPathTopology {
  totalSteps: number
  currentStep: number
  progress: number
  estimatedTotalTime: string
  nodes: LearnerReportPathNode[]
  edges: LearnerReportPathEdge[]
}

export interface LearnerReportPathNode {
  id: string
  name: string
  difficulty: number
  status: string
  estimatedTime: string
  resources: LearnerReportPathResource[]
  description: string
}

export interface LearnerReportPathResource {
  resourceId?: number
  title?: string
  name?: string
  type?: string
  matchScore?: number | null
}

export interface LearnerReportPathEdge {
  source: string
  target: string
}

export interface AbilityRadar {
  dimensions: string[]
  data: LearnerReportRadarItem[]
  averageScore: number
}

export interface LearnerReportRadarItem {
  dimension: string
  score: number
  fullMark: number
}

export interface LearnerReportCoreMetrics {
  resourceMatchAccuracy: number | null
  knowledgeCoverageRate: number | null
  answerAccuracy: number | null
  resourceMatchScore?: number | null
  resourceMatchEffectiveness?: number | null
  metrics?: MetricResult[]
  metricResults?: MetricResult[]
}

export interface LearnerReportStatistics {
  totalResources: number
  totalAnswers: number
  avgAnswerScore: number
  knowledgeBlindCount: number
}

export interface InteractionHistoryRecord {
  recordId: number
  sessionId: string | null
  sequenceIndex: number | null
  questionId: number | null
  questionType: string
  questionTopic: string | null
  questionContent?: string | null
  questionDifficulty: number
  userAnswer: unknown
  feedbackContent?: string | null
  result: string
  score: number
  timeSpentMs: number
  agentDecision: string | null
  decisionReason: string | null
  decisionConfidence: number | null
  nextAction: string | null
  nextResourceId: number | null
  feedbackGiven: boolean | null
  createdAt: string | null
}

export interface InteractionHistoryResponse {
  learnerId: number
  history: InteractionHistoryRecord[]
  total: number
  page: number
  pageSize: number
}

export type MetricStatus = 'ready' | 'collecting' | 'no_data' | 'not_applicable' | 'stale' | 'error'

export interface MetricResult {
  metricId: string
  displayName: string
  scope: 'global' | 'learner' | string
  scopeId: number | null
  value: number | null
  unit: string
  status: MetricStatus
  numerator: number
  denominator: number
  sampleCount: number
  minimumSampleSize: number
  formula: string
  source: string[]
  calculatedAt: string
  message?: string | null
  metadata?: Record<string, unknown> | null
}

export interface MetricDefinition {
  metricId: string
  displayName: string
  unit: string
  formula: string
  source: string[]
  scopes: string[]
  minimumSampleSize: number
  freshnessSeconds?: number | null
}

export interface SystemMetrics {
  metrics?: MetricResult[]
  metricRegistry?: MetricDefinition[]
  hallucinationRate: number | null
  totalChecks?: number
  evaluatedChecks?: number
  pendingChecks?: number
  confirmedHallucinations?: number
  evidenceGaps?: number
  passRate?: number | null
  hasSufficientSample?: boolean
  minimumSampleSize?: number
  resourceMatchAccuracy: number | null
  knowledgeCoverageRate: number | null
  knowledgeIndexCoverageRate?: number | null
  learningBlindSpotCoverageRate?: number | null
  resourceMatchScore?: number | null
  resourceMatchEffectiveness?: number | null
  answerAccuracy?: number | null
  metricsStatus?: 'ready' | 'no_data' | 'degraded'
  metricsSource?: string
  snapshotAvailable?: boolean
  calculatedAt?: string
  totalLearners: number
  totalResources: number
  totalAnswers: number
  totalTasks: number
  tasksCompleted: number
  /** Agent task counters returned by the performance metrics source. */
  failedTasks?: number
  runningTasks?: number
  taskSuccessRate?: number | null
  avgResponseTime: number
  avgCompletionTime: string
  activeSessions: number
  satisfactionScore: number
  trends: MetricTrend[]
}

export interface MetricTrend {
  date: string
  hallucinationRate: number | null
  resourceMatchAccuracy: number | null
  knowledgeCoverageRate: number | null
  resourceMatchScore?: number | null
  resourceMatchEffectiveness?: number | null
  knowledgeIndexCoverage?: number | null
}

export interface PaginationParams {
  page?: number
  pageSize?: number
}

export interface PagedResult<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
  totalPages: number
}

// ===========================================
// 数据隐私与合规
// ===========================================
export interface PrivacyComplianceItem {
  id: number
  category: string
  requirement: string
  status: 'pass' | 'pending' | 'fail'
  lastCheck: string
  detail?: string
}

export interface PrivacyAnonymizationRule {
  id: number
  field: string
  original: string
  anonymized: string
  method: string
  status: 'active' | 'draft'
}

export interface PrivacyPermissionItem {
  role: string
  dataAccess: string
  exportAllowed: boolean
  deleteAllowed: boolean
}

export interface PrivacyKeyInfo {
  name: string
  description: string
  algorithm: string
  maskedValue: string
  isConfigured: boolean
}

export interface PrivacyDocument {
  title: string
  date: string
  url: string
}

export interface PrivacyOverview {
  complianceStatus: 'compliant' | 'warning'
  encryptionStandard: string
  anonymizationRuleCount: number
  pendingCount: number
}

export interface AnonymizationTestResult {
  field: string
  original: string
  anonymized: string
  method: string
}
export type {
  Credibility,
  HallucinationClaim,
  HallucinationClaimStatus,
  HallucinationCitation,
  HallucinationReport,
} from '../lib/hallucinationEvidence'
