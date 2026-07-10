import { clsx } from 'clsx'
import { SelectHTMLAttributes, forwardRef, useId } from 'react'
import { ChevronDown } from 'lucide-react'

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string
  error?: string
  options: { value: string; label: string }[]
}

const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, error, options, id, className, ...props }, ref) => {
    const generatedId = useId()
    const selectId = id ?? generatedId
    return (
      <div className="space-y-1.5">
        {label && (
          <label htmlFor={selectId} className="block text-sm font-medium text-text-primary">
            {label}
          </label>
        )}
        <div className="relative">
          <select
            ref={ref}
            id={selectId}
            className={clsx(
              'w-full h-10 px-3 pr-10 bg-bg-secondary border border-border rounded-input appearance-none',
              'text-text-primary',
              'focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary',
              'transition-all duration-250',
              error && 'border-error focus:ring-error/20 focus:border-error',
              className
            )}
            aria-invalid={error ? true : undefined}
            {...props}
          >
            {options.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-tertiary pointer-events-none" />
        </div>
        {error && (
          <p className="text-xs text-error" role="alert">
            {error}
          </p>
        )}
      </div>
    )
  }
)

Select.displayName = 'Select'

export default Select
