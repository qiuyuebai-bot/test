import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

vi.mock('@/store', async () => {
  const { useStoreMock } = await import('../test/mockStore')
  return { useStore: useStoreMock }
})

vi.mock('@/api', () => ({
  agentApi: {
    getHallucinationMetrics: vi.fn(),
    getPerformanceMetrics: vi.fn(),
    getAllStatus: vi.fn(),
    getTaskList: vi.fn(),
  },
  knowledgeApi: {
    getList: vi.fn(),
  },
}))

const { resetMockStore, setMockStore } = await import('../test/mockStore')
const { agentApi, knowledgeApi } = await import('@/api')

beforeEach(() => {
  vi.clearAllMocks()
  resetMockStore()
  vi.mocked(agentApi.getHallucinationMetrics).mockResolvedValue({
    hallucinationRate: null,
    hasSufficientSample: false,
  } as never)
  vi.mocked(agentApi.getPerformanceMetrics).mockResolvedValue({
    totalTasks: 0,
    successCount: 0,
    failedCount: 0,
    runningCount: 0,
    successRate: null,
    avgDurationMs: 0,
  })
  vi.mocked(agentApi.getAllStatus).mockResolvedValue({ agents: [], total: 0 })
  vi.mocked(agentApi.getTaskList).mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 100, totalPages: 0 })
  vi.mocked(knowledgeApi.getList).mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 100, totalPages: 0 })
  setMockStore({
    systemMetrics: {
      hallucinationRate: null,
      hasSufficientSample: false,
      resourceMatchAccuracy: null,
      knowledgeCoverageRate: 100,
      totalLearners: 5,
      totalResources: 0,
      totalAnswers: 0,
      totalTasks: 0,
      tasksCompleted: 0,
      avgResponseTime: 0,
      avgCompletionTime: '-',
      activeSessions: 0,
      satisfactionScore: 0,
      trends: [],
    },
    metricsStatus: 'ready',
  })
})

describe('SystemTest runtime monitor', () => {
  it('does not present an empty Agent history as a passing test suite', async () => {
    const { default: Page } = await import('./SystemTest')

    render(<MemoryRouter><Page /></MemoryRouter>)

    expect(await screen.findByText('Agent 运行监控')).toBeInTheDocument()
    expect(screen.getByText('暂无任务类型数据')).toBeInTheDocument()
    expect(screen.getAllByText('暂无数据').length).toBeGreaterThan(0)
    expect(screen.queryByText('重新统计')).not.toBeInTheDocument()
    expect(agentApi.getHallucinationMetrics).not.toHaveBeenCalled()
    expect(agentApi.getPerformanceMetrics).not.toHaveBeenCalled()
  })
})
