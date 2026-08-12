import type { TutoringQuestion } from '@/api/core'
import Card from '@/components/Card'
import { Check, Circle } from 'lucide-react'

interface BatchQuestionNavigatorProps {
  questions: TutoringQuestion[]
  currentQuestion: number
  answersByQuestionId: Record<string, number[]>
  disabled?: boolean
  onSelect: (index: number) => void
}

export default function BatchQuestionNavigator({
  questions,
  currentQuestion,
  answersByQuestionId,
  disabled = false,
  onSelect,
}: BatchQuestionNavigatorProps) {
  return (
    <Card padding="md">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-text-primary">题号导航</h3>
          <p className="mt-1 text-xs text-text-tertiary">已答题可随时修改</p>
        </div>
        <span className="text-xs text-text-tertiary">
          {questions.filter((question) => (answersByQuestionId[question.id] ?? []).length > 0).length}/{questions.length}
        </span>
      </div>
      <div className="mt-4 grid grid-cols-5 gap-2 sm:grid-cols-6 xl:grid-cols-5">
        {questions.map((question, index) => {
          const answered = (answersByQuestionId[question.id] ?? []).length > 0
          const current = index === currentQuestion
          return (
            <button
              key={question.id}
              type="button"
              aria-label={`第 ${index + 1} 题${answered ? '，已答' : '，未答'}`}
              aria-current={current ? 'step' : undefined}
              disabled={disabled}
              onClick={() => onSelect(index)}
              className={`flex aspect-square min-h-10 items-center justify-center gap-1 rounded-lg border text-sm font-semibold transition-colors ${
                current
                  ? 'border-primary bg-primary text-text-inverse'
                  : answered
                  ? 'border-success/40 bg-success/5 text-success hover:border-success/60'
                  : 'border-border bg-bg-secondary/30 text-text-tertiary hover:border-primary/40 hover:text-text-primary'
              }`}
            >
              {answered ? <Check className="h-3.5 w-3.5" /> : <Circle className="h-3.5 w-3.5" />}
              {index + 1}
            </button>
          )
        })}
      </div>
    </Card>
  )
}
