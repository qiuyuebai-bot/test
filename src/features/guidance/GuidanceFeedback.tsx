import Card from '@/components/Card'
import type { GeneratedContent, SubmitResult } from './types'
import { BookOpen, CheckCircle2, Lightbulb, Target } from 'lucide-react'

interface GuidanceFeedbackProps {
  questionTopic: string
  result: SubmitResult
}

function decisionKey(result: SubmitResult): string {
  return String(result.agentDecision?.decision ?? result.nextAction?.type ?? (result.isCorrect ? 'advance' : 'simplify')).toLowerCase()
}

function mainFeedback(result: SubmitResult, content: GeneratedContent | undefined): { title: string; body: string } {
  const decision = decisionKey(result)
  if (decision.includes('simplify')) {
    return {
      title: '通俗纠错',
      body: content?.simpleExplanation || '先拆开题目中的关键概念，再用一个小例子重新判断。',
    }
  }
  if (decision.includes('consolidate')) {
    return {
      title: '巩固建议',
      body: content?.simpleExplanation || content?.recommendation || '建议围绕本题知识点再完成一次迁移练习。',
    }
  }
  return {
    title: '知识扩展',
    body: content?.simpleExplanation || content?.recommendation || '回答正确，可以继续关注这个知识点在真实场景中的应用。',
  }
}

function ContentSections({ content, topic }: { content: GeneratedContent; topic: string }) {
  const sections = [
    content.keyPoints?.length ? { title: '核心要点', points: content.keyPoints } : null,
    content.practiceTips ? { title: '实践建议', body: content.practiceTips } : null,
    content.recommendation ? { title: '个性化建议', body: content.recommendation } : null,
  ].filter(Boolean) as Array<{ title: string; body?: string; points?: string[] }>
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <BookOpen className="h-4 w-4 text-primary" />
        <h4 className="font-semibold text-text-primary">{content.title || `${topic} - 主要讲解`}</h4>
      </div>
      {sections.map((section) => (
        <div key={section.title} className="space-y-1">
          <h5 className="text-sm font-medium text-text-primary">{section.title}</h5>
          {section.body && <p className="text-sm leading-relaxed text-text-secondary">{section.body}</p>}
          {section.points && (
            <ul className="space-y-1">
              {section.points.map((point) => <li key={point} className="flex items-start gap-2 text-sm text-text-secondary"><span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-primary/60" />{point}</li>)}
            </ul>
          )}
        </div>
      ))}
    </div>
  )
}

export default function GuidanceFeedback({ questionTopic, result }: GuidanceFeedbackProps) {
  const feedback = mainFeedback(result, result.generatedContent)
  const expansion = result.generatedContent?.knowledgeExpansion
  const decisionReason = result.agentDecision?.reason || result.nextAction?.description

  return (
    <div className="space-y-4">
      <Card padding="md" className="border-primary/15">
        <div className="flex items-start gap-3">
          <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-primary/10">
            {result.isCorrect ? <CheckCircle2 className="h-5 w-5 text-success" /> : <Lightbulb className="h-5 w-5 text-primary" />}
          </div>
          <div className="min-w-0 flex-1">
            <p className={`text-sm font-semibold ${result.isCorrect ? 'text-success' : 'text-text-primary'}`}>
              {result.isCorrect ? '判定结果：回答正确' : '判定结果：回答错误'} · {feedback.title}
            </p>
            <p className="mt-2 text-sm leading-relaxed text-text-secondary">{feedback.body}</p>
          </div>
        </div>
        {result.generatedContent && (
          <div className="mt-4 border-t border-border/60 pt-4">
            <p className="mb-3 text-xs font-medium text-text-tertiary">简化版通俗讲解</p>
            <ContentSections content={result.generatedContent} topic={questionTopic} />
          </div>
        )}
      </Card>

      {expansion && (
        <details className="rounded-xl border border-border bg-bg-card p-4">
          <summary role="button" className="flex cursor-pointer list-none items-center gap-2 text-sm font-medium text-text-primary">
            <Target className="h-4 w-4 text-warning" />
            知识点扩展学习
          </summary>
          <div className="mt-4 space-y-3">
            {expansion.overview && <p className="text-sm leading-relaxed text-text-secondary">{expansion.overview}</p>}
            {expansion.keyPoints?.length ? <ul className="space-y-1">{expansion.keyPoints.map((point) => <li key={point} className="text-sm text-text-secondary">{point}</li>)}</ul> : null}
            {expansion.application && <p className="text-sm leading-relaxed text-text-secondary">{expansion.application}</p>}
            {expansion.pitfalls?.length ? <p className="text-sm leading-relaxed text-text-secondary">常见边界：{expansion.pitfalls.join('；')}</p> : null}
          </div>
        </details>
      )}

      <details className="rounded-lg border border-border/70 bg-bg-secondary/30 px-4 py-3">
        <summary className="cursor-pointer text-xs font-medium text-text-primary">决策依据</summary>
        <p className="mt-2 text-sm leading-relaxed text-text-secondary">
          {decisionReason || (result.isCorrect ? '答题结果支持继续深化该知识点。' : '答题结果显示需要先补齐基础概念。')}
        </p>
      </details>
    </div>
  )
}
