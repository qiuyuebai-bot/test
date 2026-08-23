import { useState, useEffect, useCallback, useRef } from 'react'
import { useStore } from '@/store'
import { useShallow } from 'zustand/react/shallow'
import Card from '@/components/Card'
import Badge from '@/components/Badge'
import Button from '@/components/Button'
import Modal from '@/components/Modal'
import { SCORE_EXCELLENT_THRESHOLD, SCORE_GOOD_THRESHOLD } from '@/lib/constants'
import { CHART_COLORS, CHART_TOOLTIP_PROPS } from '@/lib/chartTheme'
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
  Sparkles,
} from 'lucide-react'
import EmptyState from '@/components/EmptyState'
import ErrorState from '@/components/ErrorState'
import { PageSkeleton } from '@/components/Skeleton'
import { coreApi } from '@/api'
import type { InteractionHistoryRecord, LearnerReport } from '@/types'
import { normalizeHallucinationReport } from '@/lib/hallucinationEvidence'
import { findMetric, formatMetricValue, metricReady, metricStatusLabel } from '@/lib/metrics'
import { useNavigate } from 'react-router-dom'
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
  high: 'var(--color-error)',
  medium: 'var(--color-viz-3)',
  low: 'var(--color-viz-1)',
}

// 节点状态图标配置
const statusConfig = {
  completed: { icon: CheckCircle2, color: 'text-success' },
  current: { icon: Play, color: 'text-primary' },
  next: { icon: Circle, color: 'text-warning' },
  locked: { icon: Lock, color: 'text-text-tertiary' },
}

