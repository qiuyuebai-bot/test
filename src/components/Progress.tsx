import { clsx } from 'clsx'

interface ProgressProps {
  value: number
  max?: number
  size?: 'sm' | 'md' | 'lg'
  variant?: 'default' | 'success' | 'warning' | 'error'
  showLabel?: boolean
  className?: string
}

export default function Progress({
  value,
  max = 100,
  size = 'md',
  variant = 'default',
  showLabel = false,
  className,
}: ProgressProps) {
  const percentage = Math.min(Math.max((value / max) * 100, 0), 100)

  const sizeStyles = {
    sm: 'h-1',
    md: 'h-2',
    lg: 'h-3',
  }

  const variantStyles = {
    default: 'bg-primary',
    success: 'bg-success',
    warning: 'bg-warning',
    error: 'bg-error',
  }

  return (
    <div className={clsx('w-full', className)}>
      {showLabel && (
        <div className="flex justify-between mb-1.5">
          <span className="text-sm text-text-secondary">进度</span>
          <span className="text-sm font-medium text-text-primary">{Math.round(percentage)}%</span>
        </div>
      )}
      <div className={clsx('w-full bg-bg-tertiary rounded-full overflow-hidden', sizeStyles[size])}>
        <div
          className={clsx('h-full rounded-full transition-all duration-500', variantStyles[variant])}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  )
}