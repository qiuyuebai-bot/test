import { useState, useEffect, useCallback, useRef } from 'react'
import { useStore } from '@/store'
import { useShallow } from 'zustand/react/shallow'
import { coreApi } from '@/api'
import type { TutoringQuestion } from '@/api/core'
import Card from '@/components/Card'
import Badge from '@/components/Badge'
import Button from '@/components/Button'
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
} from 'lucide-react'

interface HistoryRecord {
  recordId: string
  questionTopic: string
  result: 'correct' | 'wrong' | 'partial'
  agentDecision: string
  decisionReason: string
  createdAt: string
  score: number
}

interface GeneratedContent {
  type?: string
  title?: string
  simpleExplanation?: string
  keyPoints?: string[]
  practiceTips?: string
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

type HistoryRecordRaw = {
  recordId?: string
  record_id?: string
  id?: string
  questionTopic?: string
  question_topic?: string
  topic?: string
  result?: string
  agentDecision?: string
  agent_decision?: string
  nextAction?: string
  next_action?: string
  decisionReason?: string
  decision_reason?: string
  createdAt?: string
  created_at?: string
  score?: number
}

type HistoryRespRaw = {
  items?: HistoryRecordRaw[]
  history?: HistoryRecordRaw[]
}

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
}

type SubmitResultRaw = {
  data?: SubmitDataRaw
} & SubmitDataRaw

function mapHistoryRecord(r: HistoryRecordRaw): HistoryRecord {
  return {
    recordId: r.recordId ?? r.record_id ?? r.id ?? '',
    questionTopic: r.questionTopic ?? r.question_topic ?? r.topic ?? '',
    result: (r.result === 'correct' ? 'correct' : r.result === 'wrong' ? 'wrong' : 'partial'),
    agentDecision: r.agentDecision ?? r.agent_decision ?? r.nextAction ?? r.next_action ?? '',
    decisionReason: r.decisionReason ?? r.decision_reason ?? '',
    createdAt: r.createdAt ?? r.created_at ?? '',
    score: r.score ?? 0,
  }
}

