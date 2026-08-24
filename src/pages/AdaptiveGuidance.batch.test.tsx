import { describe, expect, it, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithRouter } from '../test/renderPage'

vi.mock('@/store', async () => {
  const { useStoreMock } = await import('../test/mockStore')
  return { useStore: useStoreMock }
})
vi.mock('@/api', () => ({
  coreApi: {
    getTutoringQuestions: vi.fn(),
    getInteractionHistory: vi.fn(),
    getGuidanceRecommendations: vi.fn(),
    generateTutoringQuestions: vi.fn(),
    submitAnswer: vi.fn(),
    submitBatch: vi.fn(),
    getBatchResult: vi.fn(),
    deleteInteractionHistory: vi.fn().mockResolvedValue({ deletedCount: 0 }),
  },
  authApi: {},
  learnerApi: {},
  knowledgeApi: {},
  agentApi: {},
  privacyApi: {},
}))
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

const { resetMockStore, setMockStore } = await import('../test/mockStore')
const { coreApi } = await import('@/api')

function fillCount(value: string) {
  const inputs = screen.getAllByRole('spinbutton')
  const count = inputs[inputs.length - 1]
  return { count, value }
}

beforeEach(() => {
  vi.clearAllMocks()
  window.localStorage.clear()
  resetMockStore()
  setMockStore({ currentLearner: { id: 1, realName: 'Test learner', displayName: 'L001' } })
  vi.mocked(coreApi.getTutoringQuestions).mockResolvedValue([])
  vi.mocked(coreApi.getGuidanceRecommendations).mockResolvedValue({
    primaryTopic: null,
    alternatives: [],
    recommendedDifficulty: 3,
    reason: '',
    source: 'fallback',
  })
  vi.mocked(coreApi.getInteractionHistory).mockResolvedValue({
    learnerId: 1,
    history: [],
    total: 0,
    page: 1,
    pageSize: 20,
  })
  vi.mocked(coreApi.submitBatch).mockResolvedValue({
    sessionId: 'batch-result',
    total: 2,
    correctCount: 2,
    score: 100,
    questions: [],
  })
  vi.mocked(coreApi.getBatchResult).mockRejectedValue(new Error('not found'))
})