// 难度等级 → 类型配置
const difficultyTypeConfig: Record<number, { label: string; color: string }> = {
  1: { label: '基础', color: 'bg-success/10 border-success/30 text-success' },
  2: { label: '基础', color: 'bg-success/10 border-success/30 text-success' },
  3: { label: '进阶', color: 'bg-primary/10 border-primary/30 text-primary' },
  4: { label: '进阶', color: 'bg-primary/10 border-primary/30 text-primary' },
  5: { label: '高阶', color: 'bg-warning-light border-warning/30 text-warning-dark' },
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

function isFiniteMatchScore(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

const educationLabels: Record<string, string> = {
  high_school: '高中',
  highschool: '高中',
  college: '大专',
  associate: '大专',
  bachelor: '本科',
  undergraduate: '本科',
  master: '硕士',
  postgraduate: '硕士',
  doctor: '博士',
  phd: '博士',
}

const agentDecisionLabels: Record<string, string> = {
  advance: '深化',
  simplify: '讲解',
  maintain: '巩固',
  consolidate: '巩固',
  review: '复习',
}

interface RoundSummary {
  id: string
  topic: string
  total: number
  correct: number
  accuracy: number
  difficulty: number | null
  latestAt: string | null
  roundNumber: number
  agentDecision: string | null
}

export default function LearningReport() {
  const navigate = useNavigate()
  const { currentLearner, learners, fetchLearners, learnersLoading, learnerError } = useStore(
    useShallow((s) => ({
      currentLearner: s.currentLearner,
      learners: s.learners,
      fetchLearners: s.fetchLearners,
      learnersLoading: s.learnersLoading,
      learnerError: s.learnerError,
    }))
  )
  const learner = currentLearner || learners[0]
  const [selectedNode, setSelectedNode] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [report, setReport] = useState<LearnerReport | null>(null)
  const [testHistory, setTestHistory] = useState<InteractionHistoryRecord[]>([])
  const [systemHallucinationRate, setSystemHallucinationRate] = useState<number | null>(null)
  const [hasSufficientHallucinationSample, setHasSufficientHallucinationSample] = useState(false)
  const [abilityTrendData, setAbilityTrendData] = useState<{ week: string; score: number }[]>([])
  const [pdfExporting, setPdfExporting] = useState(false)
  const [pdfError, setPdfError] = useState<string | null>(null)
  const [selectedHeatmapItem, setSelectedHeatmapItem] = useState<LearnerReport['blindAreaHeatmap']['data'][number] | null>(null)
  const cancelledRef = useRef(false)

  useEffect(() => {
    if (!learner && !learnersLoading && !learnerError) {
      void fetchLearners({ page: 1, pageSize: 1 })
    }
  }, [fetchLearners, learner, learnersLoading, learnerError])

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
        coreApi.getInteractionHistory(learner.id, { page: 1, pageSize: 100 }).catch(() => ({
          learnerId: learner.id,
          history: [],
          total: 0,
          page: 1,
          pageSize: 100,
        })),
        coreApi.getSystemMetrics().catch(() => null),
        coreApi.getAbilityTrend(learner.id).catch(() => []),
      ])
      if (cancelledRef.current) return
      setReport(reportData)
      setTestHistory(historyData.history)
      setAbilityTrendData(abilityTrend)
      if (sysMetrics?.metrics?.length) {
        const hallucinationMetric = findMetric(sysMetrics.metrics, 'hallucination_rate')
        setSystemHallucinationRate(hallucinationMetric?.value ?? null)
        setHasSufficientHallucinationSample(metricReady(hallucinationMetric))
      } else if (sysMetrics?.hallucinationRate !== undefined) {
        setSystemHallucinationRate(sysMetrics.hallucinationRate)
        setHasSufficientHallucinationSample(sysMetrics.hasSufficientSample === true)
      }
    } catch (err) {
      if (cancelledRef.current) return
      setError(err instanceof Error ? err.message : '加载报告数据失败')
    } finally {
      if (!cancelledRef.current) setLoading(false)
    }
  }, [learner?.id])

  useEffect(() => {
    cancelledRef.current = false
    loadReport()
    return () => {
      cancelledRef.current = true
    }
  }, [loadReport])

  if (loading || (!learner && learnersLoading)) return <PageSkeleton type="dashboard" />
  if (error) return <ErrorState type="default" onRetry={() => { setError(null); loadReport() }} />
  if (!learner && learnerError) {
    return (
      <ErrorState
        type="default"
        title="学习者画像加载失败"
        description="当前账号无法读取学习者画像，请完成画像设置后再查看学情报告。"
        details={learnerError}
        onRetry={() => { void fetchLearners({ page: 1, pageSize: 1 }) }}
        onGoHome={() => navigate('/onboarding/name')}
      />
    )
  }
  if (!learner) return <EmptyState type="default" title="暂无报告数据" description="请先选择学习者以生成报告" />

  // 衍生数据
  const heatmapData = report?.blindAreaHeatmap.data ?? []
  const matchCurveData = report?.difficultyMatchCurve.data ?? []
  const learningPathNodes = report?.learningPathTopology.nodes ?? []
  const abilityRadarData = report?.abilityRadar.data ?? []
  const learnerInfo = report?.learnerInfo
  const coreMetrics = report?.coreMetrics
  const learnerMetricResults = coreMetrics?.metrics ?? coreMetrics?.metricResults
  const learnerKnowledgeMetric = findMetric(learnerMetricResults, 'knowledge_index_coverage')
  const learnerResourceMatchMetric = findMetric(learnerMetricResults, 'resource_match_score')
  const learnerEffectivenessMetric = findMetric(learnerMetricResults, 'resource_match_effectiveness')
  const statistics = report?.statistics
  const hallucinationReport = normalizeHallucinationReport(report?.hallucinationReport)
  const credibilityLabels = {
    high: '高可信度',
    medium: '中等可信度',
    low: '低可信度',
    noEvidence: '暂无证据',
  } as const
  const credibilityColors = {
    high: 'text-success bg-success/10',
    medium: 'text-warning bg-warning-light',
    low: 'text-error bg-error/10',
    noEvidence: 'text-text-secondary bg-bg-secondary',
  } as const

  const stats = {
    knowledgeCoverage: learnerMetricResults
      ? (metricReady(learnerKnowledgeMetric) ? learnerKnowledgeMetric?.value ?? null : null)
      : coreMetrics?.knowledgeCoverageRate ?? null,
    resourceMatch: learnerMetricResults
      ? (metricReady(learnerResourceMatchMetric) ? learnerResourceMatchMetric?.value ?? null : null)
      : coreMetrics?.resourceMatchAccuracy ?? null,
    hallucinationRate: systemHallucinationRate,
    totalResources: statistics?.totalResources ?? 0,
    completedTasks: Math.max(0, report?.learningPathTopology.currentStep ?? 0),
    pendingTasks: Math.max(0, (report?.learningPathTopology.totalSteps ?? 0) - (report?.learningPathTopology.currentStep ?? 0)),
  }
  const knowledgeCoverageDisplay = learnerMetricResults
    ? formatMetricValue(learnerKnowledgeMetric, metricStatusLabel(learnerKnowledgeMetric))
    : stats.knowledgeCoverage === null ? '暂无数据' : `${stats.knowledgeCoverage.toFixed(1)}%`
  const resourceMatchDisplay = learnerMetricResults
    ? formatMetricValue(learnerResourceMatchMetric, metricStatusLabel(learnerResourceMatchMetric))
    : stats.resourceMatch === null ? '暂无数据' : `${stats.resourceMatch.toFixed(1)}%`
  const resourceEffectivenessDisplay = learnerMetricResults
    ? formatMetricValue(learnerEffectivenessMetric, metricStatusLabel(learnerEffectivenessMetric))
    : '暂无数据'

  const radarChartData = abilityRadarData.map((item) => ({
    subject: item.dimension,
    score: item.score,
  }))

  const matchCurveChartData = matchCurveData.length > 0
    ? matchCurveData
    : []
  const scoredMatchCurveData = matchCurveChartData.filter((item) => isFiniteMatchScore(item.matchScore))
  const pendingMatchCurveCount = matchCurveChartData.length - scoredMatchCurveData.length
  const matchCurveMode = scoredMatchCurveData.length === 0
    ? 'pending'
    : scoredMatchCurveData.length === 1
      ? 'single'
      : 'trend'
  const formatMatchValue = (value: unknown) => {
    const numericValue = typeof value === 'number'
      ? value
      : typeof value === 'string' && value.trim() !== ''
        ? Number(value)
        : Number.NaN
    return Number.isFinite(numericValue) ? numericValue.toFixed(2) : '-'
  }

  const openResourceFlow = (mode: 'list' | 'generate') => {
    if (!selectedHeatmapItem) return
    const params = new URLSearchParams({
      mode,
      dimension: selectedHeatmapItem.dimensionKey,
      topic: selectedHeatmapItem.dimension,
      learnerId: String(learner.id),
    })
    setSelectedHeatmapItem(null)
    navigate(`/resources?${params.toString()}`)
  }

  const startDimensionPractice = () => {
    if (!selectedHeatmapItem) return
    const params = new URLSearchParams({
      dimension: selectedHeatmapItem.dimensionKey,
      learnerId: String(learner.id),
    })
    setSelectedHeatmapItem(null)
    navigate(`/guidance?${params.toString()}`)
  }

  const displayName = learnerInfo?.name || learner?.realName || '-'
  const displayEducation = learnerInfo?.education || educationLabels[learner?.educationLevel] || learner?.educationLevel || '-'
  const displayMajor = learnerInfo?.major || learner?.major || '-'

  const roundSummaries: RoundSummary[] = (() => {
    const groups = new Map<string, InteractionHistoryRecord[]>()
    testHistory.forEach((record) => {
      const key = record.sessionId || `record-${record.recordId}`
      groups.set(key, [...(groups.get(key) ?? []), record])
    })
    const chronological = Array.from(groups.entries())
      .map(([id, records]) => {
        const ordered = [...records].sort((left, right) => {
          if (left.sequenceIndex !== null && right.sequenceIndex !== null) {
            return left.sequenceIndex - right.sequenceIndex
          }
          return new Date(left.createdAt ?? '').getTime() - new Date(right.createdAt ?? '').getTime()
        })
        const correct = ordered.filter((record) => record.result === 'correct').length
        const difficulties = new Set(ordered.map((record) => record.questionDifficulty).filter(Boolean))
        return {
          id,
          topic: ordered[0]?.questionTopic || ordered[0]?.questionType || '自适应导学',
          total: ordered.length,
          correct,
          accuracy: ordered.length > 0 ? Math.round((correct / ordered.length) * 100) : 0,
          difficulty: difficulties.size === 1 ? [...difficulties][0] : null,
          latestAt: ordered[ordered.length - 1]?.createdAt ?? null,
          firstAt: new Date(ordered[0]?.createdAt ?? '').getTime() || 0,
          agentDecision: ordered[ordered.length - 1]?.agentDecision ?? null,
        }
      })
      .sort((left, right) => left.firstAt - right.firstAt)

    return chronological
      .map((round, index) => ({ ...round, roundNumber: index + 1 }))
      .sort((left, right) => (new Date(right.latestAt ?? '').getTime() || 0) - (new Date(left.latestAt ?? '').getTime() || 0))
  })()

  const exportPdf = async () => {
    if (!learner?.id || pdfExporting) return
    setPdfExporting(true)
    setPdfError(null)
    try {
      const blob = await coreApi.downloadLearnerReportPdf(learner.id)
      if (!blob.type.includes('application/pdf')) throw new Error('服务器未返回 PDF 文件')
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `${displayName.replace(/[\\/:*?"<>|]/g, '_') || '学习者'}-学情报告.pdf`
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      URL.revokeObjectURL(url)
    } catch (err) {
      setPdfError(err instanceof Error ? err.message : 'PDF 导出失败')
    } finally {
      setPdfExporting(false)
    }
  }

  return (
    <div className="space-y-5 animate-fade-in">
      {/* 顶部统计指标栏 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card padding="md" className="hover:shadow-lift transition-all">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-success/10 flex items-center justify-center">
              <Target className="w-5 h-5 text-success" />
            </div>
            <div>
              <p className="metric-number text-xl font-semibold text-text-primary">{knowledgeCoverageDisplay}</p>
              <p className="text-xs text-text-tertiary">知识点覆盖率</p>
            </div>
          </div>
        </Card>
        <Card padding="md" className="hover:shadow-lift transition-all">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
              <Zap className="w-5 h-5 text-primary" />
            </div>
            <div>
              <p className="metric-number text-xl font-semibold text-text-primary">{resourceMatchDisplay}</p>
              <p className="text-xs text-text-tertiary">{learnerMetricResults ? '资源匹配分' : '资源匹配准确率'}</p>
            </div>
          </div>
        </Card>
        <Card padding="md" className="hover:shadow-lift transition-all">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-warning-light flex items-center justify-center">
              <Crosshair className="w-5 h-5 text-warning" />
            </div>
            <div>
              <p className="metric-number text-xl font-semibold text-text-primary">
                {hasSufficientHallucinationSample && stats.hallucinationRate !== null
                  ? `${stats.hallucinationRate.toFixed(1)}%`
                  : '样本不足/待审核'}
              </p>
              <p className="text-xs text-text-tertiary">知识幻觉错误率</p>
            </div>
          </div>
        </Card>
        <Card padding="md" className="hover:shadow-lift transition-all">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-info/10 flex items-center justify-center">
              <BookOpen className="w-5 h-5 text-info" />
            </div>
            <div>
              <p className="metric-number text-xl font-semibold text-text-primary">{stats.totalResources}</p>
              <p className="text-xs text-text-tertiary">已生成资源数</p>
            </div>
          </div>
        </Card>
        {learnerMetricResults && (
          <Card padding="md" className="hover:shadow-lift transition-all">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-warning/10 flex items-center justify-center">
                <Target className="w-5 h-5 text-warning" />
              </div>
              <div>
                <p className="metric-number text-xl font-semibold text-text-primary">{resourceEffectivenessDisplay}</p>
                <p className="text-xs text-text-tertiary">资源匹配效果</p>
              </div>
            </div>
          </Card>
        )}
      </div>

      <Card padding="md">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-medium text-text-tertiary">证据可信度</p>
            <p className={`mt-1 inline-flex rounded-full px-3 py-1 text-sm font-medium ${credibilityColors[hallucinationReport.credibility]}`}>
              {credibilityLabels[hallucinationReport.credibility]}
            </p>
          </div>
          <div className="text-sm text-text-secondary">
            证据覆盖率：{(hallucinationReport.evidenceCoverage * 100).toFixed(0)}%
          </div>
          {hallucinationReport.credibility === 'noEvidence' && (
            <button
              type="button"
              onClick={() => navigate('/knowledge-base')}
              className="rounded-lg bg-primary px-3 py-2 text-sm font-medium text-white hover:bg-primary/90"
            >
              上传相关资料
            </button>
          )}
        </div>
        {hallucinationReport.citations.length > 0 && (
          <div className="mt-3 text-xs text-text-secondary">
            <span className="font-medium">来源： </span>
            {hallucinationReport.citations.map((citation) => `${citation.title} · 第${citation.paragraph}段`).join(' · ')}
          </div>
        )}
        {hallucinationReport.knowledgeGap.present && (
          <p className="mt-2 text-sm text-text-secondary">{hallucinationReport.knowledgeGap.uploadPrompt}</p>
        )}
      </Card>

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
            <button
              onClick={() => window.print()}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm text-text-secondary hover:bg-bg-secondary transition-colors"
            >
              <Printer className="w-4 h-4" />
              打印报告
            </button>
            <button
              onClick={exportPdf}
              disabled={pdfExporting}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary/10 text-primary text-sm font-medium hover:bg-primary/20 transition-colors disabled:opacity-60"
            >
              <Download className="w-4 h-4" />
              {pdfExporting ? '正在导出…' : '导出 PDF'}
            </button>
          </div>
        </div>
      </Card>

      {pdfError && <ErrorState type="default" onRetry={() => { setPdfError(null); exportPdf() }} />}

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
                    <PolarGrid stroke={CHART_COLORS.grid} strokeWidth={1} />
                    <PolarAngleAxis dataKey="subject" tick={{ fontSize: 10, fill: CHART_COLORS.text }} tickLine={false} />
                    <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fontSize: 9, fill: CHART_COLORS.text }} tickCount={4} axisLine={false} />
                    <Radar name="能力" dataKey="score" stroke={CHART_COLORS.primary} fill={CHART_COLORS.primary} fillOpacity={0.15} strokeWidth={2} />
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
                        <stop offset="5%" stopColor={CHART_COLORS.primary} stopOpacity={0.15} />
                        <stop offset="95%" stopColor={CHART_COLORS.primary} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} vertical={false} />
                    <XAxis dataKey="week" tick={{ fontSize: 10, fill: CHART_COLORS.text }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 10, fill: CHART_COLORS.text }} axisLine={false} tickLine={false} domain={[40, 100]} />
                    <Tooltip {...CHART_TOOLTIP_PROPS} />
                    <Area type="monotone" dataKey="score" stroke={CHART_COLORS.primary} strokeWidth={2} fill="url(#colorScore)" dot={{ fill: CHART_COLORS.primary, strokeWidth: 2, r: 3 }} />
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
              <div className="h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
                <div
                  className="h-full bg-success rounded-full transition-all"
                  style={{
                    width: `${report?.learningPathTopology.progress ?? 0}%`,
                  }}
                />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-text-primary">进行中任务</span>
                <span className="text-sm font-semibold text-primary">{stats.pendingTasks}</span>
              </div>
              <div className="h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary rounded-full transition-all"
                  style={{
                    width: `${100 - (report?.learningPathTopology.progress ?? 0)}%`,
                  }}
                />
              </div>
              <div className="flex items-center justify-between pt-1 text-xs text-text-tertiary">
                <span>总进度</span>
                <span>{report?.learningPathTopology.progress.toFixed(1) ?? 0}% · 预计 {report?.learningPathTopology.estimatedTotalTime ?? '-'}</span>
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
              {matchCurveMode === 'trend' ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={scoredMatchCurveData}>
                    <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} vertical={false} />
                    <XAxis dataKey="difficulty" tick={{ fontSize: 10, fill: CHART_COLORS.text }} axisLine={false} tickLine={false} label={{ value: '难度等级', position: 'bottom', fontSize: 10, fill: CHART_COLORS.text }} />
                    <YAxis tick={{ fontSize: 10, fill: CHART_COLORS.text }} axisLine={false} tickLine={false} domain={[0, 100]} tickFormatter={formatMatchValue} />
                    <Tooltip {...CHART_TOOLTIP_PROPS} formatter={formatMatchValue} />
                    <Line type="monotone" dataKey="learnerAbility" stroke={CHART_COLORS.text} strokeWidth={2} strokeDasharray="6 4" dot={false} name="学习者能力" />
                    <Line type="monotone" dataKey="matchScore" stroke={CHART_COLORS.primary} strokeWidth={2.5} dot={{ fill: CHART_COLORS.primary, strokeWidth: 2, r: 4 }} name="实际匹配度" />
                  </LineChart>
                </ResponsiveContainer>
              ) : matchCurveMode === 'single' ? (
                <div data-testid="match-curve-single" className="h-full flex flex-col items-center justify-center text-center">
                  <span className="text-xs text-text-tertiary">当前资源匹配度</span>
                  <span className="mt-1 text-3xl font-semibold text-primary">
                    {formatMatchValue(scoredMatchCurveData[0].matchScore)}
                  </span>
                  <span className="mt-2 text-xs text-text-secondary">
                    难度 {scoredMatchCurveData[0].difficulty} · 学习者能力 {formatMatchValue(scoredMatchCurveData[0].learnerAbility)}
                  </span>
                  {pendingMatchCurveCount > 0 && (
                    <span className="mt-2 text-xs text-text-tertiary">
                      另有 {pendingMatchCurveCount} 条资源待计算
                    </span>
                  )}
                </div>
              ) : (
                <div data-testid="match-curve-pending" className="h-full flex flex-col items-center justify-center text-center px-6">
                  <Zap className="w-8 h-8 text-text-tertiary mb-3" />
                  <p className="text-sm font-medium text-text-primary">
                    {matchCurveChartData.length > 0 ? '匹配度待计算' : '暂无匹配数据'}
                  </p>
                  <p className="mt-1 text-xs leading-relaxed text-text-tertiary">
                    {matchCurveChartData.length > 0
                      ? '匹配度完成计算后显示趋势'
                      : '完成答题后生成匹配曲线'}
                  </p>
                </div>
              )}
            </div>
            {matchCurveMode === 'trend' && (
              <div className="px-4 pb-4">
                {pendingMatchCurveCount > 0 && (
                  <p className="mb-3 text-xs text-text-tertiary">
                    另有 {pendingMatchCurveCount} 条资源待计算
                  </p>
                )}
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-1.5">
                    <div className="w-6 h-0.5 bg-border" style={{ backgroundImage: 'repeating-linear-gradient(90deg, var(--color-border) 0, var(--color-border) 6px, transparent 6px, transparent 10px)' }} />
                    <span className="text-xs text-text-tertiary">推荐匹配</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <div className="w-3 h-3 rounded-full bg-primary" />
                    <span className="text-xs text-text-tertiary">实际匹配</span>
                  </div>
                </div>
              </div>
            )}
          </Card>

          {/* 知识盲区热力图 */}
          <Card padding="none">
            <div className="p-4 border-b border-border">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-warning" />
                <h3 className="text-sm font-semibold text-text-primary">知识盲区热力定位</h3>
              </div>
              <p className="text-xs text-text-tertiary mt-1">点击维度查看练习与资源选项</p>
            </div>
            <div className="p-4">
              {heatmapData.length > 0 ? (
                <div className="grid grid-cols-3 gap-2">
                  {heatmapData.map((item) => {
                    const color = SEVERITY_COLOR_MAP[item.severity] || 'var(--color-viz-2)'
                    return (
                      <button
                        key={item.dimension}
                        className="relative p-3 rounded-xl transition-all hover:scale-105 hover:shadow-lift cursor-pointer group"
                        style={{ backgroundColor: `${color}15`, border: `1px solid ${color}30` }}
                        onClick={() => setSelectedHeatmapItem(item)}
                        aria-label={`打开${item.dimension}行动选项`}
                        title={item.description}
                      >
                        <div className="flex flex-col items-center gap-1">
                          <span className="text-xs font-medium" style={{ color }}>{item.score.toFixed(0)}</span>
                          <span className="text-xs text-text-secondary text-center leading-tight">{item.dimension}</span>
                          {item.isBlind && (
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
                  <div className="w-3 h-3 rounded bg-warning-light" />
                  <span className="text-xs text-text-tertiary">薄弱</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="w-3 h-3 rounded bg-error-light" />
                  <span className="text-xs text-text-tertiary">盲区</span>
                </div>
              </div>
            </div>
          </Card>

          {/* 测试历史趋势 */}
          <Card padding="md">
            <h4 className="text-xs font-medium text-text-secondary mb-3">近期轮次正确率</h4>
            {roundSummaries.length > 0 ? (
              <div className="flex items-end justify-between gap-2">
                {roundSummaries.slice(0, 5).map((round) => (
                  <div key={round.id} className="flex-1 flex flex-col items-center gap-1">
                    <div className="w-full flex flex-col items-center">
                      <span className="text-xs font-semibold text-text-primary">{round.accuracy}%</span>
                      <div className="w-full h-12 flex items-end">
                        <div
                          className={`w-full rounded-t-sm transition-all ${
                            round.accuracy >= SCORE_EXCELLENT_THRESHOLD ? 'bg-success' : round.accuracy >= SCORE_GOOD_THRESHOLD ? 'bg-primary' : 'bg-warning'
                          }`}
                          style={{ height: `${round.accuracy}%` }}
                        />
                      </div>
                    </div>
                    <span className="text-xs text-text-tertiary">第 {round.roundNumber} 轮</span>
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
                          node.status === 'completed' ? 'bg-primary/40' : 'bg-bg-tertiary'
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
                              : 'bg-bg-tertiary'
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
                                {node.estimatedTime}
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
                                        {r.title || r.name || `资源 ${ridx + 1}`}
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
              <h3 className="text-sm font-semibold text-text-primary">历史轮次详情</h3>
            </div>
            <span className="text-xs text-text-tertiary">{roundSummaries.length} 轮</span>
          </div>
        </div>
        {roundSummaries.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border/50">
                  <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary">测试时间</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary">测试主题</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary">题目数</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary">难度</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary">正确率</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary">能力评估</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary">智能体决策</th>
                </tr>
              </thead>
              <tbody>
                {roundSummaries.map((round, idx) => {
                  const status = getScoreStatus(round.accuracy)
                  return (
                    <tr key={round.id} className={`border-b border-border/30 transition-colors hover:bg-bg-secondary/30 ${idx % 2 === 1 ? 'bg-bg-secondary/10' : ''}`}>
                      <td className="px-4 py-3 text-sm text-text-secondary">{formatTestDate(round.latestAt)}</td>
                      <td className="px-4 py-3 text-sm font-medium text-text-primary">第 {round.roundNumber} 轮 · {round.topic}</td>
                      <td className="px-4 py-3 text-sm text-text-secondary">{round.correct} / {round.total}</td>
                      <td className="px-4 py-3 text-sm text-text-secondary">{round.difficulty ?? '混合'}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <span className={`text-lg font-semibold ${status.variant === 'success' ? 'text-success' : status.variant === 'warning' ? 'text-primary' : 'text-warning'}`}>
                            {round.accuracy}%
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant={status.variant} size="sm">
                          {status.label}
                        </Badge>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-xs text-text-secondary">
                          {round.agentDecision ? (
                            <span className="px-2 py-0.5 rounded bg-primary/5 text-primary border border-primary/20">
                              {agentDecisionLabels[round.agentDecision] || round.agentDecision}
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

      <Modal
        isOpen={Boolean(selectedHeatmapItem)}
        onClose={() => setSelectedHeatmapItem(null)}
        maxWidth="max-w-md"
        header={selectedHeatmapItem ? (
          <div>
            <p className="text-xs font-medium text-primary">知识盲区行动</p>
            <h2 className="mt-1 text-lg font-semibold text-text-primary">{selectedHeatmapItem.dimension}</h2>
          </div>
        ) : undefined}
      >
        {selectedHeatmapItem && (
          <div className="space-y-5 p-6">
            <div className="rounded-lg border border-border bg-bg-secondary/40 p-4">
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm text-text-secondary">当前能力评分</span>
                <span className="text-2xl font-semibold text-text-primary">{selectedHeatmapItem.score.toFixed(0)}</span>
              </div>
              <p className="mt-2 text-sm leading-relaxed text-text-secondary">{selectedHeatmapItem.description}</p>
              <div className="mt-3">
                <Badge variant={selectedHeatmapItem.isBlind ? 'error' : 'warning'} size="sm">
                  {selectedHeatmapItem.isBlind ? '盲区' : selectedHeatmapItem.severityLabel}
                </Badge>
              </div>
            </div>

            <div className="space-y-2">
              <Button className="w-full justify-center" onClick={startDimensionPractice}>
                <Play className="h-4 w-4" />
                开始针对性练习
              </Button>
              <Button variant="outline" className="w-full justify-center" onClick={() => openResourceFlow('list')}>
                <BookOpen className="h-4 w-4" />
                查看相关资源
              </Button>
              <Button variant="outline" className="w-full justify-center" onClick={() => openResourceFlow('generate')}>
                <Sparkles className="h-4 w-4" />
                生成学习资源
              </Button>
            </div>
            <p className="text-center text-xs text-text-tertiary">生成资源前会先填好该维度主题，不会自动提交生成。</p>
          </div>
        )}
      </Modal>
    </div>
  )
}
