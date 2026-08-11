import { useState, type FormEvent } from 'react'
import type { TutoringQuestion } from '@/api/core'
import type { LearnerProfile, UserRole } from '@/types'
import Button from '@/components/Button'
import EmptyState from '@/components/EmptyState'
import AdvancedGuidanceSettings from './AdvancedGuidanceSettings'
import LearnerContextBar from './LearnerContextBar'
import type { GuidanceMode, GuidanceRecommendation } from './types'
import { Lightbulb, Play, RefreshCw } from 'lucide-react'

interface GuidanceLauncherProps {
  learner: LearnerProfile | null | undefined
  learners: LearnerProfile[]
  role?: UserRole | string
  selectedLearnerId: number | null
  onLearnerChange: (learner: LearnerProfile) => void
  recommendation: GuidanceRecommendation | null
  recommendationLoading: boolean
  recommendationError: string | null
  generationError: string | null
  loading: boolean
  initialTopic?: string
  initialDifficulty?: string
  initialQuestionCount?: string
  onStart: (options?: { topic?: string; difficulty?: number; questionCount?: number; mode?: GuidanceMode }) => Promise<TutoringQuestion[]>
  onRefreshRecommendation: () => void
}

export default function GuidanceLauncher({
  learner,
  learners,
  role,
  selectedLearnerId,
  onLearnerChange,
  recommendation,
  recommendationLoading,
  recommendationError,
  generationError,
  loading,
  initialTopic = '',
  initialDifficulty = '',
  initialQuestionCount = '5',
  onStart,
  onRefreshRecommendation,
}: GuidanceLauncherProps) {
  const [topic, setTopic] = useState(initialTopic)
  const [difficulty, setDifficulty] = useState(initialDifficulty)
  const [questionCount, setQuestionCount] = useState(initialQuestionCount)
  const [mode, setMode] = useState<GuidanceMode>('adaptive')
  const [validationError, setValidationError] = useState<string | null>(null)

  const start = async (options?: { topic?: string; difficulty?: number; questionCount?: number }) => {
    setValidationError(null)
    await onStart({ ...options, mode })
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const normalizedTopic = topic.trim()
    const targetDifficulty = difficulty === '' ? undefined : Number(difficulty)
    const count = Number(questionCount)
    if (!normalizedTopic) {
      setValidationError('请输入主题关键词，例如“反向传播”或“REST API”')
      return
    }
    if (normalizedTopic.length > 200) {
      setValidationError('主题关键词不能超过 200 个字符')
      return
    }
    if (targetDifficulty !== undefined && (!Number.isInteger(targetDifficulty) || targetDifficulty < 1 || targetDifficulty > 5)) {
      setValidationError('目标难度必须是 1–5 的整数')
      return
    }
    if (!Number.isInteger(count) || count < 1 || count > 10) {
      setValidationError('题量必须是 1–10 的整数')
      return
    }
    void start({ topic: normalizedTopic || undefined, difficulty: targetDifficulty, questionCount: count })
  }

  if (!learner) {
    return (
      <EmptyState
        type="users"
        title="请先创建学习者画像"
        description="完成学习者画像后，系统才能根据你的学习状态生成自适应导学题目。"
      />
    )
  }

  const displayedError = validationError || generationError || recommendationError

  return (
    <EmptyState
      type="default"
      title="开始一轮自适应导学"
      description="系统会结合学习者画像、知识盲区和最近练习，自动准备第一道题。"
      action={(
        <div className="w-full max-w-2xl space-y-4 text-left">
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border/70 bg-bg-secondary/30 px-3 py-2">
            <LearnerContextBar
              learner={learner}
              learners={learners}
              role={role}
              selectedLearnerId={selectedLearnerId}
              onLearnerChange={onLearnerChange}
              disabled={loading}
            />
            <span className="text-xs text-text-tertiary">默认 5 题，逐题适配难度</span>
          </div>

          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2" role="group" aria-label="导学答题模式">
            {([
              { value: 'adaptive' as const, title: '逐题自适应', description: '每题提交后立即反馈，下一题随表现调整' },
              { value: 'batch' as const, title: '整卷练习', description: '一次生成整套题，完成后统一评分与解析' },
            ]).map((option) => (
              <button
                key={option.value}
                type="button"
                aria-pressed={mode === option.value}
                onClick={() => setMode(option.value)}
                disabled={loading}
                className={`rounded-lg border p-3 text-left transition-colors ${mode === option.value ? 'border-primary bg-primary/5' : 'border-border/70 bg-bg-secondary/30 hover:border-primary/30'}`}
              >
                <span className="block text-sm font-medium text-text-primary">{option.title}</span>
                <span className="mt-1 block text-xs leading-relaxed text-text-secondary">{option.description}</span>
              </button>
            ))}
          </div>

          <div className="rounded-xl border border-primary/15 bg-primary/5 p-4">
            <div className="flex items-start gap-3">
              <Lightbulb className="mt-0.5 h-5 w-5 flex-shrink-0 text-primary" />
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium uppercase tracking-wide text-primary">系统推荐</p>
                {recommendationLoading ? (
                  <p role="status" className="mt-1 text-sm text-text-secondary">正在读取你的学习重点…</p>
                ) : (
                  <>
                    <p className="mt-1 text-sm font-medium text-text-primary">
                      {recommendation?.primaryTopic || '从最近的分阶测试资源开始'}
                    </p>
                    <p className="mt-1 text-xs leading-relaxed text-text-secondary">
                      {recommendation?.reason || '留空主题即可让系统从画像和最近练习中自动选择。'}
                    </p>
                  </>
                )}
              </div>
            </div>
          </div>

          {displayedError && <p role="alert" className="text-sm text-error">{displayedError}</p>}

          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" variant="primary" loading={loading} disabled={loading} onClick={() => { void start() }}>
              <Play className="h-4 w-4" />
              一键开始
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={loading}
              onClick={onRefreshRecommendation}
            >
              <RefreshCw className="h-4 w-4" />
              重新读取推荐
            </Button>
          </div>

          <AdvancedGuidanceSettings
            topic={topic}
            difficulty={difficulty}
            questionCount={questionCount}
            loading={loading}
            onTopicChange={setTopic}
            onDifficultyChange={setDifficulty}
            onQuestionCountChange={setQuestionCount}
            onSubmit={handleSubmit}
          />
        </div>
      )}
    />
  )
}
