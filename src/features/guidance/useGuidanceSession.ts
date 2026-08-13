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
  BatchSubmitResult,
  GuidanceRecommendation,
  GuidanceMode,
  RecommendationOption,
  SessionConfig,
  SubmitResult,
  SubmitResultRaw,
  SubmitDataRaw,
} from './types'
import { mapHistoryRecord } from './types'
import type { TrainingStageContext } from '@/types/training'

interface StartSessionOptions {
  topic?: string
  difficulty?: number
  questionCount?: number
  mode?: GuidanceMode
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

export function useGuidanceSession(learnerId: number | null, trainingContext: TrainingStageContext | null = null) {
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
      let answersByQuestionId: Record<string, number[]> = {}
      let batchResult: BatchSubmitResult | null = null
      let recoveredBatchResult: BatchSubmitResult | null = null

      // A successful batch commit can be followed by a lost response. Keep the
      // local draft for recovery, then prefer the durable server result when it
      // is available on the next load.
      if (
        persisted?.config.mode === 'batch' &&
        persisted.config.sessionId &&
        !persisted.batchResult &&
        typeof coreApi.getBatchResult === 'function'
      ) {
        try {
          recoveredBatchResult = await coreApi.getBatchResult(persisted.config.sessionId, learnerId)
        } catch {
          // A 404 means the draft is still pending; transient failures must not
          // discard the answers that are stored locally.
        }
      }

      if (hydratedLearnerIdRef.current !== learnerId) {
        hydratedLearnerIdRef.current = learnerId
        if (persisted) {
          const mergedQuestions = mergeQuestions(persisted, questionsResponse)
          const remoteIds = new Set(questionsResponse.map((question) => question.id))
          const currentId = persisted.questions[persisted.currentQuestion]?.id
          const answerWasInterrupted = persisted.config.mode !== 'batch'
            && Boolean(currentId && !remoteIds.has(currentId) && (!persisted.showResult || !persisted.submitResult))
          const firstPendingIndex = mergedQuestions.findIndex((question) => remoteIds.has(question.id))
          questions = mergedQuestions
          currentQuestion = answerWasInterrupted && firstPendingIndex >= 0
            ? firstPendingIndex
            : Math.min(persisted.currentQuestion, Math.max(0, mergedQuestions.length - 1))
          answersByQuestionId = persisted.answersByQuestionId ?? {}
          const persistedQuestionId = mergedQuestions[persisted.currentQuestion]?.id
          selectedAnswers = answerWasInterrupted
            ? []
            : persisted.config.mode === 'batch'
            ? (persistedQuestionId ? answersByQuestionId[persistedQuestionId] ?? [] : [])
            : (persisted.selectedAnswers ?? [])
          showResult = answerWasInterrupted ? false : Boolean(persisted.showResult)
          correctCount = persisted.correctCount ?? 0
          generationMethod = persisted.generationMethod ?? mergedQuestions[0]?.generationMethod ?? null
          submitResult = answerWasInterrupted ? null : (persisted.submitResult ?? null)
          batchResult = answerWasInterrupted ? null : (persisted.batchResult ?? recoveredBatchResult)
          sessionConfig = persisted.config
        } else if (exited) {
          questions = []
          generationMethod = null
        } else if (questions.length > 0) {
          const firstDifficulty = questions[0].difficulty
          const allSameDifficulty = questions.every((question) => question.difficulty === firstDifficulty)
          const isBatch = questions[0].assessmentMode === 'batch_practice'
          sessionConfig = {
            mode: isBatch ? 'batch' : 'adaptive',
            topic: questions[0].topic,
            difficulty: allSameDifficulty ? firstDifficulty : undefined,
            questionCount: questions.length,
            sessionId: isBatch ? questions[0].sessionId : undefined,
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
        answersByQuestionId,
        batchResult,
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
    if (!state.sessionConfig || state.questions.length === 0 || state.phase === 'batchReview') {
      window.localStorage.removeItem(key)
      return
    }
    window.localStorage.setItem(key, JSON.stringify({
      config: state.sessionConfig,
      questions: state.questions,
      currentQuestion: state.currentQuestion,
      selectedAnswers: state.selectedAnswers,
      answersByQuestionId: state.answersByQuestionId,
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
      const request = {
        learnerId,
        topic: options.topic || undefined,
        difficulty: options.difficulty,
        questionCount: options.questionCount,
        replacePending: options.mode === 'append' || options.mode === 'start',
        ...(options.sessionConfig?.mode === 'batch'
          ? {
            assessmentMode: 'batch_practice' as const,
            sessionId: options.sessionConfig.sessionId,
          }
          : {}),
        ...(trainingContext ? { trainingContext } : {}),
      }
      const response = await coreApi.generateTutoringQuestions(request)
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
  }, [learnerId, trainingContext])

  const startSession = useCallback(async (options: StartSessionOptions = {}) => {
    const topic = options.topic?.trim() || recommendation?.primaryTopic || undefined
    const difficulty = options.difficulty
    const mode = options.mode ?? 'adaptive'
    const questionCount = Math.max(1, Math.min(10, options.questionCount ?? 5))
    const initialQuestionCount = mode === 'batch' || difficulty !== undefined ? questionCount : 1
    const sessionId = createSessionId()
    const generated = await generateQuestions({
      topic,
      difficulty,
      questionCount: initialQuestionCount,
      mode: 'start',
      sessionConfig: {
        mode,
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

  const submitBatch = useCallback(async () => {
    const config = state.sessionConfig
    if (
      !learnerId ||
      config?.mode !== 'batch' ||
      state.phase === 'submitting' ||
      state.phase === 'batchReview'
    )
      return

    const firstUnanswered = state.questions.findIndex(
      (question) => !state.answersByQuestionId[question.id]?.length,
    )
    if (firstUnanswered >= 0) {
      dispatch({
        type: 'batch_validation_failed',
        index: firstUnanswered,
        error: '请先完成全部题目再交卷',
      })
      return
    }

    const answers = state.questions.map((question, index) => ({
      questionId: question.id,
      userAnswer: (state.answersByQuestionId[question.id] ?? [])
        .map((answer) => String.fromCharCode(65 + answer))
        .join(','),
      sequenceIndex: index + 1,
    }))
    dispatch({ type: 'batch_submit_started' })
    try {
      const result = await coreApi.submitBatch({
        learnerId,
        sessionId: config.sessionId ?? '',
        answers,
      })
      dispatch({ type: 'batch_submit_succeeded', result })
      window.localStorage.removeItem(sessionStorageKey(learnerId))
      window.localStorage.removeItem(exitStorageKey(learnerId))
      void loadHistory(true)
    } catch (error) {
      dispatch({
        type: 'batch_submit_failed',
        error: toErrorMessage(error, '整卷提交失败，请重试'),
      })
    }
  }, [learnerId, loadHistory, state])

  const goToQuestion = useCallback(
    (index: number) => {
      if (
        state.sessionConfig?.mode !== 'batch' ||
        state.phase === 'submitting' ||
        state.phase === 'batchReview'
      )
        return
      dispatch({ type: 'go_to_question', index })
    },
    [state.phase, state.sessionConfig?.mode],
  )

  const nextQuestion = useCallback(() => {
    if (state.sessionConfig?.mode === 'batch') {
      if (state.currentQuestion < state.questions.length - 1)
        dispatch({ type: 'go_to_question', index: state.currentQuestion + 1 })
      return
    }
    if (state.currentQuestion < state.questions.length - 1) dispatch({ type: 'advance_question' })
  }, [state.currentQuestion, state.questions.length, state.sessionConfig?.mode])

  const previousQuestion = useCallback(() => {
    if (
      state.sessionConfig?.mode === 'batch' &&
      state.currentQuestion > 0 &&
      state.phase !== 'submitting'
    ) {
      dispatch({ type: 'go_to_question', index: state.currentQuestion - 1 })
    }
  }, [state.currentQuestion, state.phase, state.sessionConfig?.mode])

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
  const isBatch = state.sessionConfig?.mode === 'batch'
  const answeredCount = isBatch
    ? state.questions.filter((item) => (state.answersByQuestionId[item.id] ?? []).length > 0).length
    : Math.min(sessionTotal, state.currentQuestion + (state.showResult ? 1 : 0))
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
    submitBatch,
    nextQuestion,
    previousQuestion,
    goToQuestion,
    retryNextQuestion,
    exitSession,
    deleteHistory,
    clearHistory,
  }), [
    answeredCount,
    clearHistory,
    deleteHistory,
    exitSession,
    goToQuestion,
    isPreparingNext,
    loadData,
    loadHistory,
    nextQuestion,
    previousQuestion,
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
    submitBatch,
  ])
}
