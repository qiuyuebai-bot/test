import { useQuery } from '@tanstack/react-query'
import { dashboardApi, type LearnerDashboardData, type TeacherDashboardData } from '@/api/dashboard'
import type { UserRole } from '@/types'

export type DashboardRole = Extract<UserRole, 'learner' | 'teacher'>
export type DashboardData = LearnerDashboardData | TeacherDashboardData

export const dashboardQueryKey = (role: DashboardRole) => ['dashboard', role] as const

export function useDashboardData(role: DashboardRole | undefined) {
  return useQuery<DashboardData>({
    queryKey: role ? dashboardQueryKey(role) : ['dashboard', 'none'],
    enabled: Boolean(role),
    queryFn: ({ signal }) => {
      if (role === 'learner') return dashboardApi.getLearner({ signal })
      if (role === 'teacher') return dashboardApi.getTeacher({ page: 1, pageSize: 20 }, { signal })
      return Promise.reject(new Error('不支持的 Dashboard 角色'))
    },
    refetchInterval: role === 'teacher' ? 60_000 : false,
    refetchOnWindowFocus: true,
  })
}
