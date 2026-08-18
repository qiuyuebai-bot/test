import type { StateCreator } from 'zustand'
import type { AgentStatus, AgentTask, SystemMetrics } from '../types'
import { agentApi, coreApi } from '../api'
import type { AppState } from './index'
import { reportError } from '../lib/sentry'

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
  hallucinationRate?: number | null
  resourceMatchAccuracy?: number | null
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
  metricsError: string | null
  metricsStatus: 'idle' | 'ready' | 'partial' | 'error'
  fetchSystemMetrics: (options?: { silent?: boolean }) => Promise<void>
}

let _latestAgentStatusesReqId = 0
let _latestTasksReqId = 0

function normalizeUnifiedMetrics(input: SystemMetricsRaw): SystemMetrics {
  const metricResults = input.metrics ?? []
  const byId = new Map(metricResults.map((metric) => [metric.metricId, metric]))
  const valueFor = (metricId: string, fallback: number | null | undefined = null) => {
    const value = byId.get(metricId)?.value
    return typeof value === 'number' || value === null ? value : fallback ?? null
  }
  const hallucination = byId.get('hallucination_rate')
  const hasDegradedMetric = metricResults.some((metric) => ['collecting', 'stale', 'error'].includes(metric.status))
  const allUnavailable = metricResults.length > 0 && metricResults.every((metric) => ['no_data', 'not_applicable'].includes(metric.status))

  return {
    ...input,
    metrics: metricResults,
    hallucinationRate: valueFor('hallucination_rate', input.hallucinationRate),
    totalChecks: input.totalChecks ?? Number(hallucination?.metadata?.totalChecks ?? 0),
    evaluatedChecks: input.evaluatedChecks ?? Number(hallucination?.metadata?.evaluatedChecks ?? 0),
    pendingChecks: input.pendingChecks ?? Number(hallucination?.metadata?.pendingChecks ?? 0),
    confirmedHallucinations: input.confirmedHallucinations ?? Number(hallucination?.metadata?.confirmedHallucinations ?? 0),
    evidenceGaps: input.evidenceGaps ?? Number(hallucination?.metadata?.evidenceGaps ?? 0),
    passRate: input.passRate ?? (typeof hallucination?.metadata?.passRate === 'number' ? hallucination.metadata.passRate : null),
    hasSufficientSample: input.hasSufficientSample ?? hallucination?.status === 'ready',
    minimumSampleSize: input.minimumSampleSize ?? hallucination?.minimumSampleSize ?? 5,
    resourceMatchAccuracy: valueFor('resource_match_score', input.resourceMatchAccuracy),
    resourceMatchScore: valueFor('resource_match_score', input.resourceMatchScore),
    resourceMatchEffectiveness: valueFor('resource_match_effectiveness', input.resourceMatchEffectiveness),
    answerAccuracy: valueFor('answer_accuracy', input.answerAccuracy),
    knowledgeCoverageRate: valueFor('knowledge_index_coverage', input.knowledgeCoverageRate),
    knowledgeIndexCoverageRate: valueFor('knowledge_index_coverage', input.knowledgeIndexCoverageRate),
    learningBlindSpotCoverageRate: valueFor('blind_spot_resource_coverage', input.learningBlindSpotCoverageRate),
    metricsStatus: input.metricsStatus ?? (hasDegradedMetric ? 'degraded' : allUnavailable ? 'no_data' : 'ready'),
    metricsSource: input.metricsSource ?? 'realtime',
    snapshotAvailable: input.snapshotAvailable ?? false,
    calculatedAt: input.calculatedAt,
    totalLearners: input.totalLearners ?? 0,
    totalResources: input.totalResources ?? 0,
    totalAnswers: input.totalAnswers ?? 0,
    totalTasks: input.totalTasks ?? 0,
    tasksCompleted: input.tasksCompleted ?? 0,
    failedTasks: input.failedTasks ?? 0,
    runningTasks: input.runningTasks ?? 0,
    taskSuccessRate: input.taskSuccessRate ?? null,
    avgResponseTime: input.avgResponseTime ?? 0,
    avgCompletionTime: input.avgCompletionTime ?? '-',
    activeSessions: input.activeSessions ?? 0,
    satisfactionScore: input.satisfactionScore ?? 0,
    trends: (input.trends ?? []) as SystemMetrics['trends'],
  }
}

type UnifiedMetrics = SystemMetrics & { sourceFailures?: number }

