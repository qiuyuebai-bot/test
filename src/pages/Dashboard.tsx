import { useCallback, useEffect, useState } from 'react'
import { useStore } from '@/store'
import {
  dashboardApi,
  type GuidanceAction,
  type LearnerDashboardData,
  type TeacherDashboardData,
} from '@/api/dashboard'
import { toast } from '@/components/toastStore'
import EmptyState from '@/components/EmptyState'
import type { UserRole } from '@/types'
import { useDashboardRefresh } from '@/features/dashboard/useDashboardRefresh'
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
  const [learnerData, setLearnerData] = useState<LearnerDashboardData | null>(null)
  const [teacherData, setTeacherData] = useState<TeacherDashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const activeRole = role === 'learner' || role === 'teacher' ? role : undefined

  const loadData = useCallback(
    async (signal: AbortSignal) => {
      if (!activeRole) return
      setLoading(true)
      setError(null)
      try {
        if (activeRole === 'learner') {
          setLearnerData(await dashboardApi.getLearner({ signal }))
        } else {
          setTeacherData(await dashboardApi.getTeacher({ page: 1, pageSize: 20 }, { signal }))
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Dashboard 数据加载失败')
      } finally {
        setLoading(false)
      }
    },
    [activeRole],
  )

  const { refresh } = useDashboardRefresh({
    role: activeRole,
    enabled: Boolean(activeRole),
    load: loadData,
  })

  useEffect(() => {
    setLearnerData(null)
    setTeacherData(null)
    setError(null)
    setLoading(Boolean(activeRole))
  }, [activeRole])

  const handleGuidanceAction = useCallback(async (action: GuidanceAction) => {
    try {
      const state = await dashboardApi.updateGuidance(action)
      setLearnerData((current) =>
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
    } catch (err) {
      toast.error('引导状态更新失败', err instanceof Error ? err.message : '请稍后重试')
    }
  }, [])

  if (role === 'admin') return <AdminDashboard />
  if (role === 'learner') {
    return (
      <LearnerDashboard
        data={learnerData}
        loading={loading}
        error={error}
        onRetry={() => void refresh()}
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
        onRetry={() => void refresh()}
      />
    )
  }
  return <UnsupportedRoleDashboard role={role} />
}
