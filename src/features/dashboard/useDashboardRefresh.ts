import { useCallback, useEffect, useRef } from 'react'
import type { UserRole } from '@/types'

const REFRESH_INTERVALS: Partial<Record<UserRole, number>> = {
  learner: 0,
  teacher: 60_000,
  admin: 30_000,
}

const MIN_REFRESH_INTERVALS: Partial<Record<UserRole, number>> = {
  learner: 5_000,
  teacher: 30_000,
  admin: 10_000,
}

interface UseDashboardRefreshOptions {
  role: UserRole | undefined
  enabled?: boolean
  load: (signal: AbortSignal) => Promise<void>
}

export function useDashboardRefresh({ role, enabled = true, load }: UseDashboardRefreshOptions) {
  const loadRef = useRef(load)
  const inFlightRef = useRef<Promise<void> | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const lastStartedAtRef = useRef(0)
  loadRef.current = load

  const refresh = useCallback(
    async (force = true) => {
      if (inFlightRef.current) return inFlightRef.current
      const minimumInterval = MIN_REFRESH_INTERVALS[role ?? 'learner'] ?? 30_000
      const elapsed = Date.now() - lastStartedAtRef.current
      if (!force && elapsed < minimumInterval) return

      lastStartedAtRef.current = Date.now()
      const controller = new AbortController()
      abortControllerRef.current = controller
      const request = loadRef.current(controller.signal).finally(() => {
        if (inFlightRef.current === request) inFlightRef.current = null
        if (abortControllerRef.current === controller) abortControllerRef.current = null
      })
      inFlightRef.current = request
      return request
    },
    [role],
  )

  useEffect(() => {
    if (!enabled || !role || typeof document === 'undefined') return

    void refresh(true)
    const intervalMs = REFRESH_INTERVALS[role] ?? 0
    const intervalId = intervalMs
      ? window.setInterval(() => {
          if (!document.hidden) void refresh(false)
        }, intervalMs)
      : undefined

    const handleVisibilityChange = () => {
      if (!document.hidden) void refresh(false)
    }
    document.addEventListener('visibilitychange', handleVisibilityChange)

    return () => {
      if (intervalId !== undefined) window.clearInterval(intervalId)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      abortControllerRef.current?.abort()
    }
  }, [enabled, refresh, role])

  return { refresh: () => refresh(true) }
}

export function refreshIntervalForRole(role: UserRole | undefined): number {
  return REFRESH_INTERVALS[role ?? 'learner'] ?? 0
}
