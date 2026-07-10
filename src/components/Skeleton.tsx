import { cn } from '../lib/cn'
import type { CSSProperties } from 'react'

interface SkeletonProps {
  className?: string
  style?: CSSProperties
}

/** 基础骨架元素，带 shimmer 动画 */
export function Skeleton({ className, style }: SkeletonProps) {
  return (
    <div
      style={style}
      className={cn(
        'animate-shimmer rounded-md bg-gradient-to-r from-gray-200 via-gray-100 to-gray-200 dark:from-gray-700 dark:via-gray-600 dark:to-gray-700 bg-[length:200%_100%]',
        className
      )}
    />
  )
}

/** 卡片骨架（用于 Dashboard、LearnerProfile 等） */
export function CardSkeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="rounded-lg border border-border p-6 space-y-3">
      <Skeleton className="h-4 w-1/3" />
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} className="h-3 w-full" />
      ))}
      <Skeleton className="h-3 w-2/3" />
    </div>
  )
}

/** 表格骨架（用于 LearnerProfile、EnterpriseTraining 等） */
export function TableSkeleton({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div className="rounded-lg border border-border overflow-hidden">
      <div className="border-b border-border bg-bg-tertiary p-4">
        <div className="flex gap-4">
          {Array.from({ length: cols }).map((_, i) => (
            <Skeleton key={i} className="h-4 flex-1" />
          ))}
        </div>
      </div>
      {Array.from({ length: rows }).map((_, rowIdx) => (
        <div
          key={rowIdx}
          className={cn(
            'border-b border-border p-4',
            rowIdx === rows - 1 && 'border-b-0'
          )}
        >
          <div className="flex gap-4">
            {Array.from({ length: cols }).map((_, i) => (
              <Skeleton key={i} className="h-4 flex-1" />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

/** 图表骨架（用于 MetricsDashboard、LearningReport 等） */
export function ChartSkeleton({ height = 300 }: { height?: number }) {
  return (
    <div className="rounded-lg border border-border p-6">
      <Skeleton className="h-5 w-1/4 mb-4" />
      <div className="flex items-end justify-between gap-2" style={{ height }}>
        {Array.from({ length: 7 }).map((_, i) => (
          <Skeleton
            key={i}
            className="flex-1"
            // 随机高度，模拟柱状图
            style={{ height: `${30 + Math.random() * 70}%` }}
          />
        ))}
      </div>
    </div>
  )
}

/** 页面骨架（完整页面占位） */
export function PageSkeleton({ type = 'default' }: { type?: 'default' | 'table' | 'dashboard' }) {
  if (type === 'table') {
    return (
      <div className="space-y-4 p-6">
        <div className="flex justify-between items-center">
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-9 w-24 rounded-md" />
        </div>
        <TableSkeleton />
      </div>
    )
  }

  if (type === 'dashboard') {
    return (
      <div className="space-y-6 p-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
        </div>
        <ChartSkeleton />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <CardSkeleton />
          <CardSkeleton />
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4 p-6">
      <Skeleton className="h-8 w-1/4" />
      <CardSkeleton />
      <CardSkeleton />
    </div>
  )
}
