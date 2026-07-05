import { http, PagedData } from '../lib/request'
import type { LearnerProfile, PaginationParams } from '../types'

export interface LearnerListParams extends PaginationParams {
  keyword?: string
  educationLevel?: string
  targetIndustry?: string
  learningStyle?: string
  isAnonymized?: boolean
}

export interface CreateLearnerData {
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
  theoreticalFoundation?: number
  programmingAbility?: number
  algorithmDesign?: number
  systemArchitecture?: number
  dataAnalysis?: number
  engineeringPractice?: number
  knowledgeBlindAreas?: string[]
}

export const learnerApi = {
  getList(params?: LearnerListParams): Promise<PagedData<LearnerProfile>> {
    return http.get<PagedData<LearnerProfile>>('/learners', params as Record<string, string | number | boolean | undefined>)
  },

  getById(id: number): Promise<LearnerProfile> {
    return http.get<LearnerProfile>(`/learners/${id}`)
  },

  create(data: CreateLearnerData): Promise<{ id: number }> {
    return http.post<{ id: number }>('/learners', data)
  },

  update(id: number, data: Partial<CreateLearnerData>): Promise<{ id: number }> {
    return http.put<{ id: number }>(`/learners/${id}`, data)
  },

  delete(id: number): Promise<null> {
    return http.delete<null>(`/learners/${id}`)
  },

  analyze(id: number): Promise<unknown> {
    return http.post(`/learners/${id}/analyze`)
  },

  getBlindAreas(id: number): Promise<{ blindAreas: string[]; weakDimensions: unknown[] }> {
    return http.get(`/learners/${id}/blind-areas`)
  },

  getAnswerRecords(id: number, params?: PaginationParams): Promise<PagedData<unknown>> {
    return http.get<PagedData<unknown>>(`/learners/${id}/answers`, params as Record<string, string | number | boolean | undefined>)
  },
}
