import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { agentApi } from '../../api'
import type { AgentStatus, AgentTask } from '../../types'

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

function normalizeAgent(a: AgentStatusRaw): AgentStatus {
  return {
    ...a,
    agentType: (a.agentType as string) === 'judge' ? 'review' : a.agentType,
    failureCount: a.failureCount ?? a.failCount ?? 0,
    avgLatencyMs: a.avgLatencyMs ?? a.avgDurationMs,
    lastHeartbeat: a.lastHeartbeat ?? a.lastActiveAt,
  } as AgentStatus
}

function normalizeTask(t: AgentTaskRaw): AgentTask {
  return {
    ...t,
    completedAt: t.completedAt ?? undefined,
    outputData: t.outputData ?? undefined,
  } as AgentTask
}

export function useAgentStatuses() {
  return useQuery({
    queryKey: ['agent', 'statuses'],
    queryFn: async () => {
      const result = await agentApi.getAllStatus()
      return result.agents.map(normalizeAgent)
    },
    staleTime: 15 * 1000,
  })
}

export function useTasks(params?: { page?: number; pageSize?: number; status?: string }) {
  const page = params?.page ?? 1
  const pageSize = params?.pageSize ?? 10
  const status = params?.status

  return useQuery({
    queryKey: ['agent', 'tasks', { page, pageSize, status }],
    queryFn: async () => {
      const result = await agentApi.getTaskList({ page, pageSize, status })
      return {
        items: result.items.map(normalizeTask),
        total: result.total,
      }
    },
    placeholderData: keepPreviousData,
    staleTime: 10 * 1000,
  })
}

export function useTaskStatus(taskId: number | null) {
  return useQuery({
    queryKey: ['agent', 'task', taskId],
    queryFn: async () => {
      if (taskId === null) return null
      return agentApi.getTaskStatus(taskId)
    },
    enabled: taskId !== null,
    refetchInterval: (query) => {
      const data = query.state.data as AgentTask | null
      if (data && (data.status === 'running' || data.status === 'pending')) {
        return 2000
      }
      return false
    },
  })
}
