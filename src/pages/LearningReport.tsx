import { useState, useEffect, useCallback } from 'react'
import { useStore } from '@/store'
import Card from '@/components/Card'
import Badge from '@/components/Badge'
import { SCORE_EXCELLENT_THRESHOLD, SCORE_GOOD_THRESHOLD } from '@/lib/constants'
import {
  Activity,
  TrendingUp,
  Target,
  Brain,
  AlertTriangle,
  CheckCircle2,
  Download,
  Printer,
  FileText,
  Zap,
  BookOpen,
  ChevronRight,
  Lock,
  Play,
  Circle,
  Users,
  Crosshair,
} from 'lucide-react'
import LoadingState from '@/components/LoadingState'
import EmptyState from '@/components/EmptyState'
import ErrorState from '@/components/ErrorState'
import { coreApi } from '@/api'
import {
  RadarChart as RechartsRadar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Area,
  AreaChart,
} from 'recharts'

// 严重度 → 颜色映射
const SEVERITY_COLOR_MAP: Record<string, string> = {
  high: '#ef4444',
  medium: '#f59e0b',
  low: '#3d5a80',
}

// 节点状态图标配置
const statusConfig = {
  completed: { icon: CheckCircle2, color: 'text-success' },
  current: { icon: Play, color: 'text-primary' },
  next: { icon: Circle, color: 'text-amber-500' },
  locked: { icon: Lock, color: 'text-text-tertiary' },
}

// 难度等级 → 类型配置
const difficultyTypeConfig: Record<number, { label: string; color: string }> = {
  1: { label: '基础', color: 'bg-success/10 border-success/30 text-success' },
  2: { label: '基础', color: 'bg-success/10 border-success/30 text-success' },
  3: { label: '进阶', color: 'bg-primary/10 border-primary/30 text-primary' },
  4: { label: '进阶', color: 'bg-primary/10 border-primary/30 text-primary' },
  5: { label: '高阶', color: 'bg-amber-50 border-amber-200 text-amber-600' },
}

interface AbilityRadarPoint {
  dimension: string
  score: number
  fullMark: number
}

interface HeatmapItem {
  dimension: string
  dimension_key: string
  severity: string
  severity_label: string
  value: number
  score: number
  is_blind: boolean
  description: string
}

interface LearningPathNode {
  id: string
  name: string
  difficulty: number
  status: string
  estimated_time: string
  resources: Array<string | { title?: string; name?: string }>
  description: string
}

interface MatchCurvePoint {
  difficulty: number
  recommended: number
  actual: number
}

interface TestHistoryItem {
  record_id: number
  question_topic: string | null
  question_type: string
  question_difficulty: number
  result: string
  score: number
  time_spent_ms: number
  agent_decision: string | null
  created_at: string | null
}

// 后端 /report/learner/{id} 聚合接口实际响应结构
interface LearnerReportData {
  success: boolean
  learner_info?: {
    id: number
    name: string
    education: string
    major: string
    learning_style: string
    target_industry: string
    target_position: string
  }
  blind_area_heatmap?: {
    labels: string[]
    data: HeatmapItem[]
  }
  difficulty_match_curve?: {
    data: MatchCurvePoint[]
    learner_ability_raw: number
  }
  learning_path_topology?: {
    total_steps: number
    current_step: number
    progress: number
    estimated_total_time: string
    nodes: LearningPathNode[]
  }
  ability_radar?: {
    dimensions: string[]
    data: AbilityRadarPoint[]
    average_score: number
  }
  core_metrics?: {
    resource_match_accuracy: number
    knowledge_coverage_rate: number
    answer_accuracy: number
  }
  statistics?: {
    total_resources: number
    total_answers: number
    avg_answer_score: number
    knowledge_blind_count: number
  }
}

// 测试结果 → 评估文案
function getScoreStatus(score: number): { label: string; variant: 'success' | 'warning' | 'error' } {
  if (score >= SCORE_EXCELLENT_THRESHOLD) return { label: '优秀', variant: 'success' }
  if (score >= SCORE_GOOD_THRESHOLD) return { label: '良好', variant: 'warning' }
  return { label: '需提升', variant: 'error' }
}

