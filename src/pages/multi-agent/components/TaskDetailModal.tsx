import { useEffect, useState } from 'react'
import { AlertTriangle, ArrowRight, FileText, Loader2, ShieldAlert, ShieldCheck, Target } from 'lucide-react'
import Modal from '@/components/Modal'
import Badge from '@/components/Badge'
import Button from '@/components/Button'
import { agentApi } from '@/api'
import type { AgentTask, TaskEvidence } from '@/types'
import { statusConfig } from '../constants'

interface Props {
  isOpen: boolean
  onClose: () => void
  task?: AgentTask
  onViewEvidence?: () => void
  onViewResource?: (resourceId: number) => void
}

const decisionLabels: Record<string, string> = {
  approved: '已通过',
  revised_approved: '修正后通过',
  rejected: '拒绝',
  insufficient_evidence: '证据不足',
}

function decisionVariant(decision?: string): 'success' | 'warning' | 'error' | 'info' | 'default' {
  if (decision === 'approved' || decision === 'revised_approved') return 'success'
  if (decision === 'rejected') return 'error'
  if (decision === 'insufficient_evidence') return 'warning'
  return 'default'
}

export function TaskDetailModal({ isOpen, onClose, task, onViewEvidence, onViewResource }: Props) {
  const [evidence, setEvidence] = useState<TaskEvidence | null>(null)
  const [loadingEvidence, setLoadingEvidence] = useState(false)
  const [evidenceError, setEvidenceError] = useState(false)

  useEffect(() => {
    if (!isOpen || !task) return
    let cancelled = false
    setLoadingEvidence(true)
    setEvidenceError(false)
    agentApi.getTaskEvidence(task.taskId)
      .then((result) => {
        if (!cancelled) setEvidence(result)
      })
      .catch(() => {
        if (!cancelled) setEvidenceError(true)
      })
      .finally(() => {
        if (!cancelled) setLoadingEvidence(false)
      })
    return () => {
      cancelled = true
    }
  }, [isOpen, task])

  if (!isOpen || !task) return null

  const taskStatusInfo = statusConfig[task.status] || statusConfig.pending
  const decision = evidence?.summary.finalDecision
  const resourceId = evidence?.task.resourceId ?? task.resourceId
  const decisionLabel = decision ? decisionLabels[decision] || decision : '审核数据加载中'
  const stats = evidence?.summary.stats

  return (
    <Modal isOpen={isOpen} onClose={onClose} maxWidth="max-w-3xl">
      <div className="flex items-center justify-between p-5 border-b border-border">
        <div className="flex items-center gap-2">
          <Target className="w-5 h-5 text-primary" />
          <div>
            <h3 className="font-semibold text-text-primary">任务详情</h3>
            <p className="text-xs text-text-tertiary mt-0.5">#{task.taskId} · {task.taskName}</p>
          </div>
        </div>
      </div>

      <div className="p-5 space-y-5 max-h-[min(78vh,720px)] overflow-y-auto">
        <div className="flex items-center justify-between gap-3">
          <h4 className="font-medium text-text-primary truncate">{task.taskName}</h4>
          <Badge variant={task.status === 'completed' ? 'success' : task.status === 'failed' ? 'error' : 'warning'}>
            {taskStatusInfo.label}
          </Badge>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
          <div className="p-3 rounded-lg bg-bg-secondary/30">
            <span className="text-xs text-text-tertiary block mb-1">任务类型</span>
            <p className="text-text-primary font-medium">{task.taskType}</p>
          </div>
          <div className="p-3 rounded-lg bg-bg-secondary/30">
            <span className="text-xs text-text-tertiary block mb-1">学习者</span>
            <p className="text-text-primary font-medium">#{task.learnerId}</p>
          </div>
          <div className="p-3 rounded-lg bg-bg-secondary/30">
            <span className="text-xs text-text-tertiary block mb-1">当前阶段</span>
            <p className="text-text-primary font-medium">{task.flowStage || '-'}</p>
          </div>
          <div className="p-3 rounded-lg bg-bg-secondary/30">
            <span className="text-xs text-text-tertiary block mb-1">创建时间</span>
            <p className="text-text-primary font-medium">{task.createdAt ? new Date(task.createdAt).toLocaleString('zh-CN') : '-'}</p>
          </div>
          <div className="p-3 rounded-lg bg-bg-secondary/30">
            <span className="text-xs text-text-tertiary block mb-1">更新时间</span>
            <p className="text-text-primary font-medium">{task.updatedAt ? new Date(task.updatedAt).toLocaleString('zh-CN') : '-'}</p>
          </div>
          <div className="p-3 rounded-lg bg-bg-secondary/30">
            <span className="text-xs text-text-tertiary block mb-1">资源ID</span>
            <p className="text-text-primary font-medium">{resourceId ? `#${resourceId}` : '-'}</p>
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-text-tertiary">执行进度</span>
            <span className="text-sm font-medium text-text-primary">{Math.round(task.progress)}%</span>
          </div>
          <div className="h-2 bg-bg-tertiary rounded-full overflow-hidden">
            <div className={`h-full rounded-full transition-all duration-500 ${task.status === 'completed' ? 'bg-success' : task.status === 'failed' ? 'bg-error' : 'bg-primary'}`} style={{ width: `${Math.min(100, Math.max(0, task.progress))}%` }} />
          </div>
        </div>

        <section className="border border-border rounded-xl overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-3 bg-bg-secondary/30 border-b border-border">
            {evidence?.summary.hasSufficientEvidence ? <ShieldCheck className="w-4 h-4 text-success" /> : <ShieldAlert className="w-4 h-4 text-warning" />}
            <h5 className="text-sm font-semibold text-text-primary">可信结论摘要</h5>
            {loadingEvidence && <Loader2 className="w-4 h-4 text-primary animate-spin ml-auto" />}
          </div>
          {evidenceError ? (
            <div className="px-4 py-5 text-sm text-text-secondary">暂时无法加载审核摘要，请稍后重试。</div>
          ) : (
            <div className="p-4 space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div>
                  <span className="text-xs text-text-tertiary block mb-1">最终结论</span>
                  <Badge variant={decisionVariant(decision)}>{decisionLabel}</Badge>
                </div>
                <div>
                  <span className="text-xs text-text-tertiary block mb-1">可信度</span>
                  <p className="text-lg font-semibold text-text-primary">{evidence?.summary.confidence == null ? '证据不足' : `${evidence.summary.confidence}%`}</p>
                </div>
                <div>
                  <span className="text-xs text-text-tertiary block mb-1">辩论轮数</span>
                  <p className="text-lg font-semibold text-text-primary">{stats?.debateRounds ?? '-'}</p>
                </div>
                <div>
                  <span className="text-xs text-text-tertiary block mb-1">引用来源</span>
                  <p className="text-lg font-semibold text-text-primary">{stats?.sourceCount ?? '-'}</p>
                </div>
              </div>

              <div className="flex flex-wrap gap-2 text-xs text-text-secondary">
                <span className="px-2 py-1 rounded bg-bg-secondary">发现问题 {stats?.issuesFound ?? '-'}</span>
                <span className="px-2 py-1 rounded bg-bg-secondary">已修正 {stats?.correctionsApplied ?? '-'}</span>
                {evidence?.summary.credibility && <span className="px-2 py-1 rounded bg-bg-secondary">证据状态 {evidence.summary.credibility}</span>}
              </div>

              {evidence?.summary.keyCorrection && (
                <div className="p-3 rounded-lg border border-warning/30 bg-warning-light/30">
                  <span className="text-xs font-medium text-warning-dark">关键纠偏</span>
                  <p className="text-xs text-text-secondary mt-1">{evidence.summary.keyCorrection.description}</p>
                  <div className="grid md:grid-cols-2 gap-2 mt-2 text-xs">
                    <div className="p-2 rounded bg-error-light/40 text-error-dark max-h-20 overflow-hidden">原始主张：{evidence.summary.keyCorrection.original || '未留存'}</div>
                    <div className="p-2 rounded bg-success-light/40 text-success-dark max-h-20 overflow-hidden">修正结果：{evidence.summary.keyCorrection.revised || '未留存'}</div>
                  </div>
                </div>
              )}
            </div>
          )}
        </section>

        {task.errorMessage && (
          <div className="p-3 rounded-lg bg-error-light border border-error/30">
            <span className="text-xs text-error-dark font-medium flex items-center gap-1">
              <AlertTriangle className="w-3 h-3" />
              错误信息
            </span>
            <p className="text-error-dark text-xs mt-1">{task.errorMessage}</p>
          </div>
        )}

        <div className="flex flex-wrap items-center justify-end gap-2 pt-1">
          {resourceId && onViewResource && (
            <Button variant="outline" size="sm" onClick={() => onViewResource(resourceId)}>
              <FileText className="w-4 h-4" />
              查看生成资源
            </Button>
          )}
          {onViewEvidence && (
            <Button variant="primary" size="sm" onClick={onViewEvidence}>
              查看完整证据链
              <ArrowRight className="w-4 h-4" />
            </Button>
          )}
        </div>
      </div>
    </Modal>
  )
}
