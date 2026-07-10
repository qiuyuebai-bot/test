import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('../api', () => ({
  authApi: {
    login: vi.fn(),
    getCurrentUser: vi.fn(),
    logout: vi.fn(),
  },
  learnerApi: {
    getList: vi.fn(),
    getById: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
  knowledgeApi: {
    getList: vi.fn(),
    getSlices: vi.fn(),
  },
  agentApi: {
    getAllStatus: vi.fn(),
    getTaskList: vi.fn(),
    createTask: vi.fn(),
    startTask: vi.fn(),
    getTaskStatus: vi.fn(),
    runFullPipeline: vi.fn(),
    getPerformanceMetrics: vi.fn(),
    getHallucinationMetrics: vi.fn(),
  },
  coreApi: {
    getSystemMetrics: vi.fn(),
    getResourceList: vi.fn(),
    generateResources: vi.fn(),
  },
  trainingApi: {},
  privacyApi: {},
}))

vi.mock('../lib/request', () => ({
  setTokens: vi.fn(),
  setUserInfo: vi.fn(),
  getUserInfo: vi.fn(() => null),
  clearAuth: vi.fn(),
  isAuthenticated: vi.fn(() => false),
}))

const { authApi, learnerApi, knowledgeApi, agentApi, coreApi } = await import('../api')

async function freshStore() {
  vi.resetModules()
  const mod = await import('./index')
  return mod.useStore
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
})

describe('store UI state', () => {
  it('toggles dark mode and mutates document classList', async () => {
    const useStore = await freshStore()
    const state = useStore.getState()
    expect(state.isDarkMode).toBe(false)
    state.toggleDarkMode()
    expect(useStore.getState().isDarkMode).toBe(true)
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    useStore.getState().toggleDarkMode()
    expect(useStore.getState().isDarkMode).toBe(false)
    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })

  it('toggles sidebar collapsed', async () => {
    const useStore = await freshStore()
    expect(useStore.getState().isSidebarCollapsed).toBe(false)
    useStore.getState().toggleSidebar()
    expect(useStore.getState().isSidebarCollapsed).toBe(true)
  })
})

describe('store auth', () => {
  it('login sets tokens, fetches user, and marks logged in', async () => {
    vi.mocked(authApi.login).mockResolvedValue({
      accessToken: 'a',
      refreshToken: 'b',
      userId: 1,
      username: 'u',
      role: 'admin',
    } as never)
    vi.mocked(authApi.getCurrentUser).mockResolvedValue({ id: 1, username: 'u' } as never)

    const useStore = await freshStore()
    await useStore.getState().login('u', 'p')

    expect(useStore.getState().isLoggedIn).toBe(true)
    expect(useStore.getState().user).toEqual({ id: 1, username: 'u' })
    expect(useStore.getState().isLoading).toBe(false)
  })

  it('login on failure resets isLoading and rethrows', async () => {
    vi.mocked(authApi.login).mockRejectedValue(new Error('bad'))
    const useStore = await freshStore()
    await expect(useStore.getState().login('u', 'p')).rejects.toThrow('bad')
    expect(useStore.getState().isLoading).toBe(false)
    expect(useStore.getState().isLoggedIn).toBe(false)
  })

  it('logout clears auth and user even if backend logout fails', async () => {
    vi.mocked(authApi.logout).mockRejectedValue(new Error('net'))
    const useStore = await freshStore()
    useStore.setState({ user: { id: 1 } as never, isLoggedIn: true })
    await useStore.getState().logout()
    expect(useStore.getState().isLoggedIn).toBe(false)
    expect(useStore.getState().user).toBeNull()
  })
})

