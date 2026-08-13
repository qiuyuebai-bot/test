import { Link } from 'react-router-dom'
import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  CheckCircle2,
  ListChecks,
  RefreshCw,
  Users,
} from 'lucide-react'
import Badge from '@/components/Badge'
import Button from '@/components/Button'
import Card from '@/components/Card'
import EmptyState from '@/components/EmptyState'
import ErrorState from '@/components/ErrorState'
import { PageSkeleton } from '@/components/Skeleton'
import type { TeacherDashboardData } from '@/api/dashboard'

interface TeacherDashboardProps {
  data: TeacherDashboardData | null
  loading: boolean
  error: string | null
  onRetry: () => void
}

function ModuleError({ label, onRetry }: { label: string; onRetry: () => void }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-warning/30 bg-warning-light px-3 py-2 text-xs text-warning-dark">
      <span>{label}暂时不可用</span>
      <button
        type="button"
        className="inline-flex items-center gap-1 font-medium hover:text-text-primary"
        onClick={onRetry}
      >
        <RefreshCw className="h-3.5 w-3.5" />
        重试
      </button>
    </div>
  )
}

function progressLabel(value: number | null | undefined): string {
  return typeof value === 'number' ? `${value.toFixed(0)}%` : '暂无数据'
}

export default function TeacherDashboard({ data, loading, error, onRetry }: TeacherDashboardProps) {
  if (loading && !data) return <PageSkeleton type="dashboard" />
  if (error && !data) {
    return (
      <ErrorState
        title="培训管理台加载失败"
        description="班级学习数据暂时无法读取，请稍后重试。"
        details={error}
        onRetry={onRetry}
      />
    )
  }
  if (!data)
    return (
      <EmptyState
        type="users"
        title="暂无授权学习者"
        description="当前账号暂时没有可查看的学习者数据。"
      />
    )

  const { summary } = data
  const learnerError = Boolean(data.moduleErrors.learners)
  const riskError = Boolean(data.moduleErrors.risk)
  const taskError = Boolean(data.moduleErrors.tasks)
  const blindAreaError = Boolean(data.moduleErrors.blindAreas)

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <p className="text-sm font-medium text-primary">培训管理台</p>
          <h1 className="mt-1 text-2xl font-semibold text-text-primary">班级学习进度</h1>
          <p className="mt-1 text-sm text-text-secondary">
            聚焦授权范围内的学习者、风险信号和停滞任务。
          </p>
        </div>
        <Button variant="outline" onClick={onRetry} disabled={loading}>
          <RefreshCw className={loading ? 'h-4 w-4 animate-spin' : 'h-4 w-4'} />
          刷新数据
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Card padding="md">
          <div className="flex items-center gap-3">
            <Users className="h-5 w-5 text-primary" />
            <div>
              <p className="text-2xl font-semibold text-text-primary">{summary.totalLearners}</p>
              <p className="text-xs text-text-tertiary">授权学习者</p>
            </div>
          </div>
        </Card>
        <Card padding="md">
          <div className="flex items-center gap-3">
            <BarChart3 className="h-5 w-5 text-info" />
            <div>
              <p className="text-2xl font-semibold text-text-primary">
                {progressLabel(summary.averageProgress)}
              </p>
              <p className="text-xs text-text-tertiary">平均进度</p>
            </div>
          </div>
        </Card>
        <Card padding="md">
          <div className="flex items-center gap-3">
            <AlertTriangle className="h-5 w-5 text-warning" />
            <div>
              <p className="text-2xl font-semibold text-text-primary">{summary.atRiskCount}</p>
              <p className="text-xs text-text-tertiary">待关注学习者</p>
            </div>
          </div>
        </Card>
        <Card padding="md">
          <div className="flex items-center gap-3">
            <ListChecks className="h-5 w-5 text-success" />
            <div>
              <p className="text-2xl font-semibold text-text-primary">{summary.pendingTaskCount}</p>
              <p className="text-xs text-text-tertiary">待处理任务</p>
            </div>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(300px,0.8fr)]">
        <Card padding="none">
          <div className="flex items-center justify-between border-b border-border px-5 py-4">
            <div>
              <h2 className="font-semibold text-text-primary">学习者进度</h2>
              <p className="mt-1 text-xs text-text-tertiary">
                数据范围：{data.scope.learnerCount} 位授权学习者
              </p>
            </div>
            <Link
              to="/profile"
              className="text-xs font-medium text-primary hover:text-primary-dark"
            >
              打开画像
            </Link>
          </div>
          <div className="overflow-x-auto">
            {learnerError ? (
              <div className="p-4">
                <ModuleError label="学习者列表" onRetry={onRetry} />
              </div>
            ) : data.learners.length > 0 ? (
              <table className="w-full min-w-[620px]">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-text-tertiary">
                    <th className="px-5 py-3 font-medium">学习者</th>
                    <th className="px-5 py-3 font-medium">进度</th>
                    <th className="px-5 py-3 font-medium">盲区</th>
                    <th className="px-5 py-3 font-medium">待处理</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {data.learners.slice(0, 8).map((learner) => (
                    <tr key={learner.id} className="hover:bg-bg-secondary/50">
                      <td className="px-5 py-3">
                        <div className="flex items-center gap-2.5">
                          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-sm font-medium text-primary">
                            {(learner.realName || '学').slice(0, 1)}
                          </div>
                          <div>
                            <p className="text-sm font-medium text-text-primary">
                              {learner.realName || `学习者 #${learner.id}`}
                            </p>
                            <p className="text-xs text-text-tertiary">
                              {learner.major || '未设置专业'}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-3">
                        <div className="flex items-center gap-2">
                          <div className="h-1.5 w-20 overflow-hidden rounded-full bg-bg-tertiary">
                            <div
                              className="h-full rounded-full bg-primary"
                              style={{ width: `${Math.min(100, Math.max(0, learner.progress))}%` }}
                            />
                          </div>
                          <span className="text-xs font-medium text-text-primary">
                            {progressLabel(learner.progress)}
                          </span>
                        </div>
                      </td>
                      <td className="px-5 py-3">
                        <div className="flex max-w-[180px] flex-wrap gap-1">
                          {(learner.knowledgeBlindAreas || []).slice(0, 2).map((area) => (
                            <Badge key={area} variant="warning" size="sm">
                              {area}
                            </Badge>
                          ))}
                          {(learner.knowledgeBlindAreas || []).length === 0 && (
                            <span className="text-xs text-text-tertiary">暂无</span>
                          )}
                        </div>
                      </td>
                      <td className="px-5 py-3 text-sm text-text-primary">
                        {learner.pendingTaskCount}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <EmptyState
                type="users"
                title="暂无授权学习者"
                description="当前账号暂时没有可查看的学习者数据。"
              />
            )}
          </div>
        </Card>

        <Card padding="none">
          <div className="flex items-center justify-between border-b border-border px-5 py-4">
            <div>
              <h2 className="font-semibold text-text-primary">待关注学习者</h2>
              <p className="mt-1 text-xs text-text-tertiary">优先查看进度停滞或盲区较多的学习者</p>
            </div>
            <AlertTriangle className="h-4 w-4 text-warning" />
          </div>
          <div className="space-y-3 p-4">
            {riskError ? (
              <ModuleError label="风险学习者" onRetry={onRetry} />
            ) : data.atRiskLearners.length > 0 ? (
              data.atRiskLearners.map((learner) => (
                <div
                  key={learner.id}
                  className="flex items-start gap-3 rounded-lg border border-border p-3"
                >
                  <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-warning-light">
                    <AlertTriangle className="h-4 w-4 text-warning" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-text-primary">
                      {learner.name || `学习者 #${learner.id}`}
                    </p>
                    <p className="mt-1 text-xs text-text-tertiary">
                      进度 {progressLabel(learner.progress)} · 最近活跃{' '}
                      {learner.lastActiveAt ? learner.lastActiveAt.slice(0, 10) : '暂无'}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-1">
                      {learner.blindAreas.map((area) => (
                        <Badge key={area} variant="warning" size="sm">
                          {area}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  <Link
                    to="/profile"
                    aria-label={`查看${learner.name || `学习者 #${learner.id}`}画像`}
                    className="text-text-tertiary hover:text-primary"
                  >
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                </div>
              ))
            ) : (
              <div className="py-6 text-center text-sm text-text-tertiary">
                当前没有待关注学习者。
              </div>
            )}
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Card padding="none">
          <div className="flex items-center justify-between border-b border-border px-5 py-4">
            <div>
              <h2 className="font-semibold text-text-primary">停滞任务</h2>
              <p className="mt-1 text-xs text-text-tertiary">当前授权范围内需要跟进的任务</p>
            </div>
            <ListChecks className="h-4 w-4 text-text-tertiary" />
          </div>
          <div className="space-y-2 p-4">
            {taskError ? (
              <ModuleError label="停滞任务" onRetry={onRetry} />
            ) : data.stalledTasks.length > 0 ? (
              data.stalledTasks.slice(0, 5).map((task) => (
                <div
                  key={task.taskId}
                  className="flex items-center gap-3 rounded-lg bg-bg-secondary/60 p-3"
                >
                  <div
                    className={`h-2.5 w-2.5 rounded-full ${task.status === 'failed' ? 'bg-error' : 'bg-warning'}`}
                  />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm text-text-primary">{task.taskName}</p>
                    <p className="mt-1 text-xs text-text-tertiary">
                      {task.flowDescription || task.status} · {task.progress.toFixed(0)}%
                    </p>
                  </div>
                  <Badge variant={task.status === 'failed' ? 'error' : 'warning'} size="sm">
                    {task.status === 'failed' ? '失败' : '处理中'}
                  </Badge>
                </div>
              ))
            ) : (
              <div className="py-6 text-center text-sm text-text-tertiary">当前没有停滞任务。</div>
            )}
          </div>
        </Card>

        <Card padding="none">
          <div className="flex items-center justify-between border-b border-border px-5 py-4">
            <div>
              <h2 className="font-semibold text-text-primary">知识盲区分布</h2>
              <p className="mt-1 text-xs text-text-tertiary">按当前授权列表聚合</p>
            </div>
            <CheckCircle2 className="h-4 w-4 text-text-tertiary" />
          </div>
          <div className="space-y-3 p-4">
            {blindAreaError ? (
              <ModuleError label="盲区分布" onRetry={onRetry} />
            ) : data.blindAreaDistribution.length > 0 ? (
              data.blindAreaDistribution.map((item) => (
                <div key={item.topic} className="flex items-center gap-3">
                  <span className="w-28 truncate text-sm text-text-secondary">{item.topic}</span>
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-bg-tertiary">
                    <div
                      className="h-full rounded-full bg-warning"
                      style={{
                        width: `${Math.min(100, (item.count / Math.max(1, data.blindAreaDistribution[0]?.count || 1)) * 100)}%`,
                      }}
                    />
                  </div>
                  <span className="w-8 text-right text-sm font-medium text-text-primary">
                    {item.count}
                  </span>
                </div>
              ))
            ) : (
              <div className="py-6 text-center text-sm text-text-tertiary">
                当前没有知识盲区数据。
              </div>
            )}
          </div>
        </Card>
      </div>
    </div>
  )
}
