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
        calculatedAt: '2026-08-09T12:34:00Z',
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
    expect(screen.getByText('待采集')).toBeInTheDocument()
    expect(screen.getByText('样本数：0（至少 5）')).toBeInTheDocument()
    expect(screen.getByText(/更新时间：/)).toBeInTheDocument()
  })

  it('judges resource matching only after enough samples are collected', async () => {
    setMockStore({
      systemMetrics: {
        hallucinationRate: null,
        hasSufficientSample: false,
        resourceMatchAccuracy: 96.4,
        knowledgeCoverageRate: 100,
        calculatedAt: '2026-08-09T12:34:00Z',
        totalLearners: 5,
        totalResources: 5,
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

    expect(await screen.findAllByText('96.4%')).toHaveLength(2)
    expect(screen.getAllByText('达标')).toHaveLength(2)
    expect(screen.getByText('样本数：5（至少 5）')).toBeInTheDocument()
    expect(screen.getByText(/更新时间：/)).toBeInTheDocument()
  })

  it('keeps a resource match value pending while the sample is still insufficient', async () => {
    setMockStore({
      systemMetrics: {
        hallucinationRate: null,
        hasSufficientSample: false,
        resourceMatchAccuracy: 96.4,
        knowledgeCoverageRate: 100,
        calculatedAt: '2026-08-09T12:34:00Z',
        totalLearners: 5,
        totalResources: 4,
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

    expect(await screen.findAllByText('暂无数据')).not.toHaveLength(0)
    expect(screen.getByText('待采集')).toBeInTheDocument()
    expect(screen.getByText('样本数：4（至少 5）')).toBeInTheDocument()
    expect(screen.queryByText('96.4%')).not.toBeInTheDocument()
  })

  it('uses canonical statuses and keeps a calculated zero visible', async () => {
    setMockStore({
      systemMetrics: {
        metrics: [
          { metricId: 'hallucination_rate', value: null, unit: '%', status: 'collecting', sampleCount: 2, minimumSampleSize: 5 },
          { metricId: 'resource_match_score', value: 0, unit: '%', status: 'ready', sampleCount: 1, minimumSampleSize: 1 },
          { metricId: 'resource_match_effectiveness', value: null, unit: '%', status: 'collecting', sampleCount: 1, minimumSampleSize: 3 },
          { metricId: 'knowledge_index_coverage', value: null, unit: '%', status: 'no_data', sampleCount: 0, minimumSampleSize: 1 },
        ],
        totalLearners: 1,
        totalResources: 1,
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

    expect((await screen.findAllByText('资源匹配分')).length).toBeGreaterThan(0)
    expect(screen.getAllByText('0.0%').length).toBeGreaterThan(0)
    expect(screen.getAllByText('样本不足').length).toBeGreaterThan(0)
    expect(screen.getAllByText('资源匹配效果').length).toBeGreaterThan(0)
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
