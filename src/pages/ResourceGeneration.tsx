import { lazy, Suspense, useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useStore } from '@/store'
import { useShallow } from 'zustand/react/shallow'
import type { LearningResource } from '@/types'
import { agentApi, coreApi } from '@/api'
import { useResourceGenerationTask } from '@/hooks'
import Card from '@/components/Card'
import Badge from '@/components/Badge'
import Button from '@/components/Button'
import Modal from '@/components/Modal'
const MarkdownContent = lazy(() => import('@/components/MarkdownContent'))
import { normalizeResourceContent } from '@/lib/resourceContent'
import {
  FileText,
  ListChecks,
  BookOpen,
  Sparkles,
  Play,
  CheckCircle2,
  AlertCircle,
  User,
  Target,
  Brain,
  Shield,
  Eye,
  Download,
  Copy,
  Printer,
  Route,
  Search,
  X,
  Building2,
  Trash2,
} from 'lucide-react'
import EmptyState from '@/components/EmptyState'
import { CardSkeleton } from '@/components/Skeleton'
import { toast } from '@/components/toastStore'

type ResourceType = 'guide' | 'exercise' | 'lecture'
type ResourceViewMode = 'list' | 'generate'

const resourceTypeConfig: Record<
  ResourceType,
  { label: string; icon: typeof FileText; color: string }
> = {
  guide: { label: '实操指南', icon: Route, color: 'text-primary' },
  exercise: { label: '分阶测试题', icon: ListChecks, color: 'text-success' },
  lecture: { label: '专属讲义', icon: BookOpen, color: 'text-warning' },
}

const reviewStatusMap: Record<
  string,
  { label: string; variant: 'success' | 'warning' | 'error' | 'default' }
> = {
  pending: { label: '待处理', variant: 'warning' },
  approved: { label: '已通过', variant: 'success' },
  rejected: { label: '已拒绝', variant: 'error' },
  revised: { label: '已修订', variant: 'default' },
  published: { label: '已发布', variant: 'success' },
}

function getReviewStatusInfo(resource: LearningResource) {
  if (resource.status === 'failed' && resource.reviewStatus === 'pending') {
    return null
  }
  return reviewStatusMap[resource.reviewStatus] || reviewStatusMap.pending
}

const contentTypeMap: Record<string, string> = {
  pdf: 'PDF文档',
  html: 'HTML页面',
  video: '视频资源',
  text: '文本内容',
}

function isMarkdownResource(resource: LearningResource): boolean {
  return (
    ['guide', 'exercise', 'lecture'].includes(resource.resourceType) &&
    (resource.formatType === 'md' || resource.formatType === undefined)
  )
}

const generationSteps = [
  { id: 1, stage: 'diagnosis', name: '学情诊断', agent: '诊断Agent', icon: User },
  { id: 2, stage: 'knowledge_retrieval', name: '知识检索', agent: '检索Agent', icon: Target },
  { id: 3, stage: 'generation', name: '内容生成', agent: '生成Agent', icon: Brain },
  { id: 4, stage: 'debate', name: '交叉校验', agent: '裁判Agent', icon: Shield },
  { id: 5, stage: 'final_revision', name: '最终修正', agent: '系统', icon: CheckCircle2 },
  { id: 6, stage: 'complete', name: '输出成品', agent: '系统', icon: Sparkles },
]

const industryLabels = ['智能制造', '工业互联网', '软件开发', '人工智能训练', '数据分析', '网络安全', '电气工程及其自动化', '基础数学', '计算机科学与技术', '大学物理', '通用']

const stageToStepIndex: Record<string, number> = {
  init: 0,
  diagnosis: 0,
  knowledge_retrieval: 1,
  generation: 2,
  judge_first: 3,
  debate: 3,
  final_revision: 4,
  complete: 5,
}

