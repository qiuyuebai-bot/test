import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react'
import { coreApi } from '@/api'
import type { TutoringQuestion } from '@/api/core'
import { guidanceReducer, initialGuidanceState } from './guidanceReducer'
import {
  createSessionId,
  exitStorageKey,
  mergeQuestions,
  readPersistedSession,
  sessionStorageKey,
} from './sessionPersistence'
import type {
  GuidanceRecommendation,
  RecommendationOption,
  SessionConfig,
  SubmitResult,
  SubmitResultRaw,
  SubmitDataRaw,
} from './types'
import { mapHistoryRecord } from './types'

interface StartSessionOptions {
  topic?: string
  difficulty?: number
  questionCount?: number
}

interface GenerateOptions {
  topic?: string
  difficulty?: number
  questionCount: number
  mode: 'start' | 'append'
  sessionConfig?: SessionConfig
}

function toErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback
}

function normalizeRecommendation(value: GuidanceRecommendation | null | undefined): GuidanceRecommendation | null {
  if (!value) return null
  return {
    primaryTopic: value.primaryTopic ?? null,
    alternatives: (value.alternatives ?? []).map((option: RecommendationOption) => ({
      topic: option.topic,
      reason: option.reason,
      source: option.source,
    })),
    recommendedDifficulty: value.recommendedDifficulty ?? null,
    reason: value.reason ?? '',
    source: value.source ?? 'fallback',
  }
}

