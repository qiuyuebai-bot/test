import { lazy, Suspense, useCallback, useEffect, useMemo, useState, type CSSProperties } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  ArrowLeft,
  Check,
  Copy,
  Download,
  Loader2,
  PlayCircle,
  Printer,
  Send,
  SlidersHorizontal,
} from 'lucide-react'
import { coreApi } from '@/api'
import type { KnowledgePublicationRequest } from '@/api/core'
import type { LearningResource } from '@/types'
import { useStore } from '@/store'
import Button from '@/components/Button'
import Badge from '@/components/Badge'
import EmptyState from '@/components/EmptyState'
import { normalizeResourceContent } from '@/lib/resourceContent'
import { toast } from '@/components/toastStore'
const MarkdownContent = lazy(() => import('@/components/MarkdownContent'))

type ReaderSize = 'small' | 'medium' | 'large'

const publicationLabels: Record<string, { label: string; variant: 'default' | 'warning' | 'success' | 'error' }> = {
  pending: { label: '待管理员审核', variant: 'warning' },
  waiting_validation: { label: '等待校验', variant: 'warning' },
  publishing: { label: '发布中', variant: 'warning' },
  published: { label: '已入库', variant: 'success' },
  rejected: { label: '已驳回', variant: 'error' },
  publish_failed: { label: '发布失败', variant: 'error' },
}

function slugifyHeading(text: string, index: number): string {
  const slug = text.toLowerCase().replace(/[^\w\u4e00-\u9fff]+/g, '-').replace(/^-|-$/g, '')
  return `reader-${slug || 'section'}-${index}`
}