async function fetchUnifiedMetrics(options?: { silent?: boolean }): Promise<UnifiedMetrics> {
  const primaryResult = await Promise.allSettled([coreApi.getSystemMetrics(options)])
  const primary = primaryResult[0].status === 'fulfilled' ? primaryResult[0].value as SystemMetricsRaw : null
  if (primary && Array.isArray(primary.metrics)) {
    return normalizeUnifiedMetrics(primary)
  }

  // Legacy fallback is intentionally isolated here during the API migration.
  const [performanceResult, hallucinationResult] = await Promise.allSettled([
    agentApi.getPerformanceMetrics(options),
    agentApi.getHallucinationMetrics(options),
  ])
  const performance = performanceResult.status === 'fulfilled' ? performanceResult.value : null
  const hallucination = hallucinationResult.status === 'fulfilled' ? hallucinationResult.value : null
  const failedSources = [primaryResult[0], performanceResult, hallucinationResult]
    .filter((result) => result.status === 'rejected').length
  if (!primary && !performance && !hallucination) {
    throw new Error('指标服务暂时不可用，请稍后重试')
  }

  const normalized = normalizeUnifiedMetrics({
    ...(primary ?? {}),
    hallucinationRate: hallucination?.hallucinationRate ?? primary?.hallucinationRate ?? null,
    totalChecks: hallucination?.totalChecks ?? primary?.totalChecks,
    evaluatedChecks: hallucination?.evaluatedChecks ?? primary?.evaluatedChecks,
    pendingChecks: hallucination?.pendingChecks ?? primary?.pendingChecks,
    confirmedHallucinations: hallucination?.confirmedHallucinations ?? primary?.confirmedHallucinations,
    evidenceGaps: hallucination?.evidenceGaps ?? primary?.evidenceGaps,
    passRate: hallucination?.passRate ?? primary?.passRate,
    hasSufficientSample: hallucination?.hasSufficientSample ?? primary?.hasSufficientSample,
    minimumSampleSize: hallucination?.minimumSampleSize ?? primary?.minimumSampleSize,
    totalTasks: performance?.totalTasks ?? primary?.totalTasks,
    tasksCompleted: performance?.successCount ?? primary?.tasksCompleted,
    failedTasks: performance?.failedCount ?? primary?.failedTasks,
    runningTasks: performance?.runningCount ?? primary?.runningTasks,
    taskSuccessRate: performance?.successRate ?? primary?.taskSuccessRate,
    avgResponseTime: primary?.avgResponseTime ?? performance?.avgDurationMs,
    metricsStatus: primary?.metricsStatus,
  } as SystemMetricsRaw)
  return { ...normalized, sourceFailures: failedSources }
}

export const createAgentSlice: StateCreator<AppState, [], [], AgentSlice> = (set, get) => ({
  agentStatuses: [],
  tasks: [],
  tasksTotal: 0,
  currentTask: null,
  agentsLoading: false,

  fetchAgentStatuses: async (options) => {
    const reqId = ++_latestAgentStatusesReqId
    set({ agentsLoading: true })
    try {
      const result = await agentApi.getAllStatus(options)
      if (reqId !== _latestAgentStatusesReqId) return
      const agents = result.agents.map((a: AgentStatusRaw) => ({
        ...a,
        agentType: (a.agentType as string) === 'judge' ? 'review' : a.agentType,
        failureCount: a.failureCount ?? a.failCount ?? 0,
        avgLatencyMs: a.avgLatencyMs ?? a.avgDurationMs,
        lastHeartbeat: a.lastHeartbeat ?? a.lastActiveAt,
      })) as AgentStatus[]
      set({ agentStatuses: agents, agentsLoading: false })
    } catch (err) {
      if (reqId !== _latestAgentStatusesReqId) return
      if (!options?.silent) {
        reportError(err, { tags: { area: 'agent', action: 'fetch_statuses' } })
      }
      set({ agentsLoading: false })
    }
  },

  fetchTasks: async (params) => {
    const reqId = ++_latestTasksReqId
    try {
      const result = await agentApi.getTaskList({
        page: 1,
        pageSize: 20,
        ...params,
      })
      if (reqId !== _latestTasksReqId) return
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
      if (reqId !== _latestTasksReqId) return
      reportError(err, { tags: { area: 'agent', action: 'fetch_tasks' } })
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
    let timeoutId: ReturnType<typeof setTimeout> | null = null
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
          timeoutId = setTimeout(poll, 2000)
        }
      } catch (err) {
      reportError(err, { tags: { area: 'agent', action: 'poll_task_status' } })
      }
    }
    poll()
    return () => {
      stopped = true
      if (timeoutId) clearTimeout(timeoutId)
    }
  },

  setCurrentTask: (task) => set({ currentTask: task }),
})

