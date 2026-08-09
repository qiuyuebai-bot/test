import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

vi.mock('@/store', async () => {
  const { useStoreMock } = await import('../test/mockStore')
  return { useStore: useStoreMock }
})

const { resetMockStore, setMockStore } = await import('../test/mockStore')

beforeEach(() => {
  resetMockStore()
  setMockStore({
    systemMetrics: {
      hallucinationRate: 2.4,
      hasSufficientSample: true,
      resourceMatchAccuracy: 94.2,
      knowledgeCoverageRate: 88.5,
      knowledgeIndexCoverageRate: 91.2,
      totalLearners: 6,
      totalResources: 12,
      totalAnswers: 20,
      totalTasks: 18,
      tasksCompleted: 14,
      failedTasks: 1,
      runningTasks: 2,
      taskSuccessRate: 77.8,
      avgResponseTime: 250,
      avgCompletionTime: '-',
      activeSessions: 2,
      satisfactionScore: 4.2,
      trends: [],
    },
    metricsStatus: 'ready',
    fetchSystemMetrics: vi.fn().mockResolvedValue(undefined),
    fetchAgentStatuses: vi.fn().mockResolvedValue(undefined),
    fetchTasks: vi.fn().mockResolvedValue(undefined),
    agentStatuses: [
      {
        agentType: 'diagnosis',
        agentName: '诊断 Agent',
        state: 'running',
        totalTasksHandled: 8,
        successCount: 8,
        failureCount: 0,
      },
    ],
    tasks: [
      {
        taskId: 12,
        taskName: '知识生成任务',
        taskType: 'generation',
        status: 'running',
        progress: 50,
      },
    ],
  })
})

describe('AdminOpsOverview', () => {
  it('loads the shared data sources and exposes detail links', async () => {
    const state = (await import('../test/mockStore')).mockStoreState
    const fetchSystemMetrics = state.fetchSystemMetrics as ReturnType<typeof vi.fn>
    const fetchAgentStatuses = state.fetchAgentStatuses as ReturnType<typeof vi.fn>
    const fetchTasks = state.fetchTasks as ReturnType<typeof vi.fn>
    const { default: Page } = await import('./AdminOpsOverview')

    render(<MemoryRouter><Page /></MemoryRouter>)

    expect(await screen.findByText('运维总览')).toBeInTheDocument()
    expect(screen.getAllByText('88.5%').length).toBeGreaterThan(0)
    expect(screen.getByText('Agent 活跃数')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /查看指标/ })).toHaveAttribute('href', '/metrics')
    expect(screen.getByRole('link', { name: /打开多智能体/ })).toHaveAttribute('href', '/multi-agent')
    expect(screen.getByRole('link', { name: /查看监控/ })).toHaveAttribute('href', '/monitoring')
    expect(fetchSystemMetrics).toHaveBeenCalledTimes(1)
    expect(fetchAgentStatuses).toHaveBeenCalledTimes(1)
    expect(fetchTasks).toHaveBeenCalledWith({ page: 1, pageSize: 10 })
  })
})
