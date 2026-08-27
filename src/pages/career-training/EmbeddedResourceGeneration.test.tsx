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
    deleteResource: vi.fn().mockResolvedValue({ id: 1, status: 'archived' }),
  },
}))

vi.mock('@/hooks/useResourceGenerationTask', () => ({
  useResourceGenerationTask: vi.fn(),
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
import { useResourceGenerationTask } from '@/hooks/useResourceGenerationTask'
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
    vi.mocked(agentApi.runFullPipeline).mockResolvedValue({ taskId: 42 })
    vi.mocked(coreApi.getResourceList).mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 20, totalPages: 0 })
    vi.mocked(useResourceGenerationTask).mockReturnValue({
      taskId: null,
      isSubmitting: false,
      isGenerating: false,
      currentStage: null,
      progress: 0,
      description: '',
      connectionError: null,
      stream: {
        events: [],
        currentStage: null,
        progress: 0,
        isConnected: false,
        isCompleted: false,
        isFailed: false,
        error: null,
        lastEvent: null,
      },
      beginSubmission: vi.fn(() => true),
      attachTask: vi.fn(),
      failSubmission: vi.fn(),
      clearTrackedTask: vi.fn(),
    } as never)
  })

  it('无 learnerId 时提示需要学习者画像', () => {
    render(<EmbeddedResourceGeneration position={mockPosition} learnerId={null} />)
    expect(screen.getByText(/需要学习者画像/)).toBeInTheDocument()
  })

  it('有 learnerId 时显示配置表单与岗位预填', async () => {
    render(<EmbeddedResourceGeneration position={mockPosition} learnerId={10} />)
    expect(screen.getByDisplayValue('前端工程师')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /生成资料/ })).toBeInTheDocument()
    await waitFor(() => expect(coreApi.getResourceList).toHaveBeenCalled())
  })

  it('挂载时拉取已有资源列表', async () => {
    render(<EmbeddedResourceGeneration position={mockPosition} learnerId={10} />)
    await waitFor(() => {
      expect(coreApi.getResourceList).toHaveBeenCalledWith(expect.objectContaining({ learnerId: 10 }))
    })
  })

  it('以百分比两位小数显示资源匹配度', async () => {
    vi.mocked(coreApi.getResourceList).mockResolvedValue({
      items: [{
        id: 1,
        title: '前端工程师指南',
        resourceType: 'guide',
        content: '# 指南',
        matchScore: 0.755,
      }],
      total: 1,
      page: 1,
      pageSize: 20,
      totalPages: 1,
    } as never)

    render(<EmbeddedResourceGeneration position={mockPosition} learnerId={10} />)

    expect(await screen.findByText('匹配度 75.50%')).toBeInTheDocument()
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

  it('恢复到进行中的任务时保持生成按钮不可重复提交', async () => {
    vi.mocked(useResourceGenerationTask).mockReturnValue({
      taskId: 42,
      isSubmitting: false,
      isGenerating: true,
      currentStage: 'generation',
      progress: 50,
      description: '正在生成学习资源...',
      connectionError: null,
      stream: {
        events: [],
        currentStage: 'generation',
        progress: 50,
        isConnected: true,
        isCompleted: false,
        isFailed: false,
        error: null,
        lastEvent: null,
      },
      beginSubmission: vi.fn(() => false),
      attachTask: vi.fn(),
      failSubmission: vi.fn(),
      clearTrackedTask: vi.fn(),
    } as never)

    render(<EmbeddedResourceGeneration position={mockPosition} learnerId={10} />)

    expect(screen.getByRole('button', { name: '生成资料' })).toBeDisabled()
    expect(screen.getByText('生成进度')).toBeInTheDocument()
    await waitFor(() => expect(coreApi.getResourceList).toHaveBeenCalled())
  })

  it('只为 AI 生成资源显示删除操作，并在确认后移除资源', async () => {
    vi.mocked(coreApi.getResourceList).mockResolvedValue({
      items: [
        { id: 1, title: 'AI 指南', resourceType: 'guide', generationMethod: 'deepseek', content: '# AI' },
        { id: 2, title: '兜底指南', resourceType: 'guide', generationMethod: 'deterministic_fallback', content: '# 兜底' },
      ],
      total: 2,
      page: 1,
      pageSize: 20,
      totalPages: 1,
    } as never)

    render(<EmbeddedResourceGeneration position={mockPosition} learnerId={10} />)

    expect(await screen.findByText('AI生成')).toBeInTheDocument()
    expect(screen.getByText('规则兜底')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '删除AI 指南' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '删除兜底指南' })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '删除AI 指南' }))
    await userEvent.click(screen.getByRole('button', { name: '确认删除' }))

    await waitFor(() => expect(coreApi.deleteResource).toHaveBeenCalledWith(1))
    expect(screen.queryByText('AI 指南')).not.toBeInTheDocument()
  })

})
