import type { TutoringQuestion } from '@/api/core'
import type { InteractionHistoryRecord } from '@/types'

export type GuidancePhase =
  | 'initializing'
  | 'ready'
  | 'generatingQuestion'
  | 'answering'
  | 'submitting'
  | 'feedback'
  | 'preparingNext'
  | 'batchReview'
  | 'completed'

export interface HistoryRecord {
  recordId: string
  sessionId: string | null
  sequenceIndex: number | null
  questionTopic: string
  questionContent: string
  userAnswer: unknown
  feedbackContent: string
  questionDifficulty: number
  result: 'correct' | 'wrong' | 'partial'
  agentDecision: string
  decisionReason: string
  createdAt: string
  score: number
}

export type GuidanceMode = 'adaptive' | 'batch'

export interface SessionConfig {
  /** Optional at the type boundary so pre-mode persisted sessions remain readable. */
  mode?: GuidanceMode
  topic: string
  difficulty?: number
  questionCount: number
  sessionId?: string
}

export interface PersistedSession {
  config: SessionConfig
  questions: TutoringQuestion[]
  currentQuestion: number
  selectedAnswers: number[]
  showResult: boolean
  correctCount: number
  generationMethod: string | null
  submitResult: SubmitResult | null
  answersByQuestionId?: Record<string, number[]>
  batchResult?: BatchSubmitResult | null
}

export interface GeneratedContent {
  type?: string
  title?: string
  simpleExplanation?: string
  knowledgeExpansion?: {
    type?: string
    title?: string
    overview?: string
    keyPoints?: string[]
    application?: string
    pitfalls?: string[]
    suggestedResources?: Array<{ resourceId: number; title: string; type: string; difficultyLevel?: number }>
  }
  keyPoints?: string[]
  practiceTips?: string
  recommendation?: string
  challengeDescription?: string
  challengeObjectives?: string[]
  estimatedTime?: string
  bonusPoints?: number
  suggestedResources?: Array<{ resourceId: number; title: string; type: string; matchScore?: number; difficultyLevel?: number }>
}

export interface SubmitResult {
  isCorrect: boolean
  score: number
  agentDecision?: { decision?: string; reason?: string; confidence?: number }
  nextAction?: { type?: string; description?: string }
  nextQuestionDifficulty?: number
  generatedContent?: GeneratedContent
}

export interface BatchQuestionResult {
  questionId: string
  isCorrect: boolean
  score: number
  userAnswer: string[]
  correctAnswer: string[]
  explanation: string
  knowledgePoints: string[]
}

export interface BatchSubmitResult {
  sessionId: string
  total: number
  correctCount: number
  score: number
  questions: BatchQuestionResult[]
}

export interface RecommendationOption {
  topic: string
  reason: string
  source: 'blind_spot' | 'recent_resource' | 'recent_wrong_answer' | 'target_position' | 'fallback'
}

export interface GuidanceRecommendation {
  primaryTopic: string | null
  alternatives: RecommendationOption[]
  recommendedDifficulty: number | null
  reason: string
  source: RecommendationOption['source']
}

export interface GuidanceState {
  phase: GuidancePhase
  hydrated: boolean
  questions: TutoringQuestion[]
  currentQuestion: number
  selectedAnswers: number[]
  answersByQuestionId: Record<string, number[]>
  showResult: boolean
  sessionConfig: SessionConfig | null
  correctCount: number
  generationMethod: string | null
  submitResult: SubmitResult | null
  batchResult: BatchSubmitResult | null
  pendingNextDifficulty: number | null
  generationError: string | null
  submissionError: string | null
  nextQuestionError: string | null
  loadError: string | null
  historyRecords: HistoryRecord[]
  historyLoading: boolean
  historyError: string | null
}

export interface SubmitDataRaw {
  isCorrect?: boolean
  is_correct?: boolean
  score?: number
  generatedContent?: GeneratedContent
  generated_content?: GeneratedContent
  agentDecision?: { decision?: string; reason?: string; confidence?: number }
  agent_decision?: { decision?: string; reason?: string; confidence?: number }
  nextAction?: { type?: string; description?: string }
  next_action?: { type?: string; description?: string }
  nextQuestionDifficulty?: number
  next_question_difficulty?: number
}

export type SubmitResultRaw = { data?: SubmitDataRaw } & SubmitDataRaw

export function mapHistoryRecord(record: InteractionHistoryRecord): HistoryRecord {
  return {
    recordId: String(record.recordId),
    sessionId: record.sessionId ?? null,
    sequenceIndex: record.sequenceIndex ?? null,
    questionTopic: record.questionTopic ?? '',
    questionContent: record.questionContent ?? '',
    userAnswer: record.userAnswer,
    feedbackContent: record.feedbackContent ?? '',
    questionDifficulty: record.questionDifficulty ?? 0,
    result: record.result === 'correct' ? 'correct' : record.result === 'wrong' ? 'wrong' : 'partial',
    agentDecision: record.agentDecision ?? record.nextAction ?? '',
    decisionReason: record.decisionReason ?? '',
    createdAt: record.createdAt ?? '',
    score: record.score,
  }
}
