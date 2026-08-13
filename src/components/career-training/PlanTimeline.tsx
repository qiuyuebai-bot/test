import { CheckCircle, Circle, Clock } from 'lucide-react'
import type { PlanStage } from '@/types/training'

interface Props {
  stages: PlanStage[]
  completedStages: number
  onStageClick?: (stage: number) => void
}

export default function PlanTimeline({ stages, completedStages, onStageClick }: Props) {
  if (!stages.length) {
    return (
      <div className="flex items-center justify-center h-32 text-text-tertiary text-sm">
        暂无学习计划
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm">
        <span className="text-text-secondary">进度</span>
        <span className="text-primary font-medium">{completedStages} / {stages.length}</span>
      </div>
      <div className="relative pl-6">
        {/* 竖线 */}
        <div className="absolute left-2 top-2 bottom-2 w-0.5 bg-border" />
        {stages.map((s) => {
          const isCompleted = s.stage <= completedStages
          const isCurrent = s.stage === completedStages + 1
          return (
            <div
              key={s.stage}
              className={`relative pb-4 ${onStageClick ? 'cursor-pointer' : ''}`}
              onClick={() => onStageClick?.(s.stage)}
            >
              <div className="absolute -left-6 top-0">
                {isCompleted ? (
                  <CheckCircle className="w-5 h-5 text-success" />
                ) : isCurrent ? (
                  <Circle className="w-5 h-5 text-primary fill-primary-light" />
                ) : (
                  <Circle className="w-5 h-5 text-text-tertiary" />
                )}
              </div>
              <div className={`p-3 rounded-lg border ${isCurrent ? 'border-primary bg-primary-light' : 'border-border bg-bg-card'}`}>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-text-primary">阶段 {s.stage}：<span>{s.title}</span></span>
                  <span className="text-xs text-text-tertiary flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {s.estimated_hours}h
                  </span>
                </div>
                {s.description && (
                  <p className="text-xs text-text-secondary mt-1">{s.description}</p>
                )}
                <div className="text-xs text-text-tertiary mt-1">目标等级 L{s.target_level}</div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
