import { TextareaHTMLAttributes, forwardRef, useId } from 'react'
import { clsx } from 'clsx'

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string
  error?: string
}

const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ label, error, id, className, rows = 4, ...props }, ref) => {
    const generatedId = useId()
    const textareaId = id ?? generatedId
    return (
      <div className="space-y-1.5">
        {label && (
          <label htmlFor={textareaId} className="block text-sm font-medium text-text-primary">
            {label}
          </label>
        )}
        <textarea
          ref={ref}
          id={textareaId}
          rows={rows}
          className={clsx(
            'w-full px-3 py-2 bg-bg-secondary border border-border rounded-input',
            'text-text-primary placeholder:text-text-tertiary resize-y',
            'focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary',
            'transition-all duration-250',
            error && 'border-error focus:ring-error/20 focus:border-error',
            className
          )}
          aria-invalid={error ? true : undefined}
          {...props}
        />
        {error && (
          <p className="text-xs text-error" role="alert">
            {error}
          </p>
        )}
      </div>
    )
  }
)

Textarea.displayName = 'Textarea'

export default Textarea
