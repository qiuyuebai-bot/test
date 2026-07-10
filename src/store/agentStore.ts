import type { StateCreator } from 'zustand'
import type { AgentStatus, AgentTask, SystemMetrics } from '../types'
import { agentApi, coreApi } from '../api'
import type { AppState } from './index'

type AgentStatusRaw = Partial<AgentStatus> & {
  failCount?: number
  avgDurationMs?: number | null
  lastActiveAt?: string | null
}

type AgentTaskRaw = Partial<AgentTask> & {
  agentType?: string
  completedAt?: string | null
  outputData?: Record<string, unknown>
}

type SystemMetricsRaw = Partial<SystemMetrics> & {
  hallucinationRate?: number
  resourceMatchAccuracy?: number
}

export interface AgentSlice {
  agentStatuses: AgentStatus[]
  tasks: AgentTask[]
  tasksTotal: number
  currentTask: AgentTask | null
  agentsLoading: boolean
  fetchAgentStatuses: (options?: { silent?: boolean }) => Promise<void>
  fetchTasks: (params?: { page?: number; pageSize?: number; status?: string }) => Promise<void>
  startAgentTask: (params: { learnerId: number; taskType: string; taskName?: string }) => Promise<{ taskId: number }>
  runFullPipeline: (params: { learnerId: number; targetTopic: string; resourceType?: string; industry?: string }) => Promise<{ taskId: number }>
  pollTaskStatus: (taskId: number, onUpdate?: (task: AgentTask) => void) => () => void
  setCurrentTask: (task: AgentTask | null) => void
}

export interface MetricsSlice {
  systemMetrics: SystemMetrics | null
  metricsLoading: boolean
  fetchSystemMetrics: (options?: { silent?: boolean }) => Promise<void>
}

export const createAgentSlice: StateCreator<AppState, [], [], AgentSlice> = (set, get) => ({
  agentStatuses: [],
  tasks: [],
  tasksTotal: 0,
  currentTask: null,
  agentsLoading: false,

  fetchAgentStatuses: async (options) => {
    set({ agentsLoading: true })
    try {
      const result = await agentApi.getAllStatus(options)
      const agents = result.agents.map((a: AgentStatusRaw) => ({
        ...a,
        agentType: (a.agentType as string) === 'judge' ? 'review' : a.agentType,
        failureCount: a.failureCount ?? a.failCount ?? 0,
        avgLatencyMs: a.avgLatencyMs ?? a.avgDurationMs,
        lastHeartbeat: a.lastHeartbeat ?? a.lastActiveAt,
      })) as AgentStatus[]
      set({ agentStatuses: agents, agentsLoading: false })
    } catch (err) {
      if (!options?.silent) {
        console.error('fetchAgentStatuses failed:', err)
      }
      set({ agentsLoading: false })
    }
  },

  fetchTasks: async (params) => {
    try {
      const result = await agentApi.getTaskList({
        page: 1,
        pageSize: 20,
        ...params,
      })
      const items = result.items.map((t: AgentTaskRaw) => ({
        ...t,
        taskType: (t.taskType === 'learner_diagnosis' ? 'diagnosis' :
                   t.taskType === 'resource_generation' ? 'generation' :
                   t.taskType === 'full_pipeline' ? 'full_flow' : t.taskType),
        assignedAgentId: t.assignedAgentId ?? t.agentType,
        updatedAt: t.updatedAt ?? t.completedAt,
        metadata: t.metadata ?? t.outputData,
      })) as AgentTask[]
      set({ tasks: items, tasksTotal: result.total })
    } catch (err) {
      console.error('fetchTasks failed:', err)
    }
  },

  startAgentTask: async (params) => {
    const taskTypeMap: Record<string, string> = {
      diagnosis: 'learner_diagnosis',
      generation: 'resource_generation',
      review: 'review',
      full_flow: 'full_pipeline',
    }
    const backendTaskType = taskTypeMap[params.taskType] || params.taskType
    const taskNameMap: Record<string, string> = {
      diagnosis: '学情诊断任务',
      generation: '知识生成任务',
      review: '内容审核任务',
      full_flow: '全流程协同任务',
    }
    const createResult = await agentApi.createTask({
      learnerId: params.learnerId,
      taskName: params.taskName || taskNameMap[params.taskType] || '智能体任务',
      taskType: backendTaskType,
    })
    await agentApi.startTask(createResult.taskId)
    await get().fetchTasks()
    await get().fetchAgentStatuses()
    return createResult
  },

  runFullPipeline: async (params) => {
    const result = await agentApi.runFullPipeline(params)
    await get().fetchTasks()
    return result
  },

  pollTaskStatus: (taskId: number, onUpdate?: (task: AgentTask) => void) => {
    let stopped = false
    const poll = async () => {
      if (stopped) return
      try {
        const rawTask = await agentApi.getTaskStatus(taskId) as AgentTaskRaw
        const task = {
          ...rawTask,
          taskType: (rawTask.taskType === 'learner_diagnosis' ? 'diagnosis' :
                     rawTask.taskType === 'resource_generation' ? 'generation' :
                     rawTask.taskType === 'full_pipeline' ? 'full_flow' : rawTask.taskType) as AgentTask['taskType'],
          assignedAgentId: rawTask.assignedAgentId ?? rawTask.agentType,
          updatedAt: rawTask.updatedAt ?? rawTask.completedAt,
          metadata: rawTask.metadata ?? rawTask.outputData,
        } as AgentTask
        set({ currentTask: task })
        onUpdate?.(task)
        if (task.status === 'running' || task.status === 'pending') {
          setTimeout(poll, 2000)
        }
      } catch (err) {
        console.error('pollTaskStatus failed:', err)
      }
    }
    poll()
    return () => { stopped = true }
  },

  setCurrentTask: (task) => set({ currentTask: task }),
})

