import { useEffect, useState } from 'react'
import { ArrowLeft, BookOpen, CheckCircle2, ChevronDown, FileText, GitCompare, MessageSquare, Scale, ShieldAlert, ShieldCheck } from 'lucide-react'
import { useNavigate, useParams } from 'react-router-dom'
import Card from '@/components/Card'
import Badge from '@/components/Badge'
import ErrorState from '@/components/ErrorState'
import LoadingState from '@/components/LoadingState'
import MarkdownContent from '@/components/MarkdownContent'
import { agentApi } from '@/api'
import type { TaskEvidence, TaskEvidenceDebate } from '@/types'

type TabKey = 'debate' | 'knowledge' | 'revision' | 'decision'

const tabs: Array<{ key: TabKey; label: string; icon: typeof MessageSquare }> = [
  { key: 'debate', label: '辩论记录', icon: MessageSquare },
  { key: 'knowledge', label: '知识证据', icon: BookOpen },
  { key: 'revision', label: '修正对比', icon: GitCompare },
  { key: 'decision', label: '决策说明', icon: Scale },
]

const decisionLabels: Record<string, string> = {
  approved: '已通过',
  revised_approved: '修正后通过',
  rejected: '拒绝',
  insufficient_evidence: '证据不足',
}

function decisionVariant(decision: string): 'success' | 'warning' | 'error' | 'info' | 'default' {
  if (decision === 'approved' || decision === 'revised_approved') return 'success'
  if (decision === 'rejected') return 'error'
  if (decision === 'insufficient_evidence') return 'warning'
  return 'default'
}

