import { lazy, Suspense, useEffect, useState } from 'react'
import { BookOpen, Trash2 } from 'lucide-react'
import { useShallow } from 'zustand/react/shallow'
import { agentApi, coreApi } from '@/api'
import { useStore } from '@/store'
import { useResourceGenerationTask } from '@/hooks/useResourceGenerationTask'
import { reportError } from '@/lib/sentry'
import Card from '@/components/Card'
import Badge from '@/components/Badge'
import Button from '@/components/Button'
import Input from '@/components/Input'
import Select from '@/components/Select'
import LoadingState from '@/components/LoadingState'
import EmptyState from '@/components/EmptyState'
import Modal from '@/components/Modal'
const MarkdownContent = lazy(() => import('@/components/MarkdownContent'))
import type { PositionDetail } from '@/types/training'
import type { LearningResource } from '@/types'

interface Props {
  position: PositionDetail | null
  learnerId: number | null
}

const RESOURCE_TYPES = [
  { value: 'guide', label: '实操指南' },
  { value: 'exercise', label: '分阶测试题' },
  { value: 'lecture', label: '专属讲义' },
]

const STAGE_LABEL: Record<string, string> = {
  init: '任务初始化',
  diagnosis: '学情诊断',
  retrieval: '知识检索',
  knowledge_retrieval: '知识检索',
  generation: '内容生成',
  judge_first: '初次审核',
  debate: '辩论校验',
  revision: '最终修正',
  final_revision: '最终修正',
  output: '输出成品',
  complete: '已完成',
  task_completed: '已完成',
  task_failed: '失败',
}

function formatMatchScore(value: number | null | undefined): string | null {
  if (value == null || !Number.isFinite(value)) return null
  const normalized = value >= 0 && value <= 1 ? value * 100 : value
  return `${normalized.toFixed(2)}%`
}

function isAiGeneratedResource(resource: LearningResource): boolean {
  const method = resource.generationMethod?.trim().toLowerCase()
  return Boolean(method && method !== 'deterministic_fallback' && method !== 'rule_fallback')
}

