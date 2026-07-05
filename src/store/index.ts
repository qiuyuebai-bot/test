import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type {
  UserInfo,
  LearnerProfile,
  KnowledgeDoc,
  KnowledgeSlice,
  LearningResource,
  AgentStatus,
  AgentTask,
  SystemMetrics,
} from '../types'
import { authApi, learnerApi, knowledgeApi, agentApi, coreApi } from '../api'
import { clearAuth, setTokens, setUserInfo, getUserInfo, isAuthenticated } from '../lib/request'

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

interface UIState {
  isDarkMode: boolean
  isSidebarCollapsed: boolean
  toggleDarkMode: () => void
  toggleSidebar: () => void
}

interface AuthState {
  user: UserInfo | null
  isLoggedIn: boolean
  isLoading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
  fetchCurrentUser: () => Promise<void>
  initializeAuth: () => void
}

interface LearnerState {
  learners: LearnerProfile[]
  currentLearner: LearnerProfile | null
  learnersLoading: boolean
  learnerLoading: boolean
  learnersTotal: number
  pagination: { page: number; pageSize: number; total: number; totalPages: number }
  fetchLearners: (params?: { page?: number; pageSize?: number; keyword?: string }) => Promise<void>
  fetchLearnerById: (id: number) => Promise<LearnerProfile>
  setCurrentLearner: (learner: LearnerProfile | null) => void
  createLearner: (data: Parameters<typeof learnerApi.create>[0]) => Promise<{ id: number }>
  addLearner: (data: Parameters<typeof learnerApi.create>[0]) => Promise<{ id: number }>
  updateLearner: (id: number, data: Partial<Parameters<typeof learnerApi.create>[0]>) => Promise<{ id: number }>
  deleteLearner: (id: number) => Promise<void>
}

interface KnowledgeState {
  knowledgeDocs: KnowledgeDoc[]
  knowledgeSlices: KnowledgeSlice[]
  knowledgeLoading: boolean
  knowledgeError: string | null
  totalKnowledgeDocs: number
  currentPage: number
  pageSize: number
  fetchKnowledgeDocs: (params?: { page?: number; pageSize?: number; keyword?: string; industry?: string }) => Promise<void>
  fetchKnowledgeSlices: (docId: number, params?: { sliceStart?: number; sliceCount?: number }) => Promise<void>
}

interface AgentState {
  agentStatuses: AgentStatus[]
  tasks: AgentTask[]
  tasksTotal: number
  currentTask: AgentTask | null
  agentsLoading: boolean
  fetchAgentStatuses: () => Promise<void>
  fetchTasks: (params?: { page?: number; pageSize?: number; status?: string }) => Promise<void>
  startAgentTask: (params: { learnerId: number; taskType: string; taskName?: string }) => Promise<{ taskId: number }>
  runFullPipeline: (params: { learnerId: number; targetTopic: string; resourceType?: string; industry?: string }) => Promise<{ taskId: number }>
  pollTaskStatus: (taskId: number, onUpdate?: (task: AgentTask) => void) => () => void
  setCurrentTask: (task: AgentTask | null) => void
}

interface MetricsState {
  systemMetrics: SystemMetrics | null
  metricsLoading: boolean
  fetchSystemMetrics: () => Promise<void>
}

interface ResourceState {
  resources: LearningResource[]
  resourcesTotal: number
  resourcesLoading: boolean
  resourceLoading: boolean
  fetchResources: (params?: { page?: number; pageSize?: number; learnerId?: number }) => Promise<void>
  generateResources: (params: { learnerId: number; targetTopic: string; industry?: string }) => Promise<{ taskId: string }>
  generateResource: (params: { learnerId: number; resourceType: string; title: string }) => Promise<LearningResource>
}

export type AppState = UIState & AuthState & LearnerState & KnowledgeState & AgentState & MetricsState & ResourceState

let _latestSlicesReqId = 0
let _authListenerRegistered = false

