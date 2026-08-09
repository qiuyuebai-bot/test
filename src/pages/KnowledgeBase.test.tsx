import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

vi.mock('@/store', async () => {
  const { useStoreMock } = await import('../test/mockStore')
  return { useStore: useStoreMock }
})

vi.mock('@/api', () => ({
  configApi: {
    getOptions: vi.fn(),
  },
  knowledgeApi: {
    delete: vi.fn(),
    getPreview: vi.fn(),
    reindex: vi.fn(),
    search: vi.fn(),
    traceResource: vi.fn(),
    uploadText: vi.fn(),
  },
}))

const { resetMockStore, setMockStore } = await import('../test/mockStore')
const { configApi } = await import('@/api')

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
})
