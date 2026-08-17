import { clsx } from 'clsx'
import { X } from 'lucide-react'
import { ReactNode, useEffect, useId, useRef } from 'react'
import { createPortal } from 'react-dom'

interface ModalProps {
  isOpen: boolean
  onClose: () => void
  children: ReactNode
  maxWidth?: string
  className?: string
  header?: ReactNode
  footer?: ReactNode
}

export default function Modal({
  isOpen,
  onClose,
  children,
  maxWidth = 'max-w-lg',
  className,
  header,
  footer,
}: ModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null)
  const dialogTitleId = useId()

  useEffect(() => {
    if (!isOpen) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation()
        onClose()
        return
      }
      if (e.key === 'Tab' && dialogRef.current) {
        const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        )
        if (focusable.length === 0) {
          dialogRef.current.focus()
          return
        }
        const first = focusable[0]
        const last = focusable[focusable.length - 1]
        if (e.shiftKey) {
          if (document.activeElement === first || !dialogRef.current.contains(document.activeElement)) {
            e.preventDefault()
            last.focus()
          }
        } else {
          if (document.activeElement === last || !dialogRef.current.contains(document.activeElement)) {
            e.preventDefault()
            first.focus()
          }
        }
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    const t = window.setTimeout(() => {
      dialogRef.current?.focus()
    }, 0)

    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      window.clearTimeout(t)
    }
  }, [isOpen, onClose])

  useEffect(() => {
    if (!isOpen) return

    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    return () => {
      document.body.style.overflow = previousOverflow
    }
  }, [isOpen])

  if (!isOpen) return null

  return createPortal(
    <div className="fixed inset-0 z-50 h-[100dvh] overflow-y-auto overscroll-contain bg-black/30 backdrop-blur-sm animate-fade-in">
      <div className="flex min-h-full items-center justify-center p-4 sm:p-6">
        <div
          ref={dialogRef}
          role="dialog"
          aria-modal="true"
          aria-labelledby={dialogTitleId}
          tabIndex={-1}
          className={clsx(
            'relative flex min-h-0 w-full flex-col overflow-hidden rounded-2xl bg-bg-card shadow-modal outline-none animate-scale-in',
            'max-h-[calc(100dvh-2rem)] sm:max-h-[calc(100dvh-3rem)]',
            maxWidth,
          )}
        >
          <h2 id={dialogTitleId} className="sr-only">
            对话框
          </h2>
          {header && (
            <div className="shrink-0 border-b border-border bg-bg-card px-6 py-4 pr-16">
              {header}
            </div>
          )}
          <button
            type="button"
            onClick={onClose}
            aria-label="关闭对话框"
            className="absolute right-4 top-4 z-20 inline-flex h-8 w-8 items-center justify-center rounded-lg text-text-secondary transition-colors hover:bg-bg-secondary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
          >
            <X className="h-5 w-5" />
          </button>
          <div className={clsx('min-h-0 flex-1 overflow-y-auto', className)}>
            {children}
          </div>
          {footer && (
            <div className="shrink-0 border-t border-border bg-bg-card">
              {footer}
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body,
  )
}
