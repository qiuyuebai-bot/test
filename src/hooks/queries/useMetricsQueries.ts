import { useQuery } from '@tanstack/react-query'
import { coreApi } from '../../api'
import type { SystemMetrics } from '../../types'

type SystemMetricsRaw = Partial<SystemMetrics> & {
  hallucinationRate?: number
  resourceMatchAccuracy?: number
}

function normalizeMetrics(m: SystemMetricsRaw): SystemMetrics {
  return {
    ...m,
    hallucinationRate: m.hallucinationRate ?? 0,
    resourceMatchAccuracy: m.resourceMatchAccuracy ?? 0,
  } as SystemMetrics
}

export function useSystemMetrics() {
  return useQuery({
    queryKey: ['metrics', 'system'],
    queryFn: async () => {
      const result = await coreApi.getSystemMetrics()
      return normalizeMetrics(result)
    },
    staleTime: 60 * 1000,
  })
}

export function useLearnerReport(learnerId: number | null) {
  return useQuery({
    queryKey: ['report', 'learner', learnerId],
    queryFn: async () => {
      if (learnerId === null) return null
      return coreApi.getLearnerReport(learnerId)
    },
    enabled: learnerId !== null,
    staleTime: 30 * 1000,
  })
}
