import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const userState = vi.hoisted(() => ({ role: 'learner' }))

vi.mock('@/api', () => ({
  coreApi: {
    getResourceDetail: vi.fn().mockResolvedValue({
      id: 1,
      title: '测试题集',
      resourceType: 'exercise',
      content: '# 第一章\n\n题目内容\n答案：隐藏答案',
      contentSummary: '测试摘要',
      versionNumber: 1,
      knowledgeTopic: '测试主题',
      status: 'ready',
      validationPassed: true,
      hallucinationDetected: false,
    }),
    getKnowledgePublicationRequest: vi.fn(),
    exportResource: vi.fn(),
  },
}))

vi.mock('@/store', () => ({
  useStore: (selector: (state: { user: { role: string } }) => unknown) => selector({ user: { role: userState.role } }),
}))

vi.mock('@/components/MarkdownContent', () => ({
  __esModule: true,
  default: ({ content }: { content: string }) => <div data-testid="reader-content"><h1 id="reader-第一章-0">第一章</h1>{content}</div>,
}))

import ResourceReader from './ResourceReader'
import { coreApi } from '@/api'

afterEach(() => {
  cleanup()
  userState.role = 'learner'
})

describe('ResourceReader', () => {
  it('renders a full-width reading page and hides learner answers', async () => {
    render(
      <MemoryRouter initialEntries={['/resources/1/read']}>
        <Routes><Route path="/resources/:resourceId/read" element={<ResourceReader />} /></Routes>
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getAllByText('测试题集').length).toBeGreaterThan(0))
    expect(screen.getByTestId('resource-reader-toolbar')).toHaveClass('-top-16', 'pt-16')
    expect(screen.getByTestId('resource-reader-toolbar')).not.toHaveClass('backdrop-blur')
    expect(screen.queryByRole('button', { name: '目录' })).not.toBeInTheDocument()
    expect(screen.getAllByText('第一章').length).toBeGreaterThan(0)
    await waitFor(() => expect(screen.getByTestId('reader-content')).toHaveTextContent('题目内容'))
    expect(screen.getByTestId('reader-content')).not.toHaveTextContent('隐藏答案')
    expect(screen.getByRole('button', { name: /开始练习/ })).toBeInTheDocument()
  })

  it('keeps the body outside the table of contents and applies the selected font size', async () => {
    const user = userEvent.setup()
    const scrollIntoView = vi.fn()
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', { configurable: true, value: scrollIntoView })
    vi.mocked(coreApi.getResourceDetail).mockResolvedValue({
      id: 1,
      title: '测试题集',
      resourceType: 'exercise',
      content: '# 第一章\n\n题目内容\n答案：隐藏答案',
      contentSummary: '测试摘要',
      targetLearnerId: 1,
      contentType: 'text',
      qualityScore: null,
      reviewStatus: 'pending',
      generatedByAgent: 'test',
      generationTime: '',
      versionNumber: 1,
      knowledgeTopic: '测试主题',
      status: 'ready',
      validationPassed: true,
      hallucinationDetected: false,
    })
    render(<MemoryRouter initialEntries={['/resources/1/read']}><Routes><Route path="/resources/:resourceId/read" element={<ResourceReader />} /></Routes></MemoryRouter>)

    const article = await screen.findByTestId('resource-reader-content')
    const toc = screen.getByRole('navigation', { name: '资源目录' })
    expect(toc).not.toContainElement(article)

    await user.click(within(toc).getByRole('button', { name: '第一章' }))
    expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'start' })
    expect(toc).not.toContainElement(article)

    await user.selectOptions(screen.getByRole('combobox', { name: '字号' }), 'large')
    expect(article).toHaveStyle('--reader-font-size: 19px')
  })

  it('toggles Markdown-formatted exercise answers for teachers', async () => {
    const user = userEvent.setup()
    userState.role = 'teacher'
    vi.mocked(coreApi.getResourceDetail).mockResolvedValue({
      id: 6,
      title: '教师测试题',
      resourceType: 'exercise',
      content: '# 第一章\n\n题目内容\n\n**答案：A**\n**解析：A 是正确选项。**',
      contentSummary: '',
      targetLearnerId: 1,
      contentType: 'text',
      qualityScore: null,
      reviewStatus: 'pending',
      generatedByAgent: 'test',
      generationTime: '',
      versionNumber: 1,
      knowledgeTopic: '测试主题',
      status: 'ready',
      validationPassed: true,
      hallucinationDetected: false,
    })
    render(<MemoryRouter initialEntries={['/resources/6/read']}><Routes><Route path="/resources/:resourceId/read" element={<ResourceReader />} /></Routes></MemoryRouter>)

    const content = await screen.findByTestId('reader-content')
    expect(content).toHaveTextContent('答案：A')
    await user.click(screen.getByRole('button', { name: '隐藏答案' }))
    expect(content).not.toHaveTextContent('答案：A')
    expect(content).not.toHaveTextContent('解析：A 是正确选项。')

    await user.click(screen.getByRole('button', { name: '查看答案' }))
    expect(content).toHaveTextContent('答案：A')
    expect(content).toHaveTextContent('解析：A 是正确选项。')
  })

  it('does not show publication action for a failed lecture', async () => {
    vi.mocked(coreApi.getResourceDetail).mockResolvedValueOnce({
      id: 2, title: '失败讲义', resourceType: 'lecture', content: '# 内容', contentSummary: '',
      targetLearnerId: 1, contentType: 'text', qualityScore: null, reviewStatus: 'pending', generatedByAgent: 'test', generationTime: '',
      versionNumber: 1, knowledgeTopic: '测试主题', status: 'failed', validationPassed: false, hallucinationDetected: false,
    })
    render(<MemoryRouter initialEntries={['/resources/2/read']}><Routes><Route path="/resources/:resourceId/read" element={<ResourceReader />} /></Routes></MemoryRouter>)
    await waitFor(() => expect(screen.getAllByText('失败讲义').length).toBeGreaterThan(0))
    expect(screen.queryByRole('button', { name: /申请加入知识库/ })).not.toBeInTheDocument()
    expect(screen.getByText(/生成失败/)).toBeInTheDocument()
  })

  it('shows publication action for a ready validated lecture', async () => {
    vi.mocked(coreApi.getResourceDetail).mockResolvedValueOnce({
      id: 3, title: '可发布讲义', resourceType: 'lecture', content: '# 内容', contentSummary: '',
      targetLearnerId: 1, contentType: 'text', qualityScore: null, reviewStatus: 'pending', generatedByAgent: 'test', generationTime: '',
      versionNumber: 1, knowledgeTopic: '测试主题', status: 'ready', validationPassed: true, hallucinationDetected: false,
    })
    render(<MemoryRouter initialEntries={['/resources/3/read']}><Routes><Route path="/resources/:resourceId/read" element={<ResourceReader />} /></Routes></MemoryRouter>)
    await waitFor(() => expect(screen.getAllByText('可发布讲义').length).toBeGreaterThan(0))
    expect(screen.getByRole('button', { name: /提交人工入库申请/ })).toBeInTheDocument()
  })

  it('shows automatic publication state for a newly validated lecture', async () => {
    vi.mocked(coreApi.getResourceDetail).mockResolvedValueOnce({
      id: 4, title: '自动讲义', resourceType: 'lecture', content: '# 内容', contentSummary: '',
      targetLearnerId: 1, contentType: 'text', qualityScore: null, reviewStatus: 'approved', generatedByAgent: 'test', generationTime: '',
      versionNumber: 1, knowledgeTopic: '测试主题', status: 'ready', validationPassed: true, hallucinationDetected: false,
    })
    vi.mocked(coreApi.getKnowledgePublicationRequest).mockResolvedValueOnce({
      id: 8, resourceId: 4, resourceVersion: '1.0', contentHash: 'hash', status: 'publishing',
      submittedBy: 1, reviewNote: '系统自动入库', submittedAt: '', updatedAt: '',
    })
    render(<MemoryRouter initialEntries={['/resources/4/read']}><Routes><Route path="/resources/:resourceId/read" element={<ResourceReader />} /></Routes></MemoryRouter>)
    await waitFor(() => expect(screen.getAllByText('自动讲义').length).toBeGreaterThan(0))
    expect(screen.queryByRole('button', { name: /入库申请/ })).not.toBeInTheDocument()
    expect(screen.getByText(/正在自动加入所属领域知识库/)).toBeInTheDocument()
  })

  it('shows published state for an automatically published lecture', async () => {
    vi.mocked(coreApi.getResourceDetail).mockResolvedValueOnce({
      id: 5, title: '已入库讲义', resourceType: 'lecture', content: '# 内容', contentSummary: '',
      targetLearnerId: 1, contentType: 'text', qualityScore: null, reviewStatus: 'approved', generatedByAgent: 'test', generationTime: '',
      versionNumber: 1, knowledgeTopic: '测试主题', status: 'ready', validationPassed: true, hallucinationDetected: false,
    })
    vi.mocked(coreApi.getKnowledgePublicationRequest).mockResolvedValueOnce({
      id: 9, resourceId: 5, resourceVersion: '1.0', contentHash: 'hash', status: 'published',
      submittedBy: 1, knowledgeDocId: 12, submittedAt: '', updatedAt: '', publishedAt: '',
    })
    render(<MemoryRouter initialEntries={['/resources/5/read']}><Routes><Route path="/resources/:resourceId/read" element={<ResourceReader />} /></Routes></MemoryRouter>)
    await waitFor(() => expect(screen.getAllByText('已入库讲义').length).toBeGreaterThan(0))
    expect(screen.getByText('已入库')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /入库申请/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: '查看知识库文档' })).not.toBeInTheDocument()
  })
})
