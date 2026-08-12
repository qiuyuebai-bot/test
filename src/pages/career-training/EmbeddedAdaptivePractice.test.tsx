import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('@/features/guidance/useGuidanceSession', () => ({
  useGuidanceSession: vi.fn(),
}))

vi.mock('@/store', async () => {
  const { useStoreMock } = await import('../../test/mockStore')
  return { useStore: useStoreMock }
})

import { useGuidanceSession } from '@/features/guidance/useGuidanceSession'
import { resetMockStore, setMockStore } from '../../test/mockStore'
import EmbeddedAdaptivePractice from './EmbeddedAdaptivePractice'
import type { PositionDetail } from '@/types/training'

const mockPosition: PositionDetail = {
  id: 1, code: 'FE-001', name: '前端工程师', category: 'tech', industry: '软件开发',
  level: 'junior', is_active: true, competencies: [], created_at: '', updated_at: '',
}

function mockSession(overrides: Record<string, unknown> = {}) {
  const base = {
    state: {
      phase: 'ready', hydrated: true, questions: [], currentQuestion: 0,
      selectedAnswers: [], showResult: false, sessionConfig: null, correctCount: 0,
      generationMethod: null, submitResult: null, pendingNextDifficulty: null,
      generationError: null, submissionError: null, nextQuestionError: null,
      loadError: null, historyRecords: [], historyLoading: false, historyError: null,
    },
    question: null,
    isPreparingNext: false,
    sessionTotal: 0,
    answeredCount: 0,
    progress: 0,
    recommendation: null,
    recommendationLoading: false,
    recommendationError: null,
    loadData: vi.fn(),
    loadHistory: vi.fn(),
    startSession: vi.fn().mockResolvedValue([]),
    selectAnswer: vi.fn(),
    submitAnswer: vi.fn(),
    nextQuestion: vi.fn(),
    retryNextQuestion: vi.fn(),
    exitSession: vi.fn(),
    deleteHistory: vi.fn(),
    clearHistory: vi.fn(),
  }
  vi.mocked(useGuidanceSession).mockReturnValue({ ...base, ...overrides } as never)
  return base
}

describe('EmbeddedAdaptivePractice', () => {
  beforeEach(() => {
    resetMockStore()
    vi.clearAllMocks()
  })

  it('无 learnerId 时提示需要学习者画像', () => {
    mockSession()
    render(<EmbeddedAdaptivePractice position={mockPosition} learnerId={null} />)
    expect(screen.getByText(/需要学习者画像/)).toBeInTheDocument()
  })

  it('有 learnerId 且 ready 时显示岗位上下文与开始按钮', () => {
    mockSession()
    render(<EmbeddedAdaptivePractice position={mockPosition} learnerId={10} />)
    expect(screen.getByText(/前端工程师/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /开始练习/ })).toBeInTheDocument()
  })

  it('点击开始练习时用岗位名作为 topic 调用 startSession', async () => {
    const session = mockSession()
    render(<EmbeddedAdaptivePractice position={mockPosition} learnerId={10} />)
    await userEvent.click(screen.getByRole('button', { name: /开始练习/ }))
    expect(session.startSession).toHaveBeenCalledWith(expect.objectContaining({ topic: '前端工程师' }))
  })

  it('answering 阶段显示题目与选项', () => {
    mockSession({
      state: {
        phase: 'answering', hydrated: true,
        questions: [{
          id: '1', type: 'single', difficulty: 3, topic: '前端工程师',
          question: 'React 中 useState 的作用是什么？',
          options: ['状态管理', '路由', '样式', '构建'],
          generationMethod: 'deepseek',
        }],
        currentQuestion: 0, selectedAnswers: [], showResult: false,
        sessionConfig: { topic: '前端工程师', difficulty: 3, questionCount: 5 },
        correctCount: 0, generationMethod: 'deepseek', submitResult: null,
        pendingNextDifficulty: null, generationError: null, submissionError: null,
        nextQuestionError: null, loadError: null,
        historyRecords: [], historyLoading: false, historyError: null,
      },
      question: {
        id: '1', type: 'single', difficulty: 3, topic: '前端工程师',
        question: 'React 中 useState 的作用是什么？',
        options: ['状态管理', '路由', '样式', '构建'],
        generationMethod: 'deepseek',
      },
      sessionTotal: 5, answeredCount: 0, progress: 0,
    })
    render(<EmbeddedAdaptivePractice position={mockPosition} learnerId={10} />)
    expect(screen.getByText(/useState/)).toBeInTheDocument()
    expect(screen.getByText('状态管理')).toBeInTheDocument()
  })
})
