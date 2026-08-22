import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

vi.mock('@/api', () => ({
  agentApi: {
    runFullPipeline: vi.fn().mockResolvedValue({ taskId: 42 }),
  },
  coreApi: {
    getResourceDetail: vi.fn(),
    getResourceList: vi.fn(),
  },
}))

vi.mock('@/hooks', () => ({
  useTaskSSE: vi.fn().mockReturnValue({
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

vi.mock('@/store', async () => {
  const { useStoreMock } = await import('../test/mockStore')
  return { useStore: useStoreMock }
})

vi.mock('@/components/MarkdownContent', () => ({
  __esModule: true,
  default: ({ content }: { content: string }) => <div data-testid="markdown">{content}</div>,
}))

import { agentApi } from '@/api'
import { useTaskSSE } from '@/hooks'
import { mockStoreState, resetMockStore, setMockStore } from '../test/mockStore'

const learner = {
  id: 6,
  realName: '测试学习者',
  educationLevel: '本科',
  major: '计算机科学',
}

describe('ResourceGeneration context modes', () => {
  beforeEach(() => {
    resetMockStore()
    vi.clearAllMocks()
    setMockStore({
      learners: [learner],
      currentLearner: learner,
      fetchResources: vi.fn().mockResolvedValue(undefined),
      fetchLearners: vi.fn().mockResolvedValue(undefined),
    })
    vi.mocked(useTaskSSE).mockReturnValue({
      events: [],
      currentStage: null,
      progress: 0,
      isConnected: false,
      isCompleted: false,
      isFailed: false,
      error: null,
      lastEvent: null,
    } as never)
  })

  it('list mode shows existing resources without exposing generation controls', async () => {
    const { default: Page } = await import('./ResourceGeneration')
    render(
      <MemoryRouter initialEntries={['/resources?mode=list&dimension=algorithm_design&topic=%E7%AE%97%E6%B3%95%E8%AE%BE%E8%AE%A1&learnerId=6']}>
        <Page />
      </MemoryRouter>,
    )

    expect(await screen.findByRole('heading', { name: '相关学习资源' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '生成资源' })).not.toBeInTheDocument()
    await waitFor(() => {
      expect((mockStoreState.fetchResources as ReturnType<typeof vi.fn>)).toHaveBeenCalledWith(
        expect.objectContaining({ learnerId: 6, topic: '算法设计' }),
      )
    })
  })

  it('generate mode prefills the topic and waits for explicit confirmation', async () => {
    const { default: Page } = await import('./ResourceGeneration')
    render(
      <MemoryRouter initialEntries={['/resources?mode=generate&dimension=algorithm_design&topic=%E7%AE%97%E6%B3%95%E8%AE%BE%E8%AE%A1&learnerId=6']}>
        <Page />
      </MemoryRouter>,
    )

    expect(await screen.findByRole('heading', { name: '生成学习资源' })).toBeInTheDocument()
    expect(screen.getByDisplayValue('算法设计')).toBeInTheDocument()
    expect(agentApi.runFullPipeline).not.toHaveBeenCalled()

    await userEvent.click(screen.getByRole('button', { name: '生成资源' }))
    await waitFor(() => {
      expect(agentApi.runFullPipeline).toHaveBeenCalledWith(expect.objectContaining({
        learnerId: 6,
        targetTopic: '算法设计',
      }))
    })
  })
})
