import { Brain, Loader2 } from 'lucide-react'
import type { GuidancePhase } from './types'

interface GuidanceProcessingProps {
  phase: GuidancePhase
  isPreparingNext?: boolean
}

export default function GuidanceProcessing({ phase, isPreparingNext = false }: GuidanceProcessingProps) {
  const isGenerating = phase === 'generatingQuestion'
  const isSubmitting = phase === 'submitting'
  if (!isGenerating && !isSubmitting && !isPreparingNext) return null

  const message = isGenerating
    ? '正在准备导学题目…'
    : isSubmitting
    ? '正在判定答案并生成反馈…'
    : '下一题正在准备中，当前反馈不受影响'

  return (
    <div role="status" aria-label={message} className="flex items-center gap-3 rounded-lg border border-primary/15 bg-primary/5 px-4 py-3 text-sm text-text-secondary">
      <Loader2 className="h-4 w-4 animate-spin text-primary" />
      <span>{message}</span>
      <Brain className="ml-auto h-4 w-4 text-primary/70" />
    </div>
  )
}
