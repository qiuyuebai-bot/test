import { ReactNode, useEffect, useState } from 'react'
import { clsx } from 'clsx'

interface PageTransitionProps {
  children: ReactNode
  className?: string
}

export default function PageTransition({ children, className }: PageTransitionProps) {
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    const timer = requestAnimationFrame(() => setIsVisible(true))
    return () => cancelAnimationFrame(timer)
  }, [])

  return (
    <div
      className={clsx(
        'transition-all duration-200 ease-out',
        isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2',
        className
      )}
    >
      {children}
    </div>
  )
}