export function useGuidanceSession(learnerId: number | null) {
  const [state, dispatch] = useReducer(guidanceReducer, initialGuidanceState)
  const [recommendation, setRecommendation] = useState<GuidanceRecommendation | null>(null)
  const [recommendationLoading, setRecommendationLoading] = useState(false)
  const [recommendationError, setRecommendationError] = useState<string | null>(null)
  const hydratedLearnerIdRef = useRef<number | null>(null)
  const historyLoadedRef = useRef<number | null>(null)

  const loadHistory = useCallback(async (force = false) => {
    if (!learnerId || (!force && historyLoadedRef.current === learnerId)) return
    dispatch({ type: 'history_started' })
    try {
      const response = await coreApi.getInteractionHistory(learnerId, { page: 1, pageSize: 20 })
      historyLoadedRef.current = learnerId
      dispatch({ type: 'history_loaded', records: (response.history ?? []).map(mapHistoryRecord) })
    } catch (error) {
      dispatch({ type: 'history_failed', error: toErrorMessage(error, '历史记录加载失败，请稍后重试') })
    }
  }, [learnerId])

  const loadData = useCallback(async () => {
    if (!learnerId) {
      dispatch({ type: 'load_failed', error: '当前账号没有可用的学习者画像' })
      return
    }
    dispatch({ type: 'load_started' })
    setRecommendation(null)
    setRecommendationLoading(true)
    setRecommendationError(null)
    try {
      const recommendationRequest = typeof coreApi.getGuidanceRecommendations === 'function'
        ? coreApi.getGuidanceRecommendations(learnerId).catch((error) => {
          setRecommendationError(toErrorMessage(error, '学习重点推荐暂时不可用'))
          return null
        })
        : Promise.resolve(null)
      const [questionsResponse, recommendationResponse] = await Promise.all([
        coreApi.getTutoringQuestions(learnerId),
        recommendationRequest,
      ])
      const persisted = readPersistedSession(learnerId)
      const exited = window.localStorage.getItem(exitStorageKey(learnerId)) === '1'
      let questions: TutoringQuestion[] = questionsResponse
      let sessionConfig: SessionConfig | null = null
      let currentQuestion = 0
      let selectedAnswers: number[] = []
      let showResult = false
      let correctCount = 0
      let generationMethod: string | null = questions[0]?.generationMethod ?? null
      let submitResult: SubmitResult | null = null

      if (hydratedLearnerIdRef.current !== learnerId) {
        hydratedLearnerIdRef.current = learnerId
        if (persisted) {
          const mergedQuestions = mergeQuestions(persisted, questionsResponse)
          const remoteIds = new Set(questionsResponse.map((question) => question.id))
          const currentId = persisted.questions[persisted.currentQuestion]?.id
          const answerWasInterrupted = Boolean(currentId && !remoteIds.has(currentId) && (!persisted.showResult || !persisted.submitResult))
          const firstPendingIndex = mergedQuestions.findIndex((question) => remoteIds.has(question.id))
          questions = mergedQuestions
          currentQuestion = answerWasInterrupted && firstPendingIndex >= 0
            ? firstPendingIndex
            : Math.min(persisted.currentQuestion, Math.max(0, mergedQuestions.length - 1))
          selectedAnswers = answerWasInterrupted ? [] : (persisted.selectedAnswers ?? [])
          showResult = answerWasInterrupted ? false : Boolean(persisted.showResult)
          correctCount = persisted.correctCount ?? 0
          generationMethod = persisted.generationMethod ?? mergedQuestions[0]?.generationMethod ?? null
          submitResult = answerWasInterrupted ? null : (persisted.submitResult ?? null)
          sessionConfig = persisted.config
        } else if (exited) {
          questions = []
          generationMethod = null
        } else if (questions.length > 0) {
          const firstDifficulty = questions[0].difficulty
          const allSameDifficulty = questions.every((question) => question.difficulty === firstDifficulty)
          sessionConfig = {
            topic: questions[0].topic,
            difficulty: allSameDifficulty ? firstDifficulty : undefined,
            questionCount: questions.length,
          }
        }
      }

      const normalizedRecommendation = normalizeRecommendation(recommendationResponse)
      setRecommendation(normalizedRecommendation)
      dispatch({
        type: 'hydrated',
        questions,
        sessionConfig,
        currentQuestion,
        selectedAnswers,
        showResult,
        correctCount,
        generationMethod,
        submitResult,
      })
    } catch (error) {
      dispatch({ type: 'load_failed', error: toErrorMessage(error, '导学题库加载失败，请稍后重试') })
    } finally {
      setRecommendationLoading(false)
    }
  }, [learnerId])

  useEffect(() => {
    hydratedLearnerIdRef.current = null
    historyLoadedRef.current = null
    void loadData()
  }, [loadData])

  useEffect(() => {
    if (!learnerId || !state.hydrated) return
    const key = sessionStorageKey(learnerId)
    if (!state.sessionConfig || state.questions.length === 0) {
      window.localStorage.removeItem(key)
      return
    }
    window.localStorage.setItem(key, JSON.stringify({
      config: state.sessionConfig,
      questions: state.questions,
      currentQuestion: state.currentQuestion,
      selectedAnswers: state.selectedAnswers,
      showResult: state.showResult,
      correctCount: state.correctCount,
      generationMethod: state.generationMethod,
      submitResult: state.submitResult,
    }))
  }, [learnerId, state])

  const generateQuestions = useCallback(async (options: GenerateOptions): Promise<TutoringQuestion[]> => {
    if (!learnerId) return []
    dispatch({ type: 'generation_started' })
    try {
      const response = await coreApi.generateTutoringQuestions({
        learnerId,
        topic: options.topic || undefined,
        difficulty: options.difficulty,
        questionCount: options.questionCount,
        replacePending: options.mode === 'append' || options.mode === 'start',
      })
      const questions = response.questions ?? []
      if (questions.length === 0) throw new Error('暂时没有生成可用题目，请先完成资源生成')
      dispatch({
        type: 'generation_succeeded',
        mode: options.mode,
        questions,
        generationMethod: response.generationMethod ?? questions[0]?.generationMethod ?? null,
        sessionConfig: options.sessionConfig,
      })
      if (options.mode === 'start' && !options.sessionConfig?.topic?.trim() && questions[0]?.topic) {
        dispatch({ type: 'session_topic_updated', topic: questions[0].topic })
      }
      return questions
    } catch (error) {
      dispatch({ type: 'generation_failed', error: toErrorMessage(error, '题目生成失败，请稍后重试') })
      return []
    }
  }, [learnerId])

  const startSession = useCallback(async (options: StartSessionOptions = {}) => {
    const topic = options.topic?.trim() || recommendation?.primaryTopic || undefined
    const difficulty = options.difficulty
    const questionCount = Math.max(1, Math.min(10, options.questionCount ?? 5))
    const initialQuestionCount = difficulty === undefined ? 1 : questionCount
    const sessionId = createSessionId()
    const generated = await generateQuestions({
      topic,
      difficulty,
      questionCount: initialQuestionCount,
      mode: 'start',
      sessionConfig: {
        topic: topic || '',
        difficulty,
        questionCount,
        sessionId,
      },
    })
    if (generated.length > 0 && learnerId) {
      window.localStorage.removeItem(exitStorageKey(learnerId))
    }
    return generated
  }, [generateQuestions, learnerId, recommendation?.primaryTopic])

  const prepareNextQuestion = useCallback(async (difficulty: number, topic: string) => {
    if (!learnerId) return false
    dispatch({ type: 'prefetch_started', difficulty })
    try {
      const response = await coreApi.generateTutoringQuestions({
        learnerId,
        topic: topic || undefined,
        difficulty,
        questionCount: 1,
        replacePending: true,
      })
      const questions = response.questions ?? []
      if (questions.length === 0) throw new Error('下一道自适应题目生成失败，请重试')
      dispatch({
        type: 'prefetch_succeeded',
        questions,
        generationMethod: response.generationMethod ?? questions[0]?.generationMethod ?? null,
      })
      return true
    } catch (error) {
      dispatch({ type: 'prefetch_failed', error: toErrorMessage(error, '下一道自适应题目生成失败，请重试') })
      return false
    }
  }, [learnerId])

  const submitAnswer = useCallback(async () => {
    const question = state.questions[state.currentQuestion]
    if (!question || state.selectedAnswers.length === 0 || !learnerId || state.phase === 'submitting') return
    const userAnswer = state.selectedAnswers.map((index) => String.fromCharCode(65 + index)).join(',')
    dispatch({ type: 'submit_started' })
    try {
      const raw = await coreApi.submitAnswer({
        learnerId,
        questionId: question.id,
        userAnswer,
        timeSpentMs: 0,
        hintsUsed: 0,
        ...(state.sessionConfig?.sessionId
          ? { sessionId: state.sessionConfig.sessionId, sequenceIndex: state.currentQuestion + 1 }
          : {}),
      }) as SubmitResultRaw
      const data: SubmitDataRaw = raw?.data ?? raw
      const isCorrect = data.isCorrect ?? data.is_correct ?? false
      const result: SubmitResult = {
        isCorrect,
        score: data.score ?? 0,
        agentDecision: data.agentDecision ?? data.agent_decision,
        nextAction: data.nextAction ?? data.next_action,
        nextQuestionDifficulty: data.nextQuestionDifficulty ?? data.next_question_difficulty,
        generatedContent: data.generatedContent ?? data.generated_content ?? {},
      }
      const targetCount = state.sessionConfig?.questionCount ?? state.questions.length
      const completedCount = state.currentQuestion + 1
      const hasQueuedQuestion = state.currentQuestion < state.questions.length - 1
      const dynamicDifficulty = state.sessionConfig?.difficulty === undefined
      const completed = completedCount >= targetCount && !dynamicDifficulty
      const nextDifficulty = result.nextQuestionDifficulty
        ?? Math.max(1, Math.min(5, question.difficulty + (isCorrect ? 1 : -1)))
      dispatch({
        type: 'submit_succeeded',
        result,
        completed,
        nextDifficulty: dynamicDifficulty && completedCount < targetCount ? nextDifficulty : null,
      })
      void loadHistory(true)
      if (dynamicDifficulty && completedCount < targetCount && !hasQueuedQuestion) {
        void prepareNextQuestion(nextDifficulty, state.sessionConfig?.topic || question.topic)
      }
    } catch (error) {
      dispatch({ type: 'submit_failed', error: toErrorMessage(error, '答案提交失败，请重试') })
    }
  }, [learnerId, loadHistory, prepareNextQuestion, state])

  const nextQuestion = useCallback(() => {
    if (state.currentQuestion < state.questions.length - 1) dispatch({ type: 'advance_question' })
  }, [state.currentQuestion, state.questions.length])

  const retryNextQuestion = useCallback(() => {
    const question = state.questions[state.currentQuestion]
    const sessionConfig = state.sessionConfig
    if (!question || !sessionConfig || sessionConfig.difficulty !== undefined) return
    const difficulty = state.pendingNextDifficulty
      ?? Math.max(1, Math.min(5, question.difficulty + (state.submitResult?.isCorrect ? 1 : -1)))
    void prepareNextQuestion(difficulty, sessionConfig.topic || question.topic)
  }, [prepareNextQuestion, state])

  const exitSession = useCallback(() => {
    if (!learnerId) return
    hydratedLearnerIdRef.current = null
    historyLoadedRef.current = null
    window.localStorage.removeItem(sessionStorageKey(learnerId))
    window.localStorage.setItem(exitStorageKey(learnerId), '1')
    dispatch({ type: 'exit_session' })
  }, [learnerId])

  const deleteHistory = useCallback(async (params: { recordId?: number; sessionId?: string }) => {
    if (!learnerId) return
    await coreApi.deleteInteractionHistory(learnerId, params)
    const current = state.historyRecords.filter((record) => (
      params.recordId !== undefined
        ? record.recordId !== String(params.recordId)
        : params.sessionId
        ? record.sessionId !== params.sessionId
        : true
    ))
    dispatch({ type: 'history_loaded', records: current })
  }, [learnerId, state.historyRecords])

  const clearHistory = useCallback(async () => {
    if (!learnerId) return
    await coreApi.deleteInteractionHistory(learnerId)
    dispatch({ type: 'history_loaded', records: [] })
  }, [learnerId])

  const question = state.questions[state.currentQuestion]
  const isPreparingNext = state.phase === 'preparingNext'
  const sessionTotal = state.sessionConfig?.questionCount ?? state.questions.length
  const answeredCount = Math.min(sessionTotal, state.currentQuestion + (state.showResult ? 1 : 0))
  const progress = sessionTotal > 0 ? (answeredCount / sessionTotal) * 100 : 0

  return useMemo(() => ({
    state,
    question,
    isPreparingNext,
    sessionTotal,
    answeredCount,
    progress,
    recommendation,
    recommendationLoading,
    recommendationError,
    loadData,
    loadHistory,
    startSession,
    selectAnswer: (index: number) => dispatch({ type: 'select_answer', index, multiple: question?.type === 'multiple' }),
    submitAnswer,
    nextQuestion,
    retryNextQuestion,
    exitSession,
    deleteHistory,
    clearHistory,
  }), [
    answeredCount,
    clearHistory,
    deleteHistory,
    exitSession,
    isPreparingNext,
    loadData,
    loadHistory,
    nextQuestion,
    progress,
    question,
    recommendation,
    recommendationError,
    recommendationLoading,
    retryNextQuestion,
    sessionTotal,
    startSession,
    state,
    submitAnswer,
  ])
}