export default function ResourceGeneration() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const requestedResourceId = Number(searchParams.get('resourceId'))
  const requestedMode = searchParams.get('mode') as ResourceViewMode | null
  const requestedLearnerId = Number(searchParams.get('learnerId'))
  const requestedDimension = searchParams.get('dimension') || ''
  const requestedTopic = searchParams.get('topic') || ''
  const viewMode = requestedMode === 'list' || requestedMode === 'generate' ? requestedMode : null
  const { learners, currentLearner, resources, resourceLoading, resourcesTotal } = useStore(
    useShallow((s) => ({
      learners: s.learners,
      currentLearner: s.currentLearner,
      resources: s.resources,
      resourceLoading: s.resourceLoading,
      resourcesTotal: s.resourcesTotal,
    })),
  )
  const { setCurrentLearner, fetchLearners, fetchResources } = useStore(
    useShallow((s) => ({
      setCurrentLearner: s.setCurrentLearner,
      fetchLearners: s.fetchLearners,
      fetchResources: s.fetchResources,
    })),
  )

  const [stageDescription, setStageDescription] = useState('')
  const [debateInfo, setDebateInfo] = useState<{ round: number; total: number } | null>(null)
  const [industryOptions, setIndustryOptions] = useState<{ value: string; label: string }[]>([])
  const [activeTab, setActiveTab] = useState<ResourceType>('guide')
  const [selectedResource, setSelectedResource] = useState<LearningResource | null>(null)
  const [isPreviewOpen, setIsPreviewOpen] = useState(false)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [selectedLearnerId, setSelectedLearnerId] = useState<number | null>(
    Number.isInteger(requestedLearnerId) && requestedLearnerId > 0 ? requestedLearnerId : null,
  )
  const [targetTopic, setTargetTopic] = useState(requestedTopic)
  const [selectedIndustry, setSelectedIndustry] = useState('人工智能训练')
  const [currentStepDesc, setCurrentStepDesc] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [resourceToDelete, setResourceToDelete] = useState<LearningResource | null>(null)
  const [deletingResourceId, setDeletingResourceId] = useState<number | null>(null)
  const completeTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const debateRoundText = debateInfo
    ? `第${debateInfo.round}${debateInfo.total > 0 ? `/${debateInfo.total}` : ''}轮辩论中...`
    : ''

  useEffect(() => {
    setIndustryOptions(industryLabels.map((name) => ({ value: name, label: name })))
  }, [])

  useEffect(() => {
    return () => {
      if (completeTimeoutRef.current) {
        clearTimeout(completeTimeoutRef.current)
        completeTimeoutRef.current = null
      }
    }
  }, [])

  const handleSSEEvent = useCallback(
    (event: { event: string; data: unknown; timestamp: number }) => {
      const data = (event.data as Record<string, unknown>) || {}
      switch (event.event) {
        case 'stage_update':
          setStageDescription((data.description as string) || '')
          break
        case 'debate_round':
          {
            const round = Number(data.round)
            const total = Number(data.maxRounds ?? data.max_rounds ?? data.totalRounds ?? data.total_rounds)
            if (Number.isFinite(round) && round > 0) {
              setDebateInfo({ round, total: Number.isFinite(total) && total > 0 ? total : 0 })
            }
          }
          break
        case 'debate_result':
          {
            const round = Number(data.round)
            const total = Number(data.maxRounds ?? data.max_rounds ?? data.totalRounds ?? data.total_rounds)
            if (Number.isFinite(round) && round > 0) {
              setDebateInfo({ round, total: Number.isFinite(total) && total > 0 ? total : 0 })
            }
          }
          break
        case 'task_failed':
          setError((data.error as string) || '资源生成失败')
          break
      }
    },
    [],
  )

  const selectResourceById = useCallback(
    async (resourceId: number) => {
      const listItem = resources.find((r) => r.id === resourceId)
      try {
        const detail = await coreApi.getResourceDetail(resourceId)
        const effectiveMatchScore = detail.matchScore ?? listItem?.matchScore
        const normalized = {
          ...(listItem || detail),
          ...detail,
          resourceType: detail.resourceType || listItem?.resourceType || activeTab,
          targetLearnerId:
            detail.targetLearnerId ?? detail.learnerId ?? listItem?.targetLearnerId ?? 0,
          contentSummary: detail.contentSummary ?? detail.summary ?? listItem?.contentSummary ?? '',
          contentType: detail.contentType || listItem?.contentType || 'text',
          formatType: detail.formatType ?? listItem?.formatType,
          qualityScore:
            detail.qualityScore ??
            (effectiveMatchScore == null
              ? null
              : Math.round(
                  effectiveMatchScore >= 0 && effectiveMatchScore <= 1
                    ? effectiveMatchScore * 100
                    : effectiveMatchScore,
                )),
          hallucinationDetected:
            detail.hallucinationDetected ??
            detail.hasHallucination ??
            listItem?.hallucinationDetected ??
            false,
          reviewStatus: detail.reviewStatus || listItem?.reviewStatus || 'pending',
          versionNumber: detail.versionNumber ?? detail.version ?? listItem?.versionNumber ?? 1,
          generatedByAgent:
            detail.generatedByAgent ??
            detail.createdByAgent ??
            listItem?.generatedByAgent ??
            'generation-agent',
          generationTime:
            detail.generationTime ??
            detail.createdAt ??
            listItem?.generationTime ??
            new Date().toISOString(),
          metaData: detail.metaData ?? listItem?.metaData ?? {},
        } as LearningResource
        setSelectedResource(normalized)
        setActiveTab(normalized.resourceType as ResourceType)
      } catch {
        if (listItem) setSelectedResource(listItem)
      }
    },
    [activeTab, resources],
  )

  useEffect(() => {
    if (!Number.isInteger(requestedResourceId) || requestedResourceId <= 0) return
    void selectResourceById(requestedResourceId)
  }, [requestedResourceId, selectResourceById])

  const generationTask = useResourceGenerationTask({
    learnerId: selectedLearnerId,
    onEvent: handleSSEEvent,
    onComplete: (_taskId, data) => {
      setStageDescription('任务完成')
      setDebateInfo(null)
      if (completeTimeoutRef.current) clearTimeout(completeTimeoutRef.current)
      completeTimeoutRef.current = setTimeout(() => {
        void fetchResources({
          page: 1,
          pageSize: 50,
          learnerId: selectedLearnerId || undefined,
          topic: requestedTopic || undefined,
        })
        const completed = data as { result?: { resourceId?: number; resource_id?: number } }
        const resourceId = completed?.result?.resourceId ?? completed?.result?.resource_id
        if (resourceId) void selectResourceById(resourceId)
      }, 1500)
    },
    onFailed: (_taskId, message) => {
      setError(message)
      setDebateInfo(null)
    },
  })
  const sse = generationTask.stream
  const isGenerating = generationTask.isGenerating

  useEffect(() => {
    fetchLearners({ page: 1, pageSize: 50 })
  }, [fetchLearners])

  useEffect(() => {
    if (!selectedLearnerId) return
    void fetchResources({
      page: 1,
      pageSize: 50,
      learnerId: selectedLearnerId,
      topic: requestedTopic || undefined,
    })
  }, [fetchResources, requestedTopic, selectedLearnerId])

  useEffect(() => {
    if (requestedTopic) setTargetTopic(requestedTopic)
  }, [requestedTopic])

  useEffect(() => {
    if (learners.length === 0) return

    const currentId = currentLearner?.id
    const hasSelectedLearner = selectedLearnerId
      ? learners.some((l) => l.id === selectedLearnerId)
      : false
    const requestedLearner = requestedLearnerId > 0
      ? learners.find((l) => l.id === requestedLearnerId)
      : undefined
    const nextLearner = hasSelectedLearner
      ? learners.find((l) => l.id === selectedLearnerId)
      : requestedLearner || learners.find((l) => l.id === currentId) || learners[0]

    if (!nextLearner) return
    if (selectedLearnerId !== nextLearner.id) {
      setSelectedLearnerId(nextLearner.id)
    }
    if (currentLearner?.id !== nextLearner.id) {
      setCurrentLearner(nextLearner)
    }
  }, [learners, currentLearner, requestedLearnerId, selectedLearnerId, setCurrentLearner])

  useEffect(() => {
    setCurrentStepDesc(stageDescription || generationTask.description)
  }, [generationTask.description, stageDescription])

  useEffect(() => {
    if (generationTask.connectionError && generationTask.taskId) {
      setError('实时进度连接暂时中断，任务仍在后台继续执行')
    }
  }, [generationTask.connectionError, generationTask.taskId])

  const selectedLearner =
    learners.find((l) => l.id === selectedLearnerId) || currentLearner || learners[0]

  const currentStepIndex =
    (generationTask.currentStage ? stageToStepIndex[generationTask.currentStage] : undefined) ?? (isGenerating ? 0 : -1)
  const generationProgress = generationTask.progress

  const handleSelectLearner = (learnerId: number) => {
    const learner = learners.find((l) => l.id === learnerId)
    if (learner) {
      setSelectedLearnerId(learner.id)
      setCurrentLearner(learner)
    }
  }

  const handleSelectResource = useCallback(async (resource: LearningResource) => {
    setSelectedResource(resource)
    // 列表接口不含 content 字段，需要调详情接口获取完整内容
    if (!resource.content) {
      setLoadingDetail(true)
      try {
        const detail = await coreApi.getResourceDetail(resource.id)
        setSelectedResource({ ...resource, ...detail })
      } catch {
        // keep the list-level data if detail fails
      } finally {
        setLoadingDetail(false)
      }
    }
  }, [])

  useEffect(() => {
    if (requestedResourceId > 0) return
    if (resources.length > 0 && !selectedResource) {
      const filtered = resources.filter((r) => r.resourceType === activeTab)
      if (filtered.length > 0) {
        void handleSelectResource(filtered[0])
      }
    }
  }, [resources, activeTab, selectedResource, handleSelectResource, requestedResourceId])

  const handleGenerate = useCallback(async () => {
    if (!selectedLearner) {
      setError('请先选择学习者')
      return
    }
    if (!targetTopic.trim()) {
      setError('请输入目标知识点')
      return
    }
    if (!generationTask.beginSubmission()) return

    setError(null)
    setCurrentStepDesc('任务初始化中...')
    setDebateInfo(null)

    try {
      const result = await agentApi.runFullPipeline({
        learnerId: selectedLearner.id,
        targetTopic: targetTopic.trim(),
        resourceType: activeTab,
        industry: selectedIndustry,
      })
      generationTask.attachTask(result.taskId)
    } catch (err) {
      generationTask.failSubmission()
      setError(err instanceof Error ? err.message : '资源生成失败，请重试')
    }
  }, [activeTab, generationTask, selectedIndustry, selectedLearner, targetTopic])

  const filteredResources = resources.filter((r) => r.resourceType === activeTab)

  const getResourceText = () => {
    if (!selectedResource) return ''
    return (
      normalizeResourceContent(selectedResource.content).content ||
      selectedResource.contentSummary ||
      selectedResource.title
    )
  }

  const handlePreview = () => {
    if (!selectedResource) return
    setIsPreviewOpen(true)
  }

  const handleRead = () => {
    if (!selectedResource) return
    navigate(`/resources/${selectedResource.id}/read`)
  }

  const handlePrint = () => {
    if (!selectedResource) return
    window.print()
  }

  const handleCopy = async () => {
    if (!selectedResource) return
    try {
      await navigator.clipboard.writeText(getResourceText())
      toast.success('已复制到剪贴板')
    } catch {
      toast.error('复制失败')
    }
  }

  const handleExport = () => {
    if (!selectedResource) return
    const text = getResourceText()
    const isHtml = selectedResource.contentType === 'html'
    const blob = new Blob([text], {
      type: isHtml ? 'text/html;charset=utf-8' : 'text/plain;charset=utf-8',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${selectedResource.title || 'resource'}${isHtml ? '.html' : '.txt'}`
    a.click()
    URL.revokeObjectURL(url)
    toast.success('资源已导出')
  }

  const handleDeleteResource = async () => {
    if (!resourceToDelete || deletingResourceId != null) return
    const resource = resourceToDelete
    setDeletingResourceId(resource.id)
    try {
      await coreApi.deleteResource(resource.id)
      if (selectedResource?.id === resource.id) setSelectedResource(null)
      setResourceToDelete(null)
      await fetchResources({
        page: 1,
        pageSize: 50,
        learnerId: selectedLearnerId || undefined,
        topic: requestedTopic || undefined,
      })
      toast.success('资源已删除')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '删除资源失败')
    } finally {
      setDeletingResourceId(null)
    }
  }

  const renderResourceDetail = () => {
    if (!selectedResource) {
      return <EmptyState.Document />
    }

    const statusInfo = getReviewStatusInfo(selectedResource)
    const shouldRenderMarkdown = isMarkdownResource(selectedResource)
    const normalizedContent = normalizeResourceContent(selectedResource.content)

    return (
      <div className="space-y-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              {statusInfo && (
                <Badge variant={statusInfo.variant} size="sm">
                  {statusInfo.label}
                </Badge>
              )}
              <Badge variant="default" size="sm">
                {shouldRenderMarkdown
                  ? 'Markdown 文档'
                  : contentTypeMap[selectedResource.contentType] || selectedResource.contentType}
              </Badge>
              {selectedResource.hallucinationDetected && (
                <Badge variant="error" size="sm">
                  <AlertCircle className="w-3 h-3 mr-1" />
                  检测到幻觉
                </Badge>
              )}
            </div>
            <h3 className="text-base font-semibold text-text-primary mb-1">
              {selectedResource.title}
            </h3>
          </div>
        </div>

        {normalizedContent.content ? (
          <div className="rounded-xl bg-bg-secondary/70 border border-border/50 p-4">
            <div className="flex items-center gap-2 mb-2 text-xs text-text-tertiary">
              <FileText className="w-3.5 h-3.5" />
              <span>资源内容</span>
            </div>
            {shouldRenderMarkdown ? (
              <Suspense fallback={<div className="text-sm text-text-tertiary">正在加载内容预览...</div>}>
                <MarkdownContent content={normalizedContent.content} />
              </Suspense>
            ) : (
              <pre className="text-xs font-mono text-text-primary leading-relaxed whitespace-pre-wrap max-h-64 overflow-y-auto">
                {normalizedContent.content}
              </pre>
            )}
          </div>
        ) : normalizedContent.error && normalizedContent.error !== 'empty' ? (
          <div className="rounded-xl border border-warning/30 bg-warning/5 p-8 text-center">
            <AlertCircle className="w-10 h-10 text-warning mx-auto mb-2" />
            <p className="text-sm font-medium text-text-primary">该资源的历史生成结果格式异常</p>
            <p className="text-xs text-text-tertiary mt-1">请重新生成，系统不会再将审核或 mock 数据显示为资源正文。</p>
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-border p-8 text-center">
            <FileText className="w-10 h-10 text-text-tertiary mx-auto mb-2" />
            <p className="text-sm text-text-tertiary">资源内容加载中或暂不可预览</p>
            {selectedResource.contentPath && (
              <p className="text-xs text-text-tertiary mt-1">
                存储路径：{selectedResource.contentPath}
              </p>
            )}
          </div>
        )}

        {selectedResource.metaData && Object.keys(selectedResource.metaData).length > 0 && (
          <div className="pt-3 border-t border-border/50">
            <h4 className="text-xs font-medium text-text-secondary mb-2">元数据</h4>
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(selectedResource.metaData).map(([key, value]) => (
                <div key={key} className="text-xs">
                  <span className="text-text-tertiary">{key}：</span>
                  <span className="text-text-secondary">{String(value)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    )
  }

  return (
    <>
      <div className="space-y-4 animate-fade-in">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="hero-anchor text-xl font-semibold text-text-primary">
              {viewMode === 'list' ? '相关学习资源' : viewMode === 'generate' ? '生成学习资源' : '个性化资源生成'}
            </h1>
            <p className="text-sm text-text-secondary mt-1">
              {viewMode === 'list'
                ? `查看${requestedTopic || requestedDimension || '当前学习者'}的已有资源`
                : viewMode === 'generate'
                  ? `已填入${requestedTopic || requestedDimension || '目标主题'}，确认后开始生成`
                  : '多 Agent 协同生成一份个性化学习资源'}
            </p>
          </div>
          {error && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-danger/10 text-danger text-sm">
              <AlertCircle className="w-4 h-4" />
              {error}
              <button onClick={() => setError(null)}>
                <X className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>

        <div className="grid grid-cols-12 gap-4">
          {/* 左侧：学情参数配置 */}
          <div className="col-span-12 lg:col-span-3">
            {viewMode !== 'list' && (
            <Card padding="md" className="space-y-5">
              <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
                <User className="w-4 h-4 text-text-secondary" />
                学情参数配置
              </h3>

              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-2">
                    选择学习者
                  </label>
                  <div className="space-y-2 max-h-36 overflow-y-auto">
                    {learners.map((l) => {
                      const isSelected = selectedLearner?.id === l.id
                      return (
                        <button
                          key={l.id}
                          onClick={() => handleSelectLearner(l.id)}
                          disabled={isGenerating}
                          className={`w-full p-3 rounded-lg border text-left text-sm transition-all ${
                            isSelected
                              ? 'border-primary bg-primary/10 shadow-sm'
                              : 'border-border bg-bg-secondary/30 hover:border-primary/30 hover:bg-bg-card'
                          } ${isGenerating ? 'opacity-60 cursor-not-allowed' : ''}`}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <p
                              className={`font-medium ${isSelected ? 'text-primary' : 'text-text-primary'}`}
                            >
                              {l.realName}
                            </p>
                            {isSelected && (
                              <span className="inline-flex items-center gap-1 text-[11px] font-medium text-primary">
                                <CheckCircle2 className="w-3 h-3" />
                                已选
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-text-tertiary mt-1">
                            {l.educationLevel} · {l.major}
                          </p>
                        </button>
                      )
                    })}
                    {learners.length === 0 && (
                      <p className="text-xs text-text-tertiary py-2">暂无可选学习者</p>
                    )}
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-2">
                    <Building2 className="w-3 h-3 inline mr-1" />
                    所属行业
                  </label>
                  <select
                    value={selectedIndustry}
                    onChange={(e) => setSelectedIndustry(e.target.value)}
                    disabled={isGenerating}
                    className="w-full px-3 py-2 rounded-lg border border-border bg-bg-secondary/30 text-sm text-text-primary focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 disabled:opacity-60"
                  >
                    {industryOptions.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-2">
                    资源类型
                  </label>
                  <div className="grid grid-cols-1 gap-1.5">
                    {(
                      Object.entries(resourceTypeConfig) as [
                        ResourceType,
                        typeof resourceTypeConfig.guide,
                      ][]
                    ).map(([type, config]) => {
                      const Icon = config.icon
                      return (
                        <button
                          key={type}
                          onClick={() => {
                            if (!isGenerating) {
                              setActiveTab(type)
                              setSelectedResource(null)
                            }
                          }}
                          disabled={isGenerating}
                          className={`flex items-center gap-2 p-2.5 rounded-lg border text-left text-sm transition-all ${
                            activeTab === type
                              ? 'border-primary/30 bg-primary/5'
                              : 'border-border bg-bg-secondary/30 hover:border-primary/20'
                          } ${isGenerating ? 'opacity-60 cursor-not-allowed' : ''}`}
                        >
                          <Icon
                            className={`w-4 h-4 ${activeTab === type ? config.color : 'text-text-tertiary'}`}
                          />
                          <span
                            className={
                              activeTab === type
                                ? 'text-text-primary font-medium'
                                : 'text-text-secondary'
                            }
                          >
                            {config.label}
                          </span>
                        </button>
                      )
                    })}
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-2">
                    目标知识点 / 主题
                  </label>
                  <input
                    type="text"
                    value={targetTopic}
                    onChange={(e) => setTargetTopic(e.target.value)}
                    placeholder="如：反向传播算法、RESTful API 设计..."
                    disabled={isGenerating}
                    className="w-full px-3 py-2 rounded-lg border border-border bg-bg-secondary/30 text-sm text-text-primary placeholder:text-text-tertiary focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 disabled:opacity-60"
                  />
                </div>

                <div className="pt-3 border-t border-border/50 space-y-2">
                  {!isGenerating ? (
                    <Button
                      variant="primary"
                      className="w-full justify-center"
                      onClick={handleGenerate}
                      disabled={resourceLoading || generationTask.isSubmitting}
                    >
                      <Play className="w-4 h-4" />
                      生成资源
                    </Button>
                  ) : (
                    <Button
                      variant="outline"
                      className="w-full justify-center"
                      loading
                      disabled
                    >
                      正在生成
                    </Button>
                  )}
                </div>
              </div>
            </Card>
            )}

            {/* 资源统计 */}
            <Card padding="md" className="mt-4">
              <h4 className="text-xs font-medium text-text-secondary mb-3">资源产出统计</h4>
              <div className="space-y-2.5">
                {(
                  Object.entries(resourceTypeConfig) as [
                    ResourceType,
                    typeof resourceTypeConfig.guide,
                  ][]
                ).map(([type, config]) => {
                  const Icon = config.icon
                  const count = resources.filter((r) => r.resourceType === type).length
                  return (
                    <div key={type} className="flex items-center justify-between">
                      <span className="text-sm text-text-primary flex items-center gap-1.5">
                        <Icon className={`w-3.5 h-3.5 ${config.color}`} />
                        {config.label}
                      </span>
                      <span className="text-sm font-medium text-text-secondary">{count}</span>
                    </div>
                  )
                })}
                <div className="pt-2 border-t border-border/50 flex items-center justify-between">
                  <span className="text-sm font-medium text-text-primary">总计</span>
                  <span className="text-sm font-bold text-primary">
                    {resourcesTotal || resources.length}
                  </span>
                </div>
              </div>
            </Card>
          </div>

          {/* 中间：生成进度 + 资源列表 */}
          <div className="col-span-12 lg:col-span-4">
            {viewMode !== 'list' && (
            <Card padding="md">
              <h3 className="text-sm font-semibold text-text-primary mb-4 flex items-center gap-2">
                <Brain className="w-4 h-4 text-text-secondary" />多 Agent 协同生成进度
                {sse.isConnected && (
                  <span className="ml-auto flex items-center gap-1 text-[10px] text-success">
                    <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
                    实时连接
                  </span>
                )}
              </h3>

              {isGenerating && (
                <div className="mb-4">
                  <div className="h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-primary to-info rounded-full transition-all duration-500 ease-out"
                      style={{ width: `${generationProgress}%` }}
                    />
                  </div>
                  <div className="flex items-center justify-between mt-1.5">
                    <p className="text-xs text-primary truncate max-w-[70%]">
                      {debateRoundText || currentStepDesc || '处理中...'}
                    </p>
                    <p className="text-xs text-text-tertiary flex-shrink-0">
                      {Math.round(generationProgress)}%
                    </p>
                  </div>
                </div>
              )}

              <div className="space-y-2">
                {generationSteps.map((step, idx) => {
                  const Icon = step.icon
                  const isComplete = isGenerating ? idx < currentStepIndex : false
                  const isRunning = isGenerating ? idx === currentStepIndex : false
                  return (
                    <div key={step.id} className="relative">
                      {idx < generationSteps.length - 1 && (
                        <div
                          className={`absolute left-[15px] top-8 w-0.5 h-4 -translate-x-1/2 transition-colors duration-250 ${
                            isComplete ? 'bg-primary' : 'bg-bg-tertiary'
                          }`}
                        />
                      )}
                      <div
                        className={`flex items-start gap-3 p-2.5 rounded-lg transition-all duration-250 ${
                          isRunning ? 'bg-primary/5 border border-primary/20' : ''
                        }`}
                      >
                        <div
                          className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 transition-all duration-250 ${
                            isComplete
                              ? 'bg-success/10'
                              : isRunning
                                ? 'bg-primary/10'
                                : 'bg-bg-tertiary'
                          }`}
                        >
                          {isComplete ? (
                            <CheckCircle2 className="w-4 h-4 text-success" />
                          ) : isRunning ? (
                            <Icon className="w-4 h-4 text-primary animate-pulse" />
                          ) : (
                            <Icon className="w-4 h-4 text-text-tertiary" />
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p
                            className={`text-sm font-medium transition-colors ${
                              isComplete
                                ? 'text-text-primary'
                                : isRunning
                                  ? 'text-primary'
                                  : 'text-text-tertiary'
                            }`}
                          >
                            {step.name}
                          </p>
                          <p className="text-xs text-text-tertiary">{step.agent}</p>
                        </div>
                        {isRunning && (
                          <span className="text-xs text-primary animate-pulse flex items-center gap-1">
                            <span className="w-1.5 h-1.5 rounded-full bg-primary animate-ping" />
                            运行中
                          </span>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>

              {!isGenerating && generationProgress === 0 && (
                <div className="mt-4 p-3 rounded-lg bg-bg-secondary/50 text-center">
                  <p className="text-xs text-text-tertiary">
                    选择学习者和资源类型后，点击「生成资源」启动多Agent协同
                  </p>
                </div>
              )}
            </Card>
            )}

            {/* 资源列表 */}
            <Card padding="md" className="mt-4">
              <div className="flex items-center justify-between mb-3">
                <h4 className="text-xs font-medium text-text-secondary">
                  {resourceTypeConfig[activeTab].label}列表
                </h4>
                <button
                  onClick={() => fetchResources({
                    page: 1,
                    pageSize: 50,
                    learnerId: selectedLearnerId || undefined,
                    topic: requestedTopic || undefined,
                  })}
                  className="text-xs text-primary hover:text-primary/80 flex items-center gap-1"
                >
                  <Search className="w-3 h-3" />
                  刷新
                </button>
              </div>
              <div className="space-y-2 max-h-[min(32rem,55vh)] overflow-y-auto pr-1 overscroll-contain">
                {resourceLoading ? (
                  <div className="space-y-2">
                    {Array.from({ length: 3 }).map((_, i) => (
                      <div key={i} className="p-3 rounded-lg border border-border space-y-2">
                        <CardSkeleton lines={2} />
                      </div>
                    ))}
                  </div>
                ) : filteredResources.length === 0 ? (
                  <div className="py-8 text-center text-sm text-text-tertiary">
                    暂无{resourceTypeConfig[activeTab].label}资源
                  </div>
                ) : (
                  filteredResources.map((resource) => {
                    const statusInfo = getReviewStatusInfo(resource)
                    const isSelected = selectedResource?.id === resource.id
                    return (
                      <div
                        key={resource.id}
                        className={`w-full p-3 rounded-lg border transition-all ${
                          isSelected
                            ? 'border-primary/30 bg-primary/5'
                            : 'border-border bg-bg-secondary/30 hover:border-primary/20'
                        }`}
                      >
                        <div className="flex items-start gap-2 mb-1.5">
                          <button
                            type="button"
                            onClick={() => handleSelectResource(resource)}
                            className="min-w-0 flex-1 text-left"
                            aria-label={`${resource.title} v${resource.versionNumber}`}
                          >
                            <p className="text-sm font-medium text-text-primary line-clamp-1">
                              {resource.title}
                            </p>
                          </button>
                          {isAiGeneratedResource(resource) && (
                            <button
                            type="button"
                            onClick={() => setResourceToDelete(resource)}
                            disabled={deletingResourceId === resource.id}
                            aria-label={`删除${resource.title}`}
                            title="删除资源"
                              className="inline-flex shrink-0 items-center gap-1 rounded-md px-1.5 py-1 text-xs text-text-tertiary hover:bg-error/10 hover:text-error disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                              <span>删除</span>
                            </button>
                          )}
                        </div>
                        <button
                          type="button"
                          onClick={() => handleSelectResource(resource)}
                          className="w-full text-left"
                        >
                          <div className="flex items-center gap-1.5 flex-wrap">
                          {statusInfo && (
                            <Badge variant={statusInfo.variant} size="sm">
                              {statusInfo.label}
                            </Badge>
                          )}
                          {resource.hallucinationDetected && (
                            <Badge variant="error" size="sm">
                              幻觉
                            </Badge>
                          )}
                          <span className="text-xs text-text-tertiary">
                            v{resource.versionNumber}
                          </span>
                          </div>
                          {resource.contentSummary && (
                            <p className="text-xs text-text-tertiary mt-1.5 line-clamp-2">
                              {resource.contentSummary}
                            </p>
                          )}
                          <Badge variant={isAiGeneratedResource(resource) ? 'success' : 'warning'} size="sm">
                            {isAiGeneratedResource(resource) ? 'AI生成' : '规则兜底'}
                          </Badge>
                        </button>
                      </div>
                    )
                  })
                )}
              </div>
            </Card>
          </div>

          {/* 右侧：成品资源预览 */}
          <div className="col-span-12 lg:col-span-5 min-h-0">
            <Card padding="none" className="flex h-[clamp(480px,72vh,760px)] min-h-0 flex-col overflow-hidden">
              {/* 标签页 */}
              <div className="flex shrink-0 border-b border-border overflow-x-auto">
                {(
                  Object.entries(resourceTypeConfig) as [
                    ResourceType,
                    typeof resourceTypeConfig.guide,
                  ][]
                ).map(([type, config]) => {
                  const Icon = config.icon
                  const typeCount = resources.filter((r) => r.resourceType === type).length
                  return (
                    <button
                      key={type}
                      onClick={() => {
                        if (!isGenerating) {
                          setActiveTab(type)
                          setSelectedResource(null)
                        }
                      }}
                      disabled={isGenerating}
                      className={`flex-1 py-3 px-3 flex items-center justify-center gap-1.5 text-xs font-medium transition-all relative whitespace-nowrap ${
                        activeTab === type
                          ? config.color
                          : 'text-text-tertiary hover:text-text-secondary'
                      } ${isGenerating ? 'opacity-60 cursor-not-allowed' : ''}`}
                    >
                      <Icon className="w-4 h-4" />
                      {config.label}
                      {typeCount > 0 && (
                        <span
                          className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                            activeTab === type ? 'bg-current/10' : 'bg-bg-tertiary'
                          }`}
                        >
                          {typeCount}
                        </span>
                      )}
                      {activeTab === type && (
                        <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-current" />
                      )}
                    </button>
                  )
                })}
              </div>

              {/* 资源内容 */}
              <div
                data-testid="resource-content-scroll"
                className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-5"
              >
                {resourceLoading ? (
                  <div className="space-y-4">
                    <CardSkeleton lines={2} />
                    <CardSkeleton lines={6} />
                    <CardSkeleton lines={4} />
                  </div>
                ) : isGenerating && !selectedResource ? (
                  <div className="flex flex-col items-center justify-center h-full min-h-[400px]">
                    <div className="relative">
                      <div className="w-16 h-16 rounded-full border-4 border-primary/20 border-t-primary animate-spin" />
                    </div>
                    <p className="mt-4 text-sm text-text-secondary">Agent 协同生成中...</p>
                    <p className="mt-1 text-xs text-text-tertiary">{currentStepDesc || '请稍候'}</p>
                    {debateRoundText && (
                      <p className="mt-2 text-xs text-primary">{debateRoundText}</p>
                    )}
                  </div>
                ) : loadingDetail ? (
                  <div className="flex flex-col items-center justify-center h-full min-h-[400px]">
                    <div className="w-10 h-10 rounded-full border-3 border-primary/20 border-t-primary animate-spin" />
                    <p className="mt-3 text-sm text-text-secondary">加载资源内容...</p>
                  </div>
                ) : (
                  renderResourceDetail()
                )}
              </div>

              {/* 操作栏 */}
              <div className="shrink-0 p-4 border-t border-border bg-bg-secondary/20">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={!selectedResource}
                      onClick={handlePreview}
                    >
                      <Eye className="w-3.5 h-3.5" />
                      预览
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={!selectedResource}
                      onClick={handleRead}
                    >
                      <BookOpen className="w-3.5 h-3.5" />
                      阅读
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={!selectedResource}
                      onClick={handlePrint}
                    >
                      <Printer className="w-3.5 h-3.5" />
                      打印
                    </Button>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={!selectedResource}
                      onClick={handleCopy}
                    >
                      <Copy className="w-3.5 h-3.5" />
                      复制
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={!selectedResource}
                      onClick={handleExport}
                    >
                      <Download className="w-3.5 h-3.5" />
                      导出
                    </Button>
                  </div>
                </div>
              </div>
            </Card>
          </div>
        </div>
      </div>

      <Modal
        isOpen={isPreviewOpen}
        onClose={() => setIsPreviewOpen(false)}
        maxWidth="max-w-4xl"
        className="max-h-[90vh]"
      >
        {selectedResource && (
          <div className="p-6 overflow-y-auto max-h-[90vh]">
            <p className="text-xs text-text-tertiary mb-1">资源预览</p>
            <h2 className="text-xl font-semibold text-text-primary pr-8">
              {selectedResource.title}
            </h2>
            <div className="mt-5">
              {isMarkdownResource(selectedResource) ? (
                <Suspense fallback={<div className="text-sm text-text-tertiary">正在加载内容预览...</div>}>
                  <MarkdownContent content={getResourceText()} />
                </Suspense>
              ) : (
                <pre className="text-sm font-mono text-text-primary leading-relaxed whitespace-pre-wrap">
                  {getResourceText()}
                </pre>
              )}
            </div>
          </div>
        )}
      </Modal>

      <Modal
        isOpen={resourceToDelete != null}
        onClose={() => deletingResourceId == null && setResourceToDelete(null)}
        maxWidth="max-w-md"
        header={<h2 className="text-base font-semibold text-text-primary">删除资源</h2>}
        footer={
          <div className="flex justify-end gap-2 px-6 py-4">
            <Button
              variant="ghost"
              size="sm"
              disabled={deletingResourceId != null}
              onClick={() => setResourceToDelete(null)}
            >
              取消
            </Button>
            <Button
              variant="primary"
              size="sm"
              loading={deletingResourceId != null}
              onClick={() => void handleDeleteResource()}
            >
              确认删除
            </Button>
          </div>
        }
      >
        <div className="px-6 py-5 text-sm text-text-secondary">
          确定删除“{resourceToDelete?.title}”吗？删除后将从资源列表中移除，已发布的知识库内容不受影响。
        </div>
      </Modal>
    </>
  )
}

function isAiGeneratedResource(resource: LearningResource): boolean {
  const method = resource.generationMethod?.trim().toLowerCase()
  return Boolean(method && method !== 'deterministic_fallback' && method !== 'rule_fallback')
}
