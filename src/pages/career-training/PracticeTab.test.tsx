import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

vi.mock('@/store', async () => {
  const { useStoreMock } = await import('../../test/mockStore')
  return { useStore: useStoreMock }
})

vi.mock('@/api', () => ({
  trainingApi: {
    getPosition: vi.fn().mockResolvedValue({
      id: 1, code: 'FE-001', name: '前端工程师', category: 'tech', industry: '软件开发',
      level: 'junior', is_active: true, competencies: [], created_at: '', updated_at: '',
    }),
  },
  agentApi: {
    runFullPipeline: vi.fn().mockResolvedValue({ taskId: 42 }),
  },
  coreApi: {
    getResourceList: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 20, totalPages: 0 }),
    getResourceDetail: vi.fn(),
  },
}))

import { resetMockStore, setMockStore } from '../../test/mockStore'
import PracticeTab from './PracticeTab'

describe('PracticeTab', () => {
  beforeEach(() => {
    resetMockStore()
    setMockStore({
      positions: [
        { id: 1, code: 'FE-001', name: '前端工程师', is_active: true, created_at: '', updated_at: '' },
        { id: 2, code: 'BE-001', name: '后端工程师', is_active: true, created_at: '', updated_at: '' },
      ],
      fetchPositions: vi.fn(),
      learners: [{ id: 10, realName: '张三', userId: 1 }],
      currentLearner: { id: 10, realName: '张三', userId: 1 },
      fetchLearners: vi.fn(),
      setCurrentLearner: vi.fn(),
      user: { id: 1, username: 'admin', role: 'admin' },
    })
  })

  it('渲染岗位选择器与子 Tab 切换', () => {
    render(<MemoryRouter><PracticeTab /></MemoryRouter>)
    expect(screen.getByText('前端工程师')).toBeInTheDocument()
    expect(screen.getByText('后端工程师')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '资料生成' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '自适应练习' })).toBeInTheDocument()
  })

  it('默认显示资料生成子 Tab', () => {
    render(<MemoryRouter><PracticeTab /></MemoryRouter>)
    const resourceTab = screen.getByRole('tab', { name: '资料生成' })
    expect(resourceTab).toHaveAttribute('aria-selected', 'true')
  })

  it('点击切换到自适应练习子 Tab', async () => {
    render(<MemoryRouter><PracticeTab /></MemoryRouter>)
    await userEvent.click(screen.getByRole('tab', { name: '自适应练习' }))
    expect(screen.getByRole('tab', { name: '自适应练习' })).toHaveAttribute('aria-selected', 'true')
  })

  it('选择岗位后更新上下文', async () => {
    render(<MemoryRouter><PracticeTab /></MemoryRouter>)
    await userEvent.click(screen.getByText('前端工程师'))
    expect(screen.getByText(/前端工程师/)).toBeInTheDocument()
  })
})
