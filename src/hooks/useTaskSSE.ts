import { useEffect, useRef, useState, useCallback } from 'react'
import { createEventSource, http } from '../lib/request'

interface SSEEvent {
  event: string
  data: unknown
  timestamp: number
}

interface UseTaskSSEOptions {
  onEvent?: (event: SSEEvent) => void
  onComplete?: (data: unknown) => void
  onError?: (error: Event) => void
  enabled?: boolean
}

interface UseTaskSSEReturn {
  events: SSEEvent[]
  currentStage: string | null
  progress: number
  isConnected: boolean
  isCompleted: boolean
  isFailed: boolean
  error: string | null
  lastEvent: SSEEvent | null
}

export function useTaskSSE(
  taskId: number | null | undefined,
  options: UseTaskSSEOptions = {},
): UseTaskSSEReturn {
  const { onEvent, onComplete, onError, enabled = true } = options

  const [events, setEvents] = useState<SSEEvent[]>([])
  const [currentStage, setCurrentStage] = useState<string | null>(null)
  const [progress, setProgress] = useState(0)
  const [isConnected, setIsConnected] = useState(false)
  const [isCompleted, setIsCompleted] = useState(false)
  const [isFailed, setIsFailed] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastEvent, setLastEvent] = useState<SSEEvent | null>(null)

  const esRef = useRef<EventSource | null>(null)
  const callbacksRef = useRef({ onEvent, onComplete, onError })
  callbacksRef.current = { onEvent, onComplete, onError }

  const cleanup = useCallback(() => {
    if (esRef.current) {
      esRef.current.close()
      esRef.current = null
    }
    setIsConnected(false)
  }, [])

  useEffect(() => {
    if (!taskId || !enabled) {
      cleanup()
      return
    }

    cleanup()
    let cancelled = false
    let es: EventSource | null = null

    const handleOpen = () => {
      setIsConnected(true)
      setError(null)
    }

    const handleMessage = (e: MessageEvent) => {
      if (e.data === '[DONE]') {
        es?.close()
        setIsConnected(false)
        return
      }

      try {
        const parsed = JSON.parse(e.data)
        const eventObj: SSEEvent = {
          event: parsed.event || 'message',
          data: parsed.data || parsed,
          timestamp: Date.now(),
        }

        setLastEvent(eventObj)
        setEvents((prev) => [...prev.slice(-50), eventObj])
        callbacksRef.current.onEvent?.(eventObj)

        if (parsed.data) {
          const d = parsed.data
          if (typeof d.stage === 'string') {
            setCurrentStage(d.stage)
          }
          if (typeof d.progress === 'number') {
            setProgress(Math.min(100, Math.max(0, d.progress)))
          }
        }

        if (eventObj.event === 'task_completed') {
          setIsCompleted(true)
          setProgress(100)
          callbacksRef.current.onComplete?.(eventObj.data)
        } else if (eventObj.event === 'task_failed') {
          setIsFailed(true)
          const errData = eventObj.data as { error?: string }
          setError(errData?.error || '任务执行失败')
        }
      } catch {
        // ignore parse errors
      }
    }

    const handleError = (e: Event) => {
      setIsConnected(false)
      setError('连接中断')
      callbacksRef.current.onError?.(e)
    }

    http.post<{ ticket: string }>(`/agent/tasks/${taskId}/stream-ticket`)
      .then((res) => {
        if (cancelled) return
        const ticketStr = (res as { ticket?: string })?.ticket
        if (!ticketStr) {
          setError('获取SSE票据失败')
          return
        }
        es = createEventSource(`/agent/tasks/${taskId}/events`, { ticket: ticketStr })
        esRef.current = es
        es.addEventListener('open', handleOpen)
        es.addEventListener('message', handleMessage)
        es.addEventListener('error', handleError)
      })
      .catch(() => {
        if (!cancelled) setError('获取SSE票据失败')
      })

    return () => {
      cancelled = true
      if (es) {
        es.removeEventListener('open', handleOpen)
        es.removeEventListener('message', handleMessage)
        es.removeEventListener('error', handleError)
        es.close()
      }
      esRef.current = null
      setIsConnected(false)
    }
  }, [taskId, enabled, cleanup])

  return {
    events,
    currentStage,
    progress,
    isConnected,
    isCompleted,
    isFailed,
    error,
    lastEvent,
  }
}
