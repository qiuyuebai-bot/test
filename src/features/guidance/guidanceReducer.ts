import type { TutoringQuestion } from '@/api/core'
import type { BatchSubmitResult, GuidanceState, SessionConfig, SubmitResult } from './types'

export const initialGuidanceState: GuidanceState = {
  phase: 'initializing',
  hydrated: false,
  questions: [],
  currentQuestion: 0,
  selectedAnswers: [],
  answersByQuestionId: {},
  showResult: false,
  sessionConfig: null,
  correctCount: 0,
  generationMethod: null,
  submitResult: null,
  batchResult: null,
  pendingNextDifficulty: null,
  generationError: null,
  submissionError: null,
  nextQuestionError: null,
  loadError: null,
  historyRecords: [],
  historyLoading: false,
  historyError: null,
}

type GenerationMode = 'start' | 'append'

export type GuidanceAction =
  | { type: 'load_started' }
  | {
      type: 'hydrated'
      questions: TutoringQuestion[]
      sessionConfig: SessionConfig | null
      currentQuestion?: number
      selectedAnswers?: number[]
      showResult?: boolean
      correctCount?: number
      generationMethod?: string | null
      submitResult?: SubmitResult | null
      answersByQuestionId?: Record<string, number[]>
      batchResult?: BatchSubmitResult | null
    }
  | { type: 'load_failed'; error: string }
  | { type: 'generation_started'; clearError?: boolean }
  | {
      type: 'generation_succeeded'
      mode: GenerationMode
      questions: TutoringQuestion[]
      generationMethod?: string | null
      sessionConfig?: SessionConfig
    }
  | { type: 'session_topic_updated'; topic: string }
  | { type: 'generation_failed'; error: string; silent?: boolean }
  | { type: 'select_answer'; index: number; multiple: boolean }
  | { type: 'go_to_question'; index: number }
  | { type: 'submit_started' }
  | {
      type: 'submit_succeeded'
      result: SubmitResult
      completed: boolean
      nextDifficulty?: number | null
    }
  | { type: 'submit_failed'; error: string }
  | { type: 'batch_validation_failed'; index: number; error: string }
  | { type: 'batch_submit_started' }
  | { type: 'batch_submit_succeeded'; result: BatchSubmitResult }
  | { type: 'batch_submit_failed'; error: string }
  | { type: 'prefetch_started'; difficulty: number }
  | { type: 'prefetch_succeeded'; questions: TutoringQuestion[]; generationMethod?: string | null }
  | { type: 'prefetch_failed'; error: string }
  | { type: 'advance_question' }
  | { type: 'exit_session' }
  | { type: 'history_started' }
  | { type: 'history_loaded'; records: GuidanceState['historyRecords'] }
  | { type: 'history_failed'; error: string }
  | { type: 'clear_errors' }