function isAnswerLine(line: string): boolean {
  const plainLine = line.replace(/[*_`]/g, '').replace(/^>\s?/, '').trim()
  return /^(?:[-+]|\d+[.)])?\s*(?:答案|正确答案|答案解析|解析|answer|explanation)\s*[:：]/i.test(plainLine)
}

function hideAnswerLines(content: string): string {
  return content
    .split('\n')
    .filter((line) => !isAnswerLine(line))
    .join('\n')
}

export default function ResourceReader() {
  const { resourceId } = useParams<{ resourceId: string }>()
  const navigate = useNavigate()
  const user = useStore((state) => state.user)
  const [resource, setResource] = useState<LearningResource | null>(null)
  const [publication, setPublication] = useState<KnowledgePublicationRequest | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [size, setSize] = useState<ReaderSize>('medium')
  const [showAnswers, setShowAnswers] = useState(user?.role !== 'learner')
  const [submitting, setSubmitting] = useState(false)
  const id = Number(resourceId)
  const storageKey = `resource-reader-position:${id}`

  const load = useCallback(async () => {
    if (!Number.isInteger(id) || id <= 0) {
      setError('资源不存在')
      setLoading(false)
      return
    }
    setLoading(true)
    setError('')
    try {
      const detail = await coreApi.getResourceDetail(id)
      setResource(detail)
      if (detail.resourceType === 'lecture') {
        try {
          setPublication(await coreApi.getKnowledgePublicationRequest(id))
        } catch {
          setPublication(null)
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '资源加载失败')
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => { void load() }, [load])
  useEffect(() => {
    const saved = window.localStorage.getItem(storageKey)
    if (saved) window.setTimeout(() => window.scrollTo({ top: Number(saved), behavior: 'auto' }), 0)
    const save = () => window.localStorage.setItem(storageKey, String(window.scrollY))
    window.addEventListener('scroll', save, { passive: true })
    return () => window.removeEventListener('scroll', save)
  }, [storageKey])

  const content = useMemo(() => normalizeResourceContent(resource?.content).content || '', [resource?.content])
  const displayContent = resource?.resourceType === 'exercise' && !showAnswers ? hideAnswerLines(content) : content
  const hasAnswers = resource?.resourceType === 'exercise' && content.split('\n').some(isAnswerLine)
  const headings = useMemo(() => {
    let headingIndex = 0
    return displayContent.split('\n').flatMap((line) => {
      const match = /^(#{1,3})\s+(.+?)\s*$/.exec(line)
      if (!match) return []
      const item = { level: match[1].length, title: match[2].replace(/[*_`]/g, ''), id: slugifyHeading(match[2], headingIndex) }
      headingIndex += 1
      return [item]
    })
  }, [displayContent])
  const automaticRequest = publication?.reviewNote === '系统自动入库'
  const generationProcessing = resource?.resourceType === 'lecture' &&
    (resource.status === 'generating' || resource.status === 'validating')
  const autoProcessing = resource?.resourceType === 'lecture' &&
    (generationProcessing || (automaticRequest && publication?.status === 'publishing'))
  const publicationInfo = publication
    ? publicationLabels[publication.status] || { label: publication.status, variant: 'default' as const }
    : autoProcessing
      ? { label: '自动入库中', variant: 'warning' as const }
      : null
  const canSeeAnswers = user?.role === 'admin' || user?.role === 'teacher'
  const canRequestPublication = resource?.resourceType === 'lecture' &&
    (!publication || publication.status === 'rejected') &&
    !automaticRequest && !generationProcessing
  const canApplyPublication = canRequestPublication && resource.status !== 'failed' && resource.status !== 'archived' && Boolean(content.trim())
  const publicationBlockedReason = canRequestPublication && !canApplyPublication
    ? resource.status === 'failed'
      ? '该讲义生成失败，暂不能加入知识库，请重新生成。'
      : resource.status === 'archived'
        ? '该讲义已归档，暂不能申请入库。'
        : '讲义正文为空，暂不能申请入库。'
    : null
  const automaticPublicationMessage = autoProcessing
    ? generationProcessing
      ? '质量校验完成且符合条件后，系统会自动加入所属领域知识库。'
      : '已通过质量校验，系统正在自动加入所属领域知识库。'
    : null
  const readerFontSize = size === 'small' ? '15px' : size === 'large' ? '19px' : '17px'

  const scrollToHeading = (headingId: string) => {
    document.getElementById(headingId)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const copy = async () => {
    try { await navigator.clipboard.writeText(displayContent); toast.success('正文已复制') } catch { toast.error('复制失败') }
  }
  const exportResource = async () => {
    try {
      const blob = await coreApi.exportResource(id, 'md')
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `${resource?.title || 'resource'}.md`
      anchor.click()
      URL.revokeObjectURL(url)
    } catch { toast.error('导出失败') }
  }
  const applyPublication = async () => {
    setSubmitting(true)
    try {
      setPublication(await coreApi.createKnowledgePublicationRequest(id))
      toast.success('已提交入库申请')
    } catch (err) { toast.error(err instanceof Error ? err.message : '提交失败') } finally { setSubmitting(false) }
  }

  if (loading) return <div className="flex min-h-[70vh] items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div>
  if (error || !resource) {
    return <div className="mx-auto max-w-3xl py-16"><EmptyState type="default" title={error || '资源不存在'} description="请返回资源列表后重试" /><div className="mt-6 text-center"><Button variant="outline" onClick={() => navigate('/resources')}><ArrowLeft className="h-4 w-4" />返回资源列表</Button></div></div>
  }
  if (!content) {
    return <div className="mx-auto max-w-3xl py-16"><EmptyState type="default" title="暂不可阅读" description="该资源正文为空或格式异常" /><div className="mt-6 text-center"><Button variant="outline" onClick={() => navigate(-1)}><ArrowLeft className="h-4 w-4" />返回</Button></div></div>
  }

  return (
    <div className="min-h-[calc(100vh-5rem)] bg-bg-primary print:bg-white">
      <div data-testid="resource-reader-toolbar" className="sticky -top-16 z-20 border-b border-border bg-bg-primary pt-16 print:hidden">
        <div className="mx-auto flex max-w-[1440px] flex-wrap items-center gap-2 px-4 py-3 lg:px-8">
          <Button variant="ghost" size="sm" onClick={() => navigate(-1)} aria-label="返回"><ArrowLeft className="h-4 w-4" />返回</Button>
          <div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold text-text-primary">{resource.title}</p><p className="text-xs text-text-tertiary">{resource.resourceType === 'guide' ? '实操指南' : resource.resourceType === 'exercise' ? '分阶测试题' : '专属讲义'} · v{resource.versionNumber ?? resource.version ?? 1}</p></div>
          {publicationInfo && <Badge variant={publicationInfo.variant}>{publicationInfo.label}</Badge>}
          <div className="flex items-center gap-1 border-l border-border pl-2">
            <label className="flex items-center gap-1 text-xs text-text-secondary" title="字号"><SlidersHorizontal className="h-4 w-4" /><select aria-label="字号" value={size} onChange={(event) => setSize(event.target.value as ReaderSize)} className="bg-transparent"><option value="small">小</option><option value="medium">中</option><option value="large">大</option></select></label>
            <Button variant="ghost" size="sm" onClick={() => window.print()} aria-label="打印"><Printer className="h-4 w-4" /></Button>
            <Button variant="ghost" size="sm" onClick={() => void copy()} aria-label="复制"><Copy className="h-4 w-4" /></Button>
            <Button variant="ghost" size="sm" onClick={() => void exportResource()} aria-label="导出"><Download className="h-4 w-4" /></Button>
          </div>
        </div>
      </div>
      <div className="mx-auto grid max-w-[1440px] grid-cols-1 gap-8 px-4 py-8 lg:grid-cols-[240px_minmax(0,820px)] lg:px-8">
        <aside className="print:hidden lg:sticky lg:top-24 lg:h-fit"><div className="border-b border-border pb-3 text-xs font-semibold uppercase tracking-wider text-text-tertiary">目录</div><nav aria-label="资源目录" className="mt-3 space-y-1">{headings.length ? headings.map((heading) => <button key={heading.id} type="button" onClick={() => scrollToHeading(heading.id)} className="block w-full border-l-2 border-transparent py-1.5 pl-3 text-left text-sm text-text-secondary hover:border-primary hover:text-primary" style={{ paddingLeft: `${(heading.level - 1) * 12 + 12}px` }}>{heading.title}</button>) : <p className="text-sm text-text-tertiary">暂无章节</p>}</nav></aside>
        <main className="min-w-0">
          <header className="mb-8 border-b border-border pb-6"><div className="mb-3 flex flex-wrap items-center gap-2"><Badge variant="default">{resource.resourceType === 'guide' ? '实操指南' : resource.resourceType === 'exercise' ? '分阶测试题' : '专属讲义'}</Badge>{resource.knowledgeTopic && <span className="text-sm text-text-tertiary">{resource.knowledgeTopic}</span>}</div><h1 className="text-3xl font-semibold leading-tight text-text-primary">{resource.title}</h1>{resource.contentSummary && <p className="mt-4 text-base leading-7 text-text-secondary">{resource.contentSummary}</p>}</header>
          {resource.resourceType === 'exercise' && canSeeAnswers && <div className="mb-6 flex items-center justify-between border border-primary/20 bg-primary/5 px-4 py-3 print:hidden"><span className="text-sm text-text-secondary">教师/管理员答案视图</span><Button variant="outline" size="sm" onClick={() => setShowAnswers((value) => !value)} disabled={!hasAnswers}>{hasAnswers ? (showAnswers ? '隐藏答案' : '查看答案') : '暂无答案'}</Button></div>}
          {resource.resourceType === 'exercise' && !canSeeAnswers && <div className="mb-6 flex items-center justify-between border border-border bg-bg-secondary px-4 py-3 print:hidden"><span className="text-sm text-text-secondary">完成阅读后进入练习流程作答</span><Button variant="primary" size="sm" onClick={() => navigate(`/guidance?resourceId=${id}&topic=${encodeURIComponent(resource.knowledgeTopic || '')}`)}><PlayCircle className="h-4 w-4" />开始练习</Button></div>}
          <article data-testid="resource-reader-content" className="resource-reader-content leading-8 text-text-primary" style={{ '--reader-font-size': readerFontSize } as CSSProperties}>
            <Suspense fallback={<p className="text-sm text-text-tertiary">正在加载正文...</p>}><MarkdownContent content={displayContent} headingIdPrefix="reader" /></Suspense>
          </article>
          {canApplyPublication && <div className="mt-12 border-t border-border pt-6 print:hidden"><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="font-medium text-text-primary">将历史专属讲义加入领域知识库</p><p className="mt-1 text-sm text-text-secondary">仅历史资源需要提交人工入库申请；新生成且达标的讲义会自动入库。</p></div><Button variant="primary" onClick={() => void applyPublication()} disabled={submitting}><Send className="h-4 w-4" />{submitting ? '提交中...' : '提交人工入库申请'}</Button></div></div>}
          {automaticPublicationMessage && <div className="mt-12 border-t border-border pt-6 print:hidden"><p className="text-sm text-text-secondary">{automaticPublicationMessage}</p></div>}
          {publicationBlockedReason && <div className="mt-12 border-t border-border pt-6 print:hidden"><p className="text-sm text-text-secondary">{publicationBlockedReason}</p></div>}
          {publication?.status === 'rejected' && <div className="mt-12 border-t border-error/20 pt-6 print:hidden"><p className="text-sm text-error">驳回原因：{publication.reviewNote || '未填写'}</p></div>}
          {publication?.status === 'publish_failed' && <div className="mt-12 border-t border-error/20 pt-6 print:hidden"><p className="text-sm text-error">自动入库失败：{publication.errorMessage || '请联系管理员重试'}</p></div>}
          {user?.role === 'admin' && publication?.status === 'published' && publication.knowledgeDocId && <div className="mt-12 border-t border-success/20 pt-6 print:hidden"><Link to="/knowledge-base" className="inline-flex items-center gap-2 text-sm text-success hover:underline"><Check className="h-4 w-4" />查看知识库文档</Link></div>}
        </main>
      </div>
    </div>
  )
}
