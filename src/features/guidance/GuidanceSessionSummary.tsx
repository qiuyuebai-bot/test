import type { LearnerProfile, UserRole } from '@/types'
import Card from '@/components/Card'
import Button from '@/components/Button'
import LearnerContextBar from './LearnerContextBar'
import { Brain, LogOut } from 'lucide-react'

interface GuidanceSessionSummaryProps {
  learner: LearnerProfile
  learners: LearnerProfile[]
  role?: UserRole | string
  selectedLearnerId: number | null
  correctCount: number
  answeredCount: number
  sessionTotal: number
  progress: number
  disabled?: boolean
  onLearnerChange: (learner: LearnerProfile) => void
  onExit: () => void
}

export default function GuidanceSessionSummary({
  learner,
  learners,
  role,
  selectedLearnerId,
  correctCount,
  answeredCount,
  sessionTotal,
  progress,
  disabled,
  onLearnerChange,
  onExit,
}: GuidanceSessionSummaryProps) {
  return (
    <Card padding="md">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-primary/10"><Brain className="h-5 w-5 text-primary" /></div>
          <div className="min-w-0">
            <h2 className="text-lg font-semibold text-text-primary">动态自适应导学</h2>
            <div className="mt-1"><LearnerContextBar learner={learner} learners={learners} role={role} selectedLearnerId={selectedLearnerId} onLearnerChange={onLearnerChange} disabled={disabled} /></div>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <div className="text-center"><p className="metric-number text-xl font-semibold text-success">{correctCount}</p><p className="text-xs text-text-tertiary">正确数</p></div>
          <div className="h-10 w-px bg-border" />
          <div className="text-center"><p className="metric-number text-xl font-semibold text-text-primary">{answeredCount}/{sessionTotal}</p><p className="text-xs text-text-tertiary">当前进度</p></div>
          <div className="w-28"><div className="mb-1 flex items-center justify-between text-xs"><span className="text-text-tertiary">学习进度</span><span className="font-medium text-primary">{Math.round(progress)}%</span></div><div className="h-1.5 overflow-hidden rounded-full bg-bg-tertiary"><div className="h-full rounded-full bg-primary transition-all" style={{ width: `${progress}%` }} /></div></div>
          <Button variant="outline" size="sm" onClick={onExit} disabled={disabled}><LogOut className="h-4 w-4" />退出本轮</Button>
        </div>
      </div>
    </Card>
  )
}
