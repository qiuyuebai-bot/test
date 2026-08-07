import { useState, useEffect, useCallback, useMemo, useRef, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useStore } from '@/store'
import { useShallow } from 'zustand/react/shallow'
import { coreApi } from '@/api'
import type { TutoringQuestion } from '@/api/core'
import type { InteractionHistoryRecord } from '@/types'
import Card from '@/components/Card'
import Badge from '@/components/Badge'
import Button from '@/components/Button'
import Input from '@/components/Input'
import EmptyState from '@/components/EmptyState'
import ErrorState from '@/components/ErrorState'
import { PageSkeleton } from '@/components/Skeleton'
import {
  Brain,
  User,
  Lightbulb,
  Shield,
  CheckCircle2,
  XCircle,
  ChevronDown,
  ChevronRight,
  ArrowRight,
  Sparkles,
  BookOpen,
  Target,
  Zap,
  Clock,
  RefreshCw,
  MessageSquare,
  Layers,
  LogOut,
  Trash2,
} from 'lucide-react'

interface HistoryRecord {
  recordId: string
  sessionId: string | null
  sequenceIndex: number | null
  questionTopic: string
  questionContent: string
  userAnswer: unknown
  feedbackContent: string
  questionDifficulty: number
  result: 'correct' | 'wrong' | 'partial'
  agentDecision: string
  decisionReason: string
  createdAt: string
  score: number
}

interface SessionConfig {
  topic: string
  difficulty?: number
  questionCount: number
  sessionId?: string
}

interface PersistedSession {
  config: SessionConfig
  questions: TutoringQuestion[]
  currentQuestion: number
  selectedAnswers: number[]
  showResult: boolean
  correctCount: number
  generationMethod: string | null
  submitResult: SubmitResult | null
}

const SESSION_STORAGE_PREFIX = 'adaptive-guidance-session'
const EXIT_STORAGE_PREFIX = 'adaptive-guidance-exited'

function sessionStorageKey(learnerId: number) {
  return `${SESSION_STORAGE_PREFIX}:${learnerId}`
}

function exitStorageKey(learnerId: number) {
  return `${EXIT_STORAGE_PREFIX}:${learnerId}`
}

function createSessionId() {
  return `session_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`
}

