import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api', () => ({
  agentApi: {
    getTaskList: vi.fn(),
    getTaskStatus: vi.fn(),
  },
}))

vi.mock('./useTaskSSE', () => ({
  useTaskSSE: vi.fn(),
}))

import { agentApi } from '@/api'
import { useTaskSSE } from './useTaskSSE'
import { useResourceGenerationTask } from './useResourceGenerationTask'

const emptyStream = {
  events: [],
  currentStage: null,
  progress: 0,
  isConnected: false,
  isCompleted: false,
  isFailed: false,
  error: null,
  lastEvent: null,
}

describe('useResourceGenerationTask', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useTaskSSE).mockReturnValue(emptyStream as never)
    vi.mocked(agentApi.getTaskList).mockResolvedValue({
      items: [], total: 0, page: 1, pageSize: 20, totalPages: 0,
    } as never)
    vi.mocked(agentApi.getTaskStatus).mockResolvedValue({
      status: 'running', progress: 50, stage: 'generation', description: '正在生成学习资源',
    } as never)
  })

  it('restores the learner\'s in-progress task from the backend after a remount', async () => {
    vi.mocked(agentApi.getTaskList).mockResolvedValue({
      items: [{
        taskId: 42,
        taskName: '生成算法设计学习资源',
        taskType: 'full_pipeline',
        status: 'running',
        flowStage: 'generation',
        progress: 50,
        learnerId: 6,
      }],
      total: 1,
      page: 1,
      pageSize: 20,
      totalPages: 1,
    } as never)

    const { result } = renderHook(() => useResourceGenerationTask({ learnerId: 6 }))

    await waitFor(() => expect(result.current.taskId).toBe(42))
    expect(result.current.isGenerating).toBe(true)
    expect(agentApi.getTaskList).toHaveBeenCalledWith({
      learnerId: 6,
      taskType: 'full_pipeline',
      page: 1,
      pageSize: 20,
    })
  })

  it('guards a submission synchronously and finalizes from persisted task status', async () => {
    const onComplete = vi.fn()
    vi.mocked(agentApi.getTaskStatus).mockResolvedValue({
      status: 'completed', progress: 100, stage: 'complete', description: '任务完成',
    } as never)
    const { result } = renderHook(() => useResourceGenerationTask({ learnerId: 6, onComplete }))

    act(() => {
      expect(result.current.beginSubmission()).toBe(true)
      expect(result.current.beginSubmission()).toBe(false)
    })

    act(() => result.current.attachTask(42))

    await waitFor(() => expect(onComplete).toHaveBeenCalledWith(42, expect.objectContaining({ status: 'completed' })))
    expect(result.current.taskId).toBeNull()
  })
})
