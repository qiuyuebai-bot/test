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
  success: { bg: 'bg-emerald-50 dark:bg-emerald-500/10', border: 'border-emerald-200 dark:border-emerald-500/20', text: 'text-emerald-700 dark:text-emerald-400', icon: 'text-emerald-500' },
  error: { bg: 'bg-rose-50 dark:bg-rose-500/10', border: 'border-rose-200 dark:border-rose-500/20', text: 'text-rose-700 dark:text-rose-400', icon: 'text-rose-500' },
  warning: { bg: 'bg-amber-50 dark:bg-amber-500/10', border: 'border-amber-200 dark:border-amber-500/20', text: 'text-amber-700 dark:text-amber-400', icon: 'text-amber-500' },
  info: { bg: 'bg-sky-50 dark:bg-sky-500/10', border: 'border-sky-200 dark:border-sky-500/20', text: 'text-sky-700 dark:text-sky-400', icon: 'text-sky-500' },
}

export default function ToastContainer() {
  const [items, setItems] = useState<ToastItem[]>([])

  useEffect(() => {
    const unsubscribe = subscribeToast((t) => setItems(t))
    return unsubscribe
  }, [])

  if (items.length === 0) return null

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col-reverse gap-2 max-w-sm w-full pointer-events-none">
      {items.map((item) => {
        const colors = colorMap[item.type]
        const Icon = iconMap[item.type]
        return (
          <div
            key={item.id}
            className={clsx(
              'pointer-events-auto rounded-xl border p-4 shadow-lg animate-slide-up',
              'bg-bg-card dark:bg-gray-800',
              colors.border,
              'transition-all duration-300'
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
