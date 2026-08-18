import { useCallback } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useStore } from '@/store'
import {
  dashboardApi,
  type GuidanceAction,
  type LearnerDashboardData,
} from '@/api/dashboard'
import { toast } from '@/components/toastStore'
import EmptyState from '@/components/EmptyState'
import type { UserRole } from '@/types'
import { dashboardQueryKey, useDashboardData } from '@/features/dashboard/useDashboardData'
import LearnerDashboard from './dashboard/LearnerDashboard'
import TeacherDashboard from './dashboard/TeacherDashboard'
import AdminDashboard from './dashboard/AdminDashboard'

function UnsupportedRoleDashboard({ role }: { role?: UserRole }) {
  return (
    <EmptyState
      title="当前角色没有可用的工作台"
      description={`暂不支持角色 ${role || 'unknown'} 的 Dashboard，请联系管理员配置访问范围。`}
    />
  )
}

export default function Dashboard() {
  const role = useStore((state) => state.user?.role)
  const activeRole = role === 'learner' || role === 'teacher' ? role : undefined
  const queryClient = useQueryClient()
  const dashboardQuery = useDashboardData(activeRole)
  const guidanceMutation = useMutation({
    mutationFn: dashboardApi.updateGuidance,
    onSuccess: (state, action) => {
      queryClient.setQueryData<LearnerDashboardData>(dashboardQueryKey('learner'), (current) =>
        current
          ? {
              ...current,
              guidance: {
                ...current.guidance,
                ...state,
              },
            }
          : current,
      )
      if (action === 'snooze') toast.success('已稍后处理', '下次进入 Dashboard 时仍可继续引导')
    },
    onError: (err) => {
      toast.error('引导状态更新失败', err instanceof Error ? err.message : '请稍后重试')
    },
  })

  const handleGuidanceAction = useCallback(async (action: GuidanceAction) => {
    try {
      await guidanceMutation.mutateAsync(action)
    } catch {
      // The mutation callback presents the error without interrupting the dashboard.
    }
  }, [guidanceMutation])

  const learnerData = activeRole === 'learner'
    ? (dashboardQuery.data as LearnerDashboardData | undefined) ?? null
    : null
  const teacherData = activeRole === 'teacher'
    ? (dashboardQuery.data as import('@/api/dashboard').TeacherDashboardData | undefined) ?? null
    : null
  const loading = Boolean(activeRole) && dashboardQuery.isLoading
  const error = dashboardQuery.error instanceof Error ? dashboardQuery.error.message : null

  if (role === 'admin') return <AdminDashboard />
  if (role === 'learner') {
    return (
      <LearnerDashboard
        data={learnerData}
        loading={loading}
        error={error}
        onRetry={() => void dashboardQuery.refetch()}
        onGuidanceAction={handleGuidanceAction}
      />
    )
  }
  if (role === 'teacher') {
    return (
      <TeacherDashboard
        data={teacherData}
        loading={loading}
        error={error}
        onRetry={() => void dashboardQuery.refetch()}
      />
    )
  }
  return <UnsupportedRoleDashboard role={role} />
}
