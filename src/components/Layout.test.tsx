import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

vi.mock('@/store', async () => {
  const { useStoreMock } = await import('../test/mockStore')
  return { useStore: useStoreMock }
})

import { resetMockStore, setMockStore } from '../test/mockStore'
import Layout from './Layout'

describe('Layout navigation', () => {
  beforeEach(() => {
    resetMockStore()
  })

  it('hides removed privacy and deployment entries', () => {
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Routes>
          <Route path="*" element={<Layout />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.queryByText('隐私合规')).not.toBeInTheDocument()
    expect(screen.queryByText('部署说明')).not.toBeInTheDocument()
    expect(screen.getAllByText('运行监控').length).toBeGreaterThan(0)
    expect(screen.getAllByRole('link', { name: '就业培训' }).length).toBeGreaterThan(0)
  })

  it('renders the four navigation groups for administrators', () => {
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Routes>
          <Route path="*" element={<Layout />} />
        </Routes>
      </MemoryRouter>,
    )

    const navigation = within(screen.getAllByRole('navigation', { name: '主导航' })[0])
    expect(navigation.getByRole('heading', { name: '工作台' })).toBeInTheDocument()
    expect(navigation.getByRole('heading', { name: '学习准备' })).toBeInTheDocument()
    expect(navigation.getByRole('heading', { name: '学习应用' })).toBeInTheDocument()
    expect(navigation.getByRole('heading', { name: '系统管理' })).toBeInTheDocument()
    expect(navigation.getByRole('link', { name: '运维总览' })).toBeInTheDocument()
    expect(navigation.getByRole('link', { name: '多智能体' })).toBeInTheDocument()
  })

  it('hides the system management group for non-admin users', () => {
    setMockStore({ user: { id: 2, username: 'learner', role: 'learner' } })

    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Routes>
          <Route path="*" element={<Layout />} />
        </Routes>
      </MemoryRouter>,
    )

    const navigation = within(screen.getAllByRole('navigation', { name: '主导航' })[0])
    expect(navigation.queryByRole('heading', { name: '系统管理' })).not.toBeInTheDocument()
    expect(navigation.queryByRole('link', { name: '运维总览' })).not.toBeInTheDocument()
    expect(navigation.queryByRole('link', { name: '多智能体' })).not.toBeInTheDocument()
    expect(navigation.queryByRole('link', { name: '量化指标' })).not.toBeInTheDocument()
    expect(navigation.queryByRole('link', { name: '运行监控' })).not.toBeInTheDocument()
    expect(navigation.queryByRole('link', { name: '就业培训' })).not.toBeInTheDocument()
  })
})
