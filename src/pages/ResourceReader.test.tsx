import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

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
  useStore: (selector: (state: { user: { role: string } }) => unknown) => selector({ user: { role: 'learner' } }),
}))

vi.mock('@/components/MarkdownContent', () => ({
  __esModule: true,
  default: ({ content }: { content: string }) => <div data-testid="reader-content">{content}</div>,
}))

import ResourceReader from './ResourceReader'
import { coreApi } from '@/api'

afterEach(() => cleanup())

describe('ResourceReader', () => {
  it('renders a full-width reading page and hides learner answers', async () => {
    render(
      <MemoryRouter initialEntries={['/resources/1/read']}>
        <Routes><Route path="/resources/:resourceId/read" element={<ResourceReader />} /></Routes>
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getAllByText('测试题集').length).toBeGreaterThan(0))
    expect(screen.getByText('第一章')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByTestId('reader-content')).toHaveTextContent('题目内容'))
    expect(screen.getByTestId('reader-content')).not.toHaveTextContent('隐藏答案')
    expect(screen.getByRole('button', { name: /开始练习/ })).toBeInTheDocument()
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
  })
})
