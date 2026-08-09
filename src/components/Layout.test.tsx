import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

vi.mock('@/store', async () => {
  const { useStoreMock } = await import('../test/mockStore')
  return { useStore: useStoreMock }
})

import Layout from './Layout'

describe('Layout navigation', () => {
  it('hides removed enterprise, privacy, and deployment entries', () => {
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Routes>
          <Route path="*" element={<Layout />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.queryByText('企业内训')).not.toBeInTheDocument()
    expect(screen.queryByText('隐私合规')).not.toBeInTheDocument()
    expect(screen.queryByText('部署说明')).not.toBeInTheDocument()
    expect(screen.getAllByText('运行监控').length).toBeGreaterThan(0)
  })
})