export const createMetricsSlice: StateCreator<AppState, [], [], MetricsSlice> = (set) => ({
  systemMetrics: null,
  metricsLoading: false,

  fetchSystemMetrics: async (options) => {
    set({ metricsLoading: true })
    try {
      const [sysMetrics, perfMetrics, hallucMetrics] = await Promise.all([
        coreApi.getSystemMetrics(options).catch(() => null),
        agentApi.getPerformanceMetrics(options).catch(() => null),
        agentApi.getHallucinationMetrics(options).catch(() => null),
      ])
      const sysAny = sysMetrics as SystemMetricsRaw | null
      const metrics: SystemMetrics = {
        hallucinationRate: hallucMetrics?.hallucinationRate ?? sysAny?.hallucinationRate ?? 0,
        resourceMatchAccuracy: sysAny?.resourceMatchAccuracy ?? 0,
        knowledgeCoverageRate: sysAny?.knowledgeCoverageRate ?? 0,
        totalLearners: sysAny?.totalLearners ?? 0,
        totalResources: sysAny?.totalResources ?? 0,
        totalAnswers: sysAny?.totalAnswers ?? 0,
        totalTasks: perfMetrics?.totalTasks ?? sysAny?.totalTasks ?? 0,
        tasksCompleted: perfMetrics?.successCount ?? sysAny?.tasksCompleted ?? 0,
        avgResponseTime: sysAny?.avgResponseTime ?? perfMetrics?.avgDurationMs ?? 0,
        avgCompletionTime: sysAny?.avgCompletionTime ?? '-',
        activeSessions: sysAny?.activeSessions ?? 0,
        satisfactionScore: sysAny?.satisfactionScore ?? 0,
        trends: (sysAny?.trends ?? []) as SystemMetrics['trends'],
      }
      set({ systemMetrics: metrics, metricsLoading: false })
    } catch (err) {
      if (!options?.silent) {
        console.error('fetchSystemMetrics failed:', err)
      }
      set({ metricsLoading: false })
    }
  },
})
