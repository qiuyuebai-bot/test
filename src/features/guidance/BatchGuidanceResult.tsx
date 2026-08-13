import type { TutoringQuestion } from '@/api/core'
import Button from '@/components/Button'
import Card from '@/components/Card'
import type { BatchSubmitResult } from './types'
import { ArrowLeft, CheckCircle2, RotateCcw, Target, XCircle } from 'lucide-react'

interface BatchGuidanceResultProps {
  result: BatchSubmitResult
  questions: TutoringQuestion[]
  onBack: () => void
  onRetry: () => void
  onWeakDimension: (dimension: string) => void
}

function answerLabels(values: string[]): string {
  return values.length > 0 ? values.join(', ') : '未作答'
}

export default function BatchGuidanceResult({
  result,
  questions,
  onBack,
  onRetry,
  onWeakDimension,
}: BatchGuidanceResultProps) {
  const weakestDimension = [...result.dimensionSummary].sort((left, right) => left.score - right.score)[0]
  const questionById = new Map(questions.map((question) => [question.id, question]))

  return (
    <div className="space-y-4">
      <Card padding="md">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-medium text-text-tertiary">整卷练习结果</p>
            <h2 className="mt-1 text-2xl font-semibold text-text-primary">本轮完成</h2>
          </div>
          <div className="text-right">
            <p className="metric-number text-3xl font-semibold text-primary">{Math.round(result.score)}</p>
            <p className="text-xs text-text-tertiary">总分 / 100</p>
          </div>
        </div>
        <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded-lg bg-bg-secondary/50 p-3"><p className="text-xs text-text-tertiary">题目数</p><p className="mt-1 text-lg font-semibold text-text-primary">{result.total}</p></div>
          <div className="rounded-lg bg-success/5 p-3"><p className="text-xs text-text-tertiary">答对</p><p className="mt-1 text-lg font-semibold text-success">{result.correctCount}</p></div>
          <div className="rounded-lg bg-error/5 p-3"><p className="text-xs text-text-tertiary">答错</p><p className="mt-1 text-lg font-semibold text-error">{result.total - result.correctCount}</p></div>
          <div className="rounded-lg bg-primary/5 p-3"><p className="text-xs text-text-tertiary">正确率</p><p className="mt-1 text-lg font-semibold text-primary">{result.total ? Math.round((result.correctCount / result.total) * 100) : 0}%</p></div>
        </div>
      </Card>

      <Card padding="md">
        <div className="flex items-center gap-2">
          <Target className="h-4 w-4 text-primary" />
          <h3 className="text-sm font-semibold text-text-primary">能力维度汇总</h3>
        </div>
        {result.dimensionSummary.length > 0 ? (
          <div className="mt-4 divide-y divide-border/60">
            {result.dimensionSummary.map((item) => (
              <div key={item.dimension} className="flex flex-wrap items-center justify-between gap-3 py-3 first:pt-0 last:pb-0">
                <span className="text-sm text-text-primary">{item.dimension}</span>
                <span className="text-xs text-text-tertiary">{item.correctCount}/{item.answeredCount} 正确，{Math.round(item.score)}%</span>
              </div>
            ))}
          </div>
        ) : <p className="mt-3 text-sm text-text-secondary">本轮题目暂无能力维度标记。</p>}
      </Card>

      <Card padding="md">
        <h3 className="text-sm font-semibold text-text-primary">逐题解析</h3>
        <div className="mt-4 space-y-3">
          {result.questions.map((item, index) => {
            const question = questionById.get(item.questionId)
            return (
              <details key={item.questionId} className="rounded-lg border border-border/70 bg-bg-secondary/20 p-4" open={index === 0}>
                <summary className="flex cursor-pointer list-none items-start gap-3">
                  {item.isCorrect ? <CheckCircle2 className="mt-0.5 h-4 w-4 flex-shrink-0 text-success" /> : <XCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-error" />}
                  <span className="min-w-0 flex-1 text-sm font-medium text-text-primary">第 {index + 1} 题：{question?.question ?? item.questionId}</span>
                  <span className="text-xs text-text-tertiary">{Math.round(item.score)} 分</span>
                </summary>
                <div className="mt-4 space-y-2 border-t border-border/60 pt-3 text-sm">
                  <p className="text-text-secondary">我的答案：<span className="font-medium text-text-primary">{answerLabels(item.userAnswer)}</span></p>
                  <p className="text-text-secondary">正确答案：<span className="font-medium text-text-primary">{answerLabels(item.correctAnswer)}</span></p>
                  {item.knowledgePoints.length > 0 && <p className="text-text-secondary">知识点：{item.knowledgePoints.join('、')}</p>}
                  {item.explanation && <p className="leading-relaxed text-text-secondary">解析：{item.explanation}</p>}
                </div>
              </details>
            )
          })}
        </div>
      </Card>

      <div className="flex flex-wrap items-center gap-2">
        <Button variant="outline" onClick={onBack}><ArrowLeft className="h-4 w-4" />返回导学首页</Button>
        <Button variant="primary" onClick={onRetry}><RotateCcw className="h-4 w-4" />重新练习</Button>
        {weakestDimension && <Button variant="ghost" onClick={() => onWeakDimension(weakestDimension.dimension)}>练习薄弱维度</Button>}
      </div>
    </div>
  )
}
