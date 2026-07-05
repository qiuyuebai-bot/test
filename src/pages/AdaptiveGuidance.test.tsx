import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithRouter } from '../test/renderPage'

vi.mock('@/store', async () => {
  const { useStoreMock } = await import('../test/mockStore')
  return { useStore: useStoreMock }
})
vi.mock('@/api', () => ({
  coreApi: {
    getTutoringQuestions: vi.fn().mockResolvedValue([
      {
        id: 'q1',
        type: 'single',
        topic: 'CNN',
        question: '卷积神经网络的核心操作是什么？',
        options: ['卷积', '排序', '哈希', '递归'],
        correctAnswer: '卷积',
        correctIndex: 0,
        difficulty: 2,
      },
    ]),
    getInteractionHistory: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 20, totalPages: 0 }),
    generateResources: vi.fn(),
    getResourceList: vi.fn(),
    getSystemMetrics: vi.fn(),
  },
  authApi: {}, learnerApi: {}, knowledgeApi: {}, agentApi: {}, trainingApi: {}, privacyApi: {},
}))
vi.mock('@/hooks', () => ({
  useTaskSSE: () => ({
    events: [], currentStage: null, progress: 0, isConnected: false,
    isCompleted: false, isFailed: false, error: null, lastEvent: null,
  }),
}))

const { resetMockStore, setMockStore } = await import('../test/mockStore')

beforeEach(() => {
  resetMockStore()
  setMockStore({ currentLearner: { id: 1, realName: '测试学习者', displayName: 'L001' } })
})

describe('AdaptiveGuidance page', () => {
  it('renders the adaptive guidance heading with question bank loaded', async () => {
    const { default: Page } = await import('./AdaptiveGuidance')
    renderWithRouter(<Page />)
    expect(await screen.findByText('动态自适应导学', undefined, { timeout: 3000 })).toBeInTheDocument()
  })
})
