import { http } from '../lib/request'
import type { LearnerProfile } from '../types'

export type GuidanceAction = 'complete' | 'snooze' | 'resume'
export type GuidanceStage = 'profile' | 'diagnosis' | 'resource' | 'guidance' | 'feedback'

export interface DashboardTask {
  taskId: number
  taskName: string
  taskType: string
  agentType?: string
  status: string
  progress: number
  flowStage?: string
  flowDescription?: string
  learnerId?: number
  createdAt?: string
  completedAt?: string
  durationMs?: number
  errorMessage?: string | null
}

export interface DashboardResource {
  id: number
  learnerId: number
  title: string
  resourceType: string
  summary?: string | null
  difficultyLevel?: number
  matchScore?: number
  status?: string
  createdAt?: string | null
}

export interface DashboardFeedback {
  recordId: number
  questionTopic?: string | null
  result: 'correct' | 'wrong' | 'partial' | string
  score: number
  feedbackContent?: string | null
  decisionReason?: string | null
  agentDecision?: string | null
  createdAt?: string | null
}

export interface GuidanceState {
  stage: GuidanceStage
  onboardingCompletedAt?: string | null
  dashboardGuidanceDismissedAt?: string | null
}

export interface LearnerDashboardSummary {
  learningPhase: string
  learningPhaseScore: number
  progress: number
  averageAbility: number
  totalAnswers: number
  correctAnswers: number
  accuracy: number | null
  streakDays: number
  totalStudyHours: number
  lastActiveAt?: string | null
}

export interface LearnerDashboardData {
  profile: LearnerProfile | null
  summary: LearnerDashboardSummary | null
  recentResources: DashboardResource[]
  currentTasks: DashboardTask[]
  recentFeedback: DashboardFeedback[]
  facts: {
    hasDiagnosis: boolean
    resourceCount: number
    answerCount: number
    completedLearningRound: boolean
  }
  guidance: GuidanceState
  moduleErrors: Record<string, string>
}

export interface TeacherDashboardLearner extends LearnerProfile {
  progress: number
  pendingTaskCount: number
}

export interface TeacherDashboardData {
  summary: {
    totalLearners: number
    averageProgress: number | null
    atRiskCount: number
    pendingTaskCount: number
  }
  learners: TeacherDashboardLearner[]
  atRiskLearners: Array<{
    id: number
    name?: string | null
    progress: number
    blindAreas: string[]
    lastActiveAt?: string | null
  }>
  stalledTasks: DashboardTask[]
  blindAreaDistribution: Array<{ topic: string; count: number }>
  pagination: {
    page: number
    pageSize: number
    total: number
    totalPages: number
  }
  scope: { type: string; learnerCount: number }
  moduleErrors: Record<string, string>
}

export const dashboardApi = {
  getLearner(options?: { signal?: AbortSignal; silent?: boolean }): Promise<LearnerDashboardData> {
    return http.get<LearnerDashboardData>('/dashboard/learner', undefined, options)
  },

  getTeacher(
    params?: { page?: number; pageSize?: number; keyword?: string },
    options?: { signal?: AbortSignal; silent?: boolean },
  ): Promise<TeacherDashboardData> {
    return http.get<TeacherDashboardData>('/dashboard/teacher', params, options)
  },

  updateGuidance(
    action: GuidanceAction,
  ): Promise<Pick<GuidanceState, 'onboardingCompletedAt' | 'dashboardGuidanceDismissedAt'>> {
    return http.patch('/dashboard/learner/guidance', { action })
  },
}
