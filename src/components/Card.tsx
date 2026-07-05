import { clsx } from 'clsx'
import { ReactNode } from 'react'

interface CardProps {
  children: ReactNode
  className?: string
  padding?: 'none' | 'sm' | 'md' | 'lg'
  hover?: boolean
  onClick?: () => void
}

export default function Card({ children, className, padding = 'md', hover = false, onClick }: CardProps) {
  const paddingStyles = {
    none: '',
    sm: 'p-4',
    md: 'p-6',
    lg: 'p-8',
  }

  return (
    <div
      onClick={onClick}
      className={clsx(
        'bg-bg-card rounded-xl border border-border shadow-soft',
        paddingStyles[padding],
        hover && 'transition-shadow duration-200 hover:shadow-medium',
        onClick && 'cursor-pointer',
        className
      )}
    >
      {children}
    </div>
  )
}