export const useStore = create<AppState>()(
  persist(
    (set, get) => ({
      // ==================== UI State ====================
      isDarkMode: false,
      isSidebarCollapsed: false,
      toggleDarkMode: () => set((state) => {
        const newValue = !state.isDarkMode
        if (typeof document !== 'undefined') {
          if (newValue) {
            document.documentElement.classList.add('dark')
          } else {
            document.documentElement.classList.remove('dark')
          }
        }
        return { isDarkMode: newValue }
      }),
      toggleSidebar: () => set((state) => ({ isSidebarCollapsed: !state.isSidebarCollapsed })),

      // ==================== Auth State ====================
      user: (typeof window !== 'undefined' && isAuthenticated() ? getUserInfo() : null) as UserInfo | null,
      isLoggedIn: typeof window !== 'undefined' && isAuthenticated(),
      isLoading: false,

      login: async (username: string, password: string) => {
        set({ isLoading: true })
        try {
          const result = await authApi.login({ username, password })
          setTokens(result.accessToken, result.refreshToken)
          setUserInfo({ user_id: result.userId, username: result.username, role: result.role })
          const userInfo = await authApi.getCurrentUser()
          set({ user: userInfo, isLoggedIn: true, isLoading: false })
        } catch (error) {
          set({ isLoading: false })
          throw error
        }
      },

      logout: async () => {
        try {
          await authApi.logout()
        } catch (err) {
          console.error('logout failed:', err)
        }
        clearAuth()
        set({ user: null, isLoggedIn: false, currentLearner: null, currentTask: null })
      },

      fetchCurrentUser: async () => {
        if (!isAuthenticated()) return
        try {
          const userInfo = await authApi.getCurrentUser()
          set({ user: userInfo, isLoggedIn: true })
        } catch (err) {
          console.error('fetchCurrentUser failed:', err)
          clearAuth()
          set({ user: null, isLoggedIn: false })
        }
      },

      initializeAuth: () => {
        const savedUser = getUserInfo()
        if (savedUser && isAuthenticated()) {
          set({ isLoggedIn: true, user: savedUser as UserInfo })
          get().fetchCurrentUser()
        }
        if (typeof window !== 'undefined' && !_authListenerRegistered) {
          _authListenerRegistered = true
          window.addEventListener('auth:logout', () => {
            set({ user: null, isLoggedIn: false })
          })
        }
      },

      // ==================== Learner State ====================
      learners: [],
      currentLearner: null,
      learnersLoading: false,
      learnerLoading: false,
      learnersTotal: 0,
      pagination: { page: 1, pageSize: 20, total: 0, totalPages: 0 },

      fetchLearners: async (params) => {
        set({ learnersLoading: true, learnerLoading: true })
        try {
          const result = await learnerApi.getList({
            page: 1,
            pageSize: 20,
            ...params,
          })
          set({
            learners: result.items,
            learnersTotal: result.total,
            learnersLoading: false,
            learnerLoading: false,
            pagination: {
              page: result.page,
              pageSize: result.pageSize,
              total: result.total,
              totalPages: result.totalPages,
            },
          })
        } catch (err) {
          console.error('fetchLearners failed:', err)
          set({ learnersLoading: false, learnerLoading: false })
        }
      },

      fetchLearnerById: async (id: number) => {
        const learner = await learnerApi.getById(id)
        set({ currentLearner: learner })
        return learner
      },

      setCurrentLearner: (learner) => set({ currentLearner: learner }),

      createLearner: async (data) => {
        const result = await learnerApi.create(data)
        await get().fetchLearners({ page: get().pagination.page, pageSize: get().pagination.pageSize })
        return result
      },

      addLearner: async (data) => {
        return get().createLearner(data)
      },

      updateLearner: async (id, data) => {
        const result = await learnerApi.update(id, data)
        await get().fetchLearners({ page: get().pagination.page, pageSize: get().pagination.pageSize })
        const current = get().currentLearner
        if (current && current.id === id) {
          const updated = await learnerApi.getById(id)
          set({ currentLearner: updated })
        }
        return result
      },

      deleteLearner: async (id) => {
        await learnerApi.delete(id)
        const current = get().currentLearner
        if (current && current.id === id) {
          set({ currentLearner: null })
        }
        await get().fetchLearners({ page: get().pagination.page, pageSize: get().pagination.pageSize })
      },

      // ==================== Knowledge State ====================
      knowledgeDocs: [],
      knowledgeSlices: [],
      knowledgeLoading: false,
      knowledgeError: null,
      totalKnowledgeDocs: 0,
      currentPage: 1,
      pageSize: 50,

      fetchKnowledgeDocs: async (params) => {
        set({ knowledgeLoading: true, knowledgeError: null })
        try {
          const result = await knowledgeApi.getList({
            page: 1,
            pageSize: 50,
            ...params,
          })
          set({
            knowledgeDocs: result.items,
            totalKnowledgeDocs: result.total,
            currentPage: result.page,
            pageSize: result.pageSize,
            knowledgeLoading: false,
          })
        } catch (err) {
          set({
            knowledgeLoading: false,
            knowledgeError: err instanceof Error ? err.message : '加载文档列表失败',
          })
        }
      },

      fetchKnowledgeSlices: async (docId, params) => {
        const reqId = ++_latestSlicesReqId
        set({ knowledgeLoading: true, knowledgeError: null })
        try {
          const slices = await knowledgeApi.getSlices(docId, params)
          if (reqId !== _latestSlicesReqId) return
          set({ knowledgeSlices: slices, knowledgeLoading: false })
        } catch (err) {
          if (reqId !== _latestSlicesReqId) return
          set({
            knowledgeLoading: false,
            knowledgeError: err instanceof Error ? err.message : '加载切片失败',
          })
        }
      },

      // ==================== Agent State ====================
      agentStatuses: [],
      tasks: [],
      tasksTotal: 0,
      currentTask: null,
      agentsLoading: false,

      fetchAgentStatuses: async () => {
        set({ agentsLoading: true })
        try {
          const result = await agentApi.getAllStatus()
          const agents = result.agents.map((a: AgentStatusRaw) => ({
            ...a,
            agentType: (a.agentType as string) === 'judge' ? 'review' : a.agentType,
            failureCount: a.failureCount ?? a.failCount ?? 0,
            avgLatencyMs: a.avgLatencyMs ?? a.avgDurationMs,
            lastHeartbeat: a.lastHeartbeat ?? a.lastActiveAt,
          })) as AgentStatus[]
          set({ agentStatuses: agents, agentsLoading: false })
        } catch (err) {
          console.error('fetchAgentStatuses failed:', err)
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

      // ==================== Metrics State ====================
      systemMetrics: null,
      metricsLoading: false,

      fetchSystemMetrics: async () => {
        set({ metricsLoading: true })
        try {
          const [sysMetrics, perfMetrics, hallucMetrics] = await Promise.all([
            coreApi.getSystemMetrics().catch(() => null),
            agentApi.getPerformanceMetrics().catch(() => null),
            agentApi.getHallucinationMetrics().catch(() => null),
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
          console.error('fetchSystemMetrics failed:', err)
          set({ metricsLoading: false })
        }
      },

      // ==================== Resource State ====================
      resources: [],
      resourcesTotal: 0,
      resourcesLoading: false,
      resourceLoading: false,

      fetchResources: async (params) => {
        set({ resourcesLoading: true, resourceLoading: true })
        try {
          const result = await coreApi.getResourceList({
            page: 1,
            pageSize: 50,
            ...params,
          })
          const mappedItems = result.items.map((item: LearningResource) => ({
            ...item,
            resourceType: item.resourceType as LearningResource['resourceType'],
            targetLearnerId: item.targetLearnerId ?? item.learnerId ?? 0,
            contentSummary: item.contentSummary ?? item.summary ?? '',
            contentPath: item.contentPath ?? undefined,
            contentType: (item.contentType || 'text') as LearningResource['contentType'],
            qualityScore: item.qualityScore ?? Math.round((item.matchScore || 0) * 100),
            hallucinationDetected: item.hallucinationDetected ?? item.hasHallucination ?? false,
            reviewStatus: (item.reviewStatus || 'pending') as LearningResource['reviewStatus'],
            versionNumber: item.versionNumber ?? item.version ?? 1,
            generatedByAgent: item.generatedByAgent ?? item.createdByAgent ?? 'generation-agent',
            generationTime: item.generationTime ?? item.createdAt ?? new Date().toISOString(),
            metaData: item.metaData ?? {},
          }))
          set({ resources: mappedItems, resourcesTotal: result.total, resourcesLoading: false, resourceLoading: false })
        } catch (err) {
          console.error('fetchResources failed:', err)
          set({ resourcesLoading: false, resourceLoading: false })
        }
      },

      generateResources: async (params) => {
        const result = await coreApi.generateResources(params)
        return result
      },

      generateResource: async (params) => {
        set({ resourceLoading: true })
        try {
          const result = await coreApi.generateResources({
            learnerId: params.learnerId,
            targetTopic: params.title,
          })
          await get().fetchResources({ page: 1, pageSize: 20 })
          set({ resourceLoading: false })
          return {
            id: Date.now(),
            title: params.title,
            resourceType: params.resourceType as LearningResource['resourceType'],
            targetLearnerId: params.learnerId,
            contentSummary: '',
            contentType: 'text',
            qualityScore: 0,
            hallucinationDetected: false,
            reviewStatus: 'pending',
            versionNumber: 1,
            generatedByAgent: 'generation-agent',
            generationTime: new Date().toISOString(),
            metaData: { taskId: result.taskId },
          }
        } catch (error) {
          set({ resourceLoading: false })
          throw error
        }
      },
    }),
    {
      name: 'multi-agent-system-store',
      partialize: (state) => ({
        isDarkMode: state.isDarkMode,
        isSidebarCollapsed: state.isSidebarCollapsed,
      }),
      onRehydrateStorage: () => (state) => {
        if (state) {
          if (state.isDarkMode && typeof document !== 'undefined') {
            document.documentElement.classList.add('dark')
          }
          setTimeout(() => state.initializeAuth(), 0)
        }
      },
    },
  ),
)
