import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

vi.mock('@/store', async () => {
  const { useStoreMock } = await import('../../test/mockStore')
  return { useStore: useStoreMock }
})

vi.mock('@/api', () => ({
  trainingApi: {
    getPosition: vi.fn(),
    createPosition: vi.fn(),
    createCompetency: vi.fn(),
    listPositions: vi.fn(),
    listCompetencies: vi.fn(),
    addPositionCompetency: vi.fn(),
  },
}))

import { resetMockStore, setMockStore } from '../../test/mockStore'
import { trainingApi } from '@/api'
import PositionTab from './PositionTab'

describe('PositionTab', () => {
  beforeEach(() => {
    resetMockStore()
    vi.clearAllMocks()
    setMockStore({
      positions: [
        { id: 1, code: 'FE-001', name: '前端工程师', category: 'technical', is_active: true, created_at: '', updated_at: '' },
      ],
      competencies: [],
      positionsLoading: false,
      fetchPositions: vi.fn(),
      fetchCompetencies: vi.fn(),
    })
  })

  it('渲染岗位卡片列表', () => {
    render(<MemoryRouter><PositionTab /></MemoryRouter>)
    expect(screen.getByText('前端工程师')).toBeInTheDocument()
    expect(screen.getByText('FE-001')).toBeInTheDocument()
  })

  it('点击岗位卡片加载详情', async () => {
    vi.mocked(trainingApi.getPosition).mockResolvedValueOnce({
      id: 1, code: 'FE-001', name: '前端工程师', is_active: true, created_at: '', updated_at: '',
      competencies: [
        { id: 1, position_id: 1, competency_id: 2, competency_name: 'React', required_level: 4, weight: 1, is_mandatory: true, created_at: '' },
      ],
    })
    render(<MemoryRouter><PositionTab /></MemoryRouter>)
    screen.getByText('前端工程师').click()
    await waitFor(() => {
      expect(screen.getByText('胜任力矩阵')).toBeInTheDocument()
      expect(screen.getByText('React')).toBeInTheDocument()
    })
  })
})