export default function EmbeddedResourceGeneration({ position, learnerId }: Props) {
  const trainingContext = useStore(useShallow((state) => state.activeTrainingContext))
  const [topic, setTopic] = useState('')
  const [resourceType, setResourceType] = useState<string>('guide')
  const [industry, setIndustry] = useState<string>('')
  const [resources, setResources] = useState<LearningResource[]>([])
  const [selectedResource, setSelectedResource] = useState<LearningResource | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [generationError, setGenerationError] = useState<string | null>(null)
  const [resourceToDelete, setResourceToDelete] = useState<LearningResource | null>(null)
  const [deletingResourceId, setDeletingResourceId] = useState<number | null>(null)

  const generationTask = useResourceGenerationTask({
    learnerId,
    onComplete: () => {
      void fetchResources()
    },
    onFailed: (_taskId, message) => {
      setGenerationError(message)
    },
  })
  const sse = generationTask.stream
  const generating = generationTask.isGenerating

  // 岗位变化时预填主题与行业
  useEffect(() => {
    if (position) {
      setTopic(trainingContext?.stage.title ?? position.name)
      setIndustry(position.industry ?? '')
    }
  }, [position, trainingContext?.stage.title])

  // 挂载或有 learnerId 时拉取已有资源（岗位培训场景下展示历史生成物）
  useEffect(() => {
    if (learnerId) {
      void fetchResources()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [learnerId])

  useEffect(() => {
    if (generationTask.connectionError && generationTask.taskId) {
      setGenerationError('实时进度连接暂时中断，任务仍在后台继续执行')
    }
  }, [generationTask.connectionError, generationTask.taskId])

  async function fetchResources() {
    if (!learnerId) return
    try {
      const result = await coreApi.getResourceList({ page: 1, pageSize: 20, learnerId })
      setResources(result.items)
      if (result.items.length > 0 && !selectedResource) {
        void selectResource(result.items[0])
      }
    } catch (err) {
      reportError(err, { tags: { area: 'resource_generation', action: 'list' } })
    }
  }

  async function selectResource(r: LearningResource) {
    setSelectedResource(r)
    if (!r.content) {
      setDetailLoading(true)
      try {
        const detail = await coreApi.getResourceDetail(r.id)
        setSelectedResource(detail)
      } catch (err) {
        reportError(err, { tags: { area: 'resource_generation', action: 'detail' } })
      } finally {
        setDetailLoading(false)
      }
    }
  }

  async function handleGenerate() {
    if (!learnerId || !topic.trim()) return
    if (!generationTask.beginSubmission()) return
    setGenerationError(null)
    setSelectedResource(null)
    try {
      const result = await agentApi.runFullPipeline({
        learnerId,
        targetTopic: topic.trim(),
        resourceType,
        industry: industry || undefined,
        ...(trainingContext ? { trainingContext } : {}),
      })
      generationTask.attachTask(result.taskId)
    } catch (err) {
      reportError(err, { tags: { area: 'resource_generation', action: 'run_pipeline' } })
      generationTask.failSubmission()
      setGenerationError(err instanceof Error ? err.message : '资源生成失败，请重试')
    }
  }

  async function handleDeleteResource() {
    if (!resourceToDelete || deletingResourceId != null) return
    const resource = resourceToDelete
    setDeletingResourceId(resource.id)
    try {
      await coreApi.deleteResource(resource.id)
      setResources((current) => current.filter((item) => item.id !== resource.id))
      if (selectedResource?.id === resource.id) setSelectedResource(null)
      setResourceToDelete(null)
    } catch (err) {
      setGenerationError(err instanceof Error ? err.message : '删除资源失败')
    } finally {
      setDeletingResourceId(null)
    }
  }

  if (!learnerId) {
    return <EmptyState type="default" title="需要学习者画像" description="当前账号没有关联的学习者画像，无法生成资料" />
  }

  const currentStageLabel = generationTask.currentStage
    ? (STAGE_LABEL[generationTask.currentStage] ?? generationTask.currentStage)
    : null
  const selectedMatchScore = formatMatchScore(selectedResource?.matchScore)

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
      {/* 左：配置 + 进度 + 列表 */}
      <div className="lg:col-span-5 space-y-4">
        <Card>
          <div className="space-y-3">
            <h3 className="text-sm font-medium text-text-primary">生成配置</h3>
            <div>
              <label className="block text-xs font-medium text-text-secondary mb-1">目标主题</label>
              <Input value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="输入主题" />
            </div>
            <div>
              <label className="block text-xs font-medium text-text-secondary mb-1">资源类型</label>
              <Select
                value={resourceType}
                options={RESOURCE_TYPES.map((t) => ({ value: t.value, label: t.label }))}
                onChange={(e) => setResourceType(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-text-secondary mb-1">行业（可选）</label>
              <Input value={industry} onChange={(e) => setIndustry(e.target.value)} placeholder="如：软件开发" />
            </div>
            <Button
              onClick={handleGenerate}
              loading={generating}
              disabled={!topic.trim() || generationTask.isSubmitting}
              className="w-full"
            >
              生成资料
            </Button>
            {generationError && <p className="text-xs text-error" role="alert">{generationError}</p>}
          </div>
        </Card>

        {/* SSE 进度 */}
        {(generating || sse.isConnected) && (
          <Card>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-medium text-text-primary">生成进度</h4>
                {currentStageLabel && <Badge variant="info">{currentStageLabel}</Badge>}
              </div>
              <div className="w-full h-2 bg-bg-secondary rounded-full overflow-hidden">
                <div className="h-full bg-primary transition-all" style={{ width: `${generationTask.progress}%` }} />
              </div>
              <div className="space-y-1 max-h-32 overflow-y-auto">
                {sse.events.slice(-5).map((evt, i) => (
                  <div key={i} className="text-xs text-text-tertiary">
                    {STAGE_LABEL[evt.event] ?? evt.event}: {typeof evt.data === 'string' ? evt.data : ''}
                  </div>
                ))}
              </div>
            </div>
          </Card>
        )}

        {/* 资源列表 */}
        {resources.length > 0 && (
          <Card>
            <h4 className="text-sm font-medium text-text-primary mb-2">已生成资源</h4>
            <div className="space-y-1 max-h-48 overflow-y-auto">
              {resources.map((r) => (
                <div
                  key={r.id}
                  className={`w-full text-left px-3 py-2 rounded-lg border text-sm transition-colors ${
                    selectedResource?.id === r.id ? 'border-primary bg-primary-light' : 'border-border hover:border-primary'
                  }`}
                >
                  <div className="flex items-start gap-2">
                    <button type="button" onClick={() => void selectResource(r)} className="min-w-0 flex-1 text-left">
                      <div className="truncate font-medium text-text-primary">{r.title}</div>
                    </button>
                    {isAiGeneratedResource(r) && (
                      <button
                        type="button"
                        onClick={() => setResourceToDelete(r)}
                        disabled={deletingResourceId === r.id}
                        aria-label={`删除${r.title}`}
                        title="删除资源"
                        className="inline-flex shrink-0 items-center gap-1 rounded-md px-1.5 py-1 text-xs text-text-tertiary hover:bg-error/10 hover:text-error disabled:opacity-50"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                        <span>删除</span>
                      </button>
                    )}
                  </div>
                  <div className="mt-1 flex items-center gap-1.5">
                    <Badge variant={isAiGeneratedResource(r) ? 'success' : 'warning'} size="sm">
                      {isAiGeneratedResource(r) ? 'AI生成' : '规则兜底'}
                    </Badge>
                    <button type="button" onClick={() => void selectResource(r)} className="text-left text-xs text-text-tertiary">
                      {r.resourceType} · L{r.difficultyLevel ?? '-'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>

      {/* 右：预览 */}
      <div className="lg:col-span-7">
        <Card>
          {detailLoading ? (
            <LoadingState />
          ) : selectedResource?.content ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-base font-medium text-text-primary">{selectedResource.title}</h3>
                <div className="flex items-center gap-2">
                  {selectedMatchScore && <Badge variant="success">匹配度 {selectedMatchScore}</Badge>}
                  <Button variant="outline" size="sm" onClick={() => { window.location.href = `/resources/${selectedResource.id}/read` }}>
                    <BookOpen className="h-4 w-4" />阅读
                  </Button>
                </div>
              </div>
              <Suspense fallback={<LoadingState />}>
                <MarkdownContent content={selectedResource.content} />
              </Suspense>
            </div>
          ) : (
            <EmptyState type="default" title="暂无预览" description="生成资料后选择左侧列表项查看内容" />
          )}
        </Card>
      </div>

      <Modal
        isOpen={resourceToDelete != null}
        onClose={() => deletingResourceId == null && setResourceToDelete(null)}
        maxWidth="max-w-md"
        header={<h2 className="text-base font-semibold text-text-primary">删除资源</h2>}
        footer={
          <div className="flex justify-end gap-2 px-6 py-4">
            <Button variant="ghost" size="sm" disabled={deletingResourceId != null} onClick={() => setResourceToDelete(null)}>
              取消
            </Button>
            <Button variant="primary" size="sm" loading={deletingResourceId != null} onClick={() => void handleDeleteResource()}>
              确认删除
            </Button>
          </div>
        }
      >
        <div className="px-6 py-5 text-sm text-text-secondary">
          确定删除“{resourceToDelete?.title}”吗？删除后将从当前资源列表移除，已发布的知识库内容不受影响。
        </div>
      </Modal>
    </div>
  )
}
