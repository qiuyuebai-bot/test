export type ToastType = 'success' | 'error' | 'warning' | 'info'

export interface ToastItem {
  id: string
  type: ToastType
  message: string
  description?: string
  duration?: number
}

let toastListeners: ((toasts: ToastItem[]) => void)[] = []
let toasts: ToastItem[] = []
const toastTimers = new Map<string, ReturnType<typeof setTimeout>>()

function emit() {
  toastListeners.forEach((l) => l([...toasts]))
}

function addToast(toast: Omit<ToastItem, 'id'>) {
  const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2)}`
  toasts = [...toasts, { ...toast, id }]
  emit()
  const duration = toast.duration ?? 3000
  if (duration > 0) {
    const timer = setTimeout(() => removeToast(id), duration)
    toastTimers.set(id, timer)
  }
}

export function removeToast(id: string) {
  const timer = toastTimers.get(id)
  if (timer) {
    clearTimeout(timer)
    toastTimers.delete(id)
  }
  toasts = toasts.filter((t) => t.id !== id)
  emit()
}

export function subscribeToast(listener: (toasts: ToastItem[]) => void) {
  toastListeners = [...toastListeners, listener]
  return () => {
    toastListeners = toastListeners.filter((h) => h !== listener)
  }
}

export const toast = {
  success: (message: string, description?: string) => addToast({ type: 'success', message, description }),
  error: (message: string, description?: string) => addToast({ type: 'error', message, description, duration: 5000 }),
  warning: (message: string, description?: string) => addToast({ type: 'warning', message, description, duration: 4000 }),
  info: (message: string, description?: string) => addToast({ type: 'info', message, description }),
}
