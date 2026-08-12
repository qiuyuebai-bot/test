import { useCallback, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Activity,
  ArrowUpRight,
  Brain,
  CheckCircle2,
  Clock3,
  FileText,
  Gauge,
  Network,
  RefreshCw,
  Users,
} from 'lucide-react'
import { useShallow } from 'zustand/react/shallow'
import { useStore } from '@/store'
import Badge from '@/components/Badge'
import Button from '@/components/Button'
import Card from '@/components/Card'
import ErrorState from '@/components/ErrorState'
import { PageSkeleton } from '@/components/Skeleton'
import { useDashboardRefresh } from '@/features/dashboard/useDashboardRefresh'

const stateLabels: Record<
  string,
  { label: string; variant: 'success' | 'warning' | 'default' | 'error' }
> = {
  idle: { label: '空闲', variant: 'default' },
  running: { label: '运行中', variant: 'warning' },
  waiting: { label: '等待中', variant: 'warning' },
  completed: { label: '已完成', variant: 'success' },
  failed: { label: '异常', variant: 'error' },
  error: { label: '错误', variant: 'error' },
}

function formatMetric(value: number | null | undefined, suffix = ''): string {
  return typeof value === 'number' ? `${value.toFixed(1)}${suffix}` : '暂无数据'
}

