import { clsx } from 'clsx'
import { ButtonHTMLAttributes, ReactNode } from 'react'
import { Loader2 } from 'lucide-react'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost'
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
  children: ReactNode
}

export default function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled,
  className,
  children,
  ...props
}: ButtonProps) {
  const variantStyles = {
    primary: 'bg-primary text-white hover:bg-primary-hover active:bg-primary-active disabled:bg-gray-300 dark:disabled:bg-gray-600',
    secondary: 'bg-secondary text-white hover:bg-secondary-hover disabled:bg-gray-300 dark:disabled:bg-gray-600',
    outline: 'border border-border text-text-primary hover:bg-gray-50 dark:hover:bg-gray-800 disabled:border-border disabled:text-text-tertiary',
    ghost: 'text-text-secondary hover:bg-gray-50 dark:hover:bg-gray-800 hover:text-text-primary disabled:text-text-tertiary',
  }

  const sizeStyles = {
    sm: 'h-8 px-3 text-sm',
    md: 'h-10 px-4 text-sm',
    lg: 'h-12 px-6 text-base',
  }

  return (
    <button
      disabled={disabled || loading}
      className={clsx(
        'inline-flex items-center justify-center gap-2 font-medium rounded-button transition-all duration-200',
        'disabled:cursor-not-allowed',
        variantStyles[variant],
        sizeStyles[size],
        className
      )}
      {...props}
    >
      {loading && <Loader2 className="w-4 h-4 animate-spin" />}
      {children}
    </button>
  )
}