function textValue(value: unknown): string {
  if (typeof value === 'string') return value
  if (value === null || value === undefined) return '-'
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

function correctionText(value: string | Record<string, unknown>): string {
  if (typeof value === 'string') return value
  return String(value.description || value.suggestedFix || value.reason || '未提供修正说明')
}

function formatDate(value?: string | null): string {
  if (!value) return '-'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN')
}

function DebatePanel({ debate }: { debate: TaskEvidenceDebate }) {
  const [expanded, setExpanded] = useState(true)
  const decision = debate.judgeDecision || '未给出'
  return (
    <div className="border border-border rounded-xl overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        className="w-full flex items-center justify-between gap-3 px-4 py-3 bg-bg-secondary/30 hover:bg-bg-secondary/50 transition-colors text-left"
      >
        <span className="flex items-center gap-3 min-w-0">
          <span className="w-7 h-7 rounded-full bg-primary/10 text-primary text-xs font-semibold inline-flex items-center justify-center">{debate.round}</span>
          <span className="text-sm font-semibold text-text-primary">第{debate.round}轮辩论</span>
          {debate.hasConflict && <Badge variant="warning">发现冲突</Badge>}
          <Badge variant={decision === 'approved' ? 'success' : decision === 'rejected' ? 'error' : 'info'}>{decision}</Badge>
        </span>
        <ChevronDown className={`w-4 h-4 text-text-tertiary transition-transform ${expanded ? 'rotate-180' : ''}`} />
      </button>
      {expanded && (
        <div className="p-4 space-y-4">
          <div className="grid lg:grid-cols-2 gap-4">
            <div className="p-3 rounded-lg border border-border-light bg-bg-secondary/20">
              <p className="text-xs font-semibold text-text-secondary mb-2">裁判质疑</p>
              <pre className="text-xs leading-5 text-text-secondary whitespace-pre-wrap break-words font-sans">{textValue(debate.judgeStandpoint)}</pre>
            </div>
            <div className="p-3 rounded-lg border border-border-light bg-bg-secondary/20">
              <p className="text-xs font-semibold text-text-secondary mb-2">生成方回应</p>
              <pre className="text-xs leading-5 text-text-secondary whitespace-pre-wrap break-words font-sans">{textValue(debate.generationCounterargument)}</pre>
            </div>
          </div>
          {debate.conflictPoints.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-text-secondary mb-2">冲突点</p>
              <div className="space-y-2">
                {debate.conflictPoints.map((point, index) => (
                  <div key={`${debate.round}-conflict-${index}`} className="p-3 rounded-lg bg-warning-light/40 border border-warning/20 text-xs text-text-secondary whitespace-pre-wrap">
                    {textValue(point)}
                  </div>
                ))}
              </div>
            </div>
          )}
          {debate.corrections.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-text-secondary mb-2">本轮修正</p>
              <div className="space-y-2">
                {debate.corrections.map((correction, index) => (
                  <div key={`${debate.round}-correction-${index}`} className="flex gap-2 p-3 rounded-lg bg-success-light/30 border border-success/20 text-xs text-text-secondary">
                    <CheckCircle2 className="w-4 h-4 text-success shrink-0" />
                    <span className="whitespace-pre-wrap">{correctionText(correction)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          <div className="flex flex-wrap gap-3 text-xs text-text-tertiary">
            <span>状态：{debate.resolutionStatus || '-'}</span>
            <span>裁判置信度：{debate.judgeConfidence == null ? '-' : `${Math.round(debate.judgeConfidence <= 1 ? debate.judgeConfidence * 100 : debate.judgeConfidence)}%`}</span>
            <span>时间：{formatDate(debate.createdAt)}</span>
          </div>
        </div>
      )}
    </div>
  )
}

function DebateTab({ evidence }: { evidence: TaskEvidence }) {
  if (evidence.debateRecords.length === 0) {
    return <EmptyPanel icon={MessageSquare} title="暂无辩论记录" description="该任务没有触发多轮辩论，或记录尚未写入。" />
  }
  return (
    <div className="space-y-3">
      {evidence.debateRecords.map((debate) => <DebatePanel key={debate.round} debate={debate} />)}
    </div>
  )
}

function KnowledgeTab({ evidence }: { evidence: TaskEvidence }) {
  if (evidence.knowledgeEvidence.length === 0) {
    return <EmptyPanel icon={BookOpen} title="证据不足" description="没有找到可用于审计的知识库切片，可信度不会被计算为高分。" />
  }
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-text-secondary">已关联 {evidence.knowledgeEvidence.length} 个知识切片，显示完整原文以便复核。</p>
        <Badge variant={evidence.summary.hasSufficientEvidence ? 'success' : 'warning'}>{evidence.summary.hasSufficientEvidence ? '来源有效' : '来源待确认'}</Badge>
      </div>
      {evidence.knowledgeEvidence.map((item) => (
        <div key={item.sliceId} className="border border-border rounded-xl p-4 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="info">切片 #{item.sliceId}</Badge>
            <span className="text-sm font-semibold text-text-primary">{item.title || item.docTitle || '未命名切片'}</span>
            <span className="text-xs text-text-tertiary">{item.docTitle} · 第{item.sliceIndex + 1}段</span>
            {item.similarity != null && <span className="text-xs text-text-tertiary ml-auto">相关度 {Math.round(item.similarity <= 1 ? item.similarity * 100 : item.similarity)}%</span>}
          </div>
          <div className="p-3 rounded-lg bg-bg-secondary/30 border border-border-light">
            <p className="text-sm leading-6 text-text-secondary whitespace-pre-wrap break-words">{item.content}</p>
          </div>
        </div>
      ))}
      {evidence.sourceDocuments.length > 0 && (
        <div className="border border-border rounded-xl p-4">
          <p className="text-xs font-semibold text-text-secondary mb-3">来源文档</p>
          <div className="grid md:grid-cols-2 gap-2">
            {evidence.sourceDocuments.map((doc) => (
              <div key={doc.id} className="flex items-center gap-2 p-2 rounded-lg bg-bg-secondary/30 text-xs text-text-secondary">
                <FileText className="w-4 h-4 text-text-tertiary" />
                <span className="truncate">{doc.title}</span>
                <span className="text-text-tertiary ml-auto shrink-0">v{doc.version || '-'}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function RevisionTab({ evidence }: { evidence: TaskEvidence }) {
  const comparison = evidence.revisionComparison
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-text-secondary">{comparison.hasChanges ? `记录了 ${comparison.corrections.length} 项修正。` : '没有检测到修正前后差异。'}</p>
        <Badge variant={comparison.hasChanges ? 'warning' : 'default'}>{comparison.hasChanges ? '已修正' : '无变化'}</Badge>
      </div>
      <div className="grid lg:grid-cols-2 gap-4">
        <div className="border border-error/20 rounded-xl overflow-hidden">
          <div className="px-4 py-3 bg-error-light/40 text-xs font-semibold text-error-dark">修正前版本</div>
          <div className="p-4 max-h-[520px] overflow-y-auto">
            {comparison.originalContent ? <MarkdownContent content={comparison.originalContent} /> : <p className="text-sm text-text-tertiary">未留存修正前内容</p>}
          </div>
        </div>
        <div className="border border-success/20 rounded-xl overflow-hidden">
          <div className="px-4 py-3 bg-success-light/40 text-xs font-semibold text-success-dark">最终版本</div>
          <div className="p-4 max-h-[520px] overflow-y-auto">
            {comparison.finalContent ? <MarkdownContent content={comparison.finalContent} /> : <p className="text-sm text-text-tertiary">暂无最终内容</p>}
          </div>
        </div>
      </div>
      {comparison.corrections.length > 0 && (
        <div className="border border-border rounded-xl p-4">
          <p className="text-xs font-semibold text-text-secondary mb-3">修正清单</p>
          <div className="space-y-2">
            {comparison.corrections.map((correction, index) => <div key={`revision-${index}`} className="text-sm text-text-secondary flex gap-2"><span className="text-primary font-semibold">{index + 1}.</span><span>{correctionText(correction)}</span></div>)}
          </div>
        </div>
      )}
    </div>
  )
}

function DecisionTab({ evidence }: { evidence: TaskEvidence }) {
  const decision = evidence.summary.finalDecision
  return (
    <div className="space-y-5">
      <div className="flex items-start gap-3 p-4 rounded-xl border border-border bg-bg-secondary/20">
        {evidence.summary.hasSufficientEvidence ? <ShieldCheck className="w-5 h-5 text-success shrink-0" /> : <ShieldAlert className="w-5 h-5 text-warning shrink-0" />}
        <div>
          <div className="flex items-center gap-2 flex-wrap"><span className="text-sm font-semibold text-text-primary">最终决策</span><Badge variant={decisionVariant(decision)}>{decisionLabels[decision] || decision}</Badge></div>
          <p className="text-sm text-text-secondary mt-2">{evidence.decision.releaseReason}</p>
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between mb-3"><h4 className="text-sm font-semibold text-text-primary">可信度组成</h4><span className="text-sm font-semibold text-text-primary">{evidence.summary.confidence == null ? '证据不足' : `${evidence.summary.confidence}%`}</span></div>
        <div className="space-y-3">
          {evidence.summary.confidenceBreakdown.map((item) => (
            <div key={item.key}>
              <div className="flex items-center justify-between text-xs mb-1"><span className="text-text-secondary">{item.label} · 权重 {item.weight}%</span><span className="text-text-primary font-medium">{Math.round(item.score)}%</span></div>
              <div className="h-2 rounded-full bg-bg-tertiary overflow-hidden"><div className="h-full bg-primary rounded-full" style={{ width: `${Math.min(100, Math.max(0, item.score))}%` }} /></div>
            </div>
          ))}
        </div>
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <div className="border border-border rounded-xl p-4">
          <h4 className="text-sm font-semibold text-text-primary mb-3">未解决风险</h4>
          {evidence.decision.unresolvedRisks.length > 0 ? <ul className="space-y-2 text-sm text-text-secondary list-disc pl-4">{evidence.decision.unresolvedRisks.map((risk, index) => <li key={`risk-${index}`}>{risk}</li>)}</ul> : <p className="text-sm text-text-tertiary">暂无未解决风险</p>}
        </div>
        <div className="border border-border rounded-xl p-4">
          <h4 className="text-sm font-semibold text-text-primary mb-3">审核规则</h4>
          <ul className="space-y-2 text-sm text-text-secondary list-disc pl-4">{evidence.decision.reviewRules.map((rule, index) => <li key={`rule-${index}`}>{rule}</li>)}</ul>
        </div>
      </div>
    </div>
  )
}

function EmptyPanel({ icon: Icon, title, description }: { icon: typeof MessageSquare; title: string; description: string }) {
  return <div className="flex flex-col items-center justify-center py-16 text-center"><Icon className="w-8 h-8 text-text-tertiary mb-3" /><p className="text-sm font-medium text-text-primary">{title}</p><p className="text-xs text-text-tertiary mt-1 max-w-sm">{description}</p></div>
}

export default function TaskEvidenceWorkspace() {
  const { taskId } = useParams<{ taskId: string }>()
  const navigate = useNavigate()
  const [evidence, setEvidence] = useState<TaskEvidence | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [activeTab, setActiveTab] = useState<TabKey>('debate')

  useEffect(() => {
    const numericTaskId = Number(taskId)
    if (!Number.isInteger(numericTaskId) || numericTaskId <= 0) {
      setLoading(false)
      setError(true)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(false)
    agentApi.getTaskEvidence(numericTaskId)
      .then((result) => {
        if (!cancelled) setEvidence(result)
      })
      .catch(() => {
        if (!cancelled) setError(true)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [taskId])

  if (loading) return <LoadingState message="正在加载完整证据链" />
  if (error || !evidence) return <ErrorState title="证据链加载失败" description="任务不存在、无权访问，或服务暂时不可用。" onRetry={() => window.location.reload()} onGoHome={() => navigate('/multi-agent')} />

  const activeTabContent = {
    debate: <DebateTab evidence={evidence} />,
    knowledge: <KnowledgeTab evidence={evidence} />,
    revision: <RevisionTab evidence={evidence} />,
    decision: <DecisionTab evidence={evidence} />,
  }[activeTab]

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-start gap-3">
          <button type="button" onClick={() => navigate('/multi-agent')} className="p-2 rounded-lg hover:bg-bg-secondary text-text-secondary transition-colors" aria-label="返回多智能体任务">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <p className="text-xs text-text-tertiary mb-1">多智能体 / 完整证据链</p>
            <h1 className="hero-anchor text-xl font-semibold text-text-primary">{evidence.task.taskName}</h1>
            <p className="text-sm text-text-secondary mt-2">任务 #{evidence.task.taskId} · 学习者 {evidence.learner.name || `#${evidence.task.learnerId}`} · 资源类型 {evidence.finalGeneration.resourceType || '-'} · {formatDate(evidence.task.createdAt)}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={decisionVariant(evidence.summary.finalDecision)}>{decisionLabels[evidence.summary.finalDecision] || evidence.summary.finalDecision}</Badge>
          <Badge variant={evidence.summary.hasSufficientEvidence ? 'success' : 'warning'}>{evidence.summary.confidence == null ? '证据不足' : `可信度 ${evidence.summary.confidence}%`}</Badge>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card padding="sm"><p className="text-xs text-text-tertiary">辩论轮数</p><p className="text-2xl font-semibold text-text-primary mt-1">{evidence.summary.stats.debateRounds}</p></Card>
        <Card padding="sm"><p className="text-xs text-text-tertiary">发现问题</p><p className="text-2xl font-semibold text-text-primary mt-1">{evidence.summary.stats.issuesFound}</p></Card>
        <Card padding="sm"><p className="text-xs text-text-tertiary">已修正</p><p className="text-2xl font-semibold text-text-primary mt-1">{evidence.summary.stats.correctionsApplied}</p></Card>
        <Card padding="sm"><p className="text-xs text-text-tertiary">引用来源</p><p className="text-2xl font-semibold text-text-primary mt-1">{evidence.summary.stats.sourceCount}</p></Card>
      </div>

      <Card padding="md">
        <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-semibold text-text-primary">流程时间线</h2><span className="text-xs text-text-tertiary">当前阶段：{evidence.task.flowStage || '-'}</span></div>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
          {evidence.timeline.map((item) => (
            <div key={item.stage} className="relative min-w-0">
              <div className={`h-2 rounded-full mb-2 ${item.status === 'completed' ? 'bg-success' : item.status === 'active' ? 'bg-primary animate-pulse' : 'bg-bg-tertiary'}`} />
              <p className={`text-xs font-medium ${item.status === 'pending' ? 'text-text-tertiary' : 'text-text-primary'}`}>{item.label}</p>
              <p className="text-[10px] text-text-tertiary mt-1 truncate">{item.description || item.status}</p>
            </div>
          ))}
        </div>
      </Card>

      <div className="border-b border-border overflow-x-auto">
        <div className="flex items-center gap-1 min-w-max">
          {tabs.map(({ key, label, icon: Icon }) => (
            <button key={key} type="button" onClick={() => setActiveTab(key)} className={`inline-flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${activeTab === key ? 'border-primary text-primary' : 'border-transparent text-text-secondary hover:text-text-primary'}`}>
              <Icon className="w-4 h-4" />
              {label}
            </button>
          ))}
        </div>
      </div>

      <section aria-live="polite">{activeTabContent}</section>
    </div>
  )
}
