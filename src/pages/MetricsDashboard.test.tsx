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
})

describe('MetricsDashboard', () => {
  it('renders live coverage and distinguishes missing values from zero', async () => {
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
    const { default: Page } = await import('./MetricsDashboard')

    render(<MemoryRouter><Page /></MemoryRouter>)

    expect((await screen.findAllByText('100.0%')).length).toBeGreaterThan(0)
    expect(screen.getAllByText('暂无数据').length).toBeGreaterThan(0)
    expect(screen.getAllByText('样本不足/待审核').length).toBeGreaterThan(0)
  })

  it('shows an error state when the metrics request fails', async () => {
    setMockStore({
      fetchSystemMetrics: vi.fn().mockRejectedValue(new Error('指标服务不可用')),
      metricsStatus: 'error',
    })
    const { default: Page } = await import('./MetricsDashboard')

    render(<MemoryRouter><Page /></MemoryRouter>)

    expect(await screen.findByText('加载失败，请稍后重试')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '重试' })).toBeInTheDocument()
  })
})
