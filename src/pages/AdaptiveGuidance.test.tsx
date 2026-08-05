import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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
        question: 'Which option is correct?',
        options: ['Option A', 'Option B'],
        difficulty: 2,
      },
    ]),
    submitAnswer: vi.fn().mockResolvedValue({
      isCorrect: true,
      score: 100,
      generatedContent: {},
    }),
    generateTutoringQuestions: vi.fn().mockResolvedValue({
      questions: [],
      generationMethod: 'deterministic_fallback',
    }),
    getInteractionHistory: vi.fn().mockResolvedValue({ learnerId: 1, history: [], total: 0, page: 1, pageSize: 20 }),
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
const { coreApi } = await import('@/api')

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(coreApi.getTutoringQuestions).mockResolvedValue([
    {
      id: 'q1',
      type: 'single',
      topic: 'CNN',
      question: 'Which option is correct?',
      options: ['Option A', 'Option B'],
      difficulty: 2,
    },
  ])
  vi.mocked(coreApi.getInteractionHistory).mockResolvedValue({ learnerId: 1, history: [], total: 0, page: 1, pageSize: 20 })
  vi.mocked(coreApi.submitAnswer).mockResolvedValue({ isCorrect: true, score: 100, generatedContent: {} })
  vi.mocked(coreApi.generateTutoringQuestions).mockResolvedValue({
    questions: [{
      id: 'q2',
      type: 'single',
      topic: 'CNN',
      question: 'Generated next question',
      options: ['Option A', 'Option B'],
      difficulty: 3,
    }],
    generationMethod: 'deepseek',
  })
  resetMockStore()
  setMockStore({ currentLearner: { id: 1, realName: '测试学习者', displayName: 'L001' } })
})

describe('AdaptiveGuidance page', () => {
  it('renders the adaptive guidance heading with question bank loaded', async () => {
    const { default: Page } = await import('./AdaptiveGuidance')
    renderWithRouter(<Page />)
    expect(await screen.findByText('动态自适应导学', undefined, { timeout: 3000 })).toBeInTheDocument()
  })

  it('loads questions and submits an answer for the current learner without answer data', async () => {
    const user = userEvent.setup()
    const { default: Page } = await import('./AdaptiveGuidance')
    renderWithRouter(<Page />)

    await waitFor(() => expect(coreApi.getTutoringQuestions).toHaveBeenCalledWith(1))
    await user.click(await screen.findByRole('button', { name: /Option B/ }))
    await user.click(screen.getByRole('button', { name: '提交答案' }))

    await waitFor(() => expect(coreApi.submitAnswer).toHaveBeenCalledWith({
      learnerId: 1,
      questionId: 'q1',
      userAnswer: 'B',
      timeSpentMs: 0,
      hintsUsed: 0,
    }))
    await waitFor(() => expect(coreApi.generateTutoringQuestions).toHaveBeenCalledWith({
      learnerId: 1,
      topic: 'CNN',
      difficulty: 3,
      questionCount: 1,
      replacePending: true,
    }))
  })
})
