import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

const navigateMock = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => navigateMock }
})

vi.mock('@/store', async () => {
  const { useStoreMock } = await import('../../test/mockStore')
  return { useStore: useStoreMock }
})

import { resetMockStore, setMockStore } from '../../test/mockStore'
import PracticeTab from './PracticeTab'

describe('PracticeTab', () => {
  beforeEach(() => {
    resetMockStore()
    navigateMock.mockClear()
    setMockStore({
      positions: [
        { id: 1, code: 'FE-001', name: '前端工程师', is_active: true, created_at: '', updated_at: '' },
      ],
      fetchPositions: vi.fn(),
    })
  })

  it('渲染岗位选择与两个入口卡片', () => {
    render(<MemoryRouter><PracticeTab /></MemoryRouter>)
    expect(screen.getByText('培训资料生成')).toBeInTheDocument()
    expect(screen.getByText('自适应练习')).toBeInTheDocument()
  })

  it('点击资源生成跳转', async () => {
    render(<MemoryRouter><PracticeTab /></MemoryRouter>)
    await userEvent.click(screen.getByText('培训资料生成'))
    expect(navigateMock).toHaveBeenCalledWith('/resources')
  })

  it('点击自适应练习跳转', async () => {
    render(<MemoryRouter><PracticeTab /></MemoryRouter>)
    await userEvent.click(screen.getByText('自适应练习'))
    expect(navigateMock).toHaveBeenCalledWith('/guidance')
  })
})
