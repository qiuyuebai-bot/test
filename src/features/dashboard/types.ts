import type {
  DashboardFeedback,
  DashboardResource,
  DashboardTask,
  GuidanceState,
  LearnerDashboardData,
  TeacherDashboardData,
} from '@/api/dashboard'

export type DashboardModule =
  'profile' | 'summary' | 'resources' | 'tasks' | 'feedback' | 'learners' | 'risk' | 'blindAreas'

export interface DashboardModuleError {
  module: DashboardModule
  message: string
}

export interface LearnerDashboardView {
  data: LearnerDashboardData | null
  error: string | null
  loading: boolean
  moduleErrors: DashboardModuleError[]
}

export interface TeacherDashboardView {
  data: TeacherDashboardData | null
  error: string | null
  loading: boolean
  moduleErrors: DashboardModuleError[]
}

export type {
  DashboardFeedback,
  DashboardResource,
  DashboardTask,
  GuidanceState,
  LearnerDashboardData,
  TeacherDashboardData,
}
