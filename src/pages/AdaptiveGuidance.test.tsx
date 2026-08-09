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
        generationMethod: 'deterministic_fallback',
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
    deleteInteractionHistory: vi.fn().mockResolvedValue({ deletedCount: 1 }),
    generateResources: vi.fn(),
    getResourceList: vi.fn(),
    getSystemMetrics: vi.fn(),
  },
  authApi: {}, learnerApi: {}, knowledgeApi: {}, agentApi: {}, privacyApi: {},
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
  window.localStorage.clear()
  vi.mocked(coreApi.getTutoringQuestions).mockResolvedValue([
    {
      id: 'q1',
      type: 'single',
      topic: 'CNN',
      question: 'Which option is correct?',
      options: ['Option A', 'Option B'],
      difficulty: 2,
      generationMethod: 'deterministic_fallback',
    },
  ])
  vi.mocked(coreApi.getInteractionHistory).mockResolvedValue({ learnerId: 1, history: [], total: 0, page: 1, pageSize: 20 })
  vi.mocked(coreApi.deleteInteractionHistory).mockResolvedValue({ deletedCount: 1 })
  vi.mocked(coreApi.submitAnswer).mockResolvedValue({ isCorrect: true, score: 100, generatedContent: {} })
  vi.mocked(coreApi.generateTutoringQuestions).mockResolvedValue({
    questions: [{
      id: 'q2',
      type: 'single',
      topic: 'CNN',
      question: 'Generated next question',
      options: ['Option A', 'Option B'],
      difficulty: 3,
      generationMethod: 'deepseek',
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

  it('loads questions and submits an answer for the current learner without leaking answer data', async () => {
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
    expect(coreApi.generateTutoringQuestions).not.toHaveBeenCalled()
  })

  it('does not show a wrong result while the server is still judging the answer', async () => {
    const user = userEvent.setup()
    let resolveSubmit: ((value: unknown) => void) | undefined
    vi.mocked(coreApi.submitAnswer).mockReturnValueOnce(new Promise((resolve) => {
      resolveSubmit = resolve
    }))
    const { default: Page } = await import('./AdaptiveGuidance')
    renderWithRouter(<Page />)

    await user.click(await screen.findByRole('button', { name: /Option B/ }))
    await user.click(screen.getByRole('button', { name: '提交答案' }))
    expect(screen.queryByText('判定结果：回答错误')).not.toBeInTheDocument()
    expect(screen.queryByText('判定结果：回答正确')).not.toBeInTheDocument()

    resolveSubmit?.({ isCorrect: true, score: 100, generatedContent: {} })
    expect(await screen.findByText('判定结果：回答正确')).toBeInTheDocument()
  })

  it('keeps both explanation tabs available after a result is returned', async () => {
    const user = userEvent.setup()
    vi.mocked(coreApi.submitAnswer).mockResolvedValueOnce({
      isCorrect: true,
      score: 100,
      generatedContent: {
        simpleExplanation: '通俗讲解内容',
        knowledgeExpansion: {
          title: 'CNN - 知识点扩展',
          overview: '知识点概览内容',
          keyPoints: ['卷积核与感受野'],
        },
      },
    })
    const { default: Page } = await import('./AdaptiveGuidance')
    renderWithRouter(<Page />)

    await user.click(await screen.findByRole('button', { name: /Option B/ }))
    await user.click(screen.getByRole('button', { name: '提交答案' }))
    expect(await screen.findByText('简化版通俗讲解')).toBeInTheDocument()
    const expansionTab = screen.getByRole('button', { name: '知识点扩展学习' })
    expect(expansionTab).toBeEnabled()
    await user.click(expansionTab)
    expect(await screen.findByText('知识点概览内容')).toBeInTheDocument()
  })

  it('shows the generation form and sends the configured topic, difficulty and count', async () => {
    const user = userEvent.setup()
    vi.mocked(coreApi.getTutoringQuestions).mockResolvedValue([])
    const { default: Page } = await import('./AdaptiveGuidance')
    renderWithRouter(<Page />)

    const topic = await screen.findByLabelText('主题关键词')
    const difficulty = screen.getByLabelText('目标难度（1–5，可留空）')
    const count = screen.getByLabelText('题量（1–10）')
    await user.type(topic, 'REST API')
    await user.type(difficulty, '4')
    await user.clear(count)
    await user.type(count, '5')
    await user.click(screen.getByRole('button', { name: '生成导学题目' }))

    await waitFor(() => expect(coreApi.generateTutoringQuestions).toHaveBeenCalledWith({
      learnerId: 1,
      topic: 'REST API',
      difficulty: 4,
      questionCount: 5,
      replacePending: true,
    }))
    expect(await screen.findByText('Generated next question')).toBeInTheDocument()
  })

  it('rejects invalid form values without sending a generation request', async () => {
    const user = userEvent.setup()
    vi.mocked(coreApi.getTutoringQuestions).mockResolvedValue([])
    const { default: Page } = await import('./AdaptiveGuidance')
    renderWithRouter(<Page />)

    const topic = await screen.findByLabelText('主题关键词')
    const difficulty = screen.getByLabelText('目标难度（1–5，可留空）')
    const count = screen.getByLabelText('题量（1–10）')

    await user.type(topic, '反向传播')
    await user.type(difficulty, '6')
    await user.click(screen.getByRole('button', { name: '生成导学题目' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('目标难度必须是 1–5 的整数')
    expect(coreApi.generateTutoringQuestions).not.toHaveBeenCalled()

    await user.clear(topic)
    await user.clear(difficulty)
    await user.click(screen.getByRole('button', { name: '生成导学题目' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('请输入主题关键词')
    expect(coreApi.generateTutoringQuestions).not.toHaveBeenCalled()

    await user.type(topic, 'REST API')
    await user.clear(count)
    await user.type(count, '11')
    await user.click(screen.getByRole('button', { name: '生成导学题目' }))
    expect(await screen.findByText('题量必须是 1–10 的整数')).toBeInTheDocument()
    expect(coreApi.generateTutoringQuestions).not.toHaveBeenCalled()
  })

  it('uses the learner profile when target difficulty is left empty', async () => {
    const user = userEvent.setup()
    vi.mocked(coreApi.getTutoringQuestions).mockResolvedValue([])
    const { default: Page } = await import('./AdaptiveGuidance')
    renderWithRouter(<Page />)

    await user.type(await screen.findByLabelText('主题关键词'), '反向传播')
    await user.click(screen.getByRole('button', { name: '生成导学题目' }))

    await waitFor(() => expect(coreApi.generateTutoringQuestions).toHaveBeenCalledWith({
      learnerId: 1,
      topic: '反向传播',
      difficulty: undefined,
      questionCount: 1,
      replacePending: true,
    }))
  })

  it('keeps form values and allows retry after generation failure', async () => {
    const user = userEvent.setup()
    vi.mocked(coreApi.getTutoringQuestions).mockResolvedValue([])
    vi.mocked(coreApi.generateTutoringQuestions)
      .mockRejectedValueOnce(new Error('主题暂时没有可用题目'))
      .mockResolvedValueOnce({
        questions: [{
          id: 'q2',
          type: 'single',
          topic: '反向传播算法',
          question: 'Retry question',
          options: ['A', 'B'],
          difficulty: 3,
          generationMethod: 'deterministic_fallback',
        }],
        generationMethod: 'deterministic_fallback',
      })
    const { default: Page } = await import('./AdaptiveGuidance')
    renderWithRouter(<Page />)

    const topic = await screen.findByLabelText('主题关键词')
    await user.type(topic, '反向传播')
    await user.click(screen.getByRole('button', { name: '生成导学题目' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('主题暂时没有可用题目')
    expect(topic).toHaveValue('反向传播')

    await user.click(screen.getByRole('button', { name: '生成导学题目' }))
    expect(await screen.findByText('Retry question')).toBeInTheDocument()
    expect(coreApi.generateTutoringQuestions).toHaveBeenCalledTimes(2)
  })

  it('shows a specific load error and retries the question-bank request', async () => {
    const user = userEvent.setup()
    vi.mocked(coreApi.getTutoringQuestions)
      .mockRejectedValueOnce(new Error('题库服务暂时不可用'))
      .mockResolvedValueOnce([])
    const { default: Page } = await import('./AdaptiveGuidance')
    renderWithRouter(<Page />)

    expect(await screen.findByText('导学题库加载失败')).toBeInTheDocument()
    expect(screen.getByText('题库服务暂时不可用')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '重试' }))
    expect(await screen.findByLabelText('主题关键词')).toBeInTheDocument()
    expect(coreApi.getTutoringQuestions).toHaveBeenCalledTimes(2)
  })

  it('directs learners without a profile to the profile page', async () => {
    setMockStore({ currentLearner: null, learners: [] })
    const { default: Page } = await import('./AdaptiveGuidance')
    renderWithRouter(<Page />)

    expect(await screen.findByText('请先创建学习者画像')).toBeInTheDocument()
    expect(coreApi.getTutoringQuestions).not.toHaveBeenCalled()
  })

  it('displays the question generation source', async () => {
    const { default: Page } = await import('./AdaptiveGuidance')
    renderWithRouter(<Page />)

    expect(await screen.findByText('题目来源：本地兜底题')).toBeInTheDocument()
  })

  it('shows a fixed session denominator and exits back to the configuration form', async () => {
    const user = userEvent.setup()
    vi.mocked(coreApi.getTutoringQuestions).mockResolvedValue([])
    vi.mocked(coreApi.generateTutoringQuestions).mockResolvedValue({
      questions: Array.from({ length: 5 }, (_, index) => ({
        id: `fixed-${index}`,
        type: 'single',
        topic: 'REST API',
        question: `Fixed question ${index + 1}`,
        options: ['Option A', 'Option B'],
        difficulty: 5,
        generationMethod: 'deterministic_fallback',
      })),
      generationMethod: 'deterministic_fallback',
    })
    const { default: Page } = await import('./AdaptiveGuidance')
    renderWithRouter(<Page />)

    await user.type(await screen.findByLabelText('主题关键词'), 'REST API')
    await user.type(screen.getByLabelText('目标难度（1–5，可留空）'), '5')
    await user.clear(screen.getByLabelText('题量（1–10）'))
    await user.type(screen.getByLabelText('题量（1–10）'), '5')
    await user.click(screen.getByRole('button', { name: '生成导学题目' }))

    expect(await screen.findByText('0/5')).toBeInTheDocument()
    expect(await screen.findByText('Fixed question 1')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Option A/ }))
    await user.click(screen.getByRole('button', { name: '提交答案' }))
    await waitFor(() => expect(screen.getByText('1/5')).toBeInTheDocument())
    expect(coreApi.generateTutoringQuestions).toHaveBeenCalledTimes(1)
    expect(coreApi.submitAnswer).toHaveBeenCalledWith(expect.objectContaining({
      learnerId: 1,
      sequenceIndex: 1,
      sessionId: expect.stringMatching(/^session_/),
    }))
    await user.click(screen.getByRole('button', { name: '退出本轮' }))
    expect(await screen.findByLabelText('主题关键词')).toHaveValue('REST API')
    expect(screen.queryByText('Fixed question 1')).not.toBeInTheDocument()
  })

  it('keeps a blank-difficulty session adaptive without exceeding its configured count', async () => {
    const user = userEvent.setup()
    vi.mocked(coreApi.getTutoringQuestions).mockResolvedValue([])
    const { default: Page } = await import('./AdaptiveGuidance')
    renderWithRouter(<Page />)

    await user.type(await screen.findByLabelText('主题关键词'), '反向传播')
    await user.clear(screen.getByLabelText('题量（1–10）'))
    await user.type(screen.getByLabelText('题量（1–10）'), '3')
    await user.click(screen.getByRole('button', { name: '生成导学题目' }))
    await user.click(await screen.findByRole('button', { name: /Option A/ }))
    await user.click(screen.getByRole('button', { name: '提交答案' }))

    await waitFor(() => expect(coreApi.generateTutoringQuestions).toHaveBeenCalledTimes(2))
    expect(coreApi.generateTutoringQuestions).toHaveBeenLastCalledWith({
      learnerId: 1,
      topic: '反向传播',
      difficulty: 4,
      questionCount: 1,
      replacePending: true,
    })
    expect(await screen.findByText('1/3')).toBeInTheDocument()
  })

  it('restores an unfinished session after leaving and returning to the page', async () => {
    const user = userEvent.setup()
    vi.mocked(coreApi.getTutoringQuestions).mockResolvedValue([])
    const { default: Page } = await import('./AdaptiveGuidance')
    const firstRender = renderWithRouter(<Page />)

    await user.type(await screen.findByLabelText('主题关键词'), 'REST API')
    await user.click(screen.getByRole('button', { name: '生成导学题目' }))
    expect(await screen.findByText('Generated next question')).toBeInTheDocument()
    firstRender.unmount()

    renderWithRouter(<Page />)
    expect(await screen.findByText('Generated next question')).toBeInTheDocument()
  })

  it('makes interaction history useful as a clickable answer replay', async () => {
    const user = userEvent.setup()
    vi.mocked(coreApi.getInteractionHistory).mockResolvedValue({
      learnerId: 1,
      history: [{
        recordId: 7,
        sessionId: 's1',
        sequenceIndex: 1,
        questionId: 10,
        questionType: 'single',
        questionTopic: '反向传播算法',
        questionContent: '反向传播中链式法则的作用是什么？',
        questionDifficulty: 5,
        userAnswer: 'B',
        result: 'wrong',
        score: 0,
        timeSpentMs: 1000,
        agentDecision: 'simplify',
        decisionReason: '需要简化解释',
        decisionConfidence: 0.8,
        nextAction: 'simplify',
        nextResourceId: null,
        feedbackGiven: true,
        feedbackContent: '先复习链式法则的局部梯度。',
        createdAt: '2026-08-07T00:00:00Z',
      }],
      total: 1,
      page: 1,
      pageSize: 20,
    })
    const { default: Page } = await import('./AdaptiveGuidance')
    renderWithRouter(<Page />)

    await user.click(await screen.findByRole('button', { name: /反向传播算法/ }))
    expect(await screen.findByText('题目回放：')).toBeInTheDocument()
    expect(screen.getByText('反向传播中链式法则的作用是什么？')).toBeInTheDocument()
    expect(screen.getByText('我的答案：B')).toBeInTheDocument()
    expect(screen.getByText('先复习链式法则的局部梯度。')).toBeInTheDocument()
  })

  it('numbers history rounds chronologically while displaying the newest round first', async () => {
    const makeRecord = (recordId: number, sessionId: string, createdAt: string) => ({
      recordId,
      sessionId,
      sequenceIndex: 1,
      questionId: recordId,
      questionType: 'single',
      questionTopic: 'AGI',
      questionContent: `Question ${recordId}`,
      questionDifficulty: 5,
      userAnswer: 'A',
      result: 'correct',
      score: 100,
      timeSpentMs: 1000,
      agentDecision: 'advance',
      decisionReason: '本题判定为正确',
      decisionConfidence: 0.9,
      nextAction: 'advance',
      nextResourceId: null,
      feedbackGiven: true,
      feedbackContent: '反馈',
      createdAt,
    })
    vi.mocked(coreApi.getInteractionHistory).mockResolvedValue({
      learnerId: 1,
      history: [
        makeRecord(3, 'round-3', '2026-08-06T22:20:00'),
        makeRecord(2, 'round-2', '2026-08-06T22:19:00'),
        makeRecord(1, 'round-1', '2026-08-06T22:17:00'),
      ],
      total: 3,
      page: 1,
      pageSize: 20,
    })
    const { default: Page } = await import('./AdaptiveGuidance')
    renderWithRouter(<Page />)

    const roundLabels = await screen.findAllByText(/^第 \d 轮$/)
    expect(roundLabels.map((element) => element.textContent)).toEqual(['第 3 轮', '第 2 轮', '第 1 轮'])
  })

  it('lets the configuration page switch the learner profile for this round', async () => {
    const user = userEvent.setup()
    vi.mocked(coreApi.getTutoringQuestions).mockResolvedValue([])
    vi.mocked(coreApi.generateTutoringQuestions).mockResolvedValue({
      questions: [{
        id: 'learner-2-question',
        type: 'single',
        topic: 'REST API',
        question: 'Learner two question',
        options: ['A', 'B'],
        difficulty: 3,
        generationMethod: 'deterministic_fallback',
      }],
      generationMethod: 'deterministic_fallback',
    })
    setMockStore({
      currentLearner: { id: 1, realName: '测试学习者', displayName: 'L001' },
      learners: [
        { id: 1, realName: '测试学习者', displayName: 'L001', major: '算法' },
        { id: 2, realName: '第二学习者', displayName: 'L002', major: '后端开发' },
      ],
    })
    const { default: Page } = await import('./AdaptiveGuidance')
    renderWithRouter(<Page />)

    await user.selectOptions(await screen.findByLabelText('本轮学习者画像'), '2')
    await user.type(screen.getByLabelText('主题关键词'), 'REST API')
    await user.click(screen.getByRole('button', { name: '生成导学题目' }))

    await waitFor(() => expect(coreApi.generateTutoringQuestions).toHaveBeenCalledWith(expect.objectContaining({
      learnerId: 2,
    })))
    expect(await screen.findByText('Learner two question')).toBeInTheDocument()
  })

  it('deletes a single history record and keeps the history panel bounded', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    vi.mocked(coreApi.getInteractionHistory).mockResolvedValue({
      learnerId: 1,
      history: [{
        recordId: 7,
        sessionId: 'round-1',
        sequenceIndex: 1,
        questionId: 10,
        questionType: 'single',
        questionTopic: '反向传播算法',
        questionContent: '历史题目',
        questionDifficulty: 3,
        userAnswer: 'B',
        result: 'wrong',
        score: 0,
        timeSpentMs: 1000,
        agentDecision: 'simplify',
        decisionReason: '需要复习',
        decisionConfidence: 0.8,
        nextAction: 'simplify',
        nextResourceId: null,
        feedbackGiven: true,
        feedbackContent: '复习建议',
        createdAt: '2026-08-07T00:00:00Z',
      }],
      total: 1,
      page: 1,
      pageSize: 20,
    })
    const { default: Page } = await import('./AdaptiveGuidance')
    const { container } = renderWithRouter(<Page />)

    expect(await screen.findByText('第 1 轮')).toBeInTheDocument()
    expect(container.querySelector('.max-h-\\[420px\\]')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '删除第1题记录' }))

    await waitFor(() => expect(coreApi.deleteInteractionHistory).toHaveBeenCalledWith(1, { recordId: 7 }))
    expect(screen.getByText('暂无交互记录')).toBeInTheDocument()
    vi.restoreAllMocks()
  })
})
