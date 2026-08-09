import { useState, useEffect, useCallback } from 'react'
import { useStore } from '@/store'
import { useShallow } from 'zustand/react/shallow'
import { agentApi, knowledgeApi } from '@/api'
import Card from '@/components/Card'
import Badge from '@/components/Badge'
import Button from '@/components/Button'
import EmptyState from '@/components/EmptyState'
import ErrorState from '@/components/ErrorState'
import { PageSkeleton } from '@/components/Skeleton'
import { SCORE_EXCELLENT_THRESHOLD } from '@/lib/constants'
import {
  FlaskConical,
  CheckCircle2,
  XCircle,
  Database,
  Users,
  Target,
  Crosshair,
  Bug,
  Zap,
  BookOpen,
  RefreshCw,
} from 'lucide-react'
import type { AgentStatus, AgentTask, KnowledgeDoc } from '@/types'

interface TaskGroup {
  id: string
  name: string
  cases: number
  passed: number
  failed: number
  status: 'passed' | 'failed' | 'pending'
}

interface KnowledgeSliceGroup {
  id: number
  domain: string
  slices: number
  indexed: number
  coverage: number
}

const TASK_TYPE_LABEL: Record<string, string> = {
  diagnosis: '学情诊断任务',
  generation: '资源生成任务',
  review: '内容审核任务',
  full_flow: '全流程集成任务',
}

