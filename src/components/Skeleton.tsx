import { clsx } from 'clsx'

interface SkeletonProps {
  className?: string
  variant?: 'text' | 'card' | 'circle' | 'rect'
  count?: number
}

export default function Skeleton({ className, variant = 'text', count = 1 }: SkeletonProps) {
  const base = 'animate-shimmer bg-gradient-to-r from-bg-secondary via-bg-secondary/50 to-bg-secondary bg-[length:200%_100%] rounded'

  const variantStyles = {
    text: 'h-4 w-full rounded',
    card: 'h-40 w-full rounded-xl',
    circle: 'h-12 w-12 rounded-full',
    rect: 'h-20 w-full rounded-lg',
  }

  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className={clsx(base, variantStyles[variant], className)}
          style={{ animationDelay: `${i * 0.1}s` }}
        />
      ))}
    </>
  )
}

// 预设骨架屏组合
export function PageSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="space-y-4 p-6">
      <Skeleton variant="text" className="h-7 w-48" />
      <Skeleton variant="text" className="h-4 w-72" />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6">
        <Skeleton variant="card" />
        <Skeleton variant="card" />
        <Skeleton variant="card" />
      </div>
      <Skeleton variant="rect" className="h-64 mt-4" />
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-4">
          <Skeleton variant="circle" className="h-10 w-10" />
          <div className="flex-1 space-y-2">
            <Skeleton variant="text" className="h-4 w-3/4" />
            <Skeleton variant="text" className="h-3 w-1/2" />
          </div>
        </div>
      ))}
    </div>
  )
}

export function CardSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="p-6 rounded-xl border border-border bg-bg-card space-y-3">
          <Skeleton variant="text" className="h-5 w-3/4" />
          <Skeleton variant="text" className="h-4 w-full" />
          <Skeleton variant="text" className="h-4 w-5/6" />
          <div className="flex gap-2 pt-2">
            <Skeleton variant="text" className="h-6 w-16 rounded-full" />
            <Skeleton variant="text" className="h-6 w-20 rounded-full" />
          </div>
        </div>
      ))}
    </div>
  )
}