export const createMetricsSlice: StateCreator<AppState, [], [], MetricsSlice> = (set) => ({
  systemMetrics: null,
  metricsLoading: false,
  metricsError: null,
  metricsStatus: 'idle',

  fetchSystemMetricsLegacy: async (options?: { silent?: boolean }) => {
    set({ metricsLoading: true, metricsError: null })
    try {
      const results = await Promise.allSettled([
        coreApi.getSystemMetrics(options),
        agentApi.getPerformanceMetrics(options),
        agentApi.getHallucinationMetrics(options),
      ])
      const [sysResult, perfResult, hallucResult] = results
      const sysMetrics = sysResult.status === 'fulfilled' ? sysResult.value : null
      const perfMetrics = perfResult.status === 'fulfilled' ? perfResult.value : null
      const hallucMetrics = hallucResult.status === 'fulfilled' ? hallucResult.value : null
      const failedSources = results.filter((result) => result.status === 'rejected').length

      if (!sysMetrics && !perfMetrics && !hallucMetrics) {
        throw new Error('指标服务暂时不可用，请稍后重试')
      }

      const sysAny = sysMetrics as SystemMetricsRaw | null
      const metrics: SystemMetrics = {
        hallucinationRate: hallucMetrics
          ? hallucMetrics.hallucinationRate
          : sysAny?.hallucinationRate ?? null,
        totalChecks: hallucMetrics?.totalChecks ?? sysAny?.totalChecks ?? 0,
        evaluatedChecks: hallucMetrics?.evaluatedChecks ?? sysAny?.evaluatedChecks ?? 0,
        pendingChecks: hallucMetrics?.pendingChecks ?? sysAny?.pendingChecks ?? 0,
        confirmedHallucinations: hallucMetrics?.confirmedHallucinations ?? sysAny?.confirmedHallucinations ?? 0,
        evidenceGaps: hallucMetrics?.evidenceGaps ?? sysAny?.evidenceGaps ?? 0,
        passRate: hallucMetrics?.passRate ?? sysAny?.passRate ?? null,
        hasSufficientSample: hallucMetrics?.hasSufficientSample ?? sysAny?.hasSufficientSample ?? false,
        minimumSampleSize: hallucMetrics?.minimumSampleSize ?? sysAny?.minimumSampleSize ?? 5,
        resourceMatchAccuracy: sysAny?.resourceMatchAccuracy ?? null,
        knowledgeCoverageRate: sysAny?.knowledgeCoverageRate ?? null,
        knowledgeIndexCoverageRate: sysAny?.knowledgeIndexCoverageRate ?? sysAny?.knowledgeCoverageRate ?? null,
        learningBlindSpotCoverageRate: sysAny?.learningBlindSpotCoverageRate ?? null,
        metricsStatus: sysAny?.metricsStatus ?? (sysAny?.knowledgeCoverageRate == null ? 'no_data' : 'ready'),
        metricsSource: sysAny?.metricsSource ?? 'realtime',
        snapshotAvailable: sysAny?.snapshotAvailable ?? false,
        calculatedAt: sysAny?.calculatedAt,
        totalLearners: sysAny?.totalLearners ?? 0,
        totalResources: sysAny?.totalResources ?? 0,
        totalAnswers: sysAny?.totalAnswers ?? 0,
        totalTasks: perfMetrics?.totalTasks ?? sysAny?.totalTasks ?? 0,
        tasksCompleted: perfMetrics?.successCount ?? sysAny?.tasksCompleted ?? 0,
        failedTasks: perfMetrics?.failedCount ?? sysAny?.failedTasks ?? 0,
        runningTasks: perfMetrics?.runningCount ?? sysAny?.runningTasks ?? 0,
        taskSuccessRate: perfMetrics?.successRate ?? sysAny?.taskSuccessRate ?? null,
        avgResponseTime: sysAny?.avgResponseTime ?? perfMetrics?.avgDurationMs ?? 0,
        avgCompletionTime: sysAny?.avgCompletionTime ?? '-',
        activeSessions: sysAny?.activeSessions ?? 0,
        satisfactionScore: sysAny?.satisfactionScore ?? 0,
        trends: (sysAny?.trends ?? []) as SystemMetrics['trends'],
      }
      set({
        systemMetrics: metrics,
        metricsLoading: false,
        metricsStatus: failedSources > 0 ? 'partial' : 'ready',
        metricsError: failedSources > 0 ? `${failedSources} 个指标数据源暂时不可用` : null,
      })
    } catch (err) {
      if (!options?.silent) {
      reportError(err, { tags: { area: 'agent', action: 'fetch_system_metrics' } })
      }
      set({
        metricsLoading: false,
        metricsStatus: 'error',
        metricsError: err instanceof Error ? err.message : '指标加载失败',
      })
      throw err
    }
  },

  fetchSystemMetrics: async (options) => {
    set({ metricsLoading: true, metricsError: null })
    try {
      const metrics = await fetchUnifiedMetrics(options)
      const partial = (metrics.sourceFailures ?? 0) > 0
      set({
        systemMetrics: metrics,
        metricsLoading: false,
        metricsStatus: partial ? 'partial' : 'ready',
        metricsError: partial ? `${metrics.sourceFailures} 个指标数据源暂时不可用` : null,
      })
    } catch (err) {
      if (!options?.silent) reportError(err, { tags: { area: 'agent', action: 'fetch_system_metrics' } })
      set({
        metricsLoading: false,
        metricsStatus: 'error',
        metricsError: err instanceof Error ? err.message : '指标加载失败',
      })
      throw err
    }
  },
})
