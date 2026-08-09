import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

vi.mock('@/store', async () => {
  const { useStoreMock } = await import('../test/mockStore')
  return { useStore: useStoreMock }
})

vi.mock('@/api', () => ({
  configApi: {
    getOptions: vi.fn(),
  },
  domainToIndustry: vi.fn((domain: string) => ({ data_analysis: '数据分析' }[domain])),
  knowledgeApi: {
    getList: vi.fn(),
    getStats: vi.fn(),
    delete: vi.fn(),
    getPreview: vi.fn(),
    reindex: vi.fn(),
    search: vi.fn(),
    traceResource: vi.fn(),
    uploadText: vi.fn(),
  },
}))

const { resetMockStore, setMockStore } = await import('../test/mockStore')
const { configApi, knowledgeApi } = await import('@/api')

beforeEach(() => {
  vi.clearAllMocks()
  resetMockStore()
  vi.mocked(configApi.getOptions).mockResolvedValue({
    industries: [],
    domains: [
      { value: 'smart_manufacturing', label: '智能制造', color: '' },
      { value: 'industrial_internet', label: '工业互联网', color: '' },
      { value: 'software_development', label: '软件开发', color: '' },
      { value: 'artificial_intelligence', label: '人工智能', color: '' },
      { value: 'data_analysis', label: '数据分析', color: '' },
      { value: 'general', label: '通用', color: '' },
    ],
    desensitizationRules: [],
  })
  vi.mocked(knowledgeApi.getList).mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 2, totalPages: 0 })
  vi.mocked(knowledgeApi.getStats).mockResolvedValue({
    totalDocs: 1,
    indexedDocs: 1,
    pendingDocs: 0,
    errorDocs: 0,
    totalSlices: 1,
    indexedSlices: 1,
  })
  setMockStore({
    knowledgeDocs: [{
      id: 1,
      title: '数据分析文档',
      domain: 'data_analysis',
      category: '数据科学',
      totalSlices: 1,
      indexedSlices: 1,
      status: 'indexed',
      uploadTime: '',
      version: '1.0',
      fileName: 'data-analysis.md',
    }],
    totalKnowledgeDocs: 1,
  })
})

describe('KnowledgeBase domain labels', () => {
  it('uses the configured Chinese label instead of the internal domain value', async () => {
    const { default: Page } = await import('./KnowledgeBase')

    render(<Page />)

    expect(await screen.findAllByText('数据分析', { exact: true })).not.toHaveLength(0)
    expect(screen.queryByText('data_analysis', { exact: true })).not.toBeInTheDocument()
  })

  it('hides administrator-only document actions for learners', async () => {
    setMockStore({ user: { id: 2, username: 'learner', role: 'learner' } })
    const { default: Page } = await import('./KnowledgeBase')

    render(<Page />)

    await screen.findAllByText('数据分析', { exact: true })
    expect(screen.queryByRole('button', { name: '上传文档' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '导入样例' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '知识溯源' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '删除' })).not.toBeInTheDocument()
  })

  it('uses server-side search and pagination for the document table', async () => {
    const fetchKnowledgeDocs = vi.fn()
    setMockStore({
      fetchKnowledgeDocs,
      fetchKnowledgeStats: vi.fn(),
      totalKnowledgeDocs: 41,
      totalKnowledgePages: 3,
      currentPage: 1,
      pageSize: 20,
    })
    const { default: Page } = await import('./KnowledgeBase')

    render(<Page />)
    fireEvent.change(await screen.findByPlaceholderText('搜索文档...'), { target: { value: '深度学习' } })

    await waitFor(() => {
      expect(fetchKnowledgeDocs).toHaveBeenCalledWith(expect.objectContaining({ page: 1, keyword: '深度学习' }))
    })

    fireEvent.click(screen.getByRole('button', { name: '2' }))
    expect(fetchKnowledgeDocs).toHaveBeenCalledWith(expect.objectContaining({ page: 2, keyword: '深度学习' }))
  })
})
