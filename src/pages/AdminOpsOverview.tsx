import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useShallow } from 'zustand/react/shallow'
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  Clock3,
  Database,
  Gauge,
  ListChecks,
  Network,
  RefreshCw,
  ShieldCheck,
  XCircle,
} from 'lucide-react'
import { useStore } from '@/store'
import type { AgentTask, AgentStatus } from '@/types'
import Card from '@/components/Card'
import Badge from '@/components/Badge'
import Button from '@/components/Button'
import ErrorState from '@/components/ErrorState'
import EmptyState from '@/components/EmptyState'
import { PageSkeleton } from '@/components/Skeleton'

type HealthTone = 'success' | 'warning' | 'error'

const healthConfig: Record<HealthTone, { label: string; description: string; icon: typeof ShieldCheck; className: string }> = {
  success: {
    label: '系统运行正常',
    description: '核心指标、Agent 状态和任务队列均可用。',
    icon: ShieldCheck,
    className: 'border-success/30 bg-success-light text-success-dark',
  },
  warning: {
    label: '系统需要关注',
    description: '部分指标或运行任务存在异常，请查看对应详情。',
    icon: AlertTriangle,
    className: 'border-warning/30 bg-warning-light text-warning-dark',
  },
  error: {
    label: '指标服务不可用',
    description: '无法读取核心指标，请稍后重试或检查后端服务。',
    icon: XCircle,
    className: 'border-error/30 bg-error-light text-error-dark',
  },
}

function formatPercentage(value: number | null | undefined, pending = '暂无数据') {
  return typeof value === 'number' ? `${value.toFixed(1)}%` : pending
}

function getTaskCounts(tasks: AgentTask[]) {
  return tasks.reduce(
    (counts, task) => {
      if (task.status === 'running' || task.status === 'pending') counts.running += 1
      if (task.status === 'failed' || task.status === 'cancelled') counts.failed += 1
      return counts
    },
    { running: 0, failed: 0 },
  )
}

function getAgentSummary(agents: AgentStatus[]) {
  return agents.reduce(
    (summary, agent) => {
      summary.total += 1
      if (agent.state === 'running' || agent.state === 'waiting') summary.active += 1
      if (agent.state === 'error' || agent.state === 'failed') summary.unavailable += 1
      return summary
    },
    { total: 0, active: 0, unavailable: 0 },
  )
}

function MetricValue({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <p className="metric-number text-2xl font-semibold text-text-primary">{value}</p>
      <p className="mt-1 text-xs text-text-tertiary">{label}</p>
    </div>
  )
}

function DetailLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link
      to={to}
      className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:text-primary-dark"
    >
      {children}
      <ArrowUpRight className="h-3.5 w-3.5" />
    </Link>
  )
}

