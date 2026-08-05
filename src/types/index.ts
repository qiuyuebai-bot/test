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
  sliceIndex: number
  content: string
  contentType: string
  similarity: number
  keywords: string[]
  isKeyPoint: boolean
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

export interface LearningResource {
  id: number
  title: string
  resourceType: 'guide' | 'exercise' | 'lecture' | 'case' | 'quiz' | 'roadmap'
  targetLearnerId: number
  contentSummary: string
  contentPath?: string
  contentType: 'pdf' | 'html' | 'video' | 'text'
  qualityScore: number
  hallucinationDetected: boolean
  reviewStatus: 'pending' | 'approved' | 'rejected' | 'revised'
  versionNumber: number
  generatedByAgent: string
  generationMethod?: string
  createdByAgent?: string
  generationTime: string
  metaData?: Record<string, unknown>
  difficultyLevel?: number
  targetTopic?: string
  content?: string
  createdAt?: string
  status?: string
  matchScore?: number
  hasHallucination?: boolean
  sourceSliceIds?: number[]
  summary?: string
  learnerId?: number
  version?: number
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
  matchScore: number[]
  learnerAbility: number[]
  data: LearnerReportMatchCurveItem[]
  learnerAbilityRaw: number
}

export interface LearnerReportMatchCurveItem {
  name: string
  difficulty: number
  matchScore: number
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
  resourceMatchAccuracy: number
  knowledgeCoverageRate: number
  answerAccuracy: number
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
  questionDifficulty: number
  userAnswer: unknown
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

export interface SystemMetrics {
  hallucinationRate: number | null
  totalChecks?: number
  evaluatedChecks?: number
  pendingChecks?: number
  confirmedHallucinations?: number
  evidenceGaps?: number
  passRate?: number | null
  hasSufficientSample?: boolean
  minimumSampleSize?: number
  resourceMatchAccuracy: number
  knowledgeCoverageRate: number
  totalLearners: number
  totalResources: number
  totalAnswers: number
  totalTasks: number
  tasksCompleted: number
  avgResponseTime: number
  avgCompletionTime: string
  activeSessions: number
  satisfactionScore: number
  trends: MetricTrend[]
}

export interface MetricTrend {
  date: string
  hallucinationRate: number
  resourceMatchAccuracy: number
  knowledgeCoverageRate: number
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

export type TrainingStatus = 'planning' | 'ongoing' | 'completed' | 'cancelled'
export type TrainingType = 'standard' | 'transfer'

export interface TrainingProject {
  id: number
  companyName: string
  trainingName: string
  trainingType: TrainingType
  description?: string
  industry?: string
  modules: string[]
  participantCount: number
  participants: number[]
  responsiblePerson?: string
  startDate?: string
  endDate?: string
  estimatedDuration: number
  status: TrainingStatus
  progressPercentage: number
  completedModules: number
  isTransferTraining: boolean
  transferFromPosition?: string
  transferToPosition?: string
  skillGapAnalysis?: Record<string, unknown>
  passRate: number
  averageScore: number
  satisfactionRate: number
  totalResourcesUsed: number
  totalTasksCompleted: number
  createdAt?: string
  updatedAt?: string
}

export interface TrainingStats {
  companies: number
  learners: number
  passRate: number
  avgScore: number
  totalTrainings: number
  ongoingTrainings: number
  completedTrainings: number
}

export interface TransferRecord {
  id: number
  name: string
  from: string
  to: string
  company: string
  completion: number
  skillGap: number
}

export interface SkillGapItem {
  skill: string
  current: number
  required: number
  gap: number
}

export interface CreateTrainingData {
  companyName: string
  trainingName: string
  trainingType?: TrainingType
  description?: string
  industry?: string
  modules?: string[]
  participantCount?: number
  participants?: number[]
  responsiblePerson?: string
  startDate?: string
  endDate?: string
  estimatedDuration?: number
  isTransferTraining?: boolean
  transferFromPosition?: string
  transferToPosition?: string
  skillGapAnalysis?: Record<string, unknown>
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