function formatHistoryDate(value: string): string {
  if (!value) return '时间未知'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function readPersistedSession(learnerId: number): PersistedSession | null {
  try {
    const raw = window.localStorage.getItem(sessionStorageKey(learnerId))
    if (!raw) return null
    const parsed = JSON.parse(raw) as PersistedSession
    if (!parsed?.config?.topic || !Array.isArray(parsed.questions) || parsed.questions.length === 0) {
      return null
    }
    return parsed
  } catch {
    return null
  }
}

function formatUserAnswer(answer: unknown): string {
  if (Array.isArray(answer)) return answer.map(String).join(', ')
  if (answer === null || answer === undefined || answer === '') return '未记录'
  return String(answer)
}

function GuidanceLoadingAnimation() {
  return (
    <div role="status" aria-label="正在生成导学题目" className="guidance-loading relative overflow-hidden rounded-2xl border border-primary/15 bg-gradient-to-r from-primary/5 via-white to-cyan-50/60 px-5 py-3">
      <svg viewBox="0 0 720 112" className="h-24 w-full" aria-hidden="true">
        <path className="guidance-trail" d="M40 74 C180 20 280 92 410 46 S590 22 680 58" fill="none" stroke="var(--color-primary)" strokeOpacity=".14" strokeWidth="3" strokeLinecap="round" />
        <g className="guidance-star guidance-star-one" fill="var(--color-warning)">
          <path d="M118 29 l4 10 11 1-8 7 3 11-10-6-10 6 3-11-8-7 11-1z" />
        </g>
        <g className="guidance-star guidance-star-two" fill="#7dd3fc">
          <path d="M492 22 l3 8 9 1-7 6 2 9-7-5-8 5 3-9-7-6 9-1z" />
        </g>
        <g className="guidance-star guidance-star-three" fill="var(--color-warning)">
          <path d="M625 72 l3 8 9 1-7 6 2 9-7-5-8 5 3-9-7-6 9-1z" />
        </g>
        <g transform="translate(310 20)">
          <g className="guidance-runner">
          <path d="M25 24 C3 17 5 54 25 45 C7 66 18 80 32 63" fill="none" stroke="#2dd4bf" strokeWidth="9" strokeLinecap="round" />
          <path d="M67 24 C89 17 87 54 67 45 C85 66 74 80 60 63" fill="none" stroke="#2dd4bf" strokeWidth="9" strokeLinecap="round" />
          <circle cx="46" cy="30" r="22" fill="#fef3c7" stroke="#0f766e" strokeWidth="2" />
          <path d="M26 28 Q46 5 66 28 Q60 17 46 15 Q32 17 26 28" fill="#14b8a6" />
          <circle cx="38" cy="32" r="2" fill="#334155" /><circle cx="54" cy="32" r="2" fill="#334155" />
          <path d="M41 40 Q46 44 51 40" fill="none" stroke="#fb7185" strokeWidth="1.5" strokeLinecap="round" />
          <path d="M34 52 Q46 46 58 52 L64 78 Q46 87 28 78z" fill="#3d5a80" />
          <path d="M31 57 L15 70 M61 57 L77 66 M38 78 L30 95 M54 78 L63 94" fill="none" stroke="#fbbf24" strokeWidth="5" strokeLinecap="round" />
          </g>
        </g>
      </svg>
      <div className="flex items-center justify-center gap-2 text-sm text-text-secondary">
        <Sparkles className="h-4 w-4 text-primary" />
        <span>正在整理主题线索，准备本轮导学题目…</span>
        <span className="text-xs text-text-tertiary">画像诊断 · 主题检索 · 难度校准</span>
      </div>
    </div>
  )
}

interface GeneratedContent {
  type?: string
  title?: string
  simpleExplanation?: string
  knowledgeExpansion?: {
    type?: string
    title?: string
    overview?: string
    keyPoints?: string[]
    application?: string
    pitfalls?: string[]
    suggestedResources?: Array<{ resourceId: number; title: string; type: string; difficultyLevel?: number }>
  }
  keyPoints?: string[]
  practiceTips?: string
  recommendation?: string
  challengeDescription?: string
  challengeObjectives?: string[]
  estimatedTime?: string
  bonusPoints?: number
  suggestedResources?: Array<{ resourceId: number; title: string; type: string; matchScore?: number; difficultyLevel?: number }>
}

interface SubmitResult {
  isCorrect: boolean
  score: number
  agentDecision?: { decision?: string; reason?: string; confidence?: number }
  nextAction?: { type?: string; description?: string }
  generatedContent?: GeneratedContent
}

type ContentTab = 'simplified' | 'advanced'

interface AgentStep {
  agent: string
  name: string
  icon: typeof User
  action: string
  status: 'complete' | 'running' | 'pending'
}

const INITIAL_AGENT_STEPS: AgentStep[] = [
  { agent: 'diagnosis', name: '学情诊断Agent', icon: User, action: '分析答题结果与能力评估', status: 'pending' },
  { agent: 'knowledge', name: '知识生成Agent', icon: Brain, action: '检索匹配知识点内容', status: 'pending' },
  { agent: 'judge', name: '审核裁判Agent', icon: Shield, action: '校验内容并给出决策', status: 'pending' },
]

type GeneratedSection = {
  heading?: string
  content?: string
  points?: string[]
  tasks?: string[]
}

type GeneratedContentRaw = GeneratedContent & {
  sections?: GeneratedSection[]
}

type SubmitDataRaw = {
  isCorrect?: boolean
  is_correct?: boolean
  score?: number
  generatedContent?: GeneratedContentRaw
  generated_content?: GeneratedContentRaw
  agentDecision?: { decision?: string; reason?: string }
  agent_decision?: { decision?: string; reason?: string }
  nextAction?: { type?: string }
  next_action?: { type?: string }
  nextQuestionDifficulty?: number
  next_question_difficulty?: number
}

type SubmitResultRaw = {
  data?: SubmitDataRaw
} & SubmitDataRaw

function mapHistoryRecord(r: InteractionHistoryRecord): HistoryRecord {
  return {
    recordId: String(r.recordId),
    sessionId: r.sessionId ?? null,
    sequenceIndex: r.sequenceIndex ?? null,
    questionTopic: r.questionTopic ?? '',
    questionContent: r.questionContent ?? '',
    userAnswer: r.userAnswer,
    feedbackContent: r.feedbackContent ?? '',
    questionDifficulty: r.questionDifficulty ?? 0,
    result: (r.result === 'correct' ? 'correct' : r.result === 'wrong' ? 'wrong' : 'partial'),
    agentDecision: r.agentDecision ?? r.nextAction ?? '',
    decisionReason: r.decisionReason ?? '',
    createdAt: r.createdAt ?? '',
    score: r.score,
  }
}

export default function AdaptiveGuidance() {
  const navigate = useNavigate()
  const { currentLearner, learners, fetchLearners, setCurrentLearner, learnersLoading } = useStore(
    useShallow((s) => ({
      currentLearner: s.currentLearner,
      learners: s.learners,
      fetchLearners: s.fetchLearners,
      setCurrentLearner: s.setCurrentLearner,
      learnersLoading: s.learnersLoading,
    }))
  )
  const availableLearners = useMemo(() => {
    const list = currentLearner ? [currentLearner, ...learners] : learners
    return list.filter((item, index, all) => all.findIndex((candidate) => candidate.id === item.id) === index)
  }, [currentLearner, learners])
  const [selectedLearnerId, setSelectedLearnerId] = useState<number | null>(null)
  const learner = availableLearners.find((item) => item.id === selectedLearnerId)
    ?? currentLearner
    ?? availableLearners[0]

  const [questions, setQuestions] = useState<TutoringQuestion[]>([])
  const [currentQuestion, setCurrentQuestion] = useState(0)
  const [selectedAnswers, setSelectedAnswers] = useState<number[]>([])
  const [showResult, setShowResult] = useState(false)
  const [isAdjusting, setIsAdjusting] = useState(false)
  const [adjustmentProgress, setAdjustmentProgress] = useState(0)
  const [agentSteps, setAgentSteps] = useState<AgentStep[]>(INITIAL_AGENT_STEPS)
  const [activeContentTab, setActiveContentTab] = useState<ContentTab>('simplified')
  const [expandedHistory, setExpandedHistory] = useState<string | null>(null)
  const [sessionConfig, setSessionConfig] = useState<SessionConfig | null>(null)
  const [correctCount, setCorrectCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [isGenerating, setIsGenerating] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [generationError, setGenerationError] = useState<string | null>(null)
  const [answerError, setAnswerError] = useState<string | null>(null)
  const [pendingNextDifficulty, setPendingNextDifficulty] = useState<number | null>(null)
  const [generationMethod, setGenerationMethod] = useState<string | null>(null)
  const [topicInput, setTopicInput] = useState('')
  const [difficultyInput, setDifficultyInput] = useState('')
  const [questionCountInput, setQuestionCountInput] = useState('3')

  const [historyRecords, setHistoryRecords] = useState<HistoryRecord[]>([])
  const [viewingHistoryRecord, setViewingHistoryRecord] = useState<string | null>(null)
  const [historyActionError, setHistoryActionError] = useState<string | null>(null)
  const [historyActionLoading, setHistoryActionLoading] = useState(false)
  const [submitResult, setSubmitResult] = useState<SubmitResult | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const hydratedLearnerIdRef = useRef<number | null>(null)

  useEffect(() => {
    if (!selectedLearnerId || !availableLearners.some((item) => item.id === selectedLearnerId)) {
      setSelectedLearnerId(currentLearner?.id ?? availableLearners[0]?.id ?? null)
    }
  }, [availableLearners, currentLearner?.id, selectedLearnerId])

  useEffect(() => {
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  }, [])

  useEffect(() => {
    if (learner?.id || learners.length > 0 || learnersLoading) return
    void fetchLearners({ page: 1, pageSize: 20 })
  }, [fetchLearners, learner?.id, learners.length, learnersLoading])

  const loadData = useCallback(async () => {
    if (!learner?.id) {
      setLoading(false)
      return
    }
    setLoading(true)
    setLoadError(null)
    try {
      const [questionsResp, historyResp] = await Promise.all([
        coreApi.getTutoringQuestions(learner.id),
        coreApi.getInteractionHistory(learner.id, { page: 1, pageSize: 20 }).catch(() => null),
      ])

      if (hydratedLearnerIdRef.current !== learner.id) {
        hydratedLearnerIdRef.current = learner.id
        const persisted = readPersistedSession(learner.id)
        const exited = window.localStorage.getItem(exitStorageKey(learner.id)) === '1'

        if (persisted) {
          const remoteIds = new Set(questionsResp.map((item) => item.id))
          const mergedQuestions = [...persisted.questions]
          const knownIds = new Set(mergedQuestions.map((item) => item.id))
          questionsResp.forEach((item) => {
            if (!knownIds.has(item.id)) mergedQuestions.push(item)
          })
          const currentId = persisted.questions[persisted.currentQuestion]?.id
          const currentIsPending = currentId ? remoteIds.has(currentId) : false
          const answerWasInterrupted = !currentIsPending && (!persisted.showResult || !persisted.submitResult)
          const firstPendingIndex = mergedQuestions.findIndex((item) => remoteIds.has(item.id))
          const restoredCurrent = answerWasInterrupted && firstPendingIndex >= 0
            ? firstPendingIndex
            : Math.min(persisted.currentQuestion, mergedQuestions.length - 1)
          setSessionConfig(persisted.config)
          setQuestions(mergedQuestions)
          setCurrentQuestion(restoredCurrent)
          setSelectedAnswers(answerWasInterrupted ? [] : (persisted.selectedAnswers ?? []))
          setShowResult(answerWasInterrupted ? false : Boolean(persisted.showResult))
          setCorrectCount(persisted.correctCount ?? 0)
          setGenerationMethod(persisted.generationMethod ?? mergedQuestions[0]?.generationMethod ?? null)
          setSubmitResult(answerWasInterrupted ? null : (persisted.submitResult ?? null))
        } else if (exited) {
          setSessionConfig(null)
          setQuestions([])
          setCurrentQuestion(0)
          setSelectedAnswers([])
          setShowResult(false)
          setSubmitResult(null)
          setCorrectCount(0)
        } else {
          setQuestions(questionsResp)
          setGenerationMethod(questionsResp[0]?.generationMethod ?? null)
          if (questionsResp.length > 0) {
            const firstDifficulty = questionsResp[0].difficulty
            const allSameDifficulty = questionsResp.every((item) => item.difficulty === firstDifficulty)
            setSessionConfig({
              topic: questionsResp[0].topic,
              difficulty: allSameDifficulty ? firstDifficulty : undefined,
              questionCount: questionsResp.length,
            })
          } else {
            setSessionConfig(null)
          }
        }
      }

      // 转换历史记录字段
      const historyItems = historyResp?.history ?? []
      const mapped: HistoryRecord[] = historyItems.map(mapHistoryRecord)
      setHistoryRecords(mapped)
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : '导学题库加载失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }, [learner?.id])

  useEffect(() => {
    loadData()
  }, [loadData])

  useEffect(() => {
    if (!learner?.id || hydratedLearnerIdRef.current !== learner.id) return
    const key = sessionStorageKey(learner.id)
    if (!sessionConfig || questions.length === 0) {
      window.localStorage.removeItem(key)
      return
    }
    const snapshot: PersistedSession = {
      config: sessionConfig,
      questions,
      currentQuestion,
      selectedAnswers,
      showResult,
      correctCount,
      generationMethod,
      submitResult,
    }
    window.localStorage.setItem(key, JSON.stringify(snapshot))
  }, [
    learner?.id,
    sessionConfig,
    questions,
    currentQuestion,
    selectedAnswers,
    showResult,
    correctCount,
    generationMethod,
    submitResult,
  ])

  const generateQuestions = useCallback(async (options?: {
    topic?: string
    difficulty?: number
    questionCount?: number
    replacePending?: boolean
    silent?: boolean
  }): Promise<TutoringQuestion[]> => {
    if (!learner?.id) return []
    setIsGenerating(true)
    if (!options?.silent) setGenerationError(null)
    try {
      const response = await coreApi.generateTutoringQuestions({
        learnerId: learner.id,
        topic: options?.topic,
        difficulty: options?.difficulty,
        questionCount: options?.questionCount ?? 3,
        replacePending: options?.replacePending ?? false,
      })
      const generatedQuestions = response.questions ?? []
      if (generatedQuestions.length === 0) {
        throw new Error('暂时没有生成可用题目，请先完成资源生成')
      }
      setGenerationMethod(response.generationMethod ?? generatedQuestions[0]?.generationMethod ?? null)
      if (options?.replacePending) {
        setQuestions((previous) => [
          ...previous.slice(0, currentQuestion + 1),
          ...generatedQuestions,
        ])
      } else {
        setQuestions(generatedQuestions)
        setCurrentQuestion(0)
        setSelectedAnswers([])
        setShowResult(false)
        setSubmitResult(null)
      }
      return generatedQuestions
    } catch (err) {
      if (!options?.silent) {
        setGenerationError(err instanceof Error ? err.message : '题目生成失败，请稍后重试')
      }
      return []
    } finally {
      setIsGenerating(false)
    }
  }, [currentQuestion, learner?.id])

  const handleGenerateFromForm = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()

    const topic = topicInput.trim()
    const difficulty = difficultyInput === '' ? undefined : Number(difficultyInput)
    const questionCount = Number(questionCountInput)

    if (!topic) {
      setGenerationError('请输入主题关键词，例如“反向传播”或“REST API”')
      return
    }

    if (topic.length > 200) {
      setGenerationError('主题关键词不能超过 200 个字符')
      return
    }

    if (
      difficulty !== undefined &&
      (!Number.isInteger(difficulty) || difficulty < 1 || difficulty > 5)
    ) {
      setGenerationError('目标难度必须是 1–5 的整数')
      return
    }

    if (
      !Number.isInteger(questionCount) ||
      questionCount < 1 ||
      questionCount > 10
    ) {
      setGenerationError('题量必须是 1–10 的整数')
      return
    }

    setGenerationError(null)
    setPendingNextDifficulty(null)
    const initialQuestionCount = difficulty === undefined ? 1 : questionCount
    const sessionId = createSessionId()
    const generated = await generateQuestions({
      topic,
      difficulty,
      questionCount: initialQuestionCount,
      replacePending: true,
    })
    if (generated.length > 0) {
      window.localStorage.removeItem(exitStorageKey(learner?.id ?? 0))
      setSessionConfig({ topic, difficulty, questionCount, sessionId })
    }
  }

  const question = questions[currentQuestion]
  const isMultiSelect = question?.type === 'multiple'

  const handleSelect = (index: number) => {
    if (showResult) return
    if (isMultiSelect) {
      setSelectedAnswers((prev) =>
        prev.includes(index) ? prev.filter((i) => i !== index) : [...prev, index]
      )
    } else {
      setSelectedAnswers([index])
    }
  }

  const handleSubmit = async () => {
    if (!question || selectedAnswers.length === 0 || !learner?.id) return

    const userAnswer = selectedAnswers.map((i) => String.fromCharCode(65 + i)).join(',')

    setAnswerError(null)
    setIsAdjusting(true)
    setAdjustmentProgress(0)
    setAgentSteps(INITIAL_AGENT_STEPS.map((s) => ({ ...s, status: 'pending' })))
    setSubmitResult(null)

    // Agent 决策动画
    const animationSteps: { agent: string; status: 'running' | 'complete' }[] = [
      { agent: 'diagnosis', status: 'running' },
      { agent: 'diagnosis', status: 'complete' },
      { agent: 'knowledge', status: 'running' },
      { agent: 'knowledge', status: 'complete' },
      { agent: 'judge', status: 'running' },
      { agent: 'judge', status: 'complete' },
    ]
    let stepIdx = 0
    const interval = setInterval(() => {
      if (stepIdx < animationSteps.length) {
        const step = animationSteps[stepIdx]
        setAgentSteps((prev) =>
          prev.map((a) => (a.agent === step.agent ? { ...a, status: step.status } : a))
        )
        setAdjustmentProgress(((stepIdx + 1) / animationSteps.length) * 100)
        stepIdx++
      } else {
        clearInterval(interval)
        intervalRef.current = null
      }
    }, 350)
    intervalRef.current = interval

    // 调用后端真实接口提交答案
    try {
      const submitPayload = {
        learnerId: learner.id,
        questionId: question.id,
        userAnswer,
        timeSpentMs: 0,
        hintsUsed: 0,
        ...(sessionConfig?.sessionId
          ? {
              sessionId: sessionConfig.sessionId,
              sequenceIndex: currentQuestion + 1,
            }
          : {}),
      }
      const result = await coreApi.submitAnswer(submitPayload) as SubmitResultRaw

      const data: SubmitDataRaw = result?.data ?? result
      const isCorrect = data?.isCorrect ?? data?.is_correct ?? false
      const score = data?.score ?? 0
      const generated: GeneratedContent = (data?.generatedContent ?? data?.generated_content ?? {}) as GeneratedContent
      setSubmitResult({
        isCorrect: data?.isCorrect ?? data?.is_correct ?? isCorrect,
        score: data?.score ?? score,
        agentDecision: data?.agentDecision ?? data?.agent_decision,
        nextAction: data?.nextAction ?? data?.next_action,
        generatedContent: generated,
      })
      setShowResult(true)

      // 根据生成内容自动选择标签页
      setActiveContentTab('simplified')

      if (isCorrect) setCorrectCount((c) => c + 1)

      const completedCount = currentQuestion + 1
      const targetCount = sessionConfig?.questionCount ?? questions.length
      const isDynamicDifficulty = sessionConfig?.difficulty === undefined
      const hasQueuedQuestion = currentQuestion < questions.length - 1
      if (isDynamicDifficulty && completedCount < targetCount && !hasQueuedQuestion) {
        const nextDifficulty = data?.nextQuestionDifficulty
          ?? data?.next_question_difficulty
          ?? Math.max(1, Math.min(5, question.difficulty + (isCorrect ? 1 : -1)))
        setPendingNextDifficulty(nextDifficulty)
        const nextQuestions = await generateQuestions({
          topic: sessionConfig?.topic || question.topic,
          difficulty: nextDifficulty,
          questionCount: 1,
          replacePending: true,
          silent: true,
        })
        if (nextQuestions.length === 0) {
          setAnswerError('下一道自适应题目生成失败，请重试')
        } else {
          setPendingNextDifficulty(null)
        }
      }
    } catch (err) {
      setShowResult(false)
      setAnswerError(err instanceof Error ? err.message : '答案提交失败，请重试')
    } finally {
      clearInterval(interval)
      intervalRef.current = null
      setIsAdjusting(false)
      setAgentSteps(INITIAL_AGENT_STEPS.map((s) => ({ ...s, status: 'complete' })))
      setAdjustmentProgress(100)
      // 刷新历史记录
      coreApi.getInteractionHistory(learner.id, { page: 1, pageSize: 20 }).then((resp) => {
        const mapped: HistoryRecord[] = resp.history.map(mapHistoryRecord)
        setHistoryRecords(mapped)
      }).catch(() => {})
    }
  }

  const handleNext = () => {
    if (currentQuestion < questions.length - 1) {
      setCurrentQuestion((prev) => prev + 1)
      setSelectedAnswers([])
      setShowResult(false)
      setAdjustmentProgress(0)
      setAgentSteps(INITIAL_AGENT_STEPS)
      setActiveContentTab('simplified')
      setSubmitResult(null)
      setPendingNextDifficulty(null)
    }
  }

  const handleRetryNextQuestion = async () => {
    if (!question || !sessionConfig || sessionConfig.difficulty !== undefined) return
    setAnswerError(null)
    const difficulty = pendingNextDifficulty
      ?? Math.max(1, Math.min(5, question.difficulty + (submitResult?.isCorrect ? 1 : -1)))
    setPendingNextDifficulty(difficulty)
    const generated = await generateQuestions({
      topic: sessionConfig.topic || question.topic,
      difficulty,
      questionCount: 1,
      replacePending: true,
      silent: true,
    })
    if (generated.length > 0) {
      setPendingNextDifficulty(null)
    } else {
      setAnswerError('下一道自适应题目生成失败，请重试')
    }
  }

  const handleExitSession = () => {
    if (!learner?.id) return
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    window.localStorage.removeItem(sessionStorageKey(learner.id))
    window.localStorage.setItem(exitStorageKey(learner.id), '1')
    setSessionConfig(null)
    setQuestions([])
    setCurrentQuestion(0)
    setSelectedAnswers([])
    setShowResult(false)
    setIsAdjusting(false)
    setSubmitResult(null)
    setGenerationError(null)
    setAnswerError(null)
    setCorrectCount(0)
    setPendingNextDifficulty(null)
  }

  const historyGroups = useMemo(() => {
    const groups = new Map<string, { sessionId: string | null; records: HistoryRecord[] }>()
    historyRecords.forEach((record) => {
      const key = record.sessionId || `record:${record.recordId}`
      const group = groups.get(key) ?? { sessionId: record.sessionId, records: [] }
      group.records.push(record)
      groups.set(key, group)
    })
    const chronological = Array.from(groups.values())
      .map((group) => {
        const records = [...group.records].sort((left, right) => {
          if (left.sequenceIndex !== null && right.sequenceIndex !== null) {
            return left.sequenceIndex - right.sequenceIndex
          }
          return new Date(left.createdAt).getTime() - new Date(right.createdAt).getTime()
        })
        const startedAt = Math.min(...records.map((record) => {
          const timestamp = new Date(record.createdAt).getTime()
          return Number.isNaN(timestamp) ? 0 : timestamp
        }))
        return { ...group, records, startedAt }
      })
      .sort((left, right) => left.startedAt - right.startedAt)

    return chronological
      .map((group, index) => ({ ...group, label: `第 ${index + 1} 轮` }))
      .sort((left, right) => right.startedAt - left.startedAt)
  }, [historyRecords])

  const handleDeleteHistory = async (params: { recordId?: number; sessionId?: string }, message: string) => {
    if (!learner?.id || !window.confirm(message)) return
    setHistoryActionLoading(true)
    setHistoryActionError(null)
    try {
      await coreApi.deleteInteractionHistory(learner.id, params)
      setHistoryRecords((previous) => previous.filter((record) => (
        params.recordId !== undefined
          ? record.recordId !== String(params.recordId)
          : params.sessionId
          ? record.sessionId !== params.sessionId
          : false
      )))
      if (params.recordId !== undefined) {
        setExpandedHistory(null)
        setViewingHistoryRecord(null)
      }
    } catch (err) {
      setHistoryActionError(err instanceof Error ? err.message : '历史记录删除失败，请稍后重试')
    } finally {
      setHistoryActionLoading(false)
    }
  }

  const handleClearLearnerHistory = async () => {
    if (!learner?.id || !window.confirm(`确定清空“${learner.realName}”的全部交互历史吗？`)) return
    setHistoryActionLoading(true)
    setHistoryActionError(null)
    try {
      await coreApi.deleteInteractionHistory(learner.id)
      setHistoryRecords([])
      setExpandedHistory(null)
      setViewingHistoryRecord(null)
    } catch (err) {
      setHistoryActionError(err instanceof Error ? err.message : '历史记录清空失败，请稍后重试')
    } finally {
      setHistoryActionLoading(false)
    }
  }

  if (loading || (!learner && learnersLoading)) return <PageSkeleton type="default" />

  if (!learner) {
    return (
      <EmptyState
        type="users"
        title="请先创建学习者画像"
        description="完成学习者画像后，系统才能根据你的学习状态生成自适应导学题目。"
        action={(
          <Button variant="outline" onClick={() => navigate('/profile')}>
            前往学习者画像
          </Button>
        )}
      />
    )
  }

  if (loadError) {
    return (
      <ErrorState
        type="default"
        title="导学题库加载失败"
        description="无法读取当前学习者的导学题目，请稍后重试。"
        details={loadError}
        onRetry={() => { void loadData() }}
      />
    )
  }

  if (!question) {
    return (
      <EmptyState
        type="default"
        title="开始一轮自适应导学"
        description="系统会结合当前学习者画像、领域知识库和目标难度生成练习题。"
        action={(
          <form
            onSubmit={handleGenerateFromForm}
            noValidate
            className="w-full max-w-2xl space-y-4 text-left"
          >
            {isGenerating && <GuidanceLoadingAnimation />}
            <div className="space-y-2">
              <label htmlFor="adaptive-learner-selector" className="block text-sm font-medium text-text-primary">
                本轮学习者画像
              </label>
              <select
                id="adaptive-learner-selector"
                value={learner?.id ?? ''}
                onChange={(event) => {
                  const nextLearner = availableLearners.find((item) => item.id === Number(event.target.value))
                  if (!nextLearner) return
                  setSelectedLearnerId(nextLearner.id)
                  setCurrentLearner(nextLearner)
                  setGenerationError(null)
                }}
                disabled={isGenerating || learnersLoading}
                className="w-full h-11 px-3 rounded-lg border border-border bg-bg-card text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
              >
                {availableLearners.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.realName} · {item.major || item.targetIndustry || '未填写方向'}
                  </option>
                ))}
              </select>
              <p className="text-xs text-text-tertiary">
                本轮题目、难度推荐和进度都会归属于已选画像。
              </p>
            </div>

            <Input
              label="主题关键词"
              value={topicInput}
              onChange={(event) => setTopicInput(event.target.value)}
              placeholder="例如：反向传播、REST API"
              maxLength={200}
              disabled={isGenerating}
            />

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Input
                label="目标难度（1–5，可留空）"
                type="number"
                min={1}
                max={5}
                step={1}
                value={difficultyInput}
                onChange={(event) => setDifficultyInput(event.target.value)}
                placeholder="按学习者画像自动匹配"
                disabled={isGenerating}
              />

              <Input
                label="题量（1–10）"
                type="number"
                min={1}
                max={10}
                step={1}
                value={questionCountInput}
                onChange={(event) => setQuestionCountInput(event.target.value)}
                disabled={isGenerating}
              />
            </div>

            {generationError && (
              <p role="alert" className="text-sm text-error">
                {generationError}
              </p>
            )}
            <Button
              type="submit"
              variant="primary"
              loading={isGenerating}
              disabled={isGenerating}
            >
              生成导学题目
            </Button>
          </form>
        )}
      />
    )
  }

  const isCorrect = submitResult?.isCorrect ?? false
  const sessionTotal = sessionConfig?.questionCount ?? questions.length
  const answeredCount = Math.min(sessionTotal, currentQuestion + (showResult ? 1 : 0))
  const progress = sessionTotal > 0 ? (answeredCount / sessionTotal) * 100 : 0

  // 简化版内容（来自后端生成或默认模板）
  const simplifiedContent = submitResult?.generatedContent?.simpleExplanation
    ? {
        title: submitResult.generatedContent.title || `${question.topic} - 简化理解`,
        sections: [
          {
            heading: '💡 一句话理解',
            content: submitResult.generatedContent.simpleExplanation,
          },
          ...(submitResult.generatedContent.keyPoints?.length
            ? [{
                heading: '🎯 核心要点',
                points: submitResult.generatedContent.keyPoints,
              }]
            : []),
          ...(submitResult.generatedContent.practiceTips
            ? [{ heading: '🛠 实践建议', content: submitResult.generatedContent.practiceTips }]
            : []),
          ...(submitResult.generatedContent.recommendation
            ? [{ heading: '📌 个性化建议', content: submitResult.generatedContent.recommendation }]
            : []),
        ],
      }
    : null

  // 知识点扩展内容：与通俗讲解同时生成，始终可切换查看
  const expansion = submitResult?.generatedContent?.knowledgeExpansion
  const advancedContent = expansion
    ? {
        title: expansion.title || `${question.topic} - 知识点扩展`,
        sections: [
          ...(expansion.overview ? [{ heading: '知识点概览', content: expansion.overview }] : []),
          ...(expansion.keyPoints?.length ? [{ heading: '核心知识点', points: expansion.keyPoints }] : []),
          ...(expansion.application ? [{ heading: '应用联系', content: expansion.application }] : []),
          ...(expansion.pitfalls?.length ? [{ heading: '常见边界与误区', points: expansion.pitfalls }] : []),
        ],
      }
    : submitResult?.generatedContent?.challengeDescription
    ? {
        title: submitResult.generatedContent.title || `${question.topic} - 知识点扩展`,
        sections: [{ heading: '知识点概览', content: submitResult.generatedContent.challengeDescription }],
      }
    : null

  const currentGenerationMethod = question.generationMethod ?? generationMethod
  const generationSourceLabel = currentGenerationMethod === 'deepseek'
    ? 'AI 动态生成'
    : currentGenerationMethod === 'resource_generation'
    ? '分阶资源题'
    : currentGenerationMethod === 'deterministic_fallback'
    ? '本地兜底题'
    : currentGenerationMethod

  return (
    <div className="space-y-4 animate-fade-in">
      {/* 顶部信息栏 */}
      <Card padding="md">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
              <Brain className="w-6 h-6 text-primary" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-text-primary">动态自适应导学</h2>
              <p className="text-sm text-text-secondary">
                多 Agent 协同 · 实时决策反馈
                {learner && <span className="ml-2 text-text-tertiary">· {learner.realName}</span>}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-center">
              <p className="metric-number text-xl font-semibold text-success">{correctCount}</p>
              <p className="text-xs text-text-tertiary">正确数</p>
            </div>
            <div className="w-px h-10 bg-border" />
            <div className="text-center">
              <p className="metric-number text-xl font-semibold text-text-primary">{answeredCount}/{sessionTotal}</p>
              <p className="text-xs text-text-tertiary">当前进度</p>
            </div>
            <div className="w-px h-10 bg-border" />
            <div className="w-32">
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-text-tertiary">学习进度</span>
                <span className="text-primary font-medium">{Math.round(progress)}%</span>
              </div>
              <div className="h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
                <div className="h-full bg-primary rounded-full transition-all duration-250" style={{ width: `${progress}%` }} />
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={handleExitSession}
              disabled={isAdjusting || isGenerating}
            >
              <LogOut className="w-4 h-4" />
              退出本轮
            </Button>
          </div>
        </div>
      </Card>

      {/* 主内容区：左右分栏 */}
      <div className="grid grid-cols-12 gap-4">
        {/* 左侧：答题交互区 */}
        <div className="col-span-12 lg:col-span-7">
          <Card padding="none">
            {/* 题目头部 */}
            <div className="p-5 border-b border-border">
              <div className="flex items-center justify-between">
                <Badge variant="default" className="gap-1">
                  <Layers className="w-3 h-3" />
                  {isMultiSelect ? '多选题' : '单选题'}
                </Badge>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-text-tertiary px-2 py-1 bg-bg-secondary rounded-lg">
                    {question.topic} · 难度 {question.difficulty}
                  </span>
                  {generationSourceLabel && (
                    <Badge
                      variant={currentGenerationMethod === 'deterministic_fallback' ? 'warning' : 'info'}
                      size="sm"
                    >
                      题目来源：{generationSourceLabel}
                    </Badge>
                  )}
                </div>
              </div>
              <h3 className="text-base font-medium text-text-primary mt-3 leading-relaxed">
                {question.question}
              </h3>
              {currentGenerationMethod === 'deterministic_fallback' && (
                <p className="text-xs text-text-tertiary mt-2">
                  当前题目由本地兜底策略生成；补充领域知识库后可获得更强的主题针对性。
                </p>
              )}
            </div>

            {/* 选项区域 */}
            <div className="p-5 space-y-3">
              {question.options.map((option, idx) => {
                const isSelected = selectedAnswers.includes(idx)
                const isCorrectOption = showResult && isSelected && isCorrect
                const isWrongSelected = showResult && isSelected && !isCorrectOption

                return (
                  <button
                    key={idx}
                    onClick={() => handleSelect(idx)}
                    disabled={showResult || isAdjusting}
                    className={`w-full p-4 rounded-xl border text-left transition-all duration-250 ${
                      isCorrectOption
                        ? 'border-success/40 bg-success/5'
                        : isWrongSelected
                        ? 'border-warning/30 bg-warning-light/30'
                        : isSelected
                        ? 'border-primary/40 bg-primary/5'
                        : 'border-border/60 bg-bg-secondary/30 hover:border-primary/30'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className={`w-7 h-7 rounded-lg flex items-center justify-center text-sm font-medium transition-all duration-250 ${
                        isCorrectOption
                          ? 'bg-success text-white'
                          : isWrongSelected
                          ? 'bg-warning text-white'
                          : isSelected
                          ? 'bg-primary text-white'
                          : 'bg-bg-secondary text-text-tertiary'
                      }`}>
                        {isCorrectOption ? (
                          <CheckCircle2 className="w-4 h-4" />
                        ) : isWrongSelected ? (
                          <XCircle className="w-4 h-4" />
                        ) : (
                          String.fromCharCode(65 + idx)
                        )}
                      </div>
                      <span className={`flex-1 text-sm ${isCorrectOption ? 'text-success' : isWrongSelected ? 'text-warning-dark' : 'text-text-primary'}`}>
                        {option}
                      </span>
                    </div>
                  </button>
                )
              })}
            </div>

            {/* 反馈提示 */}
            {showResult && (
              <div className="mx-5 mb-5 p-4 rounded-xl bg-bg-secondary/50 border border-border/50 transition-all duration-250">
                <div className="flex items-start gap-3">
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                    isCorrect ? 'bg-success/10' : 'bg-primary/10'
                  }`}>
                    {isCorrect ? (
                      <CheckCircle2 className="w-5 h-5 text-success" />
                    ) : (
                      <Lightbulb className="w-5 h-5 text-primary" />
                    )}
                  </div>
                  <div>
                    <p className={`text-sm font-medium ${isCorrect ? 'text-success' : 'text-text-primary'}`}>
                      {isCorrect ? '判定结果：回答正确' : '判定结果：回答错误'}
                    </p>
                    <p className="text-xs text-text-secondary mt-1">
                      {sessionConfig?.difficulty !== undefined
                        ? `本轮固定难度 ${sessionConfig.difficulty}，继续完成剩余题目`
                        : isMultiSelect
                        ? '多选题需要选择所有正确答案'
                        : isCorrect
                        ? '可在下方查看通俗讲解和知识点扩展'
                        : '可在下方查看纠错讲解和知识点扩展'}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {answerError && (
              <p role="alert" className="mx-5 mb-5 text-sm text-error">
                {answerError}
              </p>
            )}

            {/* 操作按钮 */}
            <div className="p-5 pt-0 flex items-center justify-between">
              {!showResult ? (
                <span className="text-xs text-text-tertiary">共 {questions.length} 题</span>
              ) : (
                <span className="text-xs text-text-tertiary">
                  {submitResult?.agentDecision ? `决策置信度: ${((submitResult.agentDecision.confidence ?? 0) * 100).toFixed(0)}%` : 'Agent 决策已生成'}
                </span>
              )}
              <div className="flex items-center gap-2 ml-auto">
                {!showResult ? (
                  <Button
                    variant="primary"
                    onClick={handleSubmit}
                    disabled={selectedAnswers.length === 0 || isAdjusting}
                    loading={isAdjusting}
                  >
                    提交答案
                  </Button>
                ) : currentQuestion < questions.length - 1 ? (
                  <Button variant="primary" onClick={handleNext}>
                    下一题
                    <ArrowRight className="w-4 h-4 ml-1" />
                  </Button>
                ) : pendingNextDifficulty !== null && answeredCount < sessionTotal ? (
                  <Button variant="primary" onClick={() => { void handleRetryNextQuestion() }} loading={isGenerating}>
                    重试下一题
                  </Button>
                ) : (
                  <Button variant="primary" onClick={handleExitSession}>
                    <RefreshCw className="w-4 h-4 ml-1" />
                    回到导学配置
                  </Button>
                )}
              </div>
            </div>
          </Card>

          {/* 自适应内容标签页 */}
          {showResult && (simplifiedContent || advancedContent) && (
            <Card padding="none" className="mt-4">
              <div className="flex border-b border-border">
                <button
                  onClick={() => setActiveContentTab('simplified')}
                  disabled={!simplifiedContent}
                  className={`flex-1 py-3 px-4 flex items-center justify-center gap-2 text-sm font-medium transition-all duration-250 relative ${
                    activeContentTab === 'simplified'
                      ? 'text-primary'
                      : 'text-text-tertiary hover:text-text-secondary'
                  } ${!simplifiedContent ? 'opacity-40 cursor-not-allowed' : ''}`}
                >
                  <BookOpen className="w-4 h-4" />
                  简化版通俗讲解
                  {activeContentTab === 'simplified' && (
                    <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary" />
                  )}
                </button>
                <button
                  onClick={() => setActiveContentTab('advanced')}
                  disabled={!advancedContent}
                  className={`flex-1 py-3 px-4 flex items-center justify-center gap-2 text-sm font-medium transition-all duration-250 relative ${
                    activeContentTab === 'advanced'
                      ? 'text-warning-dark'
                      : 'text-text-tertiary hover:text-text-secondary'
                  } ${!advancedContent ? 'opacity-40 cursor-not-allowed' : ''}`}
                >
                  <Zap className="w-4 h-4" />
                  知识点扩展学习
                  {activeContentTab === 'advanced' && (
                    <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-warning" />
                  )}
                </button>
              </div>

              <div className="p-5 min-h-[280px] transition-all duration-250">
                {activeContentTab === 'simplified' && simplifiedContent ? (
                  <div className="space-y-4">
                    <div className="flex items-center gap-2 mb-3">
                      <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
                        <BookOpen className="w-4 h-4 text-primary" />
                      </div>
                      <h4 className="font-semibold text-text-primary">{simplifiedContent.title}</h4>
                    </div>
                    {simplifiedContent.sections.map((section: GeneratedSection) => (
                      <div key={section.heading} className="space-y-2">
                        <h5 className="text-sm font-medium text-text-primary">{section.heading}</h5>
                        {section.content && (
                          <p className="text-sm text-text-secondary leading-relaxed">{section.content}</p>
                        )}
                        {section.points && (
                          <ul className="space-y-1">
                            {section.points.map((p: string, pIdx: number) => (
                              <li key={pIdx} className="text-sm text-text-secondary flex items-start gap-2">
                                <span className="w-1.5 h-1.5 rounded-full bg-primary/50 mt-1.5 flex-shrink-0" />
                                {p}
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    ))}
                  </div>
                ) : activeContentTab === 'advanced' && advancedContent ? (
                  <div className="space-y-4">
                    <div className="flex items-center gap-2 mb-3">
                      <div className="w-8 h-8 rounded-lg bg-warning-light flex items-center justify-center">
                        <Zap className="w-4 h-4 text-warning" />
                      </div>
                      <h4 className="font-semibold text-text-primary">{advancedContent.title}</h4>
                    </div>
                    {advancedContent.sections.map((section: GeneratedSection) => (
                      <div key={section.heading} className="space-y-2">
                        <h5 className="text-sm font-medium text-text-primary">{section.heading}</h5>
                        {section.content && (
                          <p className="text-sm text-text-secondary leading-relaxed">
                            {section.content}
                          </p>
                        )}
                        {section.points && (
                          <ul className="space-y-1">
                            {section.points.map((point: string, pointIndex: number) => (
                              <li key={pointIndex} className="text-sm text-text-secondary flex items-start gap-2">
                                <Target className="w-3.5 h-3.5 text-warning mt-0.5 flex-shrink-0" />
                                {point}
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState type="default" title="该方向暂无生成内容" description="系统将根据答题结果自动生成对应方向内容" />
                )}
              </div>
            </Card>
          )}
        </div>

        {/* 右侧：Agent 决策面板 */}
        <div className="col-span-12 lg:col-span-5 space-y-4">
          {/* Agent 决策可视化 */}
          <Card padding="md">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-primary" />
                多 Agent 协同决策
              </h3>
              {isAdjusting && <RefreshCw className="w-4 h-4 text-primary animate-spin" />}
            </div>

            {isAdjusting && (
              <div className="mb-4">
                <div className="h-1 bg-bg-tertiary rounded-full overflow-hidden">
                  <div
                    className="h-full bg-primary rounded-full transition-all duration-250"
                    style={{ width: `${adjustmentProgress}%` }}
                  />
                </div>
                <p className="text-xs text-text-tertiary mt-1.5 text-right">
                  {Math.round(adjustmentProgress)}%
                </p>
              </div>
            )}

            <div className="space-y-3">
              {agentSteps.map((agent) => {
                const Icon = agent.icon
                return (
                  <div
                    key={agent.agent}
                    className={`relative p-3 rounded-xl border transition-all duration-250 ${
                      agent.status === 'complete'
                        ? 'border-success/30 bg-success/5'
                        : agent.status === 'running'
                        ? 'border-primary/30 bg-primary/5'
                        : 'border-border/50 bg-bg-secondary/30'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-250 ${
                        agent.status === 'complete'
                          ? 'bg-success/10'
                          : agent.status === 'running'
                          ? 'bg-primary/10'
                          : 'bg-bg-tertiary'
                      }`}>
                        <Icon className={`w-4 h-4 ${
                          agent.status === 'complete'
                            ? 'text-success'
                            : agent.status === 'running'
                            ? 'text-primary'
                            : 'text-text-tertiary'
                        }`} />
                      </div>
                      <div className="flex-1">
                        <p className={`text-sm font-medium ${
                          agent.status === 'complete'
                            ? 'text-success'
                            : agent.status === 'running'
                            ? 'text-primary'
                            : 'text-text-tertiary'
                        }`}>
                          {agent.name}
                        </p>
                        <p className="text-xs text-text-tertiary">{agent.action}</p>
                      </div>
                      {agent.status === 'complete' && (
                        <CheckCircle2 className="w-4 h-4 text-success" />
                      )}
                      {agent.status === 'running' && (
                        <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                      )}
                    </div>
                  </div>
                )
              })}
            </div>

            {/* 决策结果 */}
            {showResult && !isAdjusting && submitResult && (
              <div className="mt-4 pt-4 border-t border-border">
                <div className="p-3 rounded-xl bg-bg-secondary/50">
                  <div className="flex items-center gap-2 mb-2">
                    <MessageSquare className="w-4 h-4 text-text-secondary" />
                    <span className="text-xs font-medium text-text-primary">决策结论</span>
                  </div>
                  <p className="text-sm text-text-secondary leading-relaxed">
                    {submitResult.agentDecision?.reason
                      ? submitResult.agentDecision.reason
                      : isCorrect
                      ? '系统判定：答题正确，建议继续深化知识点理解'
                      : '系统判定：答题错误，建议查看纠错讲解和知识点扩展'}
                  </p>
                  {submitResult.nextAction && (
                    <p className="text-xs text-text-tertiary mt-2">
                      后续动作：{submitResult.nextAction.description}
                    </p>
                  )}
                </div>
              </div>
            )}
          </Card>

          {/* 历史交互记录 */}
          <Card padding="md">
            <div className="mb-3 flex items-start justify-between gap-3">
              <div>
                <h4 className="text-sm font-semibold text-text-primary flex items-center gap-2">
                  <Clock className="w-4 h-4 text-text-secondary" />
                  交互历史记录
                </h4>
                <p className="mt-1 text-xs text-text-tertiary">
                  {learner.realName} · {historyRecords.length} 条记录 · 点击题目可回放
                </p>
              </div>
              {historyRecords.length > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => { void handleClearLearnerHistory() }}
                  disabled={historyActionLoading}
                  className="text-error hover:text-error"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  清空当前画像
                </Button>
              )}
            </div>
            {historyActionError && (
              <p role="alert" className="mb-3 text-xs text-error">{historyActionError}</p>
            )}
            <div className="max-h-[420px] space-y-3 overflow-y-auto pr-1 overscroll-contain">
              {historyRecords.length === 0 ? (
                <EmptyState
                  type="default"
                  title="暂无交互记录"
                  description="答题后将在这里显示交互记录"
                />
              ) : (
                historyGroups.map((group) => (
                  <div key={group.sessionId ?? group.records[0]?.recordId} className="rounded-xl border border-border/60 bg-bg-secondary/10 p-2">
                    <div className="flex items-center justify-between gap-2 px-2 pb-2">
                      <div className="flex items-center gap-2 text-xs text-text-secondary">
                        <span className="font-semibold text-text-primary">{group.label}</span>
                        <span>{group.records.length} 题</span>
                        <span>· {formatHistoryDate(group.records[0]?.createdAt ?? '')}</span>
                      </div>
                      {group.sessionId && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => { void handleDeleteHistory({ sessionId: group.sessionId ?? undefined }, `确定删除${group.label}的全部记录吗？`) }}
                          disabled={historyActionLoading}
                          className="h-7 px-2 text-xs text-error hover:text-error"
                        >
                          删除本轮
                        </Button>
                      )}
                    </div>
                    <div className="space-y-2">
                      {group.records.map((record, recordIndex) => {
                        const isExpanded = expandedHistory === record.recordId
                        const isViewing = viewingHistoryRecord === record.recordId
                        const sequence = record.sequenceIndex ?? recordIndex + 1
                        return (
                          <div key={record.recordId} className="overflow-hidden rounded-xl border border-border/50 bg-bg-card transition-all duration-250">
                            <div className="flex items-stretch">
                              <button
                                aria-expanded={isExpanded}
                                onClick={() => {
                                  setExpandedHistory(isExpanded ? null : record.recordId)
                                  setViewingHistoryRecord(isViewing ? null : record.recordId)
                                }}
                                className="flex min-w-0 flex-1 items-center justify-between gap-2 p-3 text-left hover:bg-bg-secondary/50 transition-colors"
                              >
                                <div className="flex min-w-0 items-center gap-2">
                                  <div className={`w-6 h-6 rounded-lg flex items-center justify-center flex-shrink-0 ${
                                    record.result === 'correct'
                                      ? 'bg-success/10'
                                      : record.result === 'wrong'
                                      ? 'bg-warning-light'
                                      : 'bg-primary/10'
                                  }`}>
                                    {record.result === 'correct' ? (
                                      <CheckCircle2 className="w-3.5 h-3.5 text-success" />
                                    ) : record.result === 'wrong' ? (
                                      <XCircle className="w-3.5 h-3.5 text-warning" />
                                    ) : (
                                      <MessageSquare className="w-3.5 h-3.5 text-primary" />
                                    )}
                                  </div>
                                  <div className="min-w-0">
                                    <p className="truncate text-sm font-medium text-text-primary">第 {sequence} 题 · {record.questionTopic || '未知题目'}</p>
                                    <p className="mt-0.5 text-[11px] text-text-tertiary">难度 {record.questionDifficulty} · {formatHistoryDate(record.createdAt)}</p>
                                  </div>
                                </div>
                                <div className="flex flex-shrink-0 items-center gap-2">
                                  <Badge
                                    variant={record.agentDecision === 'advance' ? 'success' : record.agentDecision === 'simplify' ? 'warning' : 'default'}
                                    size="sm"
                                  >
                                    {record.agentDecision === 'advance' ? '深化' : record.agentDecision === 'simplify' ? '讲解' : '巩固'}
                                  </Badge>
                                  {isExpanded ? (
                                    <ChevronDown className="w-4 h-4 text-text-tertiary" />
                                  ) : (
                                    <ChevronRight className="w-4 h-4 text-text-tertiary" />
                                  )}
                                </div>
                              </button>
                              <button
                                type="button"
                                aria-label={`删除第${sequence}题记录`}
                                onClick={() => { void handleDeleteHistory({ recordId: Number(record.recordId) }, `确定删除${group.label}第 ${sequence} 题的记录吗？`) }}
                                disabled={historyActionLoading}
                                className="border-l border-border/50 px-3 text-text-tertiary transition-colors hover:bg-error/5 hover:text-error disabled:opacity-40"
                              >
                                <Trash2 className="h-4 w-4" />
                              </button>
                            </div>
                            {isExpanded && (
                              <div className="border-t border-border/30 bg-bg-secondary/20 p-3 transition-all duration-250">
                                <p className="text-xs text-text-secondary">
                                  <span className="font-medium">题目回放：</span>{record.questionContent || '历史数据未保存题干'}
                                </p>
                                <p className="mt-1 text-xs text-text-secondary">我的答案：{formatUserAnswer(record.userAnswer)}</p>
                                <p className="mt-1 text-xs text-text-secondary">
                                  <span className="font-medium">判定结果：</span>{record.result === 'correct' ? '正确' : '错误'}
                                </p>
                                {record.decisionReason && (
                                  <p className="mt-1 text-xs text-text-secondary"><span className="font-medium">决策原因：</span>{record.decisionReason}</p>
                                )}
                                {record.feedbackContent && (
                                  <p className="mt-1 text-xs text-text-secondary"><span className="font-medium">反馈：</span>{record.feedbackContent}</p>
                                )}
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  </div>
                ))
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