describe('store learner state', () => {
  it('fetchLearners populates list and pagination', async () => {
    vi.mocked(learnerApi.getList).mockResolvedValue({
      items: [{ id: 1 }, { id: 2 }] as never,
      total: 2,
      page: 1,
      pageSize: 20,
      totalPages: 1,
    })
    const useStore = await freshStore()
    await useStore.getState().fetchLearners({ page: 1 })
    expect(useStore.getState().learners).toHaveLength(2)
    expect(useStore.getState().learnersTotal).toBe(2)
    expect(useStore.getState().pagination.total).toBe(2)
    expect(useStore.getState().learnersLoading).toBe(false)
  })

  it('fetchLearners swallows errors and clears loading flags', async () => {
    vi.mocked(learnerApi.getList).mockRejectedValue(new Error('net'))
    const useStore = await freshStore()
    await useStore.getState().fetchLearners()
    expect(useStore.getState().learnersLoading).toBe(false)
    expect(useStore.getState().learners).toEqual([])
  })

  it('createLearner calls api and refreshes list', async () => {
    vi.mocked(learnerApi.create).mockResolvedValue({ id: 9 })
    vi.mocked(learnerApi.getList).mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 20, totalPages: 0 })
    const useStore = await freshStore()
    const res = await useStore.getState().createLearner({ realName: 'x', educationLevel: 'master', major: 'cs' } as never)
    expect(res).toEqual({ id: 9 })
    expect(learnerApi.create).toHaveBeenCalledTimes(1)
    expect(learnerApi.getList).toHaveBeenCalled()
  })

  it('addLearner delegates to createLearner (flagged as redundant)', async () => {
    vi.mocked(learnerApi.create).mockResolvedValue({ id: 7 })
    vi.mocked(learnerApi.getList).mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 20, totalPages: 0 })
    const useStore = await freshStore()
    const res = await useStore.getState().addLearner({ realName: 'y', educationLevel: 'bachelor', major: 'cs' } as never)
    expect(res).toEqual({ id: 7 })
    expect(learnerApi.create).toHaveBeenCalledTimes(1)
  })

  it('updateLearner refreshes currentLearner when it matches the updated id', async () => {
    vi.mocked(learnerApi.update).mockResolvedValue({ id: 5 })
    vi.mocked(learnerApi.getById).mockResolvedValue({ id: 5, realName: 'updated' } as never)
    vi.mocked(learnerApi.getList).mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 20, totalPages: 0 })
    const useStore = await freshStore()
    useStore.setState({ currentLearner: { id: 5 } as never })
    await useStore.getState().updateLearner(5, { realName: 'updated' } as never)
    expect(useStore.getState().currentLearner).toEqual({ id: 5, realName: 'updated' })
  })

  it('updateLearner does not touch currentLearner when id differs', async () => {
    vi.mocked(learnerApi.update).mockResolvedValue({ id: 5 })
    vi.mocked(learnerApi.getList).mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 20, totalPages: 0 })
    const useStore = await freshStore()
    const current = { id: 99 } as never
    useStore.setState({ currentLearner: current })
    await useStore.getState().updateLearner(5, {})
    expect(useStore.getState().currentLearner).toBe(current)
    expect(learnerApi.getById).not.toHaveBeenCalled()
  })

  it('deleteLearner clears currentLearner when it matches and refreshes', async () => {
    vi.mocked(learnerApi.delete).mockResolvedValue(null as never)
    vi.mocked(learnerApi.getList).mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 20, totalPages: 0 })
    const useStore = await freshStore()
    useStore.setState({ currentLearner: { id: 3 } as never })
    await useStore.getState().deleteLearner(3)
    expect(useStore.getState().currentLearner).toBeNull()
  })
})

describe('store knowledge state', () => {
  it('fetchKnowledgeDocs populates docs and clears error', async () => {
    vi.mocked(knowledgeApi.getList).mockResolvedValue({
      items: [{ id: 1, title: 'test', domain: '', category: '', totalSlices: 0, indexedSlices: 0, status: 'pending', uploadTime: '', version: '' }], total: 1, page: 1, pageSize: 50, totalPages: 1,
    })
    const useStore = await freshStore()
    await useStore.getState().fetchKnowledgeDocs()
    expect(useStore.getState().knowledgeDocs).toHaveLength(1)
    expect(useStore.getState().knowledgeError).toBeNull()
  })

  it('fetchKnowledgeDocs sets error message on failure', async () => {
    vi.mocked(knowledgeApi.getList).mockRejectedValue(new Error('boom'))
    const useStore = await freshStore()
    await useStore.getState().fetchKnowledgeDocs()
    expect(useStore.getState().knowledgeError).toBe('boom')
    expect(useStore.getState().knowledgeLoading).toBe(false)
  })

  it('fetchKnowledgeSlices populates slices', async () => {
    vi.mocked(knowledgeApi.getSlices).mockResolvedValue([{ id: 1 }] as never)
    const useStore = await freshStore()
    await useStore.getState().fetchKnowledgeSlices(7)
    expect(useStore.getState().knowledgeSlices).toHaveLength(1)
  })
})

