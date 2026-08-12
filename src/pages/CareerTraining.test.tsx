import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import CareerTraining from './CareerTraining'

vi.mock('@/store', async () => {
  const { useStoreMock } = await import('../test/mockStore')
  return { useStore: useStoreMock }
})

describe('CareerTraining 聚合页', () => {
  it('渲染 5 个 Tab 导航', () => {
    render(
      <MemoryRouter initialEntries={['/career-training']}>
        <Routes>
          <Route path="/career-training" element={<CareerTraining />} />
          <Route path="/career-training/:tab" element={<CareerTraining />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByRole('tab', { name: '岗位与胜任力' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '能力评估' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '学习计划' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '学习与练习' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '认证发证' })).toBeInTheDocument()
  })

  it('URL tab 参数切换激活态', () => {
    render(
      <MemoryRouter initialEntries={['/career-training/assessment']}>
        <Routes>
          <Route path="/career-training" element={<CareerTraining />} />
          <Route path="/career-training/:tab" element={<CareerTraining />} />
        </Routes>
      </MemoryRouter>,
    )

    const assessmentTab = screen.getByRole('tab', { name: '能力评估' })
    expect(assessmentTab).toHaveAttribute('aria-selected', 'true')
  })
})
