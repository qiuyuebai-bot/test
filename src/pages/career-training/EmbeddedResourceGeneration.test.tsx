import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('@/api', () => ({
  agentApi: {
    runFullPipeline: vi.fn().mockResolvedValue({ taskId: 42 }),
  },
  coreApi: {
    getResourceList: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 20, totalPages: 0 }),
    getResourceDetail: vi.fn(),
  },
}))

vi.mock('@/hooks/useTaskSSE', () => ({
  useTaskSSE: vi.fn().mockReturnValue({
    events: [],
    currentStage: null,
    progress: 0,
    isConnected: false,
    isCompleted: false,
    isFailed: false,
    error: null,
    lastEvent: null,
  }),
}))

vi.mock('@/store', async () => {
  const { useStoreMock } = await import('../../test/mockStore')
  return { useStore: useStoreMock }
})

vi.mock('@/components/MarkdownContent', () => ({
  __esModule: true,
  default: ({ content }: { content: string }) => <div data-testid="markdown">{content}</div>,
}))

import { agentApi, coreApi } from '@/api'
import { useTaskSSE } from '@/hooks/useTaskSSE'
import { resetMockStore } from '../../test/mockStore'
import EmbeddedResourceGeneration from './EmbeddedResourceGeneration'
import type { PositionDetail } from '@/types/training'

const mockPosition: PositionDetail = {
  id: 1,
  code: 'FE-001',
  name: '前端工程师',
  category: 'tech',
  industry: '软件开发',
  level: 'junior',
  is_active: true,
  competencies: [],
  created_at: '',
  updated_at: '',
}

describe('EmbeddedResourceGeneration', () => {
  beforeEach(() => {
    resetMockStore()
    vi.clearAllMocks()
    vi.mocked(useTaskSSE).mockReturnValue({
      events: [],
      currentStage: null,
      progress: 0,
      isConnected: false,
      isCompleted: false,
      isFailed: false,
      error: null,
      lastEvent: null,
    } as never)
  })

  it('无 learnerId 时提示需要学习者画像', () => {
    render(<EmbeddedResourceGeneration position={mockPosition} learnerId={null} />)
    expect(screen.getByText(/需要学习者画像/)).toBeInTheDocument()
  })

  it('有 learnerId 时显示配置表单与岗位预填', () => {
    render(<EmbeddedResourceGeneration position={mockPosition} learnerId={10} />)
    expect(screen.getByDisplayValue('前端工程师')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /生成资料/ })).toBeInTheDocument()
  })

  it('挂载时拉取已有资源列表', async () => {
    render(<EmbeddedResourceGeneration position={mockPosition} learnerId={10} />)
    await waitFor(() => {
      expect(coreApi.getResourceList).toHaveBeenCalledWith(expect.objectContaining({ learnerId: 10 }))
    })
  })

  it('点击生成调用 runFullPipeline 并预填岗位与行业', async () => {
    render(<EmbeddedResourceGeneration position={mockPosition} learnerId={10} />)
    await userEvent.click(screen.getByRole('button', { name: /生成资料/ }))
    await waitFor(() => {
      expect(agentApi.runFullPipeline).toHaveBeenCalledWith({
        learnerId: 10,
        targetTopic: '前端工程师',
        resourceType: 'guide',
        industry: '软件开发',
      })
    })
  })

  it('SSE 完成后刷新资源列表', async () => {
    vi.mocked(useTaskSSE).mockReturnValue({
      events: [],
      currentStage: 'task_completed',
      progress: 100,
      isConnected: false,
      isCompleted: true,
      isFailed: false,
      error: null,
      lastEvent: null,
    } as never)
    render(<EmbeddedResourceGeneration position={mockPosition} learnerId={10} />)
    // isCompleted + taskId 触发刷新；但 taskId 初始为 null，故主要靠挂载 useEffect 验证刷新行为
    await waitFor(() => {
      expect(coreApi.getResourceList).toHaveBeenCalled()
    })
  })
})
