import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
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
})
