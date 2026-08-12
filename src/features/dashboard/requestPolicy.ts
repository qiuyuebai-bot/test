import type { UserRole } from '@/types'

export const dashboardRequestPolicy: Record<UserRole, readonly string[]> = {
  learner: ['/dashboard/learner'],
  teacher: ['/dashboard/teacher'],
  admin: ['/report/metrics', '/agent/status', '/agent/tasks'],
  enterprise: [],
}

export function allowedDashboardRequests(role: UserRole | undefined): readonly string[] {
  return role ? (dashboardRequestPolicy[role] ?? []) : []
}
