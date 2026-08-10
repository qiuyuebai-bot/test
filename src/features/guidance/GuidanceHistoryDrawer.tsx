import { useMemo, useState } from 'react'
import type { HistoryRecord } from './types'
import { formatHistoryDate, formatUserAnswer } from './sessionPersistence'
import Card from '@/components/Card'
import Button from '@/components/Button'
import EmptyState from '@/components/EmptyState'
import { Clock, History, Trash2, X } from 'lucide-react'

interface GuidanceHistoryDrawerProps {
  learnerName: string
  records: HistoryRecord[]
  loading: boolean
  error: string | null
  onOpen: () => void
  onDelete: (params: { recordId?: number; sessionId?: string }) => Promise<void>
  onClear: () => Promise<void>
  defaultOpen?: boolean
}

function groupHistory(records: HistoryRecord[]) {
  const groups = new Map<string, { sessionId: string | null; records: HistoryRecord[] }>()
  records.forEach((record) => {
    const key = record.sessionId || `record:${record.recordId}`
    const group = groups.get(key) ?? { sessionId: record.sessionId, records: [] }
    group.records.push(record)
    groups.set(key, group)
  })
  return Array.from(groups.values())
    .map((group) => ({
      ...group,
      records: [...group.records].sort((left, right) => (left.sequenceIndex ?? 0) - (right.sequenceIndex ?? 0)),
      startedAt: Math.min(...group.records.map((record) => {
        const timestamp = new Date(record.createdAt).getTime()
        return Number.isNaN(timestamp) ? 0 : timestamp
      })),
    }))
    .sort((left, right) => right.startedAt - left.startedAt)
    .map((group, index, all) => ({ ...group, label: `第 ${all.length - index} 轮` }))
}

export default function GuidanceHistoryDrawer({
  learnerName,
  records,
  loading,
  error,
  onOpen,
  onDelete,
  onClear,
  defaultOpen = false,
}: GuidanceHistoryDrawerProps) {
  const [open, setOpen] = useState(defaultOpen)
  const [expandedRecord, setExpandedRecord] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const groups = useMemo(() => groupHistory(records), [records])

  const toggle = () => {
    const nextOpen = !open
    setOpen(nextOpen)
    if (nextOpen) onOpen()
  }

  const runAction = async (action: () => Promise<void>) => {
    setActionLoading(true)
    setActionError(null)
    try {
      await action()
      setExpandedRecord(null)
    } catch (actionFailure) {
      setActionError(actionFailure instanceof Error ? actionFailure.message : '历史记录操作失败，请稍后重试')
    } finally {
      setActionLoading(false)
    }
  }

  return (
    <div className="space-y-3">
      <Button variant="outline" size="sm" onClick={toggle} aria-expanded={open}>
        <History className="h-4 w-4" />
        {open ? '收起历史记录' : '查看历史记录'}
      </Button>
      {open && (
        <Card padding="md" className="relative">
          <div className="mb-3 flex items-start justify-between gap-3">
            <div>
              <h4 className="flex items-center gap-2 text-sm font-semibold text-text-primary"><Clock className="h-4 w-4 text-text-secondary" />交互历史记录</h4>
              <p className="mt-1 text-xs text-text-tertiary">{learnerName} · {records.length} 条记录 · 点击题目可回放</p>
            </div>
            <div className="flex items-center gap-1">
              {records.length > 0 && <Button variant="ghost" size="sm" onClick={() => { if (window.confirm(`确定清空“${learnerName}”的全部交互历史吗？`)) void runAction(onClear) }} disabled={actionLoading}><Trash2 className="h-3.5 w-3.5 text-error" />清空当前画像</Button>}
              <Button variant="ghost" size="sm" onClick={() => setOpen(false)} aria-label="关闭历史记录"><X className="h-4 w-4" /></Button>
            </div>
          </div>
          {(error || actionError) && <p role="alert" className="mb-3 text-xs text-error">{actionError || error}</p>}
          {loading ? (
            <p role="status" className="py-6 text-center text-sm text-text-tertiary">正在读取历史记录…</p>
          ) : records.length === 0 ? (
            <EmptyState type="default" title="暂无交互记录" description="答题后将在这里显示交互记录" />
          ) : (
            <div className="max-h-[420px] space-y-3 overflow-y-auto pr-1 overscroll-contain">
              {groups.map((group) => (
                <div key={group.sessionId ?? group.records[0]?.recordId} className="rounded-xl border border-border/60 bg-bg-secondary/10 p-2">
                  <div className="flex items-center justify-between gap-2 px-2 pb-2">
                    <div className="flex items-center gap-2 text-xs text-text-secondary"><span className="font-semibold text-text-primary">{group.label}</span><span>{group.records.length} 题</span><span>· {formatHistoryDate(group.records[0]?.createdAt ?? '')}</span></div>
                    {group.sessionId && <Button variant="ghost" size="sm" onClick={() => { if (window.confirm(`确定删除${group.label}的全部记录吗？`)) void runAction(() => onDelete({ sessionId: group.sessionId ?? undefined })) }} disabled={actionLoading} className="h-7 px-2 text-xs text-error hover:text-error">删除本轮</Button>}
                  </div>
                  <div className="space-y-2">
                    {group.records.map((record, index) => {
                      const expanded = expandedRecord === record.recordId
                      const sequence = record.sequenceIndex ?? index + 1
                      return (
                        <div key={record.recordId} className="overflow-hidden rounded-xl border border-border/50 bg-bg-card">
                          <button type="button" aria-expanded={expanded} onClick={() => setExpandedRecord(expanded ? null : record.recordId)} className="flex w-full items-center justify-between gap-2 p-3 text-left hover:bg-bg-secondary/50">
                            <span className="flex min-w-0 items-center gap-2"><span className={`flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-lg text-xs font-medium ${record.result === 'correct' ? 'bg-success/10 text-success' : 'bg-warning-light text-warning-dark'}`}>{sequence}</span><span className="truncate text-sm text-text-primary">{record.questionTopic || '未命名主题'}</span></span>
                            <span className="text-xs text-text-tertiary">{record.result === 'correct' ? '正确' : '需复习'}</span>
                          </button>
                          <Button variant="ghost" size="sm" aria-label={`删除第${sequence}题记录`} onClick={() => { if (window.confirm(`确定删除第${sequence}题记录吗？`)) void runAction(() => onDelete({ recordId: Number(record.recordId) })) }} disabled={actionLoading} className="h-8 px-2 text-error hover:text-error">删除记录</Button>
                          {expanded && (
                            <div className="space-y-2 border-t border-border/50 bg-bg-secondary/20 p-3 text-sm">
                              <p className="font-medium text-text-primary">题目回放：</p>
                              <p className="leading-relaxed text-text-secondary">{record.questionContent || '题目内容未记录'}</p>
                              <p className="text-text-secondary">我的答案：{formatUserAnswer(record.userAnswer)}</p>
                              {record.feedbackContent && <p className="leading-relaxed text-text-secondary">{record.feedbackContent}</p>}
                              <div className="pt-1 text-xs text-text-tertiary">{formatHistoryDate(record.createdAt)}</div>
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}
    </div>
  )
}
