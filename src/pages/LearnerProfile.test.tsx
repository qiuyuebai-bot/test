import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithRouter } from '../test/renderPage'

vi.mock('@/store', async () => {
  const { useStoreMock } = await import('../test/mockStore')
  return { useStore: useStoreMock }
})
vi.mock('@/hooks', () => ({
  useTaskSSE: () => ({
    events: [], currentStage: null, progress: 0, isConnected: false,
    isCompleted: false, isFailed: false, error: null, lastEvent: null,
  }),
}))
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  RadarChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  PolarGrid: () => <div />,
  PolarAngleAxis: () => <div />,
  PolarRadiusAxis: () => <div />,
  Radar: () => <div />,
  AreaChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Area: () => <div />,
  XAxis: () => <div />,
  YAxis: () => <div />,
  Tooltip: () => <div />,
  CartesianGrid: () => <div />,
}))

const { resetMockStore } = await import('../test/mockStore')

beforeEach(() => {
  resetMockStore()
})

describe('LearnerProfile page', () => {
  it('renders the management heading after load', async () => {
    const { default: Page } = await import('./LearnerProfile')
    renderWithRouter(<Page />)
    expect(await screen.findByText('学习者画像管理')).toBeInTheDocument()
  })

  it('renders the descriptive subtitle', async () => {
    const { default: Page } = await import('./LearnerProfile')
    renderWithRouter(<Page />)
    expect(await screen.findByText(/录入\/读取学习者背景数据/)).toBeInTheDocument()
  })
})