describe('AdaptiveGuidance batch mode', () => {
  it('generates all questions once, navigates locally, and shows the unified result', async () => {
    const user = userEvent.setup()
    vi.mocked(coreApi.generateTutoringQuestions).mockResolvedValue({
      questions: [
        {
          id: 'batch-1',
          type: 'single',
          topic: 'REST API',
          question: 'Batch question 1',
          options: ['Option A', 'Option B'],
          difficulty: 3,
        },
        {
          id: 'batch-2',
          type: 'single',
          topic: 'REST API',
          question: 'Batch question 2',
          options: ['Option A', 'Option B'],
          difficulty: 3,
        },
      ],
      generationMethod: 'deterministic_fallback',
    })
    vi.mocked(coreApi.submitBatch).mockResolvedValue({
      sessionId: 'batch-result',
      total: 2,
      correctCount: 1,
      score: 50,
      questions: [
        {
          questionId: 'batch-1',
          isCorrect: true,
          score: 100,
          userAnswer: ['A'],
          correctAnswer: ['A'],
          explanation: 'First explanation',
          knowledgePoints: ['REST'],
        },
        {
          questionId: 'batch-2',
          isCorrect: false,
          score: 0,
          userAnswer: ['A'],
          correctAnswer: ['B'],
          explanation: 'Second explanation',
          knowledgePoints: ['HTTP'],
        },
      ],
    })
    const { default: Page } = await import('./AdaptiveGuidance')
    renderWithRouter(<Page />)

    await user.click(await screen.findByRole('button', { name: /整卷练习/ }))
    const topic = screen.getAllByRole('textbox')[0]
    await user.type(topic, 'REST API')
    const count = fillCount('2').count
    await user.clear(count)
    await user.type(count, '2')
    const generateButton = screen
      .getAllByRole('button')
      .find((button) => /生成导学题目/.test(button.textContent ?? ''))
    expect(generateButton).toBeDefined()
    await user.click(generateButton!)

    expect(await screen.findByText('Batch question 1')).toBeInTheDocument()
    await waitFor(() =>
      expect(coreApi.generateTutoringQuestions).toHaveBeenCalledWith(
        expect.objectContaining({
          assessmentMode: 'batch_practice',
          sessionId: expect.stringMatching(/^session_/),
          questionCount: 2,
        }),
      ),
    )
    await user.click(screen.getAllByRole('button', { name: /Option A/ })[0])
    await user.click(screen.getByRole('button', { name: /下一题/ }))
    expect(await screen.findByText('Batch question 2')).toBeInTheDocument()
    await user.click(screen.getAllByRole('button', { name: /Option A/ })[0])
    await user.click(screen.getByRole('button', { name: '提交整卷' }))

    await waitFor(() =>
      expect(coreApi.submitBatch).toHaveBeenCalledWith({
        learnerId: 1,
        sessionId: expect.stringMatching(/^session_/),
        answers: [
          { questionId: 'batch-1', userAnswer: 'A', sequenceIndex: 1 },
          { questionId: 'batch-2', userAnswer: 'A', sequenceIndex: 2 },
        ],
      }),
    )
    expect(await screen.findByText('整卷练习结果')).toBeInTheDocument()
    expect(await screen.findByText(/First explanation/)).toBeInTheDocument()
  })

  it('keeps all answers and hides explanations when batch submission fails', async () => {
    const user = userEvent.setup()
    vi.mocked(coreApi.generateTutoringQuestions).mockResolvedValue({
      questions: [
        {
          id: 'batch-fail-1',
          type: 'single',
          topic: 'REST API',
          question: 'Failure question 1',
          options: ['A', 'B'],
          difficulty: 3,
        },
        {
          id: 'batch-fail-2',
          type: 'single',
          topic: 'REST API',
          question: 'Failure question 2',
          options: ['A', 'B'],
          difficulty: 3,
        },
      ],
    })
    vi.mocked(coreApi.submitBatch).mockRejectedValueOnce(new Error('batch unavailable'))
    const { default: Page } = await import('./AdaptiveGuidance')
    renderWithRouter(<Page />)

    await user.click(await screen.findByRole('button', { name: /整卷练习/ }))
    await user.type(screen.getAllByRole('textbox')[0], 'REST API')
    const count = fillCount('2').count
    await user.clear(count)
    await user.type(count, '2')
    const generateButton = screen
      .getAllByRole('button')
      .find((button) => /生成导学题目/.test(button.textContent ?? ''))
    await user.click(generateButton!)
    await screen.findByText('Failure question 1')
    await user.click(screen.getAllByRole('button', { name: /^A A$/ })[0])
    await user.click(screen.getByRole('button', { name: /下一题/ }))
    await user.click(screen.getAllByRole('button', { name: /^A A$/ })[0])
    await user.click(screen.getByRole('button', { name: '提交整卷' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('batch unavailable')
    expect(screen.queryByText('整卷练习结果')).not.toBeInTheDocument()
    expect(window.localStorage.getItem('adaptive-guidance-session:1')).toContain('batch-fail-1')
  })

  it('recovers a durable result when the submit response was lost', async () => {
    const recoveredResult = {
      sessionId: 'session_recover',
      total: 2,
      correctCount: 1,
      score: 50,
      questions: [
        {
          questionId: 'recover-1',
          isCorrect: true,
          score: 100,
          userAnswer: ['A'],
          correctAnswer: ['A'],
          explanation: 'Recovered explanation',
          knowledgePoints: [],
        },
        {
          questionId: 'recover-2',
          isCorrect: false,
          score: 0,
          userAnswer: ['B'],
          correctAnswer: ['A'],
          explanation: 'Second explanation',
          knowledgePoints: [],
        },
      ],
    }
    vi.mocked(coreApi.getTutoringQuestions).mockResolvedValue([])
    vi.mocked(coreApi.getBatchResult).mockResolvedValue(recoveredResult)
    window.localStorage.setItem(
      'adaptive-guidance-session:1',
      JSON.stringify({
        config: {
          mode: 'batch',
          topic: 'REST API',
          questionCount: 2,
          sessionId: 'session_recover',
        },
        questions: [
          {
            id: 'recover-1',
            type: 'single',
            topic: 'REST API',
            question: 'Recover question 1',
            options: ['A', 'B'],
            difficulty: 3,
          },
          {
            id: 'recover-2',
            type: 'single',
            topic: 'REST API',
            question: 'Recover question 2',
            options: ['A', 'B'],
            difficulty: 3,
          },
        ],
        currentQuestion: 1,
        selectedAnswers: [],
        answersByQuestionId: { 'recover-1': [0], 'recover-2': [1] },
        showResult: false,
        correctCount: 0,
        generationMethod: 'test',
        submitResult: null,
      }),
    )

    const { default: Page } = await import('./AdaptiveGuidance')
    renderWithRouter(<Page />)

    await waitFor(() => expect(coreApi.getBatchResult).toHaveBeenCalledWith('session_recover', 1))
    expect(await screen.findByText('整卷练习结果')).toBeInTheDocument()
    expect(await screen.findByText(/Recovered explanation/)).toBeInTheDocument()
    expect(coreApi.getBatchResult).toHaveBeenCalledWith('session_recover', 1)
    expect(window.localStorage.getItem('adaptive-guidance-session:1')).toBeNull()
  })
})
