import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

vi.mock('@/store', async () => {
  const { useStoreMock } = await import('../test/mockStore')
  return { useStore: useStoreMock }
})
vi.mock('@/hooks', () => ({
  useTaskSSE: () => ({
    events: [],
    currentStage: null,
    progress: 0,
    isConnected: false,
    isCompleted: false,
    isFailed: false,
    error: null,
    lastEvent: null,
  }),
}))
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  RadarChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  PolarGrid: () => <div />,
  PolarAngleAxis: () => <div />,
  PolarRadiusAxis: () => <div />,
  Radar: () => <div />,
}))

const { resetMockStore, setMockStore } = await import('../test/mockStore')

beforeEach(() => {
  resetMockStore()
})

describe('MultiAgentVisualization page', () => {
  it('renders the main heading after initial load', async () => {
    const { default: Page } = await import('./MultiAgentVisualization')
    render(<MemoryRouter><Page /></MemoryRouter>)
    expect(await screen.findByText('多智能体协同决策可视化')).toBeInTheDocument()
  })

  it('renders the flow step labels', async () => {
    const { default: Page } = await import('./MultiAgentVisualization')
    render(<MemoryRouter><Page /></MemoryRouter>)
    expect(await screen.findByText('读取学情画像')).toBeInTheDocument()
    expect(screen.getByText('诊断知识盲区')).toBeInTheDocument()
    expect(screen.getByText('输出个性化资源')).toBeInTheDocument()
  })

  it('renders the subtitle', async () => {
    const { default: Page } = await import('./MultiAgentVisualization')
    render(<MemoryRouter><Page /></MemoryRouter>)
    expect(await screen.findByText(/完整呈现学情诊断/)).toBeInTheDocument()
  })

  it('requires and submits a target topic for the default full-flow task', async () => {
    const startAgentTask = vi.fn().mockResolvedValue({ taskId: 9 })
    setMockStore({
      learners: [{ id: 1, realName: '测试学习者' }],
      startAgentTask,
    })
    const { default: Page } = await import('./MultiAgentVisualization')
    render(<MemoryRouter><Page /></MemoryRouter>)

    const topicInput = await screen.findByLabelText('目标主题')
    const startButton = screen.getByRole('button', { name: '启动任务' })
    expect(startButton).toBeDisabled()

    fireEvent.change(topicInput, { target: { value: '反向传播' } })
    expect(startButton).toBeEnabled()
    fireEvent.click(startButton)

    await waitFor(() => expect(startAgentTask).toHaveBeenCalledWith({
      learnerId: 1,
      taskType: 'full_flow',
      targetTopic: '反向传播',
    }))
  })
})
