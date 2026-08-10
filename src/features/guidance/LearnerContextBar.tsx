import type { LearnerProfile, UserRole } from '@/types'
import { UserRound } from 'lucide-react'

interface LearnerContextBarProps {
  learner: LearnerProfile | null | undefined
  learners?: LearnerProfile[]
  role?: UserRole | string
  selectedLearnerId?: number | null
  onLearnerChange?: (learner: LearnerProfile) => void
  disabled?: boolean
}

export default function LearnerContextBar({
  learner,
  learners = [],
  role,
  selectedLearnerId,
  onLearnerChange,
  disabled = false,
}: LearnerContextBarProps) {
  const canSwitchLearner = role === 'admin' || role === 'teacher'
  if (!learner && learners.length === 0) return null

  if (!canSwitchLearner || !onLearnerChange) {
    return (
      <div className="flex items-center gap-2 text-sm text-text-secondary" aria-label="当前学习者画像">
        <UserRound className="h-4 w-4 text-primary" />
        <span>{learner?.realName ?? '当前学习者'}</span>
        {learner?.targetPosition && <span className="text-text-tertiary">· {learner.targetPosition}</span>}
      </div>
    )
  }

  return (
    <label className="flex min-w-0 items-center gap-2 text-sm text-text-secondary">
      <UserRound className="h-4 w-4 flex-shrink-0 text-primary" />
      <span className="sr-only">本轮学习者画像</span>
      <select
        aria-label="本轮学习者画像"
        value={selectedLearnerId ?? learner?.id ?? ''}
        onChange={(event) => {
          const next = learners.find((item) => item.id === Number(event.target.value))
          if (next) onLearnerChange(next)
        }}
        disabled={disabled}
        className="h-9 min-w-0 max-w-[220px] rounded-input border border-border bg-bg-card px-2 text-sm text-text-primary focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
      >
        {learners.map((item) => (
          <option key={item.id} value={item.id}>
            {item.realName} · {item.major || item.targetIndustry || '未填写方向'}
          </option>
        ))}
      </select>
    </label>
  )
}
