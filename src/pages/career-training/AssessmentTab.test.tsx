import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

vi.mock('@/store', async () => {
  const { useStoreMock } = await import('../../test/mockStore')
  return { useStore: useStoreMock }
})

vi.mock('@/api', () => ({
  trainingApi: {
    listAssessmentTemplates: vi.fn(),
    startAssessment: vi.fn(),
    submitAssessment: vi.fn(),
    getGapAnalysis: vi.fn(),
  },
}))

import { resetMockStore, setMockStore } from '../../test/mockStore'
import { trainingApi } from '@/api'
import AssessmentTab from './AssessmentTab'

describe('AssessmentTab', () => {
  beforeEach(() => {
    resetMockStore()
    vi.clearAllMocks()
    setMockStore({
      positions: [
        { id: 1, code: 'FE-001', name: '前端工程师', is_active: true, created_at: '', updated_at: '' },
      ],
      assessmentRecords: [],
      assessmentRecordsLoading: false,
      fetchPositions: vi.fn(),
      fetchAssessmentRecords: vi.fn(),
    })
  })

  it('渲染岗位选择与历史记录区域', () => {
    render(<MemoryRouter><AssessmentTab /></MemoryRouter>)
    expect(screen.getByText('能力评估')).toBeInTheDocument()
    expect(screen.getByText('前端工程师')).toBeInTheDocument()
  })

  it('选择岗位后加载模板列表', async () => {
    vi.mocked(trainingApi.listAssessmentTemplates).mockResolvedValueOnce({
      items: [
        { id: 1, position_id: 1, name: '初级评估', competency_configs: [], pass_threshold: 60, is_active: true, created_at: '', updated_at: '' },
      ],
      total: 1, page: 1, pageSize: 20, totalPages: 1,
    })
    render(<MemoryRouter><AssessmentTab /></MemoryRouter>)
    await userEvent.click(screen.getByText('前端工程师'))
    await waitFor(() => {
      expect(screen.getByText('初级评估')).toBeInTheDocument()
    })
  })
})