export default function SystemTest() {
  const { systemMetrics, metricsError, metricsStatus, fetchSystemMetrics } = useStore(
    useShallow((s) => ({
      systemMetrics: s.systemMetrics,
      metricsError: s.metricsError,
      metricsStatus: s.metricsStatus,
      fetchSystemMetrics: s.fetchSystemMetrics,
    }))
  )
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [dataWarning, setDataWarning] = useState<string | null>(null)

  const [hallucinationRate, setHallucinationRate] = useState<number | null>(null)
  const [performance, setPerformance] = useState<{
    totalTasks: number
    successCount: number
    failedCount: number
    successRate: number | null
  } | null>(null)
  const [agents, setAgents] = useState<AgentStatus[]>([])
  const [taskGroups, setTaskGroups] = useState<TaskGroup[]>([])
  const [recentResults, setRecentResults] = useState<AgentTask[]>([])
  const [knowledgeGroups, setKnowledgeGroups] = useState<KnowledgeSliceGroup[]>([])

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    setDataWarning(null)
    try {
      const results = await Promise.allSettled([
        fetchSystemMetrics(),
        agentApi.getHallucinationMetrics(),
        agentApi.getPerformanceMetrics(),
        agentApi.getAllStatus(),
        agentApi.getTaskList({ page: 1, pageSize: 100 }),
        knowledgeApi.getList({ page: 1, pageSize: 100 }),
      ])
      const failedCount = results.filter((result) => result.status === 'rejected').length
      if (failedCount === results.length) {
        throw new Error('运行监控数据暂时不可用，请稍后重试')
      }
      if (failedCount > 0) {
        setDataWarning(`${failedCount} 个运行数据源暂时不可用，当前仅显示可用数据`)
      }

      const [, hallucResult, performanceResult, agentResult, taskResult, knowledgeResult] = results
      const hallucMetrics = hallucResult.status === 'fulfilled' ? hallucResult.value : null
      const perfMetrics = performanceResult.status === 'fulfilled' ? performanceResult.value : null
      const agentStatus = agentResult.status === 'fulfilled' ? agentResult.value : { agents: [] as AgentStatus[], total: 0 }
      const taskListResp = taskResult.status === 'fulfilled'
        ? taskResult.value
        : { items: [] as AgentTask[], total: 0, page: 1, pageSize: 100, totalPages: 0 }
      const knowledgeResp = knowledgeResult.status === 'fulfilled'
        ? knowledgeResult.value
        : { items: [] as KnowledgeDoc[], total: 0, page: 1, pageSize: 100, totalPages: 0 }

      // 幻觉率
      if (hallucMetrics?.hallucinationRate !== undefined) {
        setHallucinationRate(hallucMetrics.hallucinationRate)
      }

      // 性能指标
      if (perfMetrics) {
        setPerformance({
          totalTasks: perfMetrics.totalTasks,
          successCount: perfMetrics.successCount,
          failedCount: perfMetrics.failedCount,
          successRate: perfMetrics.successRate,
        })
      }

      // Agent 状态
      setAgents((agentStatus as { agents: AgentStatus[] }).agents || [])

      // 任务列表作为最近运行结果，不作为代码测试结果
      setRecentResults((taskListResp as { items: AgentTask[] }).items || [])

      // 按 task_type 聚合最近任务类型，仅用于运行概览
      const taskItems = (taskListResp as { items: AgentTask[] }).items || []
      const suitesMap = new Map<string, TaskGroup>()
      taskItems.forEach((t) => {
        const key = t.taskType || 'unknown'
        const label = TASK_TYPE_LABEL[key] || `${key} 任务`
        if (!suitesMap.has(key)) {
          suitesMap.set(key, {
            id: key,
            name: label,
            cases: 0,
            passed: 0,
            failed: 0,
            status: 'passed',
          })
        }
        const s = suitesMap.get(key)!
        s.cases += 1
        if (t.status === 'completed') s.passed += 1
        if (t.status === 'failed' || t.status === 'cancelled') s.failed += 1
        if (s.failed > 0) s.status = 'failed'
        if (t.status === 'running' || t.status === 'pending') s.status = 'pending'
      })
      setTaskGroups(Array.from(suitesMap.values()))

      // 知识库切片按 industry 聚合
      const docs = (knowledgeResp as { items: KnowledgeDoc[] }).items || []
      const groupMap = new Map<string, KnowledgeSliceGroup>()
      docs.forEach((d, idx) => {
        const domain = d.category || d.industry || '通用'
        if (!groupMap.has(domain)) {
          groupMap.set(domain, { id: idx + 1, domain, slices: 0, indexed: 0, coverage: 0 })
        }
        const g = groupMap.get(domain)!
        g.slices += d.totalSlices || 0
        g.indexed += d.indexedSlices || 0
        g.coverage = g.slices > 0 ? Math.round((g.indexed / g.slices) * 100) : 0
      })
      setKnowledgeGroups(Array.from(groupMap.values()))
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载数据失败')
    } finally {
      setLoading(false)
    }
  }, [fetchSystemMetrics])

  useEffect(() => {
    loadData()
  }, [loadData])

  const totalPassed = performance?.successCount ?? 0
  const totalFailed = performance?.failedCount ?? 0
  const passRate = performance?.successRate ?? null

  if (loading) return <PageSkeleton type="default" />

  if (error) {
    return <ErrorState type="default" onRetry={() => loadData()} />
  }

  // 三大核心量化指标（来自真实系统指标）
  const hallucinationSampleSufficient = systemMetrics?.hasSufficientSample === true
  const hallucinationRateValue = hallucinationRate ?? systemMetrics?.hallucinationRate ?? null
  const resourceMatchAccuracy = systemMetrics?.resourceMatchAccuracy ?? null
  const knowledgeCoverageRate = systemMetrics?.knowledgeCoverageRate ?? null

  return (
    <div className="space-y-5 animate-fade-in">
      {(dataWarning || (metricsStatus === 'partial' && metricsError)) && (
        <div className="rounded-lg border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning">
          {dataWarning || metricsError}
        </div>
      )}
      {/* 三大核心量化指标 */}
      <div className="grid grid-cols-3 gap-3">
        <Card padding="md" className="border-l-4 border-l-warning">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-warning-light flex items-center justify-center">
              <Crosshair className="w-5 h-5 text-warning" />
            </div>
            <div>
              <p className="text-xl font-semibold metric-number text-warning">
                {hallucinationSampleSufficient && hallucinationRateValue !== null
                  ? `${hallucinationRateValue.toFixed(1)}%`
                  : '样本不足/待审核'}
              </p>
              <p className="text-xs text-text-tertiary">知识幻觉错误率</p>
            </div>
          </div>
        </Card>
        <Card padding="md" className="border-l-4 border-l-primary">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
              <Target className="w-5 h-5 text-primary" />
            </div>
            <div>
              <p className="text-xl font-semibold metric-number text-primary">
                {resourceMatchAccuracy === null ? '暂无数据' : `${resourceMatchAccuracy.toFixed(1)}%`}
              </p>
              <p className="text-xs text-text-tertiary">资源匹配准确率</p>
            </div>
          </div>
        </Card>
        <Card padding="md" className="border-l-4 border-l-success">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-success/10 flex items-center justify-center">
              <Users className="w-5 h-5 text-success" />
            </div>
            <div>
              <p className="text-xl font-semibold metric-number text-success">
                {knowledgeCoverageRate === null ? '暂无数据' : `${knowledgeCoverageRate.toFixed(1)}%`}
              </p>
              <p className="text-xs text-text-tertiary">知识点覆盖率</p>
            </div>
          </div>
        </Card>
      </div>

      {/* 操作栏 */}
      <Card padding="md">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-text-primary flex items-center gap-2">
              <FlaskConical className="w-5 h-5 text-text-secondary" />
              Agent 运行监控
            </h2>
            <p className="text-sm text-text-secondary mt-1">
              展示 Agent 任务执行与知识库索引状态；此页面不执行 pytest 或前端单元测试
              {performance && (
                <span className="ml-2 text-text-tertiary">· 总任务 {performance.totalTasks} · 成功 {performance.successCount} · 失败 {performance.failedCount}</span>
              )}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => void loadData()}>
              <RefreshCw className="w-4 h-4" />
              刷新数据
            </Button>
          </div>
        </div>
      </Card>

      {/* 测试概览统计 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card padding="md" className="hover:shadow-lift transition-all">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-info/10 flex items-center justify-center">
              <FlaskConical className="w-5 h-5 text-info" />
            </div>
            <div>
              <p className="text-xl font-semibold metric-number text-text-primary">{taskGroups.length}</p>
              <p className="text-xs text-text-tertiary">任务类型</p>
            </div>
          </div>
        </Card>
        <Card padding="md" className="hover:shadow-lift transition-all">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-bg-secondary flex items-center justify-center">
              <Zap className="w-5 h-5 text-text-secondary" />
            </div>
            <div>
              <p className="text-xl font-semibold metric-number text-text-primary">{recentResults.length}</p>
              <p className="text-xs text-text-tertiary">最近任务数</p>
            </div>
          </div>
        </Card>
        <Card padding="md" className="hover:shadow-lift transition-all">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-success/10 flex items-center justify-center">
              <CheckCircle2 className="w-5 h-5 text-success" />
            </div>
            <div>
              <p className="text-xl font-semibold metric-number text-success">{totalPassed}</p>
              <p className="text-xs text-text-tertiary">通过</p>
            </div>
          </div>
        </Card>
        <Card padding="md" className="hover:shadow-lift transition-all">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
              <Zap className="w-5 h-5 text-primary" />
            </div>
            <div>
              <p className="text-xl font-semibold metric-number text-primary">{passRate === null ? '暂无数据' : `${passRate}%`}</p>
              <p className="text-xs text-text-tertiary">任务成功率</p>
            </div>
          </div>
        </Card>
      </div>

      {/* 主内容区 */}
      <div className="grid grid-cols-12 gap-4">
        {/* 左侧：知识库切片管理 & 任务类型 */}
        <div className="col-span-12 lg:col-span-8 space-y-4">
          {/* 知识库切片管理 */}
          <Card padding="none">
            <div className="p-4 border-b border-border">
              <div className="flex items-center gap-2">
                <Database className="w-4 h-4 text-text-secondary" />
                <h3 className="text-sm font-semibold text-text-primary">领域知识库切片管理</h3>
              </div>
            </div>
            {knowledgeGroups.length === 0 ? (
              <div className="p-6">
                <EmptyState type="data" title="暂无知识库切片" description="上传领域知识文档以构建专业内容库" />
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-border/50">
                      <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary">领域</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary">切片数</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary">已索引</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary">覆盖率</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary">状态</th>
                    </tr>
                  </thead>
                  <tbody>
                    {knowledgeGroups.map((slice, idx) => (
                      <tr key={slice.id} className={`border-b border-border/30 transition-colors hover:bg-bg-secondary/30 ${idx % 2 === 1 ? 'bg-bg-secondary/10' : ''}`}>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <BookOpen className="w-4 h-4 text-primary" />
                            <span className="text-sm font-medium text-text-primary">{slice.domain}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-sm text-text-secondary">{slice.slices}</td>
                        <td className="px-4 py-3 text-sm text-text-secondary">{slice.indexed}</td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <div className="w-16 h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
                              <div className="h-full bg-primary rounded-full" style={{ width: `${slice.coverage}%` }} />
                            </div>
                            <span className="text-xs text-text-secondary">{slice.coverage}%</span>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant={slice.coverage === 100 ? 'success' : 'warning'} size="sm">
                            {slice.coverage === 100 ? '已就绪' : '部分索引'}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          {/* 任务类型概览 */}
          <Card padding="none">
            <div className="p-4 border-b border-border">
              <h3 className="text-sm font-semibold text-text-primary">任务类型概览（最近100条）</h3>
            </div>
            {taskGroups.length === 0 ? (
              <div className="p-6">
                <EmptyState type="default" title="暂无任务类型数据" description="运行 Agent 任务后将显示统计结果" />
              </div>
            ) : (
              <div className="divide-y divide-border/30">
                {taskGroups.map((suite) => (
                  <div key={suite.id} className="p-4 hover:bg-bg-secondary/30 transition-colors flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${
                        suite.status === 'passed' ? 'bg-success/10' : suite.status === 'failed' ? 'bg-warning-light' : 'bg-info/10'
                      }`}>
                        {suite.status === 'passed' ? (
                          <CheckCircle2 className="w-4 h-4 text-success" />
                        ) : suite.status === 'failed' ? (
                          <Bug className="w-4 h-4 text-warning" />
                        ) : (
                          <RefreshCw className="w-4 h-4 text-info" />
                        )}
                      </div>
                      <div>
                        <p className="text-sm font-medium text-text-primary">{suite.name}</p>
                        <p className="text-xs text-text-tertiary">
                          {suite.cases} 条任务 · {suite.passed} 成功
                          {suite.failed > 0 && ` · ${suite.failed} 失败`}
                        </p>
                      </div>
                    </div>
                    <Badge variant={suite.status === 'passed' ? 'success' : suite.status === 'failed' ? 'warning' : 'info'} size="sm">
                      {suite.status === 'passed' ? '已通过' : suite.status === 'failed' ? '部分失败' : '运行中'}
                    </Badge>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* 右侧：Agent 状态 & 最近任务结果 */}
        <div className="col-span-12 lg:col-span-4 space-y-4">
          {/* Agent 状态 */}
          <Card padding="md">
            <h4 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
              <Zap className="w-4 h-4 text-text-secondary" />
              多智能体执行统计
            </h4>
            <div className="space-y-2">
              {agents.length === 0 ? (
                <EmptyState type="default" title="暂无 Agent 数据" />
              ) : (
                agents.map((agent, idx) => {
                  const total = agent.successCount + agent.failureCount
                  const rate = total > 0 ? Math.round((agent.successCount / total) * 100) : 0
                  return (
                    <div key={idx} className="flex items-center justify-between p-2 rounded-lg bg-bg-secondary/30">
                      <span className="text-sm text-text-primary">{agent.agentName}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-text-tertiary">{agent.totalTasksHandled} 任务</span>
                        <span className={`text-xs font-medium ${rate === 100 ? 'text-success' : rate >= SCORE_EXCELLENT_THRESHOLD ? 'text-primary' : 'text-warning'}`}>
                          {rate}%
                        </span>
                      </div>
                    </div>
                  )
                })
              )}
            </div>
          </Card>

          {/* 最近测试结果 */}
          <Card padding="none">
            <div className="p-4 border-b border-border">
              <h4 className="text-sm font-semibold text-text-primary">最近任务执行结果</h4>
            </div>
            {recentResults.length === 0 ? (
              <div className="p-6">
                <EmptyState type="default" title="暂无任务记录" description="运行 Agent 任务后将显示在此处" />
              </div>
            ) : (
              <div className="divide-y divide-border/30">
                {recentResults.map((result) => {
                  const passed = result.status === 'completed'
                  const pending = result.status === 'running' || result.status === 'pending'
                  return (
                    <div key={result.taskId} className="p-3 hover:bg-bg-secondary/30 transition-colors">
                      <div className="flex items-start gap-2">
                        {passed ? (
                          <CheckCircle2 className="w-4 h-4 text-success mt-0.5 flex-shrink-0" />
                        ) : pending ? (
                          <RefreshCw className="w-4 h-4 text-info mt-0.5 flex-shrink-0 animate-spin" />
                        ) : (
                          <XCircle className="w-4 h-4 text-warning mt-0.5 flex-shrink-0" />
                        )}
                        <div className="flex-1 min-w-0">
                          <p className="text-sm text-text-primary truncate">
                            #{result.taskId} · {result.taskName}
                          </p>
                          {result.errorMessage && (
                            <p className="text-xs text-warning mt-0.5 truncate">{result.errorMessage}</p>
                          )}
                          <p className="text-xs text-text-tertiary">
                            {result.taskType} · {result.status} · 进度 {result.progress}%
                          </p>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </Card>

          {/* 失败统计 */}
          <Card padding="md">
            <h4 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
              <Bug className="w-4 h-4 text-text-secondary" />
              失败统计
            </h4>
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 rounded-lg bg-warning-light/50">
                <p className="text-xs text-text-tertiary mb-1">总失败数</p>
                <p className="text-xl font-semibold metric-number text-warning">{totalFailed}</p>
              </div>
              <div className="p-3 rounded-lg bg-success/5">
                <p className="text-xs text-text-tertiary mb-1">总通过数</p>
                <p className="text-xl font-semibold metric-number text-success">{totalPassed}</p>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
