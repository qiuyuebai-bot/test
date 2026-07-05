import { http, PagedData } from '../lib/request'
import type { AgentStatus, AgentTask, DebateRecord, PaginationParams } from '../types'

export interface CreateTaskData {
  learnerId: number
  taskName: string
  taskType: string
  targetTopic?: string
  resourceType?: string
  industry?: string
  inputData?: Record<string, unknown>
}

export interface DiagnosisRequest {
  learnerId: number
}

export interface FullPipelineRequest {
  learnerId: number
  targetTopic: string
  resourceType?: string
  industry?: string
}

export const agentApi = {
  getAllStatus(): Promise<{ agents: AgentStatus[]; total: number }> {
    return http.get<{ agents: AgentStatus[]; total: number }>('/agent/status')
  },

  getStatus(agentType: string): Promise<AgentStatus> {
    return http.get<AgentStatus>(`/agent/status/${agentType}`)
  },

  createTask(data: CreateTaskData): Promise<{ taskId: number }> {
    return http.post<{ taskId: number }>('/agent/tasks', data)
  },

  startTask(taskId: number): Promise<{ taskId: number }> {
    return http.post<{ taskId: number }>(`/agent/tasks/${taskId}/start`)
  },

  getTaskStatus(taskId: number): Promise<AgentTask> {
    return http.get<AgentTask>(`/agent/tasks/${taskId}/status`)
  },

  getTaskLogs(taskId: number): Promise<{ taskId: number; logs: Array<{ stage: string; progress: number; description: string; timestamp: string }>; total: number }> {
    return http.get(`/agent/tasks/${taskId}/logs`)
  },

  getTaskList(params?: PaginationParams & { learnerId?: number; status?: string; taskType?: string }): Promise<PagedData<AgentTask>> {
    return http.get<PagedData<AgentTask>>('/agent/tasks', params as Record<string, string | number | boolean | undefined>)
  },

  runDiagnosis(data: DiagnosisRequest): Promise<unknown> {
    return http.post('/agent/diagnose', data)
  },

  runFullPipeline(data: FullPipelineRequest): Promise<{ taskId: number }> {
    return http.post<{ taskId: number }>('/agent/run/full-pipeline', data)
  },

  getDebateRecords(taskId: number): Promise<{ taskId: number; debateRecords: DebateRecord[]; totalRounds: number; hasHallucination: boolean; allResolved: boolean }> {
    return http.get(`/agent/debate/${taskId}`)
  },

  getHallucinationMetrics(): Promise<{ totalChecks: number; hallucinationCount: number; hallucinationRate: number; passRate: number; unit: string }> {
    return http.get('/agent/metrics/hallucination')
  },

  getPerformanceMetrics(): Promise<{ totalTasks: number; successCount: number; failedCount: number; runningCount: number; successRate: number; avgDurationMs: number }> {
    return http.get('/agent/metrics/performance')
  },
}