export default function AdminOpsOverview() {
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
  const [error, setError] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      await Promise.all([
        fetchSystemMetrics(),
        fetchAgentStatuses(),
        fetchTasks({ page: 1, pageSize: 10 }),
      ])
    } catch (err) {
      setError(err instanceof Error ? err.message : '运维数据加载失败')
    } finally {
      setLoading(false)
    }
  }, [fetchAgentStatuses, fetchSystemMetrics, fetchTasks])

  useEffect(() => {
    void loadData()
  }, [loadData])

  const taskCounts = useMemo(() => getTaskCounts(tasks), [tasks])
  const agentSummary = useMemo(() => getAgentSummary(agentStatuses), [agentStatuses])
  const hasMetrics = Boolean(systemMetrics)
  const healthTone: HealthTone = metricsStatus === 'error'
    ? 'error'
    : metricsStatus === 'partial' || metricsStatus === 'idle' || !hasMetrics || agentSummary.unavailable > 0
      ? 'warning'
      : 'success'
  const health = healthConfig[healthTone]
  const HealthIcon = health.icon
  const recentTasks = tasks.slice(0, 5)

  if (loading && !hasMetrics && agentStatuses.length === 0 && tasks.length === 0) {
    return <PageSkeleton type="dashboard" />
  }

  if (error && !hasMetrics && agentStatuses.length === 0 && tasks.length === 0) {
    return <ErrorState type="default" onRetry={() => void loadData()} />
  }

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <h1 className="hero-anchor text-xl font-semibold text-text-primary">运维总览</h1>
          <p className="mt-1 text-sm text-text-secondary">从一个入口查看系统质量、Agent 运行态和任务队列。</p>
        </div>
        <Button variant="outline" onClick={() => void loadData()} disabled={loading || metricsLoading}>
          <RefreshCw className={loading || metricsLoading ? 'h-4 w-4 animate-spin' : 'h-4 w-4'} />
          刷新数据
        </Button>
      </div>

      {metricsError && metricsStatus === 'partial' && (
        <div className="rounded-lg border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning">
          {metricsError}，当前页面仍显示可用数据。
        </div>
      )}

      <div className={`flex items-start gap-3 rounded-lg border px-4 py-3 ${health.className}`}>
        <HealthIcon className="mt-0.5 h-5 w-5 flex-shrink-0" />
        <div>
          <p className="text-sm font-semibold">{health.label}</p>
          <p className="mt-0.5 text-xs opacity-90">{health.description}</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Card padding="md">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
              <Gauge className="h-5 w-5 text-primary" />
            </div>
            <MetricValue
              value={formatPercentage(systemMetrics?.knowledgeCoverageRate)}
              label="知识覆盖率"
            />
          </div>
        </Card>
        <Card padding="md">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-info/10">
              <Network className="h-5 w-5 text-info" />
            </div>
            <MetricValue value={`${agentSummary.active}/${agentSummary.total}`} label="Agent 活跃数" />
          </div>
        </Card>
        <Card padding="md">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-warning/10">
              <Clock3 className="h-5 w-5 text-warning" />
            </div>
            <MetricValue value={`${systemMetrics?.runningTasks ?? taskCounts.running}`} label="运行中任务" />
          </div>
        </Card>
        <Card padding="md">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-error/10">
              <AlertTriangle className="h-5 w-5 text-error" />
            </div>
            <MetricValue value={`${systemMetrics?.failedTasks ?? taskCounts.failed}`} label="失败任务" />
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card padding="md" className="xl:col-span-2">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <Activity className="h-5 w-5 text-text-secondary" />
                <h2 className="font-semibold text-text-primary">质量指标摘要</h2>
              </div>
              <p className="mt-1 text-xs text-text-tertiary">指标详情、趋势和样本状态集中在量化指标页。</p>
            </div>
            <DetailLink to="/metrics">查看指标</DetailLink>
          </div>
          <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="rounded-lg bg-bg-secondary/60 p-3">
              <MetricValue
                value={systemMetrics?.hasSufficientSample ? formatPercentage(systemMetrics.hallucinationRate) : '待审核'}
                label="知识幻觉率"
              />
              <p className="mt-2 text-xs text-text-tertiary">目标 &lt; 5%</p>
            </div>
            <div className="rounded-lg bg-bg-secondary/60 p-3">
              <MetricValue value={formatPercentage(systemMetrics?.resourceMatchAccuracy)} label="资源匹配准确率" />
              <p className="mt-2 text-xs text-text-tertiary">目标 &gt; 90%</p>
            </div>
            <div className="rounded-lg bg-bg-secondary/60 p-3">
              <MetricValue value={formatPercentage(systemMetrics?.knowledgeCoverageRate)} label="知识点覆盖率" />
              <p className="mt-2 text-xs text-text-tertiary">目标 &gt; 85%</p>
            </div>
          </div>
        </Card>

        <Card padding="md">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <Database className="h-5 w-5 text-text-secondary" />
                <h2 className="font-semibold text-text-primary">知识库状态</h2>
              </div>
              <p className="mt-1 text-xs text-text-tertiary">索引覆盖率直接来自系统指标服务。</p>
            </div>
            <DetailLink to="/knowledge-base">管理知识库</DetailLink>
          </div>
          <div className="mt-5 flex items-end justify-between">
            <MetricValue value={formatPercentage(systemMetrics?.knowledgeIndexCoverageRate ?? systemMetrics?.knowledgeCoverageRate)} label="索引覆盖率" />
            <div className="text-right">
              <p className="metric-number text-2xl font-semibold text-text-primary">{systemMetrics?.totalResources ?? 0}</p>
              <p className="mt-1 text-xs text-text-tertiary">资源总数</p>
            </div>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card padding="md">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <Network className="h-5 w-5 text-text-secondary" />
                <h2 className="font-semibold text-text-primary">Agent 运行态</h2>
              </div>
              <p className="mt-1 text-xs text-text-tertiary">查看在线状态和任务处理能力。</p>
            </div>
            <DetailLink to="/multi-agent">打开多智能体</DetailLink>
          </div>
          <div className="mt-4 divide-y divide-border/50">
            {agentStatuses.length === 0 ? (
              <EmptyState type="default" title="暂无 Agent 状态" />
            ) : (
              agentStatuses.slice(0, 4).map((agent) => {
                const isAvailable = agent.state !== 'error' && agent.state !== 'failed'
                return (
                  <div key={agent.agentType} className="flex items-center justify-between py-2.5">
                    <div className="flex min-w-0 items-center gap-2">
                      {isAvailable ? <CheckCircle2 className="h-4 w-4 text-success" /> : <XCircle className="h-4 w-4 text-error" />}
                      <span className="truncate text-sm text-text-primary">{agent.agentName}</span>
                    </div>
                    <Badge variant={isAvailable ? 'success' : 'error'} size="sm">
                      {isAvailable ? agent.state : '异常'}
                    </Badge>
                  </div>
                )
              })
            )}
          </div>
        </Card>

        <Card padding="md">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <Clock3 className="h-5 w-5 text-text-secondary" />
                <h2 className="font-semibold text-text-primary">最近任务</h2>
              </div>
              <p className="mt-1 text-xs text-text-tertiary">运行监控页提供完整任务记录和筛选。</p>
            </div>
            <DetailLink to="/monitoring">查看监控</DetailLink>
          </div>
          <div className="mt-4 divide-y divide-border/50">
            {recentTasks.length === 0 ? (
              <EmptyState type="default" title="暂无运行任务" />
            ) : (
              recentTasks.map((task) => {
                const isCompleted = task.status === 'completed'
                const isFailed = task.status === 'failed' || task.status === 'cancelled'
                return (
                  <div key={task.taskId} className="flex items-center justify-between gap-3 py-2.5">
                    <div className="flex min-w-0 items-center gap-2">
                      {isCompleted ? <CheckCircle2 className="h-4 w-4 text-success" /> : isFailed ? <XCircle className="h-4 w-4 text-error" /> : <RefreshCw className="h-4 w-4 animate-spin text-info" />}
                      <span className="truncate text-sm text-text-primary">#{task.taskId} {task.taskName}</span>
                    </div>
                    <Badge variant={isCompleted ? 'success' : isFailed ? 'error' : 'warning'} size="sm">
                      {isCompleted ? '已完成' : isFailed ? '失败' : '运行中'}
                    </Badge>
                  </div>
                )
              })
            )}
          </div>
        </Card>
      </div>

      <Card padding="md" className="border-primary/20 bg-primary/5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3">
            <ListChecks className="mt-0.5 h-5 w-5 flex-shrink-0 text-primary" />
            <div>
              <p className="text-sm font-semibold text-text-primary">需要执行诊断？</p>
              <p className="mt-1 text-xs text-text-secondary">系统诊断页用于内部排查，不作为日常运维入口。</p>
            </div>
          </div>
          <Link to="/monitoring" className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:text-primary-dark">
            进入运行监控
            <ArrowUpRight className="h-4 w-4" />
          </Link>
        </div>
      </Card>
    </div>
  )
}
