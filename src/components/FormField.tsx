import { ReactNode } from 'react'
import { clsx } from 'clsx'

interface FormFieldProps {
  label?: string
  error?: string
  required?: boolean
  description?: string
  children: ReactNode
  className?: string
}

export function FormField({ label, error, required, description, children, className }: FormFieldProps) {
  return (
    <div className={clsx('space-y-1.5', className)}>
      {label && (
        <label className="block text-sm font-medium text-text-primary">
          {label}
          {required && <span className="text-error ml-1">*</span>}
        </label>
      )}
      {description && (
        <p className="text-xs text-text-tertiary">{description}</p>
      )}
      {children}
      {error && (
        <p className="text-xs text-error flex items-center gap-1">
          {error}
        </p>
      )}
    </div>
  )
}

interface FormSectionProps {
  title?: string
  description?: string
  children: ReactNode
  className?: string
}

export function FormSection({ title, description, children, className }: FormSectionProps) {
  return (
    <div className={clsx('space-y-4', className)}>
      {(title || description) && (
        <div className="space-y-1">
          {title && <h3 className="text-base font-medium text-text-primary">{title}</h3>}
          {description && <p className="text-sm text-text-secondary">{description}</p>}
        </div>
      )}
      <div className="space-y-4">
        {children}
      </div>
    </div>
  )
}

interface FormActionsProps {
  children: ReactNode
  className?: string
  align?: 'left' | 'center' | 'right'
}

export function FormActions({ children, className, align = 'right' }: FormActionsProps) {
  const alignStyles = {
    left: 'justify-start',
    center: 'justify-center',
    right: 'justify-end',
  }

  return (
    <div className={clsx('flex items-center gap-3 pt-4', alignStyles[align], className)}>
      {children}
    </div>
  )
}
