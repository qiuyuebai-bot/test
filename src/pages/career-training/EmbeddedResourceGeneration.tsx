import { useEffect, useState } from 'react'
import { useShallow } from 'zustand/react/shallow'
import { agentApi, coreApi } from '@/api'
import { useStore } from '@/store'
import { useTaskSSE } from '@/hooks/useTaskSSE'
import Card from '@/components/Card'
import Badge from '@/components/Badge'
import Button from '@/components/Button'
import Input from '@/components/Input'
import Select from '@/components/Select'
import LoadingState from '@/components/LoadingState'
import EmptyState from '@/components/EmptyState'
import MarkdownContent from '@/components/MarkdownContent'
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
  diagnosis: '学情诊断',
  retrieval: '知识检索',
  generation: '内容生成',
  debate: '辩论校验',
  revision: '最终修正',
  output: '输出成品',
  task_completed: '已完成',
  task_failed: '失败',
}

export default function EmbeddedResourceGeneration({ position, learnerId }: Props) {
  const trainingContext = useStore(useShallow((state) => state.activeTrainingContext))
  const [topic, setTopic] = useState('')
  const [resourceType, setResourceType] = useState<string>('guide')
  const [industry, setIndustry] = useState<string>('')
  const [taskId, setTaskId] = useState<number | null>(null)
  const [generating, setGenerating] = useState(false)
  const [resources, setResources] = useState<LearningResource[]>([])
  const [selectedResource, setSelectedResource] = useState<LearningResource | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

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

  const sse = useTaskSSE(taskId, {
    onComplete: () => {
      setGenerating(false)
      void fetchResources()
    },
    onError: () => setGenerating(false),
  })

  // SSE 完成（isCompleted 翻转为 true）时也刷新，兼容 mock 不触发 onComplete 的情况
  useEffect(() => {
    if (sse.isCompleted && taskId) {
      setGenerating(false)
      void fetchResources()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sse.isCompleted, taskId])

  async function fetchResources() {
    if (!learnerId) return
    try {
      const result = await coreApi.getResourceList({ page: 1, pageSize: 20, learnerId })
      setResources(result.items)
      if (result.items.length > 0 && !selectedResource) {
        void selectResource(result.items[0])
      }
    } catch (err) {
      console.error('getResourceList failed:', err)
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
        console.error('getResourceDetail failed:', err)
      } finally {
        setDetailLoading(false)
      }
    }
  }

  async function handleGenerate() {
    if (!learnerId || !topic.trim()) return
    setGenerating(true)
    setSelectedResource(null)
    try {
      const result = await agentApi.runFullPipeline({
        learnerId,
        targetTopic: topic.trim(),
        resourceType,
        industry: industry || undefined,
        ...(trainingContext ? { trainingContext } : {}),
      })
      setTaskId(result.taskId)
    } catch (err) {
      console.error('runFullPipeline failed:', err)
      setGenerating(false)
    }
  }

  if (!learnerId) {
    return <EmptyState type="default" title="需要学习者画像" description="当前账号没有关联的学习者画像，无法生成资料" />
  }

  const currentStageLabel = sse.currentStage ? (STAGE_LABEL[sse.currentStage] ?? sse.currentStage) : null

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
            <Button onClick={handleGenerate} loading={generating} disabled={!topic.trim()} className="w-full">
              生成资料
            </Button>
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
                <div className="h-full bg-primary transition-all" style={{ width: `${sse.progress}%` }} />
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
                <button
                  key={r.id}
                  onClick={() => void selectResource(r)}
                  className={`w-full text-left px-3 py-2 rounded-lg border text-sm transition-colors ${
                    selectedResource?.id === r.id ? 'border-primary bg-primary-light' : 'border-border hover:border-primary'
                  }`}
                >
                  <div className="truncate font-medium text-text-primary">{r.title}</div>
                  <div className="text-xs text-text-tertiary">
                    {r.resourceType} · L{r.difficultyLevel ?? '-'}
                  </div>
                </button>
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
                {selectedResource.matchScore != null && (
                  <Badge variant="success">匹配度 {selectedResource.matchScore}</Badge>
                )}
              </div>
              <MarkdownContent content={selectedResource.content} />
            </div>
          ) : (
            <EmptyState type="default" title="暂无预览" description="生成资料后选择左侧列表项查看内容" />
          )}
        </Card>
      </div>
    </div>
  )
}
