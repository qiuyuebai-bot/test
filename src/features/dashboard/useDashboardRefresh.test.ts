import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { refreshIntervalForRole, useDashboardRefresh } from './useDashboardRefresh'

describe('dashboard refresh policy', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('does not schedule learner polling', async () => {
    const load = vi.fn(() => Promise.resolve())
    renderHook(() => useDashboardRefresh({ role: 'learner', load }))

    expect(load).toHaveBeenCalledTimes(1)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(300_000)
    })
    expect(load).toHaveBeenCalledTimes(1)
    expect(refreshIntervalForRole('learner')).toBe(0)
  })

  it('deduplicates a manual refresh while the initial request is in flight', async () => {
    let resolveRequest: (() => void) | undefined
    const load = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveRequest = resolve
        }),
    )
    const { result } = renderHook(() => useDashboardRefresh({ role: 'admin', load }))

    expect(load).toHaveBeenCalledTimes(1)
    await act(async () => {
      void result.current.refresh()
      void result.current.refresh()
    })
    expect(load).toHaveBeenCalledTimes(1)

    await act(async () => {
      resolveRequest?.()
      await Promise.resolve()
    })
  })

  it('uses the designed role intervals', () => {
    expect(refreshIntervalForRole('teacher')).toBe(60_000)
    expect(refreshIntervalForRole('admin')).toBe(30_000)
  })
})
