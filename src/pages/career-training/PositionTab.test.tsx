import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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
    updatePosition: vi.fn(),
    updateCompetency: vi.fn(),
    updatePositionCompetency: vi.fn(),
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

  it('打开胜任力管理时不显示右上角提示', async () => {
    render(<MemoryRouter><PositionTab /></MemoryRouter>)

    await userEvent.click(screen.getByRole('button', { name: '胜任力管理' }))

    const dialog = screen.getByRole('dialog')
    expect(within(dialog).getByRole('heading', { name: '胜任力管理' })).toBeInTheDocument()
    expect(within(dialog).getByText('暂无胜任力，请先点击“新增胜任力”创建。')).toBeInTheDocument()
    expect(within(dialog).queryByText(/右上角/)).not.toBeInTheDocument()
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

  it('teacher can edit a position from the detail modal', async () => {
    vi.mocked(trainingApi.getPosition).mockResolvedValueOnce({
      id: 1, code: 'FE-001', name: '前端工程师', is_active: true, created_at: '', updated_at: '', competencies: [],
    })
    vi.mocked(trainingApi.updatePosition).mockResolvedValueOnce({
      id: 1, code: 'FE-001', name: '前端工程师', is_active: true, created_at: '', updated_at: '',
    })
    render(<MemoryRouter><PositionTab /></MemoryRouter>)
    await userEvent.click(screen.getByText('前端工程师'))
    await userEvent.click((await screen.findAllByRole('button', { name: '编辑岗位' }))[0])
    await userEvent.click(screen.getByRole('button', { name: '保存' }))

    await waitFor(() => {
      expect(trainingApi.updatePosition).toHaveBeenCalledWith(1, expect.objectContaining({ name: '前端工程师' }))
    })
  })

  it('teacher can create a position from the empty state', async () => {
    setMockStore({
      positions: [],
      user: { id: 9, username: 'teacher', role: 'teacher' },
    })
    vi.mocked(trainingApi.createPosition).mockResolvedValueOnce({
      id: 2, code: 'FE-002', name: '后端工程师', is_active: true, created_at: '', updated_at: '',
    })

    render(<MemoryRouter><PositionTab /></MemoryRouter>)
    await userEvent.click(screen.getByRole('button', { name: '新增岗位' }))

    const dialog = screen.getByRole('dialog')
    const inputs = within(dialog).getAllByRole('textbox')
    await userEvent.type(inputs[0], 'FE-002')
    await userEvent.type(inputs[1], '后端工程师')
    await userEvent.click(within(dialog).getByRole('button', { name: '创建' }))

    await waitFor(() => {
      expect(trainingApi.createPosition).toHaveBeenCalledWith(expect.objectContaining({
        code: 'FE-002',
        name: '后端工程师',
      }))
    })
  })
})