export function guidanceReducer(state: GuidanceState, action: GuidanceAction): GuidanceState {
  switch (action.type) {
    case 'load_started':
      return {
        ...initialGuidanceState,
        phase: 'initializing',
        historyLoading: state.historyLoading,
      }
    case 'hydrated':
      {
      const sessionConfig = action.sessionConfig?.mode
        ? action.sessionConfig
        : action.sessionConfig
        ? { ...action.sessionConfig, mode: 'adaptive' as const }
        : null
      return {
        ...state,
        phase: action.questions.length > 0
          ? sessionConfig?.mode === 'batch' && action.batchResult ? 'batchReview' : action.showResult ? 'feedback' : 'answering'
          : 'ready',
        hydrated: true,
        questions: action.questions,
        sessionConfig,
        currentQuestion: action.currentQuestion ?? 0,
        selectedAnswers: action.selectedAnswers ?? [],
        answersByQuestionId: action.answersByQuestionId ?? {},
        showResult: action.showResult ?? false,
        correctCount: action.correctCount ?? 0,
        generationMethod: action.generationMethod ?? null,
        submitResult: action.submitResult ?? null,
        batchResult: action.batchResult ?? null,
        generationError: null,
        submissionError: null,
        nextQuestionError: null,
        loadError: null,
      }
      }
    case 'load_failed':
      return { ...state, hydrated: true, phase: 'ready', loadError: action.error }
    case 'generation_started':
      return {
        ...state,
        phase: 'generatingQuestion',
        generationError: action.clearError === false ? state.generationError : null,
        nextQuestionError: null,
      }
    case 'generation_succeeded':
      if (action.mode === 'append') {
        const insertAt = state.currentQuestion + 1
        return {
          ...state,
          phase: state.showResult ? 'feedback' : 'answering',
          questions: [...state.questions.slice(0, insertAt), ...action.questions, ...state.questions.slice(insertAt)],
          generationMethod: action.generationMethod ?? state.generationMethod,
          generationError: null,
          nextQuestionError: null,
          pendingNextDifficulty: null,
        }
      }
      return {
        ...state,
        phase: 'answering',
        questions: action.questions,
        currentQuestion: 0,
        selectedAnswers: [],
        showResult: false,
        submitResult: null,
        answersByQuestionId: {},
        batchResult: null,
        sessionConfig: action.sessionConfig ?? state.sessionConfig,
        generationMethod: action.generationMethod ?? action.questions[0]?.generationMethod ?? null,
        generationError: null,
        submissionError: null,
        nextQuestionError: null,
        pendingNextDifficulty: null,
      }
    case 'session_topic_updated':
      if (!state.sessionConfig || state.sessionConfig.topic.trim() || !action.topic.trim()) return state
      return {
        ...state,
        sessionConfig: { ...state.sessionConfig, topic: action.topic.trim() },
      }
    case 'generation_failed':
      return {
        ...state,
        phase: state.questions.length > 0 ? (state.showResult ? 'feedback' : 'answering') : 'ready',
        generationError: action.silent ? state.generationError : action.error,
        nextQuestionError: action.silent ? action.error : state.nextQuestionError,
        pendingNextDifficulty: action.silent ? state.pendingNextDifficulty : null,
      }
    case 'select_answer': {
      const selectedAnswers = action.multiple
        ? state.selectedAnswers.includes(action.index)
          ? state.selectedAnswers.filter((index) => index !== action.index)
          : [...state.selectedAnswers, action.index]
        : [action.index]
      if (state.sessionConfig?.mode === 'batch' && state.questions[state.currentQuestion]) {
        const questionId = state.questions[state.currentQuestion].id
        return {
          ...state,
          selectedAnswers,
          answersByQuestionId: { ...state.answersByQuestionId, [questionId]: selectedAnswers },
          phase: 'answering',
          submissionError: null,
        }
      }
      return { ...state, selectedAnswers, phase: state.showResult ? state.phase : 'answering' }
    }
    case 'go_to_question': {
      const currentQuestion = Math.min(Math.max(0, action.index), Math.max(0, state.questions.length - 1))
      const questionId = state.questions[currentQuestion]?.id
      return {
        ...state,
        currentQuestion,
        selectedAnswers: questionId ? state.answersByQuestionId[questionId] ?? [] : [],
        phase: 'answering',
        showResult: false,
        submitResult: null,
        submissionError: null,
      }
    }
    case 'submit_started':
      return { ...state, phase: 'submitting', submissionError: null, nextQuestionError: null, submitResult: null }
    case 'submit_succeeded':
      return {
        ...state,
        phase: action.completed ? 'completed' : 'feedback',
        showResult: true,
        submitResult: action.result,
        correctCount: action.result.isCorrect ? state.correctCount + 1 : state.correctCount,
        pendingNextDifficulty: action.nextDifficulty ?? null,
        submissionError: null,
      }
    case 'submit_failed':
      return { ...state, phase: 'answering', showResult: false, submissionError: action.error }
    case 'batch_validation_failed':
      return {
        ...state,
        phase: 'answering',
        currentQuestion: Math.min(Math.max(0, action.index), Math.max(0, state.questions.length - 1)),
        selectedAnswers: state.questions[action.index]?.id ? state.answersByQuestionId[state.questions[action.index].id] ?? [] : [],
        showResult: false,
        submissionError: action.error,
      }
    case 'batch_submit_started':
      return { ...state, phase: 'submitting', submissionError: null, batchResult: null }
    case 'batch_submit_succeeded':
      return {
        ...state,
        phase: 'batchReview',
        showResult: true,
        batchResult: action.result,
        correctCount: action.result.correctCount,
        submissionError: null,
      }
    case 'batch_submit_failed':
      return { ...state, phase: 'answering', showResult: false, submissionError: action.error }
    case 'prefetch_started':
      return { ...state, phase: 'preparingNext', pendingNextDifficulty: action.difficulty, nextQuestionError: null }
    case 'prefetch_succeeded':
      return {
        ...state,
        phase: state.showResult ? 'feedback' : 'answering',
        questions: [...state.questions.slice(0, state.currentQuestion + 1), ...action.questions],
        generationMethod: action.generationMethod ?? state.generationMethod,
        pendingNextDifficulty: null,
        nextQuestionError: null,
      }
    case 'prefetch_failed':
      return { ...state, phase: state.showResult ? 'feedback' : 'answering', nextQuestionError: action.error }
    case 'advance_question':
      return {
        ...state,
        phase: state.currentQuestion + 1 >= state.questions.length ? 'completed' : 'answering',
        currentQuestion: Math.min(state.currentQuestion + 1, Math.max(0, state.questions.length - 1)),
        selectedAnswers: [],
        showResult: false,
        submitResult: null,
        submissionError: null,
        nextQuestionError: null,
        pendingNextDifficulty: null,
      }
    case 'exit_session':
      return {
        ...state,
        phase: 'ready',
        questions: [],
        currentQuestion: 0,
        selectedAnswers: [],
        answersByQuestionId: {},
        showResult: false,
        sessionConfig: null,
        correctCount: 0,
        submitResult: null,
        batchResult: null,
        pendingNextDifficulty: null,
        generationError: null,
        submissionError: null,
        nextQuestionError: null,
      }
    case 'history_started':
      return { ...state, historyLoading: true, historyError: null }
    case 'history_loaded':
      return { ...state, historyLoading: false, historyError: null, historyRecords: action.records }
    case 'history_failed':
      return { ...state, historyLoading: false, historyError: action.error }
    case 'clear_errors':
      return { ...state, generationError: null, submissionError: null, nextQuestionError: null, loadError: null }
    default:
      return state
  }
}