describe('store agent state normalization', () => {
  it('fetchAgentStatuses maps judge->review, failCount->failureCount, avgDurationMs->avgLatencyMs', async () => {
    vi.mocked(agentApi.getAllStatus).mockResolvedValue({
      agents: [
        { agentType: 'judge', failCount: 2, avgDurationMs: 100, lastActiveAt: 't1' },
        { agentType: 'generation', failureCount: 1, avgLatencyMs: 50, lastHeartbeat: 't2' },
      ],
    } as never)
    const useStore = await freshStore()
    await useStore.getState().fetchAgentStatuses()
    const agents = useStore.getState().agentStatuses
    expect(agents[0].agentType).toBe('review')
    expect(agents[0].failureCount).toBe(2)
    expect(agents[0].avgLatencyMs).toBe(100)
    expect(agents[0].lastHeartbeat).toBe('t1')
    expect(agents[1].agentType).toBe('generation')
    expect(agents[1].failureCount).toBe(1)
  })

  it('fetchTasks maps backend taskType codes to frontend codes', async () => {
    vi.mocked(agentApi.getTaskList).mockResolvedValue({
      items: [
        { taskType: 'learner_diagnosis', agentType: 'diagnosis', completedAt: 'c1', outputData: { x: 1 } },
        { taskType: 'resource_generation' },
        { taskType: 'full_pipeline' },
        { taskType: 'review', assignedAgentId: 'r' },
      ],
      total: 4,
    } as never)
    const useStore = await freshStore()
    await useStore.getState().fetchTasks()
    const tasks = useStore.getState().tasks
    expect(tasks[0].taskType).toBe('diagnosis')
    expect(tasks[0].updatedAt).toBe('c1')
    expect(tasks[0].metadata).toEqual({ x: 1 })
    expect(tasks[1].taskType).toBe('generation')
    expect(tasks[2].taskType).toBe('full_flow')
    expect(tasks[3].assignedAgentId).toBe('r')
    expect(useStore.getState().tasksTotal).toBe(4)
  })

  it('startAgentTask maps taskType to backend code and default name', async () => {
    vi.mocked(agentApi.createTask).mockResolvedValue({ taskId: 42 })
    vi.mocked(agentApi.startTask).mockResolvedValue(undefined as never)
    vi.mocked(agentApi.getAllStatus).mockResolvedValue({ agents: [] } as never)
    vi.mocked(agentApi.getTaskList).mockResolvedValue({ items: [], total: 0 } as never)
    const useStore = await freshStore()
    const res = await useStore.getState().startAgentTask({ learnerId: 1, taskType: 'diagnosis' })
    expect(res).toEqual({ taskId: 42 })
    expect(agentApi.createTask).toHaveBeenCalledWith(expect.objectContaining({
      learnerId: 1,
      taskType: 'learner_diagnosis',
      taskName: '学情诊断任务',
    }))
  })

  it('pollTaskStatus updates currentTask and stops on terminal status', async () => {
    vi.mocked(agentApi.getTaskStatus).mockResolvedValueOnce({ taskType: 'learner_diagnosis', status: 'running' } as never)
    vi.mocked(agentApi.getTaskStatus).mockResolvedValueOnce({ taskType: 'learner_diagnosis', status: 'completed' } as never)
    const useStore = await freshStore()
    vi.useFakeTimers()
    const stop = useStore.getState().pollTaskStatus(1)
    await vi.advanceTimersByTimeAsync(0)
    expect(useStore.getState().currentTask?.status).toBe('running')
    await vi.advanceTimersByTimeAsync(2000)
    expect(useStore.getState().currentTask?.status).toBe('completed')
    stop()
    vi.useRealTimers()
  })
})

describe('store metrics state', () => {
  it('fetchSystemMetrics merges three sources with fallbacks', async () => {
    vi.mocked(coreApi.getSystemMetrics).mockResolvedValue({
      hallucinationRate: 1.1,
      resourceMatchAccuracy: 90,
      totalLearners: 5,
    } as never)
    vi.mocked(agentApi.getPerformanceMetrics).mockResolvedValue({
      totalTasks: 10, successCount: 8, avgDurationMs: 200,
    } as never)
    vi.mocked(agentApi.getHallucinationMetrics).mockResolvedValue({
      hallucinationRate: 0.5,
    } as never)
    const useStore = await freshStore()
    await useStore.getState().fetchSystemMetrics()
    const m = useStore.getState().systemMetrics
    expect(m?.hallucinationRate).toBe(0.5)
    expect(m?.resourceMatchAccuracy).toBe(90)
    expect(m?.totalLearners).toBe(5)
    expect(m?.totalTasks).toBe(10)
    expect(m?.tasksCompleted).toBe(8)
    expect(m?.avgResponseTime).toBe(200)
    expect(useStore.getState().metricsLoading).toBe(false)
  })
})

describe('store resource state normalization', () => {
  it('fetchResources maps backend fields to frontend schema with fallbacks', async () => {
    vi.mocked(coreApi.getResourceList).mockResolvedValue({
      items: [
        {
          resourceType: 'guide',
          learnerId: 3,
          summary: 's',
          matchScore: 0.9,
          hasHallucination: true,
          version: '2',
          createdByAgent: 'agent-x',
          createdAt: '2024-01-01',
        },
      ],
      total: 1,
    } as never)
    const useStore = await freshStore()
    await useStore.getState().fetchResources({ page: 1 })
    const r = useStore.getState().resources[0] as never as Record<string, unknown>
    expect(r.targetLearnerId).toBe(3)
    expect(r.contentSummary).toBe('s')
    expect(r.qualityScore).toBe(90)
    expect(r.hallucinationDetected).toBe(true)
    expect(r.reviewStatus).toBe('pending')
    expect(r.versionNumber).toBe('2')
    expect(r.generatedByAgent).toBe('agent-x')
    expect(useStore.getState().resourcesTotal).toBe(1)
  })

  it('generateResource returns a synthetic object with Date.now id (flagged tech debt)', async () => {
    vi.mocked(coreApi.generateResources).mockResolvedValue({ taskId: 't1' } as never)
    vi.mocked(coreApi.getResourceList).mockResolvedValue({ items: [], total: 0 } as never)
    const useStore = await freshStore()
    const r = await useStore.getState().generateResource({ learnerId: 1, resourceType: 'guide', title: 'T' })
    expect(typeof r.id).toBe('number')
    expect(r.title).toBe('T')
    expect(r.metaData).toEqual({ taskId: 't1' })
    expect(useStore.getState().resourceLoading).toBe(false)
  })
})
