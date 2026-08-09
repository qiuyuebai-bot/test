import { describe, expect, it, vi } from 'vitest'
import { render, waitFor } from '@testing-library/react'

vi.mock('@/store', async () => {
  const { useStoreMock } = await import('./test/mockStore')
  return { useStore: useStoreMock }
})

vi.mock('./pages/Dashboard', () => ({
  default: () => <div>dashboard page</div>,
}))

import App from './App'

describe('hidden legacy routes', () => {
  it.each(['/enterprise', '/privacy', '/deployment'])(
    'redirects %s to the dashboard for authenticated users', async (path) => {
      window.history.replaceState({}, '', path)
      render(<App />)

      await waitFor(() => expect(window.location.pathname).toBe('/dashboard'))
    },
  )

  it('redirects the legacy test route to runtime monitoring', async () => {
    window.history.replaceState({}, '', '/test')
    render(<App />)

    await waitFor(() => expect(window.location.pathname).toBe('/monitoring'))
  })
})
