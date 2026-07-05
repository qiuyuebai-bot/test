import { useState, useEffect, useCallback, useRef } from 'react'
import { useStore } from '@/store'
import type { LearningResource } from '@/types'
import { agentApi, configApi } from '@/api'
import type { IndustryOption } from '@/api/config'
import { useTaskSSE } from '@/hooks'
import Card from '@/components/Card'
import Badge from '@/components/Badge'
import Button from '@/components/Button'
import { SCORE_EXCELLENT_THRESHOLD, SCORE_GOOD_THRESHOLD } from '@/lib/constants'
import {
  FileText,
  ListChecks,
  BookOpen,
  Sparkles,
  Play,
  CheckCircle2,
  AlertCircle,
  Lightbulb,
  Code2,
  User,
  Target,
  Brain,
  Shield,
  Eye,
  Download,
  Copy,
  Printer,
  Route,
  GraduationCap,
  BookMarked,
  Search,
  X,
  Building2,
} from 'lucide-react'
import LoadingState from '@/components/LoadingState'
import EmptyState from '@/components/EmptyState'

type ResourceType = 'guide' | 'lecture' | 'case' | 'quiz' | 'roadmap'

const resourceTypeConfig: Record<ResourceType, { label: string; icon: typeof FileText; color: string }> = {
  guide: { label: '学习路径指南', icon: Route, color: 'text-primary' },
  lecture: { label: '图文讲义', icon: BookOpen, color: 'text-amber-500' },
  case: { label: '案例场景', icon: BookMarked, color: 'text-purple-500' },
  quiz: { label: '测试题', icon: ListChecks, color: 'text-success' },
  roadmap: { label: '学习路线图', icon: GraduationCap, color: 'text-blue-500' },
}

const reviewStatusMap: Record<string, { label: string; variant: 'success' | 'warning' | 'error' | 'default' }> = {
  pending: { label: '待审核', variant: 'warning' },
  approved: { label: '已通过', variant: 'success' },
  rejected: { label: '已拒绝', variant: 'error' },
  revised: { label: '已修订', variant: 'default' },
  published: { label: '已发布', variant: 'success' },
}

const contentTypeMap: Record<string, string> = {
  pdf: 'PDF文档',
  html: 'HTML页面',
  video: '视频资源',
  text: '文本内容',
}

