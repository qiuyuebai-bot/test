import { useState, useEffect, useCallback, useRef } from 'react'
import { useStore } from '@/store'
import { useShallow } from 'zustand/react/shallow'
import { useTaskSSE } from '@/hooks'
import type { AgentTask } from '@/types'

interface SseTaskProgress {
  stage: string
  progress: number
  description: string
}

export function useMultiAgentData() {
  const { agentStatuses, tasks, learners } = useStore(
    useShallow((s) => ({
      agentStatuses: s.agentStatuses,
      tasks: s.tasks,
      learners: s.learners,
    }))
  )
  const { fetchAgentStatuses, fetchTasks, fetchLearners, startAgentTask } = useStore(
    useShallow((s) => ({
      fetchAgentStatuses: s.fetchAgentStatuses,
      fetchTasks: s.fetchTasks,
      fetchLearners: s.fetchLearners,
      startAgentTask: s.startAgentTask,
    }))
  )

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedLearnerId, setSelectedLearnerId] = useState<number | null>(null)
  const [selectedTaskType, setSelectedTaskType] = useState<string>('full_flow')
  const [isStarting, setIsStarting] = useState(false)
  const [selectedTask, setSelectedTask] = useState<AgentTask>()
  const [runningTaskId, setRunningTaskId] = useState<number | null>(null)
  const [sseTaskId, setSseTaskId] = useState<number | null>(null)
  const [sseTaskProgress, setSseTaskProgress] = useState<SseTaskProgress>({ stage: 'init', progress: 0, description: '' })

  const addLogRef = useRef<(agent: string, content: string, type?: string) => void>(() => {})

  const handleSSEEvent = useCallback((event: { event: string; data: unknown; timestamp: number }) => {
    const data = (event.data as Record<string, unknown>) || {}
    switch (event.event) {
      case 'connected':
        setSseTaskProgress({
          stage: (data.stage as string) || 'init',
          progress: (data.progress as number) || 0,
          description: (data.description as string) || '已连接',
        })
        break
      case 'stage_update': {
        setSseTaskProgress({
          stage: (data.stage as string) || 'init',
          progress: (data.progress as number) || 0,
          description: (data.description as string) || '',
        })
        const stage = data.stage as string
        const agentType = stage === 'diagnosis' ? 'diagnosis' :
          stage === 'generation' || stage === 'knowledge_retrieval' ? 'generation' :
          stage === 'judge_first' || stage === 'debate' || stage === 'final_revision' ? 'review' : 'system'
        addLogRef.current(agentType, (data.description as string) || '', 'info')
        fetchTasks()
        fetchAgentStatuses()
        break
      }
      case 'debate_round':
        addLogRef.current('review', (data.description as string) || '', 'info')
        break
      case 'debate_result':
        addLogRef.current('review', (data.description as string) || '', data.decision === 'approved' ? 'success' : 'info')
        break
      case 'task_failed':
        setSseTaskProgress({ stage: 'failed', progress: 0, description: (data.error as string) || '任务失败' })
        addLogRef.current('system', `任务失败: ${(data.error as string) || '未知错误'}`, 'error')
        setRunningTaskId(null)
        setSseTaskId(null)
        fetchTasks()
        fetchAgentStatuses()
        break
    }
  }, [fetchTasks, fetchAgentStatuses])

  const sse = useTaskSSE(sseTaskId, {
    onEvent: handleSSEEvent,
    onComplete: (result) => {
      const data = result as { taskId?: number }
      setSseTaskProgress({ stage: 'complete', progress: 100, description: '任务完成' })
      addLogRef.current('system', `任务 #${data?.taskId || sseTaskId} 完成`, 'success')
      setRunningTaskId(null)
      setSseTaskId(null)
      fetchTasks()
      fetchAgentStatuses()
    },
    onError: () => {
      addLogRef.current('system', 'SSE连接断开，将通过轮询继续更新', 'error')
    },
  })

  const connectToRunningTask = useCallback((taskId: number) => {
    setRunningTaskId(taskId)
    setSseTaskId(taskId)
  }, [])

  useEffect(() => {
    const loadData = async () => {
      setLoading(true)
      try {
        await Promise.all([
          fetchAgentStatuses(),
          fetchTasks(),
          fetchLearners({ page: 1, pageSize: 50 }),
        ])
        setError(null)
      } catch {
        setError('加载数据失败')
      } finally {
        setLoading(false)
      }
    }
    loadData()

    const refreshInterval = setInterval(() => {
      fetchAgentStatuses()
      fetchTasks()
    }, 15000)

    return () => {
      clearInterval(refreshInterval)
    }
  }, [fetchAgentStatuses, fetchTasks, fetchLearners])

  useEffect(() => {
    const runningTask = tasks.find(t => t.status === 'running')
    if (runningTask && !runningTaskId && !sseTaskId) {
      connectToRunningTask(runningTask.taskId)
    }
    if (!runningTask && runningTaskId && !sseTaskId) {
      setRunningTaskId(null)
    }
  }, [tasks, runningTaskId, sseTaskId, connectToRunningTask])

  useEffect(() => {
    if (learners.length > 0 && !selectedLearnerId) {
      setSelectedLearnerId(learners[0].id)
    }
  }, [learners, selectedLearnerId])

  const handleStartTask = useCallback(async (addLog: (agent: string, content: string, type?: string) => void) => {
    if (!selectedLearnerId || isStarting) return

    setIsStarting(true)
    try {
      const result = await startAgentTask({
        learnerId: selectedLearnerId,
        taskType: selectedTaskType,
      })
      addLog('system', `已启动任务 #${result.taskId}`, 'success')
      setSseTaskProgress({ stage: 'init', progress: 0, description: '任务初始化中...' })
      await fetchTasks()
      await fetchAgentStatuses()
      connectToRunningTask(result.taskId)
    } catch {
      setError('启动任务失败')
      addLog('system', '启动任务失败', 'error')
    } finally {
      setIsStarting(false)
    }
  }, [selectedLearnerId, isStarting, selectedTaskType, startAgentTask, fetchTasks, fetchAgentStatuses, connectToRunningTask])

  const handleReset = useCallback((clearLogs: () => void) => {
    clearLogs()
    fetchAgentStatuses()
    fetchTasks()
  }, [fetchAgentStatuses, fetchTasks])

  const setAddLog = useCallback((fn: (agent: string, content: string, type?: string) => void) => {
    addLogRef.current = fn
  }, [])

  return {
    agentStatuses,
    tasks,
    learners,
    loading,
    error,
    selectedLearnerId,
    selectedTaskType,
    isStarting,
    selectedTask,
    runningTaskId,
    sseTaskProgress,
    sse,
    setSelectedLearnerId,
    setSelectedTaskType,
    setSelectedTask,
    setError,
    setLoading,
    setAddLog,
    handleStartTask,
    handleReset,
    fetchAgentStatuses,
    fetchTasks,
    fetchLearners,
  }
}
