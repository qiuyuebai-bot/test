import { http, PagedData } from '../lib/request'
import type {
  TrainingProject,
  TrainingStats,
  TransferRecord,
  SkillGapItem,
  CreateTrainingData,
  PaginationParams,
} from '../types'

export interface TrainingListParams extends PaginationParams {
  keyword?: string
  status?: string
  trainingType?: string
}

export const trainingApi = {
  getList(params?: TrainingListParams): Promise<PagedData<TrainingProject>> {
    return http.get<PagedData<TrainingProject>>(
      '/trainings',
      params as Record<string, string | number | boolean | undefined>,
    )
  },

  getById(id: number): Promise<TrainingProject> {
    return http.get<TrainingProject>(`/trainings/${id}`)
  },

  create(data: CreateTrainingData): Promise<{ id: number }> {
    return http.post<{ id: number }>('/trainings', data)
  },

  update(id: number, data: Partial<CreateTrainingData>): Promise<{ id: number }> {
    return http.put<{ id: number }>(`/trainings/${id}`, data)
  },

  delete(id: number): Promise<null> {
    return http.delete<null>(`/trainings/${id}`)
  },

  getStats(): Promise<TrainingStats> {
    return http.get<TrainingStats>('/trainings/stats/overview')
  },

  getTransfers(): Promise<TransferRecord[]> {
    return http.get<TransferRecord[]>('/trainings/transfers/list')
  },

  getSkillGaps(trainingId?: number): Promise<SkillGapItem[]> {
    return http.get<SkillGapItem[]>(
      '/trainings/skill-gaps/analysis',
      trainingId ? { trainingId } : undefined,
    )
  },

  batchImport(data: {
    companyName: string
    trainingName: string
    trainingType?: string
    industry?: string
    participantCount?: number
    responsiblePerson?: string
  }[]): Promise<{ successCount: number; failedCount: number }> {
    return http.post<{ successCount: number; failedCount: number }>(
      '/trainings/batch-import',
      { trainings: data },
    )
  },
}
