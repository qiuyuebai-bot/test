import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

vi.mock('@/api/dashboard', () => ({
  dashboardApi: {
    getLearner: vi.fn(),
    getTeacher: vi.fn(),
    updateGuidance: vi.fn(),
  },
}))

vi.mock('@/store', async () => {
  const { useStoreMock } = await import('@/test/mockStore')
  return { useStore: useStoreMock }
})

import { dashboardApi } from '@/api/dashboard'
import Dashboard from './Dashboard'
import { resetMockStore, setMockStore } from '@/test/mockStore'

describe('role adaptive dashboard', () => {
  beforeEach(() => {
    resetMockStore()
    vi.clearAllMocks()
  })

  it('renders the learner workbench and only calls the learner aggregate endpoint', async () => {
    setMockStore({ user: { id: 7, username: 'learner', role: 'learner' } })
    vi.mocked(dashboardApi.getLearner).mockResolvedValue({
      profile: null,
      summary: null,
      recentResources: [],
      currentTasks: [],
      recentFeedback: [],
      facts: {
        hasDiagnosis: false,
        resourceCount: 0,
        answerCount: 0,
        completedLearningRound: false,
      },
      guidance: { stage: 'profile' },
      moduleErrors: {},
    } as never)

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    )

    expect(await screen.findByText('下一步该做什么')).toBeInTheDocument()
    expect(dashboardApi.getLearner).toHaveBeenCalledTimes(1)
    expect(dashboardApi.getTeacher).not.toHaveBeenCalled()
  })

  it('renders the teacher workbench and does not call learner or system endpoints', async () => {
    setMockStore({ user: { id: 8, username: 'teacher', role: 'teacher' } })
    vi.mocked(dashboardApi.getTeacher).mockResolvedValue({
      summary: { totalLearners: 0, averageProgress: null, atRiskCount: 0, pendingTaskCount: 0 },
      learners: [],
      atRiskLearners: [],
      stalledTasks: [],
      blindAreaDistribution: [],
      pagination: { page: 1, pageSize: 20, total: 0, totalPages: 0 },
      scope: { type: 'teacher_learner_list', learnerCount: 0 },
      moduleErrors: {},
    } as never)

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    )

    expect(await screen.findByText('培训管理台')).toBeInTheDocument()
    expect(dashboardApi.getTeacher).toHaveBeenCalledWith(
      { page: 1, pageSize: 20 },
      { signal: expect.any(AbortSignal) },
    )
    expect(dashboardApi.getLearner).not.toHaveBeenCalled()
  })

  it('keeps system requests on the admin dashboard only', async () => {
    const fetchSystemMetrics = vi.fn(() => Promise.resolve())
    const fetchAgentStatuses = vi.fn(() => Promise.resolve())
    const fetchTasks = vi.fn(() => Promise.resolve())
    setMockStore({
      user: { id: 1, username: 'admin', role: 'admin' },
      fetchSystemMetrics,
      fetchAgentStatuses,
      fetchTasks,
    })

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getByText('管理员 Dashboard')).toBeInTheDocument())
    expect(fetchSystemMetrics).toHaveBeenCalledTimes(1)
    expect(fetchAgentStatuses).toHaveBeenCalledTimes(1)
    expect(fetchTasks).toHaveBeenCalledWith({ page: 1, pageSize: 10 })
    expect(dashboardApi.getLearner).not.toHaveBeenCalled()
    expect(dashboardApi.getTeacher).not.toHaveBeenCalled()
  })
})
