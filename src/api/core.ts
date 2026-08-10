import { http, PagedData } from '../lib/request'
import type { InteractionHistoryRecord, InteractionHistoryResponse, LearnerReport, LearningResource, SystemMetrics, MetricDefinition, PaginationParams } from '../types'

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
  difficulty: number
  knowledgePoints?: string[]
  generationMethod?: string
}

export interface GenerateTutoringQuestionsRequest {
  learnerId: number
  topic?: string
  difficulty?: number
  questionCount?: number
  replacePending?: boolean
}

export interface GenerateTutoringQuestionsResponse {
  questions: TutoringQuestion[]
  generationMethod?: string
}

export interface SubmitAnswerRequest {
  learnerId: number
  questionId: string
  userAnswer: string
  timeSpentMs: number
  hintsUsed: number
  sessionId?: string
  sequenceIndex?: number
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
    // 报告生成涉及 LLM 路径规划（推理模型首次调用需 30-60s），使用长超时
    return http.get<LearnerReport>(`/report/learner/${learnerId}`, undefined, { timeout: 120000 })
  },

  downloadLearnerReportPdf(learnerId: number): Promise<Blob> {
    // PDF 导出内部同样会生成报告（含 LLM 调用），使用长超时
    return http.get<Blob>(`/report/learner/${learnerId}/pdf`, undefined, { timeout: 120000 })
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

  getSystemMetrics(options?: { silent?: boolean }): Promise<SystemMetrics> {
    return http.get<SystemMetrics>('/report/metrics', undefined, options)
  },

  getMetricDefinitions(): Promise<MetricDefinition[]> {
    return http.get<MetricDefinition[]>('/report/metrics/definitions')
  },

  submitAnswer(data: SubmitAnswerRequest): Promise<unknown> {
    return http.post('/tutoring/answer', data)
  },

  async getInteractionHistory(learnerId: number, params?: PaginationParams & { sessionId?: string }): Promise<InteractionHistoryResponse> {
    const response = await http.get<{
      items?: InteractionHistoryRecord[]
      history?: InteractionHistoryRecord[]
      total?: number
      page?: number
      pageSize?: number
    }>(`/tutoring/history/${learnerId}`, params as Record<string, string | number | boolean | undefined>)
    return {
      learnerId,
      history: response.history ?? response.items ?? [],
      total: response.total ?? 0,
      page: response.page ?? 1,
      pageSize: response.pageSize ?? params?.pageSize ?? 20,
    }
  },

  deleteInteractionHistory(
    learnerId: number,
    params?: { recordId?: number; sessionId?: string },
  ): Promise<{ deletedCount: number }> {
    return http.delete<{ deletedCount: number }>(`/tutoring/history/${learnerId}`, params, { silent: true })
  },

  getDecisionLogic(): Promise<unknown> {
    return http.get('/tutoring/decision-logic')
  },

  getTutoringQuestions(learnerId: number): Promise<TutoringQuestion[]> {
    return http.get<TutoringQuestion[]>('/tutoring/questions', { learnerId })
  },

  generateTutoringQuestions(data: GenerateTutoringQuestionsRequest): Promise<GenerateTutoringQuestionsResponse> {
    return http.post<GenerateTutoringQuestionsResponse>('/tutoring/questions/generate', data, {
      timeout: 120000,
      silent: true,
    })
  },
}
