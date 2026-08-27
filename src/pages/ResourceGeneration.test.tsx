import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

vi.mock('@/api', () => ({
  agentApi: {
    runFullPipeline: vi.fn().mockResolvedValue({ taskId: 42 }),
  },
  coreApi: {
    getResourceDetail: vi.fn(),
    getResourceList: vi.fn(),
    deleteResource: vi.fn().mockResolvedValue({ id: 1, status: 'archived' }),
  },
}))

vi.mock('@/hooks', () => ({
  useResourceGenerationTask: vi.fn(),
}))

vi.mock('@/store', async () => {
  const { useStoreMock } = await import('../test/mockStore')
  return { useStore: useStoreMock }
})

vi.mock('@/components/MarkdownContent', () => ({
  __esModule: true,
  default: ({ content }: { content: string }) => <div data-testid="markdown">{content}</div>,
}))

import { agentApi, coreApi } from '@/api'
import { useResourceGenerationTask } from '@/hooks'
import { mockStoreState, resetMockStore, setMockStore } from '../test/mockStore'

const learner = {
  id: 6,
  realName: '测试学习者',
  educationLevel: '本科',
  major: '计算机科学',
}

describe('ResourceGeneration context modes', () => {
  beforeEach(() => {
    resetMockStore()
    vi.clearAllMocks()
    setMockStore({
      learners: [learner],
      currentLearner: learner,
      fetchResources: vi.fn().mockResolvedValue(undefined),
      fetchLearners: vi.fn().mockResolvedValue(undefined),
    })
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

  it('list mode shows existing resources without exposing generation controls', async () => {
    const { default: Page } = await import('./ResourceGeneration')
    render(
      <MemoryRouter initialEntries={['/resources?mode=list&dimension=algorithm_design&topic=%E7%AE%97%E6%B3%95%E8%AE%BE%E8%AE%A1&learnerId=6']}>
        <Page />
      </MemoryRouter>,
    )

    expect(await screen.findByRole('heading', { name: '相关学习资源' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '生成资源' })).not.toBeInTheDocument()
    await waitFor(() => {
      expect((mockStoreState.fetchResources as ReturnType<typeof vi.fn>)).toHaveBeenCalledWith(
        expect.objectContaining({ learnerId: 6, topic: '算法设计' }),
      )
    })
  })

  it('generate mode prefills the topic and waits for explicit confirmation', async () => {
    const { default: Page } = await import('./ResourceGeneration')
    render(
      <MemoryRouter initialEntries={['/resources?mode=generate&dimension=algorithm_design&topic=%E7%AE%97%E6%B3%95%E8%AE%BE%E8%AE%A1&learnerId=6']}>
        <Page />
      </MemoryRouter>,
    )

    expect(await screen.findByRole('heading', { name: '生成学习资源' })).toBeInTheDocument()
    expect(screen.getByDisplayValue('算法设计')).toBeInTheDocument()
    expect(agentApi.runFullPipeline).not.toHaveBeenCalled()

    await userEvent.click(screen.getByRole('button', { name: '生成资源' }))
    await waitFor(() => {
      expect(agentApi.runFullPipeline).toHaveBeenCalledWith(expect.objectContaining({
        learnerId: 6,
        targetTopic: '算法设计',
      }))
    })
  })

  it('submits the resource pipeline only once for repeated immediate clicks', async () => {
    let resolveRequest: ((value: { taskId: number }) => void) | undefined
    vi.mocked(agentApi.runFullPipeline).mockImplementationOnce(
      () => new Promise((resolve) => { resolveRequest = resolve }),
    )
    const beginSubmission = vi.fn()
      .mockReturnValueOnce(true)
      .mockReturnValue(false)
    vi.mocked(useResourceGenerationTask).mockReturnValue({
      taskId: null,
      isSubmitting: false,
      isGenerating: false,
      currentStage: null,
      progress: 0,
      description: '',
      connectionError: null,
      stream: {
        events: [], currentStage: null, progress: 0, isConnected: false,
        isCompleted: false, isFailed: false, error: null, lastEvent: null,
      },
      beginSubmission,
      attachTask: vi.fn(),
      failSubmission: vi.fn(),
      clearTrackedTask: vi.fn(),
    } as never)

    const { default: Page } = await import('./ResourceGeneration')
    render(
      <MemoryRouter initialEntries={['/resources?mode=generate&learnerId=6&topic=%E7%AE%97%E6%B3%95%E8%AE%BE%E8%AE%A1']}>
        <Page />
      </MemoryRouter>,
    )

    const generateButton = await screen.findByRole('button', { name: '生成资源' })
    fireEvent.click(generateButton)
    fireEvent.click(generateButton)

    expect(agentApi.runFullPipeline).toHaveBeenCalledTimes(1)
    resolveRequest?.({ taskId: 42 })
  })

  it('does not expose quality validation failure labels for any resource type', async () => {
    setMockStore({
      resources: [
        {
          id: 11,
          title: '失败实操指南',
          resourceType: 'guide',
          content: '# 指南',
          contentSummary: '',
          status: 'failed',
          reviewStatus: 'pending',
          versionNumber: 1,
        },
        {
          id: 12,
          title: '失败分阶测试题',
          resourceType: 'exercise',
          content: '# 测试题',
          contentSummary: '',
          status: 'failed',
          reviewStatus: 'pending',
          versionNumber: 1,
        },
        {
          id: 13,
          title: '失败专属讲义',
          resourceType: 'lecture',
          content: '# 讲义',
          contentSummary: '',
          status: 'failed',
          reviewStatus: 'pending',
          versionNumber: 1,
        },
      ],
      resourcesTotal: 3,
    })

    const { default: Page } = await import('./ResourceGeneration')
    render(
      <MemoryRouter initialEntries={['/resources?mode=list&learnerId=6']}>
        <Page />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getAllByText('失败实操指南').length).toBeGreaterThan(0))
    expect(screen.queryByText('质量校验未通过')).not.toBeInTheDocument()

    for (const [label, title] of [['分阶测试题', '失败分阶测试题'], ['专属讲义', '失败专属讲义']]) {
      await userEvent.click(screen.getByRole('button', { name: new RegExp(label) }))
      await waitFor(() => expect(screen.getAllByText(title).length).toBeGreaterThan(0))
      expect(screen.queryByText('质量校验未通过')).not.toBeInTheDocument()
    }
  })

  it('hides generated metadata and the detail summary for every resource type', async () => {
    setMockStore({
      resources: [
        {
          id: 21,
          title: '实操指南',
          resourceType: 'guide',
          content: '# 指南正文',
          contentSummary: '指南摘要',
          generationMethod: 'deepseek',
          generationTime: '2026-08-25T02:47:27Z',
          versionNumber: 1,
        },
        {
          id: 22,
          title: '分阶测试题',
          resourceType: 'exercise',
          content: '# 测试正文',
          contentSummary: '测试摘要',
          generationMethod: 'deepseek',
          generationTime: '2026-08-25T02:47:27Z',
          versionNumber: 1,
        },
        {
          id: 23,
          title: '专属讲义',
          resourceType: 'lecture',
          content: '# 讲义正文',
          contentSummary: '讲义摘要',
          generationMethod: 'deepseek',
          generationTime: '2026-08-25T02:47:27Z',
          versionNumber: 1,
        },
      ],
      resourcesTotal: 3,
    })

    const { default: Page } = await import('./ResourceGeneration')
    render(
      <MemoryRouter initialEntries={['/resources?mode=list&learnerId=6']}>
        <Page />
      </MemoryRouter>,
    )

    const preview = screen.getByTestId('resource-content-scroll')
    for (const [label, summary] of [['实操指南', '指南摘要'], ['分阶测试题', '测试摘要'], ['专属讲义', '讲义摘要']]) {
      await userEvent.click(screen.getByRole('button', { name: new RegExp(`^${label}\\s*1$`) }))
      await waitFor(() => expect(within(preview).getByText(label)).toBeInTheDocument())
      expect(within(preview).queryByText(summary)).not.toBeInTheDocument()
      expect(within(preview).queryByText(/DeepSeek生成/)).not.toBeInTheDocument()
      expect(within(preview).queryByText('内容摘要')).not.toBeInTheDocument()
    }
  })

  it('deletes a resource after confirmation and refreshes the active list', async () => {
    setMockStore({
      resources: [{
        id: 31,
        title: '待删除指南',
        resourceType: 'guide',
        content: '# 指南',
        contentSummary: '',
        generationMethod: 'deepseek',
        versionNumber: 1,
      }],
      resourcesTotal: 1,
    })

    const { default: Page } = await import('./ResourceGeneration')
    render(
      <MemoryRouter initialEntries={['/resources?mode=list&learnerId=6']}>
        <Page />
      </MemoryRouter>,
    )

    await userEvent.click(await screen.findByRole('button', { name: '删除待删除指南' }))
    expect(screen.getByRole('dialog')).toHaveTextContent('确定删除“待删除指南”吗？')
    await userEvent.click(screen.getByRole('button', { name: '确认删除' }))

    await waitFor(() => {
      expect(coreApi.deleteResource).toHaveBeenCalledWith(31)
      expect(mockStoreState.fetchResources).toHaveBeenCalledWith(expect.objectContaining({ learnerId: 6 }))
    })
  })
})