export default function AdaptiveGuidance() {
  const { currentLearner, learners } = useStore(
    useShallow((s) => ({
      currentLearner: s.currentLearner,
      learners: s.learners,
    }))
  )
  const learner = currentLearner || learners[0]

  const [questions, setQuestions] = useState<TutoringQuestion[]>([])
  const [currentQuestion, setCurrentQuestion] = useState(0)
  const [selectedAnswers, setSelectedAnswers] = useState<number[]>([])
  const [showResult, setShowResult] = useState(false)
  const [isAdjusting, setIsAdjusting] = useState(false)
  const [adjustmentProgress, setAdjustmentProgress] = useState(0)
  const [agentSteps, setAgentSteps] = useState<AgentStep[]>(INITIAL_AGENT_STEPS)
  const [activeContentTab, setActiveContentTab] = useState<ContentTab>('simplified')
  const [expandedHistory, setExpandedHistory] = useState<string | null>(null)
  const [correctCount, setCorrectCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [historyRecords, setHistoryRecords] = useState<HistoryRecord[]>([])
  const [submitResult, setSubmitResult] = useState<SubmitResult | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  }, [])

  const loadData = useCallback(async () => {
    if (!learner?.id) {
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const [questionsResp, historyResp] = await Promise.all([
        coreApi.getTutoringQuestions().catch(() => [] as TutoringQuestion[]),
        coreApi.getInteractionHistory(learner.id, { page: 1, pageSize: 20 }).catch(() => null),
      ])
      setQuestions((questionsResp as TutoringQuestion[]) || [])

      // 转换历史记录字段
      const historyAny = historyResp as HistoryRespRaw | null
      const historyItems: HistoryRecordRaw[] = historyAny?.items || historyAny?.history || []
      const mapped: HistoryRecord[] = historyItems.map(mapHistoryRecord)
      setHistoryRecords(mapped)
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载数据失败')
    } finally {
      setLoading(false)
    }
  }, [learner?.id])

  useEffect(() => {
    loadData()
  }, [loadData])

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

    const correctIndexes = isMultiSelect ? question.correctIndexes || [] : [question.correctIndex ?? 0]
    const selectedSorted = [...selectedAnswers].sort()
    const correctSorted = [...correctIndexes].sort()
    const isCorrect =
      isMultiSelect
        ? JSON.stringify(selectedSorted) === JSON.stringify(correctSorted)
        : selectedAnswers[0] === correctIndexes[0]
    const score = isCorrect ? 100 : 0
    const userAnswer = selectedAnswers.map((i) => String.fromCharCode(65 + i)).join(',')
    const correctAnswer = correctIndexes.map((i) => String.fromCharCode(65 + i)).join(',')

    setShowResult(true)
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
      const result = await coreApi.submitAnswer({
        learnerId: learner.id,
        questionId: question.id,
        questionType: question.type,
        questionTopic: question.topic,
        questionDifficulty: question.difficulty,
        questionContent: question.question,
        userAnswer,
        correctAnswer,
        score,
        timeSpentMs: 0,
        hintsUsed: 0,
      }) as SubmitResultRaw

      const data: SubmitDataRaw = result?.data ?? result
      const generated: GeneratedContent = (data?.generatedContent ?? data?.generated_content ?? {}) as GeneratedContent
      setSubmitResult({
        isCorrect: data?.isCorrect ?? data?.is_correct ?? isCorrect,
        score: data?.score ?? score,
        agentDecision: data?.agentDecision ?? data?.agent_decision,
        nextAction: data?.nextAction ?? data?.next_action,
        generatedContent: generated,
      })

      // 根据生成内容自动选择标签页
      const decision = (data?.agentDecision?.decision ?? data?.agent_decision?.decision ?? data?.nextAction?.type ?? data?.next_action?.type ?? '').toLowerCase()
      if (decision === 'advance') {
        setActiveContentTab('advanced')
      } else {
        setActiveContentTab('simplified')
      }

      if (isCorrect) setCorrectCount((c) => c + 1)
    } catch {
      // 接口失败时仍展示本地判断结果
      setSubmitResult({
        isCorrect,
        score,
        generatedContent: {},
      })
      setActiveContentTab(isCorrect ? 'advanced' : 'simplified')
      if (isCorrect) setCorrectCount((c) => c + 1)
    } finally {
      clearInterval(interval)
      intervalRef.current = null
      setIsAdjusting(false)
      setAgentSteps(INITIAL_AGENT_STEPS.map((s) => ({ ...s, status: 'complete' })))
      setAdjustmentProgress(100)
      // 刷新历史记录
      coreApi.getInteractionHistory(learner.id, { page: 1, pageSize: 20 }).then((resp: unknown) => {
        const items: HistoryRecordRaw[] = (resp as HistoryRespRaw)?.items || (resp as HistoryRespRaw)?.history || []
        const mapped: HistoryRecord[] = items.map(mapHistoryRecord)
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
    }
  }

  if (loading) return <PageSkeleton type="default" />

  if (error) {
    return <ErrorState type="default" onRetry={() => loadData()} />
  }

  if (!question) {
    return (
      <EmptyState
        type="default"
        title="暂无导学题目"
        description="请稍后重试或联系管理员配置题库"
      />
    )
  }

  const isCorrect = submitResult?.isCorrect ?? false
  const progress = ((currentQuestion + (showResult ? 1 : 0)) / questions.length) * 100

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
        ],
      }
    : null

  // 进阶挑战内容
  const advancedContent = submitResult?.generatedContent?.challengeDescription
    ? {
        title: submitResult.generatedContent.title || `${question.topic} - 进阶挑战`,
        sections: [
          {
            heading: '挑战描述',
            content: submitResult.generatedContent.challengeDescription,
          },
          ...(submitResult.generatedContent.challengeObjectives?.length
            ? [{ heading: '实践任务', tasks: submitResult.generatedContent.challengeObjectives }]
            : []),
          ...(submitResult.generatedContent.estimatedTime
            ? [{ heading: '预估时间', content: submitResult.generatedContent.estimatedTime }]
            : []),
        ],
      }
    : null

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
          <div className="flex items-center gap-6">
            <div className="text-center">
              <p className="text-xl font-semibold text-success">{correctCount}</p>
              <p className="text-xs text-text-tertiary">正确数</p>
            </div>
            <div className="w-px h-10 bg-border" />
            <div className="text-center">
              <p className="text-xl font-semibold text-text-primary">{currentQuestion + 1}/{questions.length}</p>
              <p className="text-xs text-text-tertiary">当前进度</p>
            </div>
            <div className="w-px h-10 bg-border" />
            <div className="w-32">
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-text-tertiary">学习进度</span>
                <span className="text-primary font-medium">{Math.round(progress)}%</span>
              </div>
              <div className="h-1.5 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
                <div className="h-full bg-primary rounded-full transition-all duration-300" style={{ width: `${progress}%` }} />
              </div>
            </div>
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
                <span className="text-xs text-text-tertiary px-2 py-1 bg-bg-secondary rounded-lg">
                  {question.topic} · 难度 {question.difficulty}
                </span>
              </div>
              <h3 className="text-base font-medium text-text-primary mt-3 leading-relaxed">
                {question.question}
              </h3>
            </div>

            {/* 选项区域 */}
            <div className="p-5 space-y-3">
              {question.options.map((option, idx) => {
                const isSelected = selectedAnswers.includes(idx)
                const correctIndexes = isMultiSelect ? question.correctIndexes || [] : [question.correctIndex ?? 0]
                const isCorrectOption = showResult && correctIndexes.includes(idx)
                const isWrongSelected = showResult && isSelected && !isCorrectOption

                return (
                  <button
                    key={idx}
                    onClick={() => handleSelect(idx)}
                    disabled={showResult}
                    className={`w-full p-4 rounded-xl border text-left transition-all duration-200 ${
                      isCorrectOption
                        ? 'border-success/40 bg-success/5'
                        : isWrongSelected
                        ? 'border-amber-200/50 bg-amber-50/30'
                        : isSelected
                        ? 'border-primary/40 bg-primary/5'
                        : 'border-border/60 bg-bg-secondary/30 hover:border-primary/30'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className={`w-7 h-7 rounded-lg flex items-center justify-center text-sm font-medium transition-all duration-200 ${
                        isCorrectOption
                          ? 'bg-success text-white'
                          : isWrongSelected
                          ? 'bg-amber-400 text-white'
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
                      <span className={`flex-1 text-sm ${isCorrectOption ? 'text-success' : isWrongSelected ? 'text-amber-600' : 'text-text-primary'}`}>
                        {option}
                      </span>
                    </div>
                  </button>
                )
              })}
            </div>

            {/* 反馈提示 */}
            {showResult && (
              <div className="mx-5 mb-5 p-4 rounded-xl bg-bg-secondary/50 border border-border/50 transition-all duration-300">
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
                      {isCorrect ? '回答正确，表现优秀！' : '回答错误，已触发自适应调整'}
                    </p>
                    <p className="text-xs text-text-secondary mt-1">
                      {isMultiSelect
                        ? '多选题需要选择所有正确答案'
                        : isCorrect
                        ? '继续挑战更高难度内容'
                        : '系统将为你降维讲解该知识点'}
                    </p>
                    {submitResult?.score !== undefined && (
                      <p className="text-xs text-text-tertiary mt-1">得分：{submitResult.score} 分</p>
                    )}
                  </div>
                </div>
              </div>
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
                ) : (
                  <Button variant="primary" onClick={() => loadData()}>
                    <RefreshCw className="w-4 h-4 ml-1" />
                    重新开始
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
                  className={`flex-1 py-3 px-4 flex items-center justify-center gap-2 text-sm font-medium transition-all duration-200 relative ${
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
                  className={`flex-1 py-3 px-4 flex items-center justify-center gap-2 text-sm font-medium transition-all duration-200 relative ${
                    activeContentTab === 'advanced'
                      ? 'text-amber-600'
                      : 'text-text-tertiary hover:text-text-secondary'
                  } ${!advancedContent ? 'opacity-40 cursor-not-allowed' : ''}`}
                >
                  <Zap className="w-4 h-4" />
                  高阶拓展挑战
                  {activeContentTab === 'advanced' && (
                    <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-amber-500" />
                  )}
                </button>
              </div>

              <div className="p-5 min-h-[280px] transition-all duration-300">
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
                      <div className="w-8 h-8 rounded-lg bg-amber-50 flex items-center justify-center">
                        <Zap className="w-4 h-4 text-amber-500" />
                      </div>
                      <h4 className="font-semibold text-text-primary">{advancedContent.title}</h4>
                    </div>
                    {advancedContent.sections.map((section: GeneratedSection) => (
                      <div key={section.heading} className="space-y-2">
                        <h5 className="text-sm font-medium text-text-primary">{section.heading}</h5>
                        {section.content && (
                          <p className="text-xs text-text-secondary font-mono bg-bg-secondary/50 p-2 rounded-lg leading-relaxed">
                            {section.content}
                          </p>
                        )}
                        {section.tasks && (
                          <ul className="space-y-1">
                            {section.tasks.map((t: string, tIdx: number) => (
                              <li key={tIdx} className="text-sm text-text-secondary flex items-start gap-2">
                                <Target className="w-3.5 h-3.5 text-amber-500 mt-0.5 flex-shrink-0" />
                                {t}
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
                <div className="h-1 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-primary rounded-full transition-all duration-300"
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
                    className={`relative p-3 rounded-xl border transition-all duration-200 ${
                      agent.status === 'complete'
                        ? 'border-success/30 bg-success/5'
                        : agent.status === 'running'
                        ? 'border-primary/30 bg-primary/5'
                        : 'border-border/50 bg-bg-secondary/30'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-200 ${
                        agent.status === 'complete'
                          ? 'bg-success/10'
                          : agent.status === 'running'
                          ? 'bg-primary/10'
                          : 'bg-gray-100 dark:bg-gray-800'
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
                      ? '系统判定：答题正确，建议进入高阶挑战任务，继续提升'
                      : '系统判定：答题错误，自动触发降维简化讲解'}
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

          {/* 学习者状态 */}
          <Card padding="md">
            <h4 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
              <User className="w-4 h-4 text-text-secondary" />
              学习者状态
            </h4>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-text-secondary">理论基础</span>
                <span className="text-sm font-medium text-text-primary">{learner?.theoreticalFoundation ?? 0}%</span>
              </div>
              <div className="h-1.5 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
                <div className="h-full bg-primary rounded-full" style={{ width: `${learner?.theoreticalFoundation ?? 0}%` }} />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-text-secondary">学习风格</span>
                <Badge variant="info" size="sm">
                  {learner?.learningStyle === 'visual' ? '视觉型' : learner?.learningStyle === 'kinesthetic' ? '动觉型' : learner?.learningStyle === 'auditory' ? '听觉型' : '阅读型'}
                </Badge>
              </div>
            </div>
          </Card>

          {/* 历史交互记录 */}
          <Card padding="md">
            <h4 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
              <Clock className="w-4 h-4 text-text-secondary" />
              交互历史记录
            </h4>
            <div className="space-y-2">
              {historyRecords.length === 0 ? (
                <EmptyState
                  type="default"
                  title="暂无交互记录"
                  description="答题后将在这里显示交互记录"
                />
              ) : (
                historyRecords.map((record) => {
                  const isExpanded = expandedHistory === record.recordId
                  return (
                    <div key={record.recordId} className="rounded-xl border border-border/50 overflow-hidden transition-all duration-200">
                      <button
                        onClick={() => setExpandedHistory(isExpanded ? null : record.recordId)}
                        className="w-full p-3 flex items-center justify-between bg-bg-secondary/30 hover:bg-bg-secondary/50 transition-colors"
                      >
                        <div className="flex items-center gap-2">
                          <div className={`w-6 h-6 rounded-lg flex items-center justify-center ${
                            record.result === 'correct'
                              ? 'bg-success/10'
                              : record.result === 'wrong'
                              ? 'bg-amber-50'
                              : 'bg-primary/10'
                          }`}>
                            {record.result === 'correct' ? (
                              <CheckCircle2 className="w-3.5 h-3.5 text-success" />
                            ) : record.result === 'wrong' ? (
                              <XCircle className="w-3.5 h-3.5 text-amber-500" />
                            ) : (
                              <MessageSquare className="w-3.5 h-3.5 text-primary" />
                            )}
                          </div>
                          <span className="text-sm font-medium text-text-primary">{record.questionTopic || '未知题目'}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge
                            variant={record.agentDecision === 'advance' ? 'success' : record.agentDecision === 'simplify' ? 'warning' : 'default'}
                            size="sm"
                          >
                            {record.agentDecision === 'advance' ? '进阶' : record.agentDecision === 'simplify' ? '降维' : '维持'}
                          </Badge>
                          {isExpanded ? (
                            <ChevronDown className="w-4 h-4 text-text-tertiary" />
                          ) : (
                            <ChevronRight className="w-4 h-4 text-text-tertiary" />
                          )}
                        </div>
                      </button>
                      {isExpanded && (
                        <div className="p-3 bg-bg-secondary/20 border-t border-border/30 transition-all duration-200">
                          <p className="text-xs text-text-secondary">
                            <span className="font-medium">决策时间：</span>{record.createdAt || '未知'}
                          </p>
                          <p className="text-xs text-text-secondary mt-1">
                            <span className="font-medium">得分：</span>{record.score}
                          </p>
                          {record.decisionReason && (
                            <p className="text-xs text-text-secondary mt-1">
                              <span className="font-medium">决策原因：</span>{record.decisionReason}
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  )
                })
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
