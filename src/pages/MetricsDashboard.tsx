import { useState, useEffect, useCallback } from 'react'
import { useStore } from '@/store'
import { useShallow } from 'zustand/react/shallow'
import Card from '@/components/Card'
import Badge from '@/components/Badge'
import Progress from '@/components/Progress'
import { PageSkeleton } from '@/components/Skeleton'
import EmptyState from '@/components/EmptyState'
import ErrorState from '@/components/ErrorState'
import { CHART_COLORS, CHART_TOOLTIP_PROPS } from '@/lib/chartTheme'
import {
  TrendingUp,
  Target,
  Brain,
  AlertTriangle,
  CheckCircle,
  BarChart3,
  LineChart as LineChartIcon,
  Users,
  Clock,
  Activity,
} from 'lucide-react'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Legend,
} from 'recharts'

const RESOURCE_MATCH_MIN_SAMPLE_SIZE = 5

function formatMetricUpdatedAt(value?: string): string {
  if (!value) return '暂无'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '暂无'
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export default function MetricsDashboard() {
  const { systemMetrics, metricsLoading, metricsError, metricsStatus } = useStore(
    useShallow((s) => ({
      systemMetrics: s.systemMetrics,
      metricsLoading: s.metricsLoading,
      metricsError: s.metricsError,
      metricsStatus: s.metricsStatus,
    }))
  )
  const fetchSystemMetrics = useStore((s) => s.fetchSystemMetrics)
  const [error, setError] = useState<string | null>(null)
  const [loaded, setLoaded] = useState(false)

  const loadMetrics = useCallback(async () => {
    setError(null)
    try {
      await fetchSystemMetrics()
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载指标失败')
    } finally {
      setLoaded(true)
    }
  }, [fetchSystemMetrics])

  useEffect(() => {
    loadMetrics()
  }, [loadMetrics])

  const rawHallucinationRate = systemMetrics?.hallucinationRate
  const hasSufficientHallucinationSample = systemMetrics?.hasSufficientSample === true && typeof rawHallucinationRate === 'number'
  const hallucinationRate = systemMetrics?.hasSufficientSample === true && typeof rawHallucinationRate === 'number'
    ? rawHallucinationRate
    : null
  const hallucinationRateLabel = hasSufficientHallucinationSample
    ? `${(hallucinationRate ?? 0).toFixed(1)}%`
    : '样本不足/待审核'
  const rawResourceMatchAccuracy = systemMetrics?.resourceMatchAccuracy ?? null
  const resourceMatchSampleCount = systemMetrics?.totalResources ?? 0
  const hasSufficientResourceMatchSample = resourceMatchSampleCount >= RESOURCE_MATCH_MIN_SAMPLE_SIZE
  const hasResourceMatchData = hasSufficientResourceMatchSample && rawResourceMatchAccuracy !== null
  const resourceMatchAccuracy = hasResourceMatchData ? rawResourceMatchAccuracy : null
  const resourceMatchUpdatedAt = formatMetricUpdatedAt(systemMetrics?.calculatedAt)
  const knowledgeCoverageRate = systemMetrics?.knowledgeCoverageRate ?? null
  const trendData = systemMetrics?.trends ?? []

  const metricCards = [
    {
      label: '幻觉率',
      value: hallucinationRateLabel,
      isPending: !hasSufficientHallucinationSample,
      pendingLabel: '样本不足/待审核',
      target: '< 5%',
      isOnTarget: hasSufficientHallucinationSample && (hallucinationRate ?? 0) < 5,
      icon: AlertTriangle,
      color: 'text-success',
      bgColor: 'bg-success/10',
      progressValue: hallucinationRate ?? 0,
      progressMax: 10,
      progressVariant: 'success' as const,
      description: '衡量生成内容与知识库事实的偏离程度。通过内容审核裁判 Agent 交叉验证计算得出。',
      targetText: '行业优秀水平: < 5%',
    },
    {
      label: '资源匹配准确率',
      value: resourceMatchAccuracy === null ? '暂无数据' : `${resourceMatchAccuracy.toFixed(1)}%`,
      isPending: !hasResourceMatchData,
      pendingLabel: '待采集',
      target: '> 90%',
      isOnTarget: resourceMatchAccuracy !== null && resourceMatchAccuracy >= 90,
      icon: Target,
      color: 'text-primary',
      bgColor: 'bg-primary/10',
      progressValue: resourceMatchAccuracy ?? 0,
      progressMax: 100,
      progressVariant: 'default' as const,
      description: '衡量生成资源与学习者需求的匹配程度。基于用户反馈和测试结果持续优化。',
      targetText: '目标值: > 90%',
      showSampleMetadata: true,
    },
    {
      label: '知识点覆盖率',
      value: knowledgeCoverageRate === null ? '暂无数据' : `${knowledgeCoverageRate.toFixed(1)}%`,
      isPending: knowledgeCoverageRate === null,
      pendingLabel: '暂无数据',
      target: '> 85%',
      isOnTarget: knowledgeCoverageRate !== null && knowledgeCoverageRate >= 85,
      icon: Brain,
      color: 'text-info',
      bgColor: 'bg-info/10',
      progressValue: knowledgeCoverageRate ?? 0,
      progressMax: 100,
      progressVariant: 'default' as const,
      description: '衡量知识库对目标领域知识点的覆盖程度。通过知识点图谱自动分析计算。',
      targetText: '目标值: > 85%',
    },
  ]

  if (metricsLoading && !loaded) {
    return <PageSkeleton type="dashboard" />
  }

  if (error || (metricsStatus === 'error' && !systemMetrics)) {
    return <ErrorState type="default" onRetry={() => loadMetrics()} />
  }

  if (!systemMetrics) {
    return <EmptyState type="default" title="暂无指标数据" description="请稍后重试或检查后端服务" />
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {metricsError && metricsStatus === 'partial' && (
        <div className="rounded-lg border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning">
          {metricsError}，页面已显示可用数据。
        </div>
      )}
      {/* 核心指标卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {metricCards.map((metric) => (
          <Card key={metric.label} padding="lg">
            <div className="flex items-start justify-between mb-4">
              <div className={`${metric.bgColor} p-3 rounded-xl`}>
                <metric.icon className={`w-6 h-6 ${metric.color}`} />
              </div>
              <Badge variant={metric.isPending ? 'default' : metric.isOnTarget ? 'success' : 'warning'} size="sm">
                {metric.isPending ? <Clock className="w-3 h-3 mr-1" /> : <CheckCircle className="w-3 h-3 mr-1" />}
                {metric.isPending ? metric.pendingLabel : metric.isOnTarget ? '达标' : '待优化'}
              </Badge>
            </div>
            <p className="metric-number text-3xl font-semibold text-text-primary mb-1">{metric.value}</p>
            <p className="text-sm text-text-secondary mb-3">{metric.label}</p>
            <div className="flex items-center justify-between">
              <span className="text-xs text-text-tertiary">目标: {metric.target}</span>
              <span className="text-xs text-text-tertiary">{metric.targetText}</span>
            </div>
            {'showSampleMetadata' in metric && metric.showSampleMetadata && (
              <div className="mt-3 space-y-1 text-xs text-text-tertiary">
                <p>样本数：{resourceMatchSampleCount}（至少 {RESOURCE_MATCH_MIN_SAMPLE_SIZE}）</p>
                <p>更新时间：{resourceMatchUpdatedAt}</p>
              </div>
            )}
          </Card>
        ))}
      </div>

      {/* 指标趋势图 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card padding="none">
          <div className="p-6 border-b border-border">
            <div className="flex items-center gap-2">
              <LineChartIcon className="w-5 h-5 text-text-secondary" />
              <h3 className="font-semibold text-text-primary">指标月度趋势</h3>
            </div>
          </div>
          <div className="p-6 h-[300px]">
            {trendData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trendData}>
                  <defs>
                    <linearGradient id="colorHallucination" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="var(--color-error)" stopOpacity={0.2} />
                      <stop offset="95%" stopColor="var(--color-error)" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="colorAccuracy" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={CHART_COLORS.primary} stopOpacity={0.2} />
                      <stop offset="95%" stopColor={CHART_COLORS.primary} stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="colorCoverage" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={CHART_COLORS.secondary} stopOpacity={0.2} />
                      <stop offset="95%" stopColor={CHART_COLORS.secondary} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} />
                  <XAxis dataKey="date" tick={{ fontSize: 12, fill: CHART_COLORS.text }} />
                  <YAxis tick={{ fontSize: 12, fill: CHART_COLORS.text }} />
                  <Tooltip {...CHART_TOOLTIP_PROPS} />
                  <Legend />
                  <Area
                    type="monotone"
                    dataKey="hallucinationRate"
                    name="幻觉率"
                    stroke="var(--color-error)"
                    fillOpacity={1}
                    fill="url(#colorHallucination)"
                  />
                  <Area
                    type="monotone"
                    dataKey="resourceMatchAccuracy"
                    name="资源匹配准确率"
                    stroke={CHART_COLORS.primary}
                    fillOpacity={1}
                    fill="url(#colorAccuracy)"
                  />
                  <Area
                    type="monotone"
                    dataKey="knowledgeCoverageRate"
                    name="知识点覆盖率"
                    stroke={CHART_COLORS.secondary}
                    fillOpacity={1}
                    fill="url(#colorCoverage)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center">
                <EmptyState type="default" title="暂无趋势数据" description="系统运行后将自动生成月度趋势" />
              </div>
            )}
          </div>
        </Card>

        <Card padding="none">
          <div className="p-6 border-b border-border">
            <div className="flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-text-secondary" />
              <h3 className="font-semibold text-text-primary">指标对比</h3>
            </div>
          </div>
          <div className="p-6 h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={[
                  {
                    name: '当前指标',
                    hallucinationRate: hallucinationRate,
                    resourceMatchAccuracy: resourceMatchAccuracy,
                    knowledgeCoverageRate: knowledgeCoverageRate,
                  },
                ]}
                layout="vertical"
              >
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} />
                <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 12, fill: CHART_COLORS.text }} />
                <YAxis dataKey="name" type="category" tick={{ fontSize: 12, fill: CHART_COLORS.text }} width={70} />
                <Tooltip {...CHART_TOOLTIP_PROPS} />
                <Legend />
                <Bar dataKey="hallucinationRate" name="幻觉率" fill="var(--color-error)" radius={[0, 4, 4, 0]} />
                <Bar dataKey="resourceMatchAccuracy" name="资源匹配准确率" fill={CHART_COLORS.primary} radius={[0, 4, 4, 0]} />
                <Bar dataKey="knowledgeCoverageRate" name="知识点覆盖率" fill={CHART_COLORS.secondary} radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      {/* 系统运行统计 */}
      <Card padding="md">
        <h2 className="text-lg font-semibold text-text-primary mb-4">系统运行统计</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl bg-bg-secondary/50">
            <div className="flex items-center gap-2 mb-2">
              <Users className="w-4 h-4 text-success" />
              <span className="text-sm text-text-secondary">总学习者</span>
            </div>
            <p className="metric-number text-2xl font-semibold text-text-primary">{systemMetrics.totalLearners}</p>
          </div>
          <div className="p-4 rounded-xl bg-bg-secondary/50">
            <div className="flex items-center gap-2 mb-2">
              <Activity className="w-4 h-4 text-primary" />
              <span className="text-sm text-text-secondary">活跃会话</span>
            </div>
            <p className="metric-number text-2xl font-semibold text-text-primary">{systemMetrics.activeSessions ?? 0}</p>
          </div>
          <div className="p-4 rounded-xl bg-bg-secondary/50">
            <div className="flex items-center gap-2 mb-2">
              <Clock className="w-4 h-4 text-info" />
              <span className="text-sm text-text-secondary">平均完成时间</span>
            </div>
            <p className="metric-number text-2xl font-semibold text-text-primary">{systemMetrics.avgCompletionTime ?? '-'}</p>
          </div>
          <div className="p-4 rounded-xl bg-bg-secondary/50">
            <div className="flex items-center gap-2 mb-2">
              <CheckCircle className="w-4 h-4 text-success" />
              <span className="text-sm text-text-secondary">满意度评分</span>
            </div>
            <p className="metric-number text-2xl font-semibold text-text-primary">{systemMetrics.satisfactionScore ?? 0} / 5.0</p>
          </div>
        </div>
      </Card>

      {/* 指标详细说明 */}
      <Card padding="md">
        <h2 className="text-lg font-semibold text-text-primary mb-4">指标详细说明</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {metricCards.map((metric) => (
            <div key={metric.label} className="p-4 rounded-xl border border-border">
              <div className="flex items-center gap-2 mb-3">
                <metric.icon className={`w-5 h-5 ${metric.color}`} />
                <span className="font-medium text-text-primary">{metric.label}</span>
              </div>
              <p className="text-sm text-text-secondary mb-3">{metric.description}</p>
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-text-tertiary">当前值</span>
                  <span className={`font-medium ${metric.color}`}>{metric.value}</span>
                </div>
                <Progress
                  value={metric.progressValue}
                  max={metric.progressMax}
                  size="sm"
                  variant={metric.progressVariant}
                />
                <p className="text-xs text-text-tertiary">{metric.targetText}</p>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* 系统任务统计 */}
      <Card padding="md">
        <h2 className="text-lg font-semibold text-text-primary mb-4">系统任务统计</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl bg-bg-secondary/50">
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="w-4 h-4 text-primary" />
              <span className="text-sm text-text-secondary">总任务数</span>
            </div>
            <p className="metric-number text-2xl font-semibold text-text-primary">{systemMetrics.totalTasks ?? 0}</p>
          </div>
          <div className="p-4 rounded-xl bg-bg-secondary/50">
            <div className="flex items-center gap-2 mb-2">
              <CheckCircle className="w-4 h-4 text-success" />
              <span className="text-sm text-text-secondary">已完成</span>
            </div>
            <p className="metric-number text-2xl font-semibold text-text-primary">{systemMetrics.tasksCompleted ?? 0}</p>
          </div>
          <div className="p-4 rounded-xl bg-bg-secondary/50">
            <div className="flex items-center gap-2 mb-2">
              <BarChart3 className="w-4 h-4 text-info" />
              <span className="text-sm text-text-secondary">生成资源数</span>
            </div>
            <p className="metric-number text-2xl font-semibold text-text-primary">{systemMetrics.totalResources}</p>
          </div>
          <div className="p-4 rounded-xl bg-bg-secondary/50">
            <div className="flex items-center gap-2 mb-2">
              <Activity className="w-4 h-4 text-primary" />
              <span className="text-sm text-text-secondary">平均响应时间</span>
            </div>
            <p className="metric-number text-2xl font-semibold text-text-primary">
              {systemMetrics.avgResponseTime ? `${systemMetrics.avgResponseTime.toFixed(0)}ms` : '-'}
            </p>
          </div>
        </div>
      </Card>
    </div>
  )
}
