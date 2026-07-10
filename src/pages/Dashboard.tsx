import { useState, useEffect } from 'react'
import { useStore } from '@/store'
import { useShallow } from 'zustand/react/shallow'
import Card from '@/components/Card'
import Badge from '@/components/Badge'
import { PageSkeleton } from '@/components/Skeleton'
import EmptyState from '@/components/EmptyState'
import {
  Users,
  Brain,
  FileText,
  TrendingUp,
  Activity,
  Clock,
  CheckCircle,
} from 'lucide-react'

export default function Dashboard() {
  const { systemMetrics, learners, agentStatuses, tasks } = useStore(
    useShallow((s) => ({
      systemMetrics: s.systemMetrics,
      learners: s.learners,
      agentStatuses: s.agentStatuses,
      tasks: s.tasks,
    }))
  )
  const { fetchSystemMetrics, fetchLearners, fetchAgentStatuses, fetchResources, fetchTasks } = useStore(
    useShallow((s) => ({
      fetchSystemMetrics: s.fetchSystemMetrics,
      fetchLearners: s.fetchLearners,
      fetchAgentStatuses: s.fetchAgentStatuses,
      fetchResources: s.fetchResources,
      fetchTasks: s.fetchTasks,
    }))
  )
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const loadData = async () => {
      setLoading(true)
      await Promise.all([
        fetchSystemMetrics(),
        fetchLearners({ page: 1, pageSize: 50 }),
        fetchAgentStatuses(),
        fetchResources({ page: 1, pageSize: 50 }),
        fetchTasks({ page: 1, pageSize: 10 }),
      ])
      setLoading(false)
    }
    loadData()

    let visibilityRefreshing = false
    const refreshInterval = setInterval(() => {
      // 标签页隐藏时跳过轮询，避免后台无效请求消耗带宽和 CPU
      if (document.hidden) return
      // 后台轮询使用 silent 模式，避免 ERR_ABORTED 等瞬时错误污染控制台和 Sentry
      fetchSystemMetrics({ silent: true })
      fetchAgentStatuses({ silent: true })
      fetchTasks({ page: 1, pageSize: 10 })
    }, 30000)

    // 标签页重新可见时立即刷新一次，保证数据新鲜度
    // 使用并发守卫避免与轮询或前一次可见刷新重叠触发 ERR_ABORTED
    const handleVisibilityChange = () => {
      if (document.hidden || visibilityRefreshing) return
      visibilityRefreshing = true
      Promise.all([
        fetchSystemMetrics({ silent: true }),
        fetchAgentStatuses({ silent: true }),
      ]).finally(() => {
        visibilityRefreshing = false
      })
    }
    document.addEventListener('visibilitychange', handleVisibilityChange)

    return () => {
      clearInterval(refreshInterval)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [fetchSystemMetrics, fetchLearners, fetchAgentStatuses, fetchResources, fetchTasks])

  const stats = [
    {
      label: '总学习者',
      value: systemMetrics?.totalLearners ?? 0,
      icon: Users,
      color: 'bg-primary',
    },
    {
      label: '已完成任务',
      value: systemMetrics?.tasksCompleted ?? 0,
      icon: Activity,
      color: 'bg-success',
    },
    {
      label: '生成资源',
      value: systemMetrics?.totalResources ?? 0,
      icon: FileText,
      color: 'bg-warning',
    },
    {
      label: '幻觉率',
      value: `${systemMetrics?.hallucinationRate?.toFixed(1) ?? 0}%`,
      icon: Brain,
      color: 'bg-info',
    },
  ]

  const recentTasks = tasks.slice(0, 5)

  const stateLabelMap: Record<string, { label: string; variant: 'success' | 'warning' | 'default' | 'error' }> = {
    idle: { label: '空闲', variant: 'default' },
    running: { label: '运行中', variant: 'warning' },
    waiting: { label: '等待中', variant: 'warning' },
    completed: { label: '已完成', variant: 'success' },
    failed: { label: '异常', variant: 'error' },
    error: { label: '错误', variant: 'error' },
  }

  const learningStyleMap: Record<string, string> = {
    visual: '视觉型',
    auditory: '听觉型',
    reading: '阅读型',
    kinesthetic: '动觉型',
  }

  if (loading) {
    return <PageSkeleton type="dashboard" />
  }

  const displayLearners = learners.slice(0, 3)
  const hasLearners = learners.length > 0

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat) => (
          <Card key={stat.label} padding="md" className="relative overflow-hidden">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-text-secondary mb-1">{stat.label}</p>
                <p className="metric-number text-3xl font-semibold text-text-primary">{stat.value}</p>
                <p className="text-xs text-text-tertiary mt-1 flex items-center gap-1">
                  <TrendingUp className="w-3 h-3" />
                  实时数据
                </p>
              </div>
              <div className={`${stat.color} p-3 rounded-xl`}>
                <stat.icon className="w-5 h-5 text-white" />
              </div>
            </div>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card padding="none" className="lg:col-span-2">
          <div className="p-6 border-b border-border">
            <h2 className="text-lg font-semibold text-text-primary">智能体运行状态</h2>
            <p className="text-sm text-text-secondary mt-1">实时监控多智能体协同工作流</p>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {agentStatuses.length > 0 ? (
                agentStatuses.map((agent) => {
                  const stateInfo = stateLabelMap[agent.state] || stateLabelMap.idle
                  return (
                    <div
                      key={agent.agentType}
                      className="p-4 rounded-xl border border-border bg-bg-secondary/50"
                    >
                      <div className="flex items-center gap-3 mb-3">
                        <div
                          className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                            agent.agentType === 'diagnosis'
                              ? 'bg-viz-1'
                              : agent.agentType === 'generation'
                              ? 'bg-viz-2'
                              : 'bg-viz-3'
                          }`}
                        >
                          <Brain className="w-5 h-5 text-white" />
                        </div>
                        <div>
                          <p className="text-sm font-medium text-text-primary">{agent.agentName}</p>
                          <Badge variant={stateInfo.variant}>
                            {stateInfo.label}
                          </Badge>
                        </div>
                      </div>
                      <div className="space-y-2 text-xs text-text-secondary">
                        <div className="flex justify-between">
                          <span>处理任务</span>
                          <span className="font-medium text-text-primary">{agent.totalTasksHandled}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>成功率</span>
                          <span className="font-medium text-text-primary">
                            {agent.totalTasksHandled > 0
                              ? `${((agent.successCount / agent.totalTasksHandled) * 100).toFixed(0)}%`
                              : '-'}
                          </span>
                        </div>
                      </div>
                    </div>
                  )
                })
              ) : (
                <div className="col-span-3 text-center py-8 text-text-tertiary text-sm">
                  暂无智能体状态数据
                </div>
              )}
            </div>
          </div>
        </Card>

        <Card padding="none">
          <div className="p-6 border-b border-border">
            <h2 className="text-lg font-semibold text-text-primary">近期任务</h2>
          </div>
          <div className="p-4 space-y-3">
            {recentTasks.length > 0 ? (
              recentTasks.map((task) => (
                <div
                  key={task.taskId}
                  className="flex items-start gap-3 p-3 rounded-lg hover:bg-bg-secondary/50 transition-colors"
                >
                  <div
                    className={`mt-0.5 p-1.5 rounded-full ${
                      task.status === 'completed'
                        ? 'bg-success-light'
                        : task.status === 'running'
                        ? 'bg-warning-light'
                        : task.status === 'failed'
                        ? 'bg-error-light'
                        : 'bg-info-light'
                    }`}
                  >
                    {task.status === 'completed' ? (
                      <CheckCircle className="w-3.5 h-3.5 text-success" />
                    ) : task.status === 'running' ? (
                      <Activity className="w-3.5 h-3.5 text-warning" />
                    ) : (
                      <Clock className="w-3.5 h-3.5 text-info" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-text-primary truncate">{task.taskName}</p>
                    <p className="text-xs text-text-tertiary flex items-center gap-1 mt-0.5">
                      <Clock className="w-3 h-3" />
                      {task.flowStage} · 进度 {task.progress}%
                    </p>
                  </div>
                </div>
              ))
            ) : (
              <div className="text-center py-6 text-text-tertiary text-sm">暂无任务记录</div>
            )}
          </div>
        </Card>
      </div>

      <Card padding="none">
        <div className="p-6 border-b border-border">
          <h2 className="text-lg font-semibold text-text-primary">学习者概览</h2>
        </div>
        {hasLearners ? (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border">
                  <th className="px-6 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">
                    学习者
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">
                    学历专业
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">
                    综合能力
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">
                    知识盲区
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">
                    学习风格
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {displayLearners.map((learner) => (
                  <tr key={learner.id} className="hover:bg-bg-secondary/50 transition-colors">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                          <span className="text-sm font-medium text-primary">
                            {(learner.realName || 'U').charAt(0)}
                          </span>
                        </div>
                        <span className="text-sm font-medium text-text-primary">
                          {learner.realName || `学习者 #${learner.id}`}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div>
                        <p className="text-sm text-text-primary">{learner.educationLevel}</p>
                        <p className="text-xs text-text-tertiary">{learner.major}</p>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-1.5 bg-bg-tertiary rounded-full max-w-[80px]">
                          <div
                            className="h-full bg-primary rounded-full"
                            style={{ width: `${learner.averageAbility}%` }}
                          />
                        </div>
                        <span className="metric-number text-sm font-medium text-text-primary">
                          {learner.averageAbility.toFixed(2)}%
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex flex-wrap gap-1">
                        {learner.knowledgeBlindAreas.slice(0, 2).map((spot) => (
                          <Badge key={spot} variant="warning" size="sm">
                            {spot}
                          </Badge>
                        ))}
                        {learner.knowledgeBlindAreas.length > 2 && (
                          <Badge variant="default" size="sm">
                            +{learner.knowledgeBlindAreas.length - 2}
                          </Badge>
                        )}
                        {learner.knowledgeBlindAreas.length === 0 && (
                          <span className="text-xs text-text-tertiary">无</span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <Badge variant="info">
                        {learningStyleMap[learner.learningStyle || ''] || '未设置'}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            type="default"
            title="暂无学习者数据"
            description="系统尚未录入学习者档案，请先在学习者画像页面添加"
          />
        )}
      </Card>
    </div>
  )
}
