import { http, PagedData } from '../lib/request'
import type { LearnerReport, LearningResource, SystemMetrics, PaginationParams } from '../types'

export interface GenerateResourcesRequest {
  learnerId: number
  targetTopic: string
  industry?: string
}

export interface TutoringQuestion {
  id: string
  type: 'single' | 'multiple'
  topic: string
  question: string
  options: string[]
  correctAnswer: string
  correctIndex?: number
  correctIndexes?: number[]
  difficulty: number
}

export interface SubmitAnswerRequest {
  learnerId: number
  questionId: string
  questionType: string
  questionTopic: string
  questionDifficulty: number
  questionContent: string
  userAnswer: string
  correctAnswer: string
  score: number
  timeSpentMs: number
  hintsUsed: number
}

export const coreApi = {
  generateResources(data: GenerateResourcesRequest): Promise<{ taskId: string; learnerId: number; targetTopic: string }> {
    return http.post('/resources/generate', data)
  },

  generateResourcesSync(data: GenerateResourcesRequest): Promise<unknown> {
    return http.post('/resources/generate/sync', data)
  },

  getTaskStatus(taskId: string): Promise<{ taskId: string; status: string; ready: boolean; progress?: number; stage?: string; message?: string }> {
    return http.get(`/tasks/${taskId}/status`)
  },

  getResourceList(params?: PaginationParams & { learnerId?: number; resourceType?: string; difficultyLevel?: number; status?: string }): Promise<PagedData<LearningResource>> {
    return http.get<PagedData<LearningResource>>('/resources', params as Record<string, string | number | boolean | undefined>)
  },

  getResourceDetail(id: number): Promise<LearningResource> {
    return http.get<LearningResource>(`/resources/${id}`)
  },

  exportResource(id: number, format: 'txt' | 'md' = 'txt'): Promise<Blob> {
    return http.get<Blob>(`/resources/${id}/export`, { format })
  },

  getLearnerReport(learnerId: number): Promise<LearnerReport> {
    return http.get<LearnerReport>(`/report/learner/${learnerId}`)
  },

  getHeatmap(learnerId: number): Promise<unknown> {
    return http.get(`/report/heatmap/${learnerId}`)
  },

  getMatchCurve(learnerId: number): Promise<unknown> {
    return http.get(`/report/match-curve/${learnerId}`)
  },

  getAbilityTrend(learnerId: number): Promise<{ week: string; score: number }[]> {
    return http.get(`/report/ability-trend/${learnerId}`)
  },

  getLearningPath(learnerId: number): Promise<unknown> {
    return http.get(`/report/learning-path/${learnerId}`)
  },

  getAbilityRadar(learnerId: number): Promise<unknown> {
    return http.get(`/report/ability-radar/${learnerId}`)
  },

  getSystemMetrics(): Promise<SystemMetrics> {
    return http.get<SystemMetrics>('/report/metrics')
  },

  submitAnswer(data: SubmitAnswerRequest): Promise<unknown> {
    return http.post('/tutoring/answer', data)
  },

  getInteractionHistory(learnerId: number, params?: PaginationParams & { sessionId?: string }): Promise<PagedData<unknown>> {
    return http.get<PagedData<unknown>>(`/tutoring/history/${learnerId}`, params as Record<string, string | number | boolean | undefined>)
  },

  getDecisionLogic(): Promise<unknown> {
    return http.get('/tutoring/decision-logic')
  },

  getTutoringQuestions(): Promise<TutoringQuestion[]> {
    return http.get<TutoringQuestion[]>('/tutoring/questions')
  },
}
