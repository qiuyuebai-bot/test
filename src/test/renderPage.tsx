import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { type ReactNode } from 'react'

export function renderWithRouter(node: ReactNode) {
  return render(<MemoryRouter>{node}</MemoryRouter>)
}
