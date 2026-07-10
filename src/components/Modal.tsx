import { clsx } from 'clsx'
import { X } from 'lucide-react'
import { ReactNode, useEffect, useRef } from 'react'

interface ModalProps {
  isOpen: boolean
  onClose: () => void
  children: ReactNode
  maxWidth?: string
  className?: string
}

export default function Modal({ isOpen, onClose, children, maxWidth = 'max-w-lg', className }: ModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null)

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

  if (!isOpen) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/30 backdrop-blur-sm animate-fade-in">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        tabIndex={-1}
        className={clsx(
          'relative w-full bg-bg-card rounded-2xl shadow-modal overflow-hidden animate-scale-in outline-none',
          maxWidth,
          className
        )}
      >
        <h2 id="modal-title" className="sr-only">
          对话框
        </h2>
        <button
          onClick={onClose}
          aria-label="关闭对话框"
          className="absolute top-5 right-5 p-1 hover:bg-bg-secondary rounded-lg transition-colors z-10"
        >
          <X className="w-5 h-5 text-text-secondary" />
        </button>
        {children}
      </div>
    </div>
  )
}