export default function AdminDashboard() {
  const {
    systemMetrics,
    metricsLoading,
    metricsError,
    metricsStatus,
    agentStatuses,
    tasks,
    fetchSystemMetrics,
    fetchAgentStatuses,
    fetchTasks,
  } = useStore(
    useShallow((state) => ({
      systemMetrics: state.systemMetrics,
      metricsLoading: state.metricsLoading,
      metricsError: state.metricsError,
      metricsStatus: state.metricsStatus,
      agentStatuses: state.agentStatuses,
      tasks: state.tasks,
      fetchSystemMetrics: state.fetchSystemMetrics,
      fetchAgentStatuses: state.fetchAgentStatuses,
      fetchTasks: state.fetchTasks,
    })),
  )
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    setLoading(true)
    setLoadError(null)
    const results = await Promise.allSettled([
      fetchSystemMetrics(),
      fetchAgentStatuses(),
      fetchTasks({ page: 1, pageSize: 10 }),
    ])
    const failures = results.filter((result) => result.status === 'rejected')
    if (failures.length === results.length) {
      setLoadError('系统总览数据暂时不可用')
    }
    setLoading(false)
  }, [fetchAgentStatuses, fetchSystemMetrics, fetchTasks])

  const { refresh } = useDashboardRefresh({ role: 'admin', load: loadData })

  if (loading && !systemMetrics && agentStatuses.length === 0 && tasks.length === 0) {
    return <PageSkeleton type="dashboard" />
  }
  if (loadError && !systemMetrics && agentStatuses.length === 0 && tasks.length === 0) {
    return (
      <ErrorState title="系统总览加载失败" details={loadError} onRetry={() => void refresh()} />
    )
  }

  const recentTasks = tasks.slice(0, 5)
  const runningAgents = agentStatuses.filter(
    (agent) => agent.state === 'running' || agent.state === 'waiting',
  ).length
  const failedTasks =
    systemMetrics?.failedTasks ?? tasks.filter((task) => task.status === 'failed').length

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <p className="text-sm font-medium text-primary">系统总览</p>
          <h1 className="mt-1 text-2xl font-semibold text-text-primary">管理员 Dashboard</h1>
          <p className="mt-1 text-sm text-text-secondary">
            保留关键运行信号，详细运维操作进入专门页面。
          </p>
        </div>
        <Button
          variant="outline"
          onClick={() => void refresh()}
          disabled={loading || metricsLoading}
        >
          <RefreshCw className={loading || metricsLoading ? 'h-4 w-4 animate-spin' : 'h-4 w-4'} />
          刷新数据
        </Button>
      </div>

      {metricsError && (
        <div className="flex items-center justify-between gap-3 rounded-lg border border-warning/30 bg-warning-light px-4 py-3 text-sm text-warning-dark">
          <span>{metricsError}，当前页面仍显示可用数据。</span>
          <button
            type="button"
            onClick={() => void refresh()}
            className="inline-flex items-center gap-1 font-medium"
          >
            <RefreshCw className="h-4 w-4" />
            重试
          </button>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Card padding="md">
          <div className="flex items-center gap-3">
            <Users className="h-5 w-5 text-primary" />
            <div>
              <p className="text-2xl font-semibold text-text-primary">
                {systemMetrics?.totalLearners ?? '暂无'}
              </p>
              <p className="text-xs text-text-tertiary">学习者总数</p>
            </div>
          </div>
        </Card>
        <Card padding="md">
          <div className="flex items-center gap-3">
            <FileText className="h-5 w-5 text-info" />
            <div>
              <p className="text-2xl font-semibold text-text-primary">
                {systemMetrics?.totalResources ?? '暂无'}
              </p>
              <p className="text-xs text-text-tertiary">资源总数</p>
            </div>
          </div>
        </Card>
        <Card padding="md">
          <div className="flex items-center gap-3">
            <Network className="h-5 w-5 text-success" />
            <div>
              <p className="text-2xl font-semibold text-text-primary">
                {runningAgents}/{agentStatuses.length || '暂无'}
              </p>
              <p className="text-xs text-text-tertiary">运行中 Agent</p>
            </div>
          </div>
        </Card>
        <Card padding="md">
          <div className="flex items-center gap-3">
            <Activity className="h-5 w-5 text-warning" />
            <div>
              <p className="text-2xl font-semibold text-text-primary">{failedTasks}</p>
              <p className="text-xs text-text-tertiary">失败任务</p>
            </div>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(300px,0.8fr)]">
        <Card padding="none">
          <div className="flex items-center justify-between border-b border-border px-5 py-4">
            <div>
              <h2 className="font-semibold text-text-primary">Agent 状态</h2>
              <p className="mt-1 text-xs text-text-tertiary">
                摘要状态，详细诊断和证据链进入运维页面
              </p>
            </div>
            <Link
              to="/multi-agent"
              className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:text-primary-dark"
            >
              打开多智能体
              <ArrowUpRight className="h-3.5 w-3.5" />
            </Link>
          </div>
          <div className="grid gap-3 p-4 md:grid-cols-3">
            {agentStatuses.length > 0 ? (
              agentStatuses.map((agent) => {
                const stateInfo = stateLabels[agent.state] || stateLabels.idle
                return (
                  <div
                    key={agent.agentType}
                    className="rounded-lg border border-border bg-bg-secondary/50 p-4"
                  >
                    <div className="flex items-center gap-2.5">
                      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
                        <Brain className="h-4 w-4 text-primary" />
                      </div>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-text-primary">
                          {agent.agentName}
                        </p>
                        <Badge variant={stateInfo.variant}>{stateInfo.label}</Badge>
                      </div>
                    </div>
                    <div className="mt-4 flex justify-between text-xs text-text-secondary">
                      <span>处理任务</span>
                      <span className="font-medium text-text-primary">
                        {agent.totalTasksHandled}
                      </span>
                    </div>
                  </div>
                )
              })
            ) : (
              <div className="py-8 text-center text-sm text-text-tertiary md:col-span-3">
                暂无 Agent 状态数据。
              </div>
            )}
          </div>
        </Card>

        <Card padding="none">
          <div className="flex items-center justify-between border-b border-border px-5 py-4">
            <div>
              <h2 className="font-semibold text-text-primary">核心信号</h2>
              <p className="mt-1 text-xs text-text-tertiary">只保留系统总览所需指标</p>
            </div>
            <Gauge className="h-4 w-4 text-text-tertiary" />
          </div>
          <div className="space-y-4 p-5">
            <div className="flex items-center justify-between">
              <span className="text-sm text-text-secondary">幻觉率</span>
              <span className="text-sm font-semibold text-text-primary">
                {systemMetrics?.hasSufficientSample
                  ? formatMetric(systemMetrics.hallucinationRate, '%')
                  : '样本不足/待审核'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-text-secondary">知识覆盖率</span>
              <span className="text-sm font-semibold text-text-primary">
                {formatMetric(systemMetrics?.knowledgeCoverageRate, '%')}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-text-secondary">任务成功率</span>
              <span className="text-sm font-semibold text-text-primary">
                {formatMetric(systemMetrics?.taskSuccessRate, '%')}
              </span>
            </div>
            <div
              className={`rounded-lg px-3 py-2 text-xs ${metricsStatus === 'error' ? 'bg-error-light text-error' : metricsStatus === 'partial' ? 'bg-warning-light text-warning-dark' : 'bg-success-light text-success-dark'}`}
            >
              {metricsStatus === 'error'
                ? '指标服务不可用'
                : metricsStatus === 'partial'
                  ? '部分指标暂时不可用'
                  : '指标服务可用'}
            </div>
            <div className="flex gap-2">
              <Link
                to="/ops"
                className="inline-flex items-center gap-1 text-xs font-medium text-primary"
              >
                运维总览
                <ArrowUpRight className="h-3.5 w-3.5" />
              </Link>
              <Link
                to="/metrics"
                className="inline-flex items-center gap-1 text-xs font-medium text-primary"
              >
                量化指标
                <ArrowUpRight className="h-3.5 w-3.5" />
              </Link>
            </div>
          </div>
        </Card>
      </div>

      <Card padding="none">
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <div>
            <h2 className="font-semibold text-text-primary">近期任务</h2>
            <p className="mt-1 text-xs text-text-tertiary">
              系统任务摘要，进入多智能体页面查看完整队列
            </p>
          </div>
          <Clock3 className="h-4 w-4 text-text-tertiary" />
        </div>
        <div className="grid gap-2 p-4 md:grid-cols-2">
          {recentTasks.length > 0 ? (
            recentTasks.map((task) => (
              <div
                key={task.taskId}
                className="flex items-center gap-3 rounded-lg border border-border px-3 py-3"
              >
                <div
                  className={`h-2.5 w-2.5 rounded-full ${task.status === 'completed' ? 'bg-success' : task.status === 'failed' ? 'bg-error' : 'bg-warning'}`}
                />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm text-text-primary">{task.taskName}</p>
                  <p className="mt-1 text-xs text-text-tertiary">
                    {task.flowStage || task.status} · {task.progress.toFixed(0)}%
                  </p>
                </div>
                {task.status === 'completed' ? (
                  <CheckCircle2 className="h-4 w-4 text-success" />
                ) : (
                  <Clock3 className="h-4 w-4 text-text-tertiary" />
                )}
              </div>
            ))
          ) : (
            <div className="py-8 text-center text-sm text-text-tertiary md:col-span-2">
              暂无系统任务。
            </div>
          )}
        </div>
      </Card>
    </div>
  )
}
