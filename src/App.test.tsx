import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, waitFor } from '@testing-library/react'

vi.mock('@/store', async () => {
  const { useStoreMock } = await import('./test/mockStore')
  return { useStore: useStoreMock }
})

vi.mock('./pages/Dashboard', () => ({
  default: () => <div>dashboard page</div>,
}))

import App from './App'
import { resetMockStore, setMockStore } from './test/mockStore'

describe('hidden legacy routes', () => {
  beforeEach(() => {
    resetMockStore()
  })

  it.each(['/privacy', '/deployment'])(
    'redirects %s to the dashboard for authenticated users',
    async (path) => {
      window.history.replaceState({}, '', path)
      render(<App />)

      await waitFor(() => expect(window.location.pathname).toBe('/dashboard'))
    },
  )

  it('redirects /enterprise to the career-training position tab', async () => {
    window.history.replaceState({}, '', '/enterprise')
    render(<App />)

    await waitFor(() => expect(window.location.pathname).toBe('/career-training/position'))
  })

  it('redirects the legacy test route to runtime monitoring', async () => {
    window.history.replaceState({}, '', '/test')
    render(<App />)

    await waitFor(() => expect(window.location.pathname).toBe('/monitoring'))
  })

  it.each([
    '/ops',
    '/multi-agent',
    '/metrics',
    '/monitoring',
    '/career-training',
    '/career-training/position',
    '/enterprise',
  ])('redirects non-admin users away from %s', async (path) => {
    setMockStore({ user: { id: 2, username: 'learner', role: 'learner' } })
    window.history.replaceState({}, '', path)
    render(<App />)

    await waitFor(() => expect(window.location.pathname).toBe('/dashboard'))
  })
})
