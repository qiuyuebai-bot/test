import { useEffect, useState } from 'react'
import { clsx } from 'clsx'
import { CheckCircle2, AlertCircle, XCircle, Info, X } from 'lucide-react'
import { ToastItem, ToastType, removeToast, subscribeToast } from './toastStore'

const iconMap: Record<ToastType, typeof CheckCircle2> = {
  success: CheckCircle2,
  error: XCircle,
  warning: AlertCircle,
  info: Info,
}

const colorMap: Record<ToastType, { bg: string; border: string; text: string; icon: string }> = {
  success: { bg: 'bg-success-light', border: 'border-success/30', text: 'text-success-dark', icon: 'text-success' },
  error: { bg: 'bg-error-light', border: 'border-error/30', text: 'text-error-dark', icon: 'text-error' },
  warning: { bg: 'bg-warning-light', border: 'border-warning/30', text: 'text-warning-dark', icon: 'text-warning' },
  info: { bg: 'bg-info-light', border: 'border-info/30', text: 'text-info-dark', icon: 'text-info' },
}

export default function ToastContainer() {
  const [items, setItems] = useState<ToastItem[]>([])

  useEffect(() => {
    const unsubscribe = subscribeToast((t) => setItems(t))
    return unsubscribe
  }, [])

  if (items.length === 0) return null

  return (
    <div
      role="status"
      aria-live="polite"
      aria-atomic="false"
      className="fixed bottom-6 right-6 z-50 flex flex-col-reverse gap-2 max-w-sm w-full pointer-events-none"
    >
      {items.map((item) => {
        const colors = colorMap[item.type]
        const Icon = iconMap[item.type]
        return (
          <div
            key={item.id}
            className={clsx(
              'pointer-events-auto rounded-xl border p-4 shadow-lg animate-slide-up',
              'bg-bg-card',
              colors.border,
              'transition-all duration-250'
            )}
          >
            <div className="flex items-start gap-3">
              <Icon className={clsx('w-5 h-5 flex-shrink-0 mt-0.5', colors.icon)} />
              <div className="flex-1 min-w-0">
                <p className={clsx('text-sm font-medium', colors.text)}>{item.message}</p>
                {item.description && (
                  <p className="text-xs text-text-secondary mt-1">{item.description}</p>
                )}
              </div>
              <button
                onClick={() => removeToast(item.id)}
                className="text-text-tertiary hover:text-text-primary transition-colors flex-shrink-0"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
        )
      })}
    </div>
  )
}
