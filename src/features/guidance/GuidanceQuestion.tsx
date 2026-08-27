import Card from '@/components/Card'
import Badge from '@/components/Badge'
import Button from '@/components/Button'
import type { TutoringQuestion } from '@/api/core'
import type { GuidanceMode, SubmitResult } from './types'
import { ArrowRight, CheckCircle2, Layers, XCircle } from 'lucide-react'

interface GuidanceQuestionProps {
  question: TutoringQuestion
  selectedAnswers: number[]
  showResult: boolean
  isSubmitting: boolean
  isPreparingNext: boolean
  submitResult: SubmitResult | null
  answerError: string | null
  nextQuestionError: string | null
  currentGenerationMethod?: string | null
  sessionDifficulty?: number
  questionCount: number
  hasNext: boolean
  mode?: GuidanceMode
  hasPrevious?: boolean
  batchCanSubmit?: boolean
  onSelect: (index: number) => void
  onSubmit: () => void
  onNext: () => void
  onRetryNext: () => void
  onPrevious?: () => void
  onExit: () => void
}

function difficultyLabel(value?: number): string {
  return ['入门', '基础', '进阶', '挑战', '专家'][Math.max(0, Math.min(4, (value ?? 3) - 1))]
}

function generationLabel(method?: string | null): string | null {
  if (!method) return null
  if (method === 'deepseek' || method === 'ai_generated') return 'AI 动态生成'
  if (method === 'resource_generation') return '分阶资源题'
  if (method === 'deterministic_fallback') return '本地兜底题'
  return method
}

export default function GuidanceQuestion({
  question,
  selectedAnswers,
  showResult,
  isSubmitting,
  isPreparingNext,
  submitResult,
  answerError,
  nextQuestionError,
  currentGenerationMethod,
  sessionDifficulty,
  questionCount,
  hasNext,
  mode = 'adaptive',
  hasPrevious = false,
  batchCanSubmit = false,
  onSelect,
  onSubmit,
  onNext,
  onRetryNext,
  onPrevious,
  onExit,
}: GuidanceQuestionProps) {
  const isMultiSelect = question.type === 'multiple'
  const isCorrect = submitResult?.isCorrect ?? false
  const sourceLabel = generationLabel(question.generationMethod ?? currentGenerationMethod)
  return (
    <Card padding="none">
      <div className="border-b border-border p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Badge variant="default" className="gap-1">
            <Layers className="h-3 w-3" />
            {isMultiSelect ? '多选题' : '单选题'}
          </Badge>
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-lg bg-bg-secondary px-2 py-1 text-xs text-text-tertiary">
              {question.topic} · {sessionDifficulty ? `固定${difficultyLabel(sessionDifficulty)}` : difficultyLabel(question.difficulty)}
            </span>
            {sourceLabel && <Badge variant={question.generationMethod === 'deterministic_fallback' ? 'warning' : 'info'} size="sm">题目来源：{sourceLabel}</Badge>}
          </div>
        </div>
        <h3 className="mt-3 text-base font-medium leading-relaxed text-text-primary">{question.question}</h3>
        {question.generationMethod === 'deterministic_fallback' && (
          <p className="mt-2 text-xs text-text-tertiary">当前题目由本地兜底策略生成；补充领域知识库后可获得更强的主题针对性。</p>
        )}
      </div>

      <div className="space-y-3 p-5">
        {question.options.map((option, index) => {
          const selected = selectedAnswers.includes(index)
          const correctSelection = showResult && selected && isCorrect
          const wrongSelection = showResult && selected && !correctSelection
          return (
            <button
              key={`${question.id}-${index}`}
              type="button"
              aria-pressed={selected}
              onClick={() => onSelect(index)}
              disabled={showResult || isSubmitting}
              className={`w-full rounded-xl border p-4 text-left transition-all ${
                correctSelection
                  ? 'border-success/40 bg-success/5'
                  : wrongSelection
                  ? 'border-warning/30 bg-warning-light/30'
                  : selected
                  ? 'border-primary/40 bg-primary/5'
                  : 'border-border/60 bg-bg-secondary/30 hover:border-primary/30'
              }`}
            >
              <span className="flex items-center gap-3">
                <span className={`flex h-7 w-7 items-center justify-center rounded-lg text-sm font-medium ${
                  correctSelection ? 'bg-success text-white' : wrongSelection ? 'bg-warning text-white' : selected ? 'bg-primary text-white' : 'bg-bg-secondary text-text-tertiary'
                }`}>
                  {correctSelection ? <CheckCircle2 className="h-4 w-4" /> : wrongSelection ? <XCircle className="h-4 w-4" /> : String.fromCharCode(65 + index)}
                </span>
                <span className="flex-1 text-sm text-text-primary">{option}</span>
              </span>
            </button>
          )
        })}
      </div>

      {showResult && submitResult && (
        <div className="mx-5 mb-5 rounded-xl border border-border/50 bg-bg-secondary/50 p-4" role="status">
          <p className={`text-sm font-medium ${isCorrect ? 'text-success' : 'text-text-primary'}`}>
            {isCorrect ? '判定结果：回答正确' : '判定结果：回答错误'}
          </p>
          <p className="mt-1 text-xs text-text-secondary">
            {sessionDifficulty !== undefined
              ? `本轮固定${difficultyLabel(sessionDifficulty)}，继续完成剩余题目`
              : isMultiSelect
              ? '多选题需要选择所有正确答案'
              : isCorrect
              ? '反馈已生成，可继续查看主要建议'
              : '反馈已生成，可先查看通俗纠错'}
          </p>
        </div>
      )}

      {answerError && <p role="alert" className="mx-5 mb-5 text-sm text-error">{answerError}</p>}
      {nextQuestionError && <p role="alert" className="mx-5 mb-5 text-sm text-error">{nextQuestionError}</p>}

      <div className="flex flex-wrap items-center justify-between gap-3 p-5 pt-0">
        <span className="text-xs text-text-tertiary">共 {questionCount} 题</span>
        <div className={`${mode === 'batch' ? 'w-full justify-between sm:w-auto' : 'ml-auto'} flex items-center gap-2`}>
          {mode === 'batch' ? (
            <>
              <Button variant="outline" size="sm" onClick={onPrevious} disabled={!hasPrevious || isSubmitting}>
                上一题
              </Button>
              {hasNext ? (
                <Button variant="primary" size="sm" onClick={onNext} disabled={isSubmitting}>
                  下一题 <ArrowRight className="h-4 w-4" />
                </Button>
              ) : (
                <Button variant="primary" size="sm" onClick={onSubmit} disabled={!batchCanSubmit || isSubmitting} loading={isSubmitting}>
                  提交整卷
                </Button>
              )}
            </>
          ) : !showResult ? (
            <Button variant="primary" onClick={onSubmit} disabled={selectedAnswers.length === 0 || isSubmitting} loading={isSubmitting}>
              提交答案
            </Button>
          ) : hasNext ? (
            <Button variant="primary" onClick={onNext}>
              下一题 <ArrowRight className="h-4 w-4" />
            </Button>
          ) : isPreparingNext || nextQuestionError ? (
            <Button variant="primary" onClick={onRetryNext} loading={isPreparingNext} disabled={isPreparingNext}>
              {nextQuestionError ? '重试下一题' : '下一题准备中'}
            </Button>
          ) : (
            <Button variant="primary" onClick={onExit}>回到导学配置</Button>
          )}
        </div>
      </div>
    </Card>
  )
}
