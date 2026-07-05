import { clsx } from 'clsx'
import { X } from 'lucide-react'
import { ReactNode } from 'react'

interface ModalProps {
  isOpen: boolean
  onClose: () => void
  children: ReactNode
  maxWidth?: string
  className?: string
}

export default function Modal({ isOpen, onClose, children, maxWidth = 'max-w-lg', className }: ModalProps) {
  if (!isOpen) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/30 backdrop-blur-sm animate-fade-in">
      <div
        className={clsx(
          'relative w-full bg-bg-card rounded-2xl shadow-xl overflow-hidden animate-scale-in',
          maxWidth,
          className
        )}
      >
        <button
          onClick={onClose}
          className="absolute top-5 right-5 p-1 hover:bg-bg-secondary rounded-lg transition-colors z-10"
        >
          <X className="w-5 h-5 text-text-secondary" />
        </button>
        {children}
      </div>
    </div>
  )
}
