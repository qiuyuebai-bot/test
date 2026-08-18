import { useEffect, useRef, useState } from 'react'
import { buildUrl, getAccessToken } from '../lib/request'

interface SSEEvent {
  event: string
  data: unknown
  timestamp: number
}

interface UseTaskSSEOptions {
  onEvent?: (event: SSEEvent) => void
  onComplete?: (data: unknown) => void
  onError?: (error: unknown) => void
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

  const abortRef = useRef<AbortController | null>(null)
  const callbacksRef = useRef({ onEvent, onComplete, onError })
  callbacksRef.current = { onEvent, onComplete, onError }

  useEffect(() => {
    if (!taskId || !enabled) {
      abortRef.current?.abort()
      abortRef.current = null
      setIsConnected(false)
      return
    }

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    let cancelled = false

    const handleMessage = (raw: string) => {
      if (raw === '[DONE]') {
        setIsConnected(false)
        return true
      }

      try {
        const parsed = JSON.parse(raw)
        const eventObj: SSEEvent = {
          event: parsed.event || 'message',
          data: parsed.data || parsed,
          timestamp: Date.now(),
        }

        setLastEvent(eventObj)
        setEvents((prev) => [...prev.slice(-50), eventObj])
        callbacksRef.current.onEvent?.(eventObj)

        const data = parsed.data
        if (data && typeof data.stage === 'string') setCurrentStage(data.stage)
        if (data && typeof data.progress === 'number') {
          setProgress(Math.min(100, Math.max(0, data.progress)))
        }

        if (eventObj.event === 'task_completed') {
          setIsCompleted(true)
          setProgress(100)
          callbacksRef.current.onComplete?.(eventObj.data)
        } else if (eventObj.event === 'task_failed') {
          setIsFailed(true)
          const errorData = eventObj.data as { error?: string }
          setError(errorData?.error || '任务执行失败')
        }
      } catch {
        // Ignore malformed event frames and continue reading the stream.
      }
      return false
    }

    const connect = async () => {
      try {
        const headers: Record<string, string> = { Accept: 'text/event-stream' }
        const token = getAccessToken()
        if (token) headers.Authorization = `Bearer ${token}`

        const response = await fetch(buildUrl(`/agent/tasks/${taskId}/events`), {
          headers,
          credentials: 'include',
          signal: controller.signal,
        })
        if (!response.ok || !response.body) {
          throw new Error(`SSE connection failed: ${response.status}`)
        }

        setIsConnected(true)
        setError(null)
        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (!cancelled) {
          const { value, done } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const frames = buffer.split('\n\n')
          buffer = frames.pop() || ''
          for (const frame of frames) {
            const data = frame
              .split('\n')
              .filter((line) => line.startsWith('data:'))
              .map((line) => line.slice(5).trimStart())
              .join('\n')
            if (data && handleMessage(data)) return
          }
        }
        setIsConnected(false)
      } catch (err) {
        if (cancelled || (err instanceof DOMException && err.name === 'AbortError')) return
        setIsConnected(false)
        setError('连接中断')
        callbacksRef.current.onError?.(err)
      }
    }

    void connect()

    return () => {
      cancelled = true
      controller.abort()
      if (abortRef.current === controller) abortRef.current = null
      setIsConnected(false)
    }
  }, [taskId, enabled])

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
