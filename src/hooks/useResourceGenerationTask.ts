import { useCallback, useEffect, useRef, useState } from 'react'
import { agentApi } from '@/api'
import type { AgentTask } from '@/types'
import { useTaskSSE } from './useTaskSSE'

const ACTIVE_TASK_STATUSES = new Set(['pending', 'running'])
const STATUS_POLL_INTERVAL_MS = 5000

type TaskStreamEvent = {
  event: string
  data: unknown
  timestamp: number
}

type TaskStatusSnapshot = {
  status?: string
  progress?: number
  stage?: string
  description?: string
  error?: string | null
}

type ListedTask = AgentTask & {
  flowDescription?: string
}

interface UseResourceGenerationTaskOptions {
  learnerId: number | null | undefined
  onEvent?: (event: TaskStreamEvent) => void
  onComplete?: (taskId: number, data: unknown) => void
  onFailed?: (taskId: number, message: string) => void
}

/**
 * Restores the learner's durable generation task after a remount and keeps
 * watching it until the backend records a terminal state.
 */
export function useResourceGenerationTask({
  learnerId,
  onEvent,
  onComplete,
  onFailed,
}: UseResourceGenerationTaskOptions) {
  const [taskId, setTaskId] = useState<number | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [snapshot, setSnapshot] = useState<TaskStatusSnapshot | null>(null)

  const taskIdRef = useRef<number | null>(null)
  const submittingRef = useRef(false)
  const recoveryRequestRef = useRef(0)
  const finalizedTaskIdRef = useRef<number | null>(null)
  const callbacksRef = useRef({ onEvent, onComplete, onFailed })
  callbacksRef.current = { onEvent, onComplete, onFailed }

  const setTrackedTaskId = useCallback((nextTaskId: number | null) => {
    taskIdRef.current = nextTaskId
    setTaskId(nextTaskId)
  }, [])

  const clearTrackedTask = useCallback((expectedTaskId?: number) => {
    if (expectedTaskId != null && taskIdRef.current !== expectedTaskId) return
    setTrackedTaskId(null)
    setSnapshot(null)
  }, [setTrackedTaskId])

  const finalizeTask = useCallback((status: 'completed' | 'failed', data: unknown) => {
    const activeTaskId = taskIdRef.current
    if (!activeTaskId || finalizedTaskIdRef.current === activeTaskId) return

    finalizedTaskIdRef.current = activeTaskId
    submittingRef.current = false
    setIsSubmitting(false)
    clearTrackedTask(activeTaskId)

    if (status === 'completed') {
      callbacksRef.current.onComplete?.(activeTaskId, data)
      return
    }

    const failure = data as { error?: string | null }
    callbacksRef.current.onFailed?.(activeTaskId, failure?.error || '资源生成失败')
  }, [clearTrackedTask])

  const stream = useTaskSSE(taskId, {
    onEvent: (event) => {
      callbacksRef.current.onEvent?.(event)
      if (event.event === 'task_failed') {
        finalizeTask('failed', event.data)
      }
    },
    onComplete: (data) => finalizeTask('completed', data),
    // A disconnected browser stream must not change the durable task state.
    // The status poll below will reconnect the page to its eventual result.
    onError: () => {},
  })

  const beginSubmission = useCallback(() => {
    if (submittingRef.current || taskIdRef.current != null) return false
    submittingRef.current = true
    finalizedTaskIdRef.current = null
    setIsSubmitting(true)
    return true
  }, [])

  const attachTask = useCallback((nextTaskId: number) => {
    finalizedTaskIdRef.current = null
    submittingRef.current = false
    setIsSubmitting(false)
    if (taskIdRef.current !== nextTaskId) {
      setSnapshot({ status: 'running', progress: 0, stage: 'init', description: '任务初始化中...' })
      setTrackedTaskId(nextTaskId)
    }
  }, [setTrackedTaskId])

  const failSubmission = useCallback(() => {
    submittingRef.current = false
    setIsSubmitting(false)
  }, [])

  useEffect(() => {
    const requestId = ++recoveryRequestRef.current
    submittingRef.current = false
    setIsSubmitting(false)
    clearTrackedTask()

    if (!learnerId) return

    const restore = async () => {
      try {
        const result = await agentApi.getTaskList({
          learnerId,
          taskType: 'full_pipeline',
          page: 1,
          pageSize: 20,
        })
        if (requestId !== recoveryRequestRef.current || taskIdRef.current != null) return

        const activeTask = (result.items as ListedTask[]).find((task) =>
          ACTIVE_TASK_STATUSES.has(String(task.status)),
        )
        if (!activeTask) return

        finalizedTaskIdRef.current = null
        setSnapshot({
          status: activeTask.status,
          progress: activeTask.progress,
          stage: activeTask.flowStage,
          description: activeTask.flowDescription,
        })
        setTrackedTaskId(activeTask.taskId)
      } catch {
        // Resource generation remains server-side. A later remount or status
        // poll can restore it, so a transient list failure is not terminal.
      }
    }

    void restore()
  }, [clearTrackedTask, learnerId, setTrackedTaskId])

  useEffect(() => {
    if (!taskId) return

    let cancelled = false
    const refreshStatus = async () => {
      try {
        const status = await agentApi.getTaskStatus(taskId, { silent: true }) as unknown as TaskStatusSnapshot
        if (cancelled || taskIdRef.current !== taskId) return

        setSnapshot(status)
        if (status.status === 'completed') {
          finalizeTask('completed', status)
        } else if (status.status === 'failed') {
          finalizeTask('failed', status)
        }
      } catch {
        // Keep the active task attached. A failed status request does not mean
        // the background generation has stopped.
      }
    }

    void refreshStatus()
    const intervalId = window.setInterval(() => void refreshStatus(), STATUS_POLL_INTERVAL_MS)
    return () => {
      cancelled = true
      window.clearInterval(intervalId)
    }
  }, [finalizeTask, taskId])

  const currentStage = stream.currentStage ?? snapshot?.stage ?? null
  const progress = stream.currentStage != null || stream.progress > 0
    ? stream.progress
    : snapshot?.progress ?? 0

  return {
    taskId,
    isSubmitting,
    isGenerating: isSubmitting || taskId != null,
    currentStage,
    progress,
    description: snapshot?.description ?? '',
    connectionError: stream.error,
    stream,
    beginSubmission,
    attachTask,
    failSubmission,
    clearTrackedTask,
  }
}