// 测试日期格式化
function formatTestDate(isoString: string | null): string {
  if (!isoString) return '-'
  try {
    const d = new Date(isoString)
    if (isNaN(d.getTime())) return isoString.slice(0, 10)
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  } catch {
    return isoString.slice(0, 10)
  }
}

export default function LearningReport() {
  const currentLearner = useStore((s) => s.currentLearner)
  const learners = useStore((s) => s.learners)
  const learner = currentLearner || learners[0]
  const [selectedNode, setSelectedNode] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [report, setReport] = useState<LearnerReportData | null>(null)
  const [testHistory, setTestHistory] = useState<TestHistoryItem[]>([])
  const [systemHallucinationRate, setSystemHallucinationRate] = useState(0)
  const [abilityTrendData, setAbilityTrendData] = useState<{ week: string; score: number }[]>([])

  const loadReport = useCallback(async () => {
    if (!learner?.id) {
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const [reportData, historyData, sysMetrics, abilityTrend] = await Promise.all([
        coreApi.getLearnerReport(learner.id).catch(() => null),
        coreApi.getInteractionHistory(learner.id).catch(() => ({ items: [] as TestHistoryItem[] })),
        coreApi.getSystemMetrics().catch(() => null),
        coreApi.getAbilityTrend(learner.id).catch(() => []),
      ])
      setReport((reportData as LearnerReportData | null) ?? null)
      setTestHistory((historyData?.items as TestHistoryItem[]) ?? [])
      setAbilityTrendData((abilityTrend as { week: string; score: number }[]) ?? [])
      if (sysMetrics?.hallucinationRate !== undefined) {
        setSystemHallucinationRate(sysMetrics.hallucinationRate)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载报告数据失败')
    } finally {
      setLoading(false)
    }
  }, [learner?.id])

  useEffect(() => {
    loadReport()
  }, [loadReport])

  if (loading) return <LoadingState.Analyzing />
  if (error) return <ErrorState type="default" onRetry={() => { setError(null); loadReport() }} />
  if (!learner) return <EmptyState type="default" title="暂无报告数据" description="请先选择学习者以生成报告" />

  // 衍生数据
  const heatmapData = report?.blind_area_heatmap?.data ?? []
  const matchCurveData = report?.difficulty_match_curve?.data ?? []
  const learningPathNodes = report?.learning_path_topology?.nodes ?? []
  const abilityRadarData = report?.ability_radar?.data ?? []
  const learnerInfo = report?.learner_info
  const coreMetrics = report?.core_metrics
  const statistics = report?.statistics

  const stats = {
    knowledgeCoverage: coreMetrics?.knowledge_coverage_rate ?? 0,
    resourceMatch: coreMetrics?.resource_match_accuracy ?? 0,
    hallucinationRate: systemHallucinationRate ?? 0,
    totalResources: statistics?.total_resources ?? 0,
    completedTasks: Math.max(0, (report?.learning_path_topology?.current_step ?? 0)),
    pendingTasks: Math.max(0, (report?.learning_path_topology?.total_steps ?? 0) - (report?.learning_path_topology?.current_step ?? 0)),
  }

  const radarChartData = abilityRadarData.map((item) => ({
    subject: item.dimension,
    score: item.score,
  }))

  const matchCurveChartData = matchCurveData.length > 0
    ? matchCurveData
    : []

  const displayName = learnerInfo?.name || learner?.realName || '-'
  const displayEducation = learnerInfo?.education || learner?.educationLevel || '-'
  const displayMajor = learnerInfo?.major || learner?.major || '-'

  return (
    <div className="space-y-5 animate-fade-in">
      {/* 顶部统计指标栏 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card padding="md" className="hover:shadow-soft transition-all">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-success/10 flex items-center justify-center">
              <Target className="w-5 h-5 text-success" />
            </div>
            <div>
              <p className="text-xl font-semibold text-text-primary">{stats.knowledgeCoverage.toFixed(1)}%</p>
              <p className="text-xs text-text-tertiary">知识点覆盖率</p>
            </div>
          </div>
        </Card>
        <Card padding="md" className="hover:shadow-soft transition-all">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
              <Zap className="w-5 h-5 text-primary" />
            </div>
            <div>
              <p className="text-xl font-semibold text-text-primary">{stats.resourceMatch.toFixed(1)}%</p>
              <p className="text-xs text-text-tertiary">资源匹配准确率</p>
            </div>
          </div>
        </Card>
        <Card padding="md" className="hover:shadow-soft transition-all">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-amber-50 flex items-center justify-center">
              <Crosshair className="w-5 h-5 text-amber-500" />
            </div>
            <div>
              <p className="text-xl font-semibold text-text-primary">{stats.hallucinationRate.toFixed(1)}%</p>
              <p className="text-xs text-text-tertiary">知识幻觉错误率</p>
            </div>
          </div>
        </Card>
        <Card padding="md" className="hover:shadow-soft transition-all">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-info/10 flex items-center justify-center">
              <BookOpen className="w-5 h-5 text-info" />
            </div>
            <div>
              <p className="text-xl font-semibold text-text-primary">{stats.totalResources}</p>
              <p className="text-xs text-text-tertiary">已生成资源数</p>
            </div>
          </div>
        </Card>
      </div>

      {/* 学习者信息与操作栏 */}
      <Card padding="md">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-xl bg-primary/10 flex items-center justify-center">
              <span className="text-xl font-semibold text-primary">{displayName.slice(0, 1)}</span>
            </div>
            <div>
              <h2 className="text-lg font-semibold text-text-primary">{displayName}</h2>
              <p className="text-sm text-text-secondary">{displayEducation} · {displayMajor}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm text-text-secondary hover:bg-bg-secondary transition-colors">
              <Printer className="w-4 h-4" />
              打印报告
            </button>
            <button className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary/10 text-primary text-sm font-medium hover:bg-primary/20 transition-colors">
              <Download className="w-4 h-4" />
              导出 PDF
            </button>
          </div>
        </div>
      </Card>

      {/* 三大分区主区域 */}
      <div className="grid grid-cols-12 gap-4">
        {/* 分区一：整体学情总览 */}
        <div className="col-span-12 lg:col-span-4 space-y-4">
          <Card padding="none">
            <div className="p-4 border-b border-border">
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-text-secondary" />
                <h3 className="text-sm font-semibold text-text-primary">知识能力雷达图</h3>
              </div>
            </div>
            <div className="p-4 h-[240px]">
              {radarChartData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <RechartsRadar data={radarChartData}>
                    <PolarGrid stroke="#e2e8f0" strokeWidth={1} />
                    <PolarAngleAxis dataKey="subject" tick={{ fontSize: 10, fill: '#64748b' }} tickLine={false} />
                    <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fontSize: 9, fill: '#94a3b8' }} tickCount={4} axisLine={false} />
                    <Radar name="能力" dataKey="score" stroke="#3d5a80" fill="#3d5a80" fillOpacity={0.15} strokeWidth={2} />
                  </RechartsRadar>
                </ResponsiveContainer>
              ) : (
                <div className="h-full flex items-center justify-center">
                  <EmptyState type="default" title="暂无能力数据" description="未获取到能力评估数据" />
                </div>
              )}
            </div>
          </Card>

          <Card padding="none">
            <div className="p-4 border-b border-border">
              <div className="flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-text-secondary" />
                <h3 className="text-sm font-semibold text-text-primary">能力发展趋势</h3>
              </div>
            </div>
            <div className="p-4 h-[180px]">
              {abilityTrendData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={abilityTrendData}>
                    <defs>
                      <linearGradient id="colorScore" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#3d5a80" stopOpacity={0.15} />
                        <stop offset="95%" stopColor="#3d5a80" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                    <XAxis dataKey="week" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} domain={[40, 100]} />
                    <Tooltip contentStyle={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 8, fontSize: 12 }} />
                    <Area type="monotone" dataKey="score" stroke="#3d5a80" strokeWidth={2} fill="url(#colorScore)" dot={{ fill: '#3d5a80', strokeWidth: 2, r: 3 }} />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full flex items-center justify-center">
                  <EmptyState type="default" title="暂无趋势数据" description="未获取到能力发展趋势" />
                </div>
              )}
            </div>
          </Card>

          {/* 学习进度概览 */}
          <Card padding="md">
            <h4 className="text-xs font-medium text-text-secondary mb-3">学习进度概览</h4>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-text-primary">已完成任务</span>
                <span className="text-sm font-semibold text-success">{stats.completedTasks}</span>
              </div>
              <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-success rounded-full transition-all"
                  style={{
                    width: `${report?.learning_path_topology?.progress ?? 0}%`,
                  }}
                />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-text-primary">进行中任务</span>
                <span className="text-sm font-semibold text-primary">{stats.pendingTasks}</span>
              </div>
              <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary rounded-full transition-all"
                  style={{
                    width: `${100 - (report?.learning_path_topology?.progress ?? 0)}%`,
                  }}
                />
              </div>
              <div className="flex items-center justify-between pt-1 text-xs text-text-tertiary">
                <span>总进度</span>
                <span>{report?.learning_path_topology?.progress?.toFixed(1) ?? 0}% · 预计 {report?.learning_path_topology?.estimated_total_time ?? '-'}</span>
              </div>
            </div>
          </Card>
        </div>

        {/* 分区二：数据曲线图表 */}
        <div className="col-span-12 lg:col-span-4 space-y-4">
          <Card padding="none">
            <div className="p-4 border-b border-border">
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-text-secondary" />
                <h3 className="text-sm font-semibold text-text-primary">资源难度匹配曲线</h3>
              </div>
              <p className="text-xs text-text-tertiary mt-1">学习者能力与资源难度匹配度分析</p>
            </div>
            <div className="p-4 h-[220px]">
              {matchCurveChartData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={matchCurveChartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                    <XAxis dataKey="difficulty" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} label={{ value: '难度等级', position: 'bottom', fontSize: 10, fill: '#94a3b8' }} />
                    <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} domain={[30, 100]} />
                    <Tooltip contentStyle={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 8, fontSize: 12 }} labelStyle={{ fontWeight: 500 }} />
                    <Line type="monotone" dataKey="recommended" stroke="#cbd5e1" strokeWidth={2} strokeDasharray="6 4" dot={false} name="推荐匹配度" />
                    <Line type="monotone" dataKey="actual" stroke="#3d5a80" strokeWidth={2.5} dot={{ fill: '#3d5a80', strokeWidth: 2, r: 4 }} name="实际匹配度" />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full flex items-center justify-center">
                  <EmptyState type="default" title="暂无匹配数据" description="完成答题后生成匹配曲线" />
                </div>
              )}
            </div>
            <div className="px-4 pb-4 flex items-center gap-4">
              <div className="flex items-center gap-1.5">
                <div className="w-6 h-0.5 bg-gray-300" style={{ backgroundImage: 'repeating-linear-gradient(90deg, #cbd5e1 0, #cbd5e1 6px, transparent 6px, transparent 10px)' }} />
                <span className="text-xs text-text-tertiary">推荐匹配</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-3 rounded-full bg-primary" />
                <span className="text-xs text-text-tertiary">实际匹配</span>
              </div>
            </div>
          </Card>

          {/* 知识盲区热力图 */}
          <Card padding="none">
            <div className="p-4 border-b border-border">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-500" />
                <h3 className="text-sm font-semibold text-text-primary">知识盲区热力定位</h3>
              </div>
              <p className="text-xs text-text-tertiary mt-1">点击色块可快速跳转学习资源</p>
            </div>
            <div className="p-4">
              {heatmapData.length > 0 ? (
                <div className="grid grid-cols-3 gap-2">
                  {heatmapData.map((item) => {
                    const color = SEVERITY_COLOR_MAP[item.severity] || '#5b8def'
                    return (
                      <button
                        key={item.dimension}
                        className="relative p-3 rounded-xl transition-all hover:scale-105 hover:shadow-soft cursor-pointer group"
                        style={{ backgroundColor: `${color}15`, border: `1px solid ${color}30` }}
                        onClick={() => {}}
                        title={item.description}
                      >
                        <div className="flex flex-col items-center gap-1">
                          <span className="text-xs font-medium" style={{ color }}>{item.score.toFixed(0)}</span>
                          <span className="text-xs text-text-secondary text-center leading-tight">{item.dimension}</span>
                          {item.is_blind && (
                            <span className="text-[9px] text-error">盲区</span>
                          )}
                        </div>
                        <div className="absolute inset-0 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center" style={{ backgroundColor: `${color}20` }}>
                          <ChevronRight className="w-4 h-4" style={{ color }} />
                        </div>
                      </button>
                    )
                  })}
                </div>
              ) : (
                <div className="py-6">
                  <EmptyState type="default" title="暂无热力图数据" description="未获取到知识盲区数据" />
                </div>
              )}
              <div className="mt-3 flex items-center justify-center gap-2 flex-wrap">
                <div className="flex items-center gap-1">
                  <div className="w-3 h-3 rounded bg-success/30" />
                  <span className="text-xs text-text-tertiary">掌握</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="w-3 h-3 rounded bg-primary/30" />
                  <span className="text-xs text-text-tertiary">良好</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="w-3 h-3 rounded bg-amber-50" />
                  <span className="text-xs text-text-tertiary">薄弱</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="w-3 h-3 rounded bg-red-50" />
                  <span className="text-xs text-text-tertiary">盲区</span>
                </div>
              </div>
            </div>
          </Card>

          {/* 测试历史趋势 */}
          <Card padding="md">
            <h4 className="text-xs font-medium text-text-secondary mb-3">近期测试成绩</h4>
            {testHistory.length > 0 ? (
              <div className="flex items-end justify-between gap-2">
                {testHistory.slice(0, 5).map((test, idx) => (
                  <div key={test.record_id} className="flex-1 flex flex-col items-center gap-1">
                    <div className="w-full flex flex-col items-center">
                      <span className="text-xs font-semibold text-text-primary">{test.score.toFixed(0)}</span>
                      <div className="w-full h-12 flex items-end">
                        <div
                          className={`w-full rounded-t-sm transition-all ${
                            test.score >= SCORE_EXCELLENT_THRESHOLD ? 'bg-success' : test.score >= SCORE_GOOD_THRESHOLD ? 'bg-primary' : 'bg-amber-500'
                          }`}
                          style={{ height: `${test.score}%` }}
                        />
                      </div>
                    </div>
                    <span className="text-xs text-text-tertiary">{idx + 1}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-6">
                <EmptyState type="default" title="暂无测试记录" description="完成答题后展示成绩趋势" />
              </div>
            )}
          </Card>
        </div>

        {/* 分区三：学习路径拓扑图 */}
        <div className="col-span-12 lg:col-span-4">
          <Card padding="none" className="h-full">
            <div className="p-4 border-b border-border">
              <div className="flex items-center gap-2">
                <Brain className="w-4 h-4 text-text-secondary" />
                <h3 className="text-sm font-semibold text-text-primary">个性化学习路径规划图</h3>
              </div>
              <p className="text-xs text-text-tertiary mt-1">基础 → 进阶 → 高阶完整路径</p>
            </div>
            <div className="p-4 space-y-3">
              {learningPathNodes.length > 0 ? (
                learningPathNodes.map((node, idx) => {
                  const typeConfig = difficultyTypeConfig[node.difficulty] || difficultyTypeConfig[3]
                  const statusKey = (node.status in statusConfig ? node.status : 'locked') as keyof typeof statusConfig
                  const statusIcon = statusConfig[statusKey]
                  const Icon = statusIcon.icon
                  const isSelected = selectedNode === node.id

                  return (
                    <div key={node.id} className="relative">
                      {idx < learningPathNodes.length - 1 && (
                        <div className={`absolute left-[18px] top-10 w-0.5 h-5 ${
                          node.status === 'completed' ? 'bg-primary/40' : 'bg-gray-200'
                        }`} />
                      )}
                      <div
                        className={`relative p-3 rounded-xl border transition-all cursor-pointer ${
                          isSelected
                            ? 'border-primary/40 bg-primary/5 shadow-soft'
                            : node.status === 'locked'
                            ? 'border-border/50 bg-bg-secondary/30 opacity-60'
                            : 'border-border/50 bg-bg-secondary/30 hover:border-primary/20 hover:bg-bg-secondary/50'
                        }`}
                        onClick={() => setSelectedNode(isSelected ? null : node.id)}
                      >
                        <div className="flex items-start gap-3">
                          <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                            node.status === 'completed'
                              ? 'bg-success/10'
                              : node.status === 'current'
                              ? 'bg-primary/10'
                              : 'bg-gray-100'
                          }`}>
                            <Icon className={`w-4 h-4 ${statusIcon.color}`} />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <span className={`text-sm font-medium ${node.status === 'locked' ? 'text-text-tertiary' : 'text-text-primary'}`}>
                                {node.name}
                              </span>
                              <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium border ${typeConfig.color}`}>
                                {typeConfig.label}
                              </span>
                            </div>
                            <div className="flex items-center gap-3 text-xs text-text-tertiary">
                              <span className="flex items-center gap-1">
                                <FileText className="w-3 h-3" />
                                {node.resources?.length ?? 0} 资源
                              </span>
                              <span className="flex items-center gap-1">
                                <Target className="w-3 h-3" />
                                难度 {node.difficulty}
                              </span>
                              <span className="flex items-center gap-1">
                                <Users className="w-3 h-3" />
                                {node.estimated_time}
                              </span>
                            </div>
                          </div>
                          <ChevronRight className={`w-4 h-4 text-text-tertiary transition-transform ${isSelected ? 'rotate-90' : ''}`} />
                        </div>

                        {/* 展开详情 */}
                        {isSelected && (
                          <div className="mt-3 pt-3 border-t border-border/50">
                            <div className="space-y-2">
                              <p className="text-xs text-text-secondary">{node.description}</p>
                              {node.resources && node.resources.length > 0 ? (
                                <>
                                  <p className="text-xs text-text-secondary">配套资源：</p>
                                  <div className="flex flex-wrap gap-1">
                                    {node.resources.map((r, ridx) => (
                                      <span key={ridx} className="px-2 py-0.5 rounded bg-primary/5 text-xs text-primary border border-primary/20">
                                        {typeof r === 'string' ? r : (r.title || r.name || `资源 ${ridx + 1}`)}
                                      </span>
                                    ))}
                                  </div>
                                </>
                              ) : (
                                <p className="text-xs text-text-tertiary">暂无配套资源</p>
                              )}
                              <p className="text-xs text-text-secondary">前置知识：{idx > 0 ? learningPathNodes[idx - 1].name : '无'}</p>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )
                })
              ) : (
                <div className="py-6">
                  <EmptyState type="default" title="暂无学习路径" description="未生成个性化学习路径" />
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>

      {/* 底部测试历史详情表 */}
      <Card padding="none">
        <div className="p-4 border-b border-border">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-text-secondary" />
              <h3 className="text-sm font-semibold text-text-primary">历史测试详情</h3>
            </div>
            <span className="text-xs text-text-tertiary">{testHistory.length} 条记录</span>
          </div>
        </div>
        {testHistory.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border/50">
                  <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary">测试时间</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary">测试主题</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary">难度</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary">得分</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary">能力评估</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary">Agent 决策</th>
                </tr>
              </thead>
              <tbody>
                {testHistory.map((test, idx) => {
                  const status = getScoreStatus(test.score)
                  return (
                    <tr key={test.record_id ?? idx} className={`border-b border-border/30 transition-colors hover:bg-bg-secondary/30 ${idx % 2 === 1 ? 'bg-bg-secondary/10' : ''}`}>
                      <td className="px-4 py-3 text-sm text-text-secondary">{formatTestDate(test.created_at)}</td>
                      <td className="px-4 py-3 text-sm font-medium text-text-primary">{test.question_topic || test.question_type}</td>
                      <td className="px-4 py-3 text-sm text-text-secondary">{test.question_difficulty}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <span className={`text-lg font-semibold ${status.variant === 'success' ? 'text-success' : status.variant === 'warning' ? 'text-primary' : 'text-amber-500'}`}>
                            {test.score.toFixed(0)}
                          </span>
                          <span className="text-sm text-text-tertiary">/ 100</span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant={status.variant} size="sm">
                          {status.label}
                        </Badge>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-xs text-text-secondary">
                          {test.agent_decision ? (
                            <span className="px-2 py-0.5 rounded bg-primary/5 text-primary border border-primary/20">
                              {test.agent_decision}
                            </span>
                          ) : '-'}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="py-10">
            <EmptyState type="default" title="暂无测试记录" description="完成答题后此处显示历史测试详情" />
          </div>
        )}
      </Card>
    </div>
  )
}