const generationSteps = [
  { id: 1, stage: 'diagnosis', name: '学情诊断', agent: '诊断Agent', icon: User },
  { id: 2, stage: 'knowledge_retrieval', name: '知识检索', agent: '检索Agent', icon: Target },
  { id: 3, stage: 'generation', name: '内容生成', agent: '生成Agent', icon: Brain },
  { id: 4, stage: 'debate', name: '交叉校验', agent: '裁判Agent', icon: Shield },
  { id: 5, stage: 'final_revision', name: '最终修正', agent: '系统', icon: CheckCircle2 },
  { id: 6, stage: 'complete', name: '输出成品', agent: '系统', icon: Sparkles },
]

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
  const learners = useStore((s) => s.learners)
  const currentLearner = useStore((s) => s.currentLearner)
  const setCurrentLearner = useStore((s) => s.setCurrentLearner)
  const fetchLearners = useStore((s) => s.fetchLearners)
  const resources = useStore((s) => s.resources)
  const fetchResources = useStore((s) => s.fetchResources)
  const resourceLoading = useStore((s) => s.resourceLoading)
  const resourcesTotal = useStore((s) => s.resourcesTotal)

  const [sseTaskId, setSseTaskId] = useState<number | null>(null)
  const [stageDescription, setStageDescription] = useState('')
  const [debateInfo, setDebateInfo] = useState<{ round: number; total: number } | null>(null)
  const [industryOptions, setIndustryOptions] = useState<IndustryOption[]>([])
  const [activeTab, setActiveTab] = useState<ResourceType>('guide')
  const [selectedResource, setSelectedResource] = useState<LearningResource | null>(null)
  const [resourceTitle, setResourceTitle] = useState('')
  const [selectedIndustry, setSelectedIndustry] = useState('technology')
  const [isGenerating, setIsGenerating] = useState(false)
  const [currentStepDesc, setCurrentStepDesc] = useState('')
  const [error, setError] = useState<string | null>(null)
  const cancelledRef = useRef(false)
  const completeTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const debateRoundText = debateInfo ? `第${debateInfo.round}/${debateInfo.total}轮辩论中...` : ''

  useEffect(() => {
    configApi.getOptions().then(opts => setIndustryOptions(opts.industries)).catch(() => {})
  }, [])

  useEffect(() => {
    return () => {
      if (completeTimeoutRef.current) {
        clearTimeout(completeTimeoutRef.current)
        completeTimeoutRef.current = null
      }
    }
  }, [])

  const handleSSEEvent = useCallback((event: { event: string; data: unknown; timestamp: number }) => {
    const data = (event.data as Record<string, unknown>) || {}
    switch (event.event) {
      case 'stage_update':
        setStageDescription((data.description as string) || '')
        break
      case 'debate_round':
        setDebateInfo({
          round: data.round as number,
          total: data.maxRounds as number,
        })
        break
      case 'debate_result':
        setDebateInfo({
          round: data.round as number,
          total: data.maxRounds as number,
        })
        break
      case 'task_failed':
        setError((data.error as string) || '资源生成失败')
        setIsGenerating(false)
        setSseTaskId(null)
        break
    }
  }, [])

  const sse = useTaskSSE(sseTaskId, {
    onEvent: handleSSEEvent,
    onComplete: () => {
      setStageDescription('任务完成')
      setDebateInfo(null)
      setResourceTitle('')
      if (completeTimeoutRef.current) clearTimeout(completeTimeoutRef.current)
      completeTimeoutRef.current = setTimeout(() => {
        setIsGenerating(false)
        fetchResources({ page: 1, pageSize: 20 })
      }, 1500)
      setSseTaskId(null)
    },
    onError: () => {
      // SSE 连接错误
    },
  })

  useEffect(() => {
    fetchLearners({ page: 1, pageSize: 50 })
    fetchResources({ page: 1, pageSize: 20 })
  }, [fetchLearners, fetchResources])

  useEffect(() => {
    if (!currentLearner && learners.length > 0) {
      setCurrentLearner(learners[0])
    }
  }, [learners, currentLearner, setCurrentLearner])

  useEffect(() => {
    if (resources.length > 0 && !selectedResource) {
      const filtered = resources.filter(r => r.resourceType === activeTab)
      if (filtered.length > 0) {
        setSelectedResource(filtered[0])
      }
    }
  }, [resources, activeTab, selectedResource])

  useEffect(() => {
    setCurrentStepDesc(stageDescription)
  }, [stageDescription])

  useEffect(() => {
    if (sse.error) {
      setError(sse.error)
      setIsGenerating(false)
    }
  }, [sse.error])

  const selectedLearner = currentLearner || learners[0]

  const currentStepIndex = (sse.currentStage ? stageToStepIndex[sse.currentStage] : undefined) ?? (isGenerating ? 0 : -1)
  const generationProgress = sse.progress

  const handleSelectLearner = (learnerId: number) => {
    const learner = learners.find(l => l.id === learnerId)
    if (learner) {
      setCurrentLearner(learner)
    }
  }

  const handleGenerate = useCallback(async () => {
    if (!selectedLearner) {
      setError('请先选择学习者')
      return
    }
    if (!resourceTitle.trim()) {
      setError('请输入资源标题')
      return
    }

    setIsGenerating(true)
    setError(null)
    setCurrentStepDesc('任务初始化中...')
    setDebateInfo(null)
    cancelledRef.current = false

    try {
      const result = await agentApi.runFullPipeline({
        learnerId: selectedLearner.id,
        targetTopic: resourceTitle.trim(),
        resourceType: activeTab,
        industry: selectedIndustry,
      })

      if (cancelledRef.current) return
      setSseTaskId(result.taskId)
    } catch (err) {
      if (cancelledRef.current) return
      setIsGenerating(false)
      setError(err instanceof Error ? err.message : '资源生成失败，请重试')
    }
  }, [selectedLearner, resourceTitle, activeTab, selectedIndustry])

  const handleCancel = () => {
    cancelledRef.current = true
    setSseTaskId(null)
    setIsGenerating(false)
    setCurrentStepDesc('')
    setDebateInfo(null)
  }

  const filteredResources = resources.filter(r => r.resourceType === activeTab)

  const getQualityScoreColor = (score: number) => {
    if (score >= SCORE_EXCELLENT_THRESHOLD) return 'text-success'
    if (score >= SCORE_GOOD_THRESHOLD) return 'text-amber-500'
    return 'text-danger'
  }

  const renderResourceDetail = () => {
    if (!selectedResource) {
      return <EmptyState.Document />
    }

    const statusInfo = reviewStatusMap[selectedResource.reviewStatus] || reviewStatusMap.pending

    return (
      <div className="space-y-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <Badge variant={statusInfo.variant} size="sm">{statusInfo.label}</Badge>
              <Badge variant="default" size="sm">{contentTypeMap[selectedResource.contentType] || selectedResource.contentType}</Badge>
              {selectedResource.hallucinationDetected && (
                <Badge variant="error" size="sm">
                  <AlertCircle className="w-3 h-3 mr-1" />
                  检测到幻觉
                </Badge>
              )}
            </div>
            <h3 className="text-base font-semibold text-text-primary mb-1">{selectedResource.title}</h3>
            <p className="text-xs text-text-tertiary">
              v{selectedResource.versionNumber} · {selectedResource.generatedByAgent} · {new Date(selectedResource.generationTime).toLocaleString('zh-CN')}
            </p>
          </div>
          <div className="flex flex-col items-center">
            <span className={`text-2xl font-bold ${getQualityScoreColor(selectedResource.qualityScore)}`}>
              {selectedResource.qualityScore}
            </span>
            <span className="text-xs text-text-tertiary">质量分</span>
          </div>
        </div>

        <div className="p-4 rounded-lg bg-primary/5 border border-primary/10">
          <div className="flex items-center gap-2 mb-2">
            <Lightbulb className="w-4 h-4 text-primary" />
            <span className="text-sm font-medium text-text-primary">内容摘要</span>
          </div>
          <p className="text-sm text-text-secondary leading-relaxed">
            {selectedResource.contentSummary || '暂无摘要信息'}
          </p>
        </div>

        {selectedResource.content ? (
          <div className="rounded-xl bg-bg-secondary/70 border border-border/50 p-4 overflow-x-auto">
            <div className="flex items-center gap-2 mb-2 text-xs text-text-tertiary">
              <Code2 className="w-3.5 h-3.5" />
              <span>资源内容</span>
            </div>
            <pre className="text-xs font-mono text-text-primary leading-relaxed whitespace-pre-wrap max-h-64 overflow-y-auto">
              {selectedResource.content}
            </pre>
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-border p-8 text-center">
            <FileText className="w-10 h-10 text-text-tertiary mx-auto mb-2" />
            <p className="text-sm text-text-tertiary">资源内容加载中或暂不可预览</p>
            {selectedResource.contentPath && (
              <p className="text-xs text-text-tertiary mt-1">存储路径：{selectedResource.contentPath}</p>
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
    <div className="space-y-4 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">个性化资源生成</h1>
          <p className="text-sm text-text-secondary mt-1">多 Agent 协同产出学习路径指南、图文讲义、案例场景、测试题、学习路线图</p>
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
          <Card padding="md" className="space-y-5">
            <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
              <User className="w-4 h-4 text-text-secondary" />
              学情参数配置
            </h3>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-text-secondary mb-2">选择学习者</label>
                <div className="space-y-2 max-h-36 overflow-y-auto">
                  {learners.map((l) => (
                    <button
                      key={l.id}
                      onClick={() => handleSelectLearner(l.id)}
                      disabled={isGenerating}
                      className={`w-full p-3 rounded-lg border text-left text-sm transition-all ${
                        selectedLearner?.id === l.id
                          ? 'border-primary/30 bg-primary/5'
                          : 'border-border bg-bg-secondary/30 hover:border-primary/20'
                      } ${isGenerating ? 'opacity-60 cursor-not-allowed' : ''}`}
                    >
                      <p className="font-medium text-text-primary">{l.realName}</p>
                      <p className="text-xs text-text-tertiary">{l.educationLevel} · {l.major}</p>
                    </button>
                  ))}
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
                  {industryOptions.map(opt => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-text-secondary mb-2">资源类型</label>
                <div className="grid grid-cols-1 gap-1.5">
                  {(Object.entries(resourceTypeConfig) as [ResourceType, typeof resourceTypeConfig.guide][]).map(([type, config]) => {
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
                        <Icon className={`w-4 h-4 ${activeTab === type ? config.color : 'text-text-tertiary'}`} />
                        <span className={activeTab === type ? 'text-text-primary font-medium' : 'text-text-secondary'}>
                          {config.label}
                        </span>
                      </button>
                    )
                  })}
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-text-secondary mb-2">资源主题/标题</label>
                <input
                  type="text"
                  value={resourceTitle}
                  onChange={(e) => setResourceTitle(e.target.value)}
                  placeholder="输入要生成的主题，如：Python入门..."
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
                    disabled={resourceLoading}
                  >
                    <Play className="w-4 h-4" />
                    生成资源
                  </Button>
                ) : (
                  <Button
                    variant="outline"
                    className="w-full justify-center"
                    onClick={handleCancel}
                  >
                    <X className="w-4 h-4" />
                    取消生成
                  </Button>
                )}
              </div>
            </div>
          </Card>

          {/* 资源统计 */}
          <Card padding="md" className="mt-4">
            <h4 className="text-xs font-medium text-text-secondary mb-3">资源产出统计</h4>
            <div className="space-y-2.5">
              {(Object.entries(resourceTypeConfig) as [ResourceType, typeof resourceTypeConfig.guide][]).map(([type, config]) => {
                const Icon = config.icon
                const count = resources.filter(r => r.resourceType === type).length
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
                <span className="text-sm font-bold text-primary">{resourcesTotal || resources.length}</span>
              </div>
            </div>
          </Card>
        </div>

        {/* 中间：生成进度 + 资源列表 */}
        <div className="col-span-12 lg:col-span-4">
          <Card padding="md">
            <h3 className="text-sm font-semibold text-text-primary mb-4 flex items-center gap-2">
              <Brain className="w-4 h-4 text-text-secondary" />
              多 Agent 协同生成进度
              {sse.isConnected && (
                <span className="ml-auto flex items-center gap-1 text-[10px] text-success">
                  <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
                  实时连接
                </span>
              )}
            </h3>

            {isGenerating && (
              <div className="mb-4">
                <div className="h-1.5 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-primary to-blue-400 rounded-full transition-all duration-500 ease-out"
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
                      <div className={`absolute left-[15px] top-8 w-0.5 h-4 -translate-x-1/2 transition-colors duration-300 ${
                        isComplete ? 'bg-primary' : 'bg-gray-200 dark:bg-gray-700'
                      }`} />
                    )}
                    <div className={`flex items-start gap-3 p-2.5 rounded-lg transition-all duration-300 ${
                      isRunning ? 'bg-primary/5 border border-primary/20' : ''
                    }`}>
                      <div className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 transition-all duration-300 ${
                        isComplete ? 'bg-success/10' : isRunning ? 'bg-primary/10' : 'bg-gray-100 dark:bg-gray-800'
                      }`}>
                        {isComplete ? (
                          <CheckCircle2 className="w-4 h-4 text-success" />
                        ) : isRunning ? (
                          <Icon className="w-4 h-4 text-primary animate-pulse" />
                        ) : (
                          <Icon className="w-4 h-4 text-text-tertiary" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className={`text-sm font-medium transition-colors ${
                          isComplete ? 'text-text-primary' : isRunning ? 'text-primary' : 'text-text-tertiary'
                        }`}>
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
                <p className="text-xs text-text-tertiary">选择学习者和资源类型后，点击「生成资源」启动多Agent协同</p>
              </div>
            )}
          </Card>

          {/* 资源列表 */}
          <Card padding="md" className="mt-4">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-xs font-medium text-text-secondary">
                {resourceTypeConfig[activeTab].label}列表
              </h4>
              <button
                onClick={() => fetchResources({ page: 1, pageSize: 20 })}
                className="text-xs text-primary hover:text-primary/80 flex items-center gap-1"
              >
                <Search className="w-3 h-3" />
                刷新
              </button>
            </div>
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {resourceLoading ? (
                <div className="py-8 text-center">
                  <LoadingState.Generating />
                </div>
              ) : filteredResources.length === 0 ? (
                <div className="py-8 text-center text-sm text-text-tertiary">
                  暂无{resourceTypeConfig[activeTab].label}资源
                </div>
              ) : (
                filteredResources.map((resource) => {
                  const statusInfo = reviewStatusMap[resource.reviewStatus] || reviewStatusMap.pending
                  const isSelected = selectedResource?.id === resource.id
                  return (
                    <button
                      key={resource.id}
                      onClick={() => setSelectedResource(resource)}
                      className={`w-full p-3 rounded-lg border text-left transition-all ${
                        isSelected
                          ? 'border-primary/30 bg-primary/5'
                          : 'border-border bg-bg-secondary/30 hover:border-primary/20'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2 mb-1.5">
                        <p className="text-sm font-medium text-text-primary line-clamp-1 flex-1">
                          {resource.title}
                        </p>
                        <span className={`text-sm font-bold flex-shrink-0 ${getQualityScoreColor(resource.qualityScore)}`}>
                          {resource.qualityScore}
                        </span>
                      </div>
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <Badge variant={statusInfo.variant} size="sm">{statusInfo.label}</Badge>
                        {resource.hallucinationDetected && (
                          <Badge variant="error" size="sm">幻觉</Badge>
                        )}
                        <span className="text-xs text-text-tertiary">
                          v{resource.versionNumber}
                        </span>
                      </div>
                      <p className="text-xs text-text-tertiary mt-1.5 line-clamp-2">
                        {resource.contentSummary || '暂无摘要'}
                      </p>
                    </button>
                  )
                })
              )}
            </div>
          </Card>
        </div>

        {/* 右侧：成品资源预览 */}
        <div className="col-span-12 lg:col-span-5">
          <Card padding="none">
            {/* 标签页 */}
            <div className="flex border-b border-border overflow-x-auto">
              {(Object.entries(resourceTypeConfig) as [ResourceType, typeof resourceTypeConfig.guide][]).map(([type, config]) => {
                const Icon = config.icon
                const typeCount = resources.filter(r => r.resourceType === type).length
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
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                        activeTab === type ? 'bg-current/10' : 'bg-gray-100 dark:bg-gray-800'
                      }`}>
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
            <div className="p-5 min-h-[500px]">
              {resourceLoading ? (
                <LoadingState.Generating />
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
              ) : (
                renderResourceDetail()
              )}
            </div>

            {/* 操作栏 */}
            <div className="p-4 border-t border-border bg-bg-secondary/20">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1">
                  <Button variant="ghost" size="sm" disabled={!selectedResource}>
                    <Eye className="w-3.5 h-3.5" />
                    预览
                  </Button>
                  <Button variant="ghost" size="sm" disabled={!selectedResource}>
                    <Printer className="w-3.5 h-3.5" />
                    打印
                  </Button>
                </div>
                <div className="flex items-center gap-1">
                  <Button variant="outline" size="sm" disabled={!selectedResource}>
                    <Copy className="w-3.5 h-3.5" />
                    复制
                  </Button>
                  <Button variant="outline" size="sm" disabled={!selectedResource}>
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
  )
}
