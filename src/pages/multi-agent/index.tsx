import { useState, useRef, useCallback } from 'react'
import {
  Play,
  ZoomIn,
  ZoomOut,
  Maximize2,
  MessageSquare,
  AlertTriangle,
  Clock,
  User,
  Brain,
  Scale,
  Target,
  RefreshCw,
  ChevronRight,
} from 'lucide-react'
import Card from '@/components/Card'
import Badge from '@/components/Badge'
import Button from '@/components/Button'
import { PageSkeleton } from '@/components/Skeleton'
import ErrorState from '@/components/ErrorState'
import type { AgentStatus } from '@/types'
import { useMultiAgentData } from './hooks/useMultiAgentData'
import { useTaskLogs } from './hooks/useTaskLogs'
import { AgentOverviewCard } from './components/AgentOverviewCard'
import { TaskDetailModal } from './components/TaskDetailModal'
import {
  flowSteps,
  agentColorMap,
  statusConfig,
  taskTypeOptions,
  stageToStepMap,
  getTaskTypeLabel,
  getTaskTypeColor,
} from './constants'

export default function MultiAgentVisualization() {
  const data = useMultiAgentData()
  const { logs, addLog, clearLogs } = useTaskLogs()
  const [scale, setScale] = useState(1)
  const svgRef = useRef<SVGSVGElement>(null)

  data.setAddLog(addLog)

  const handleZoomIn = () => setScale(prev => Math.min(prev + 0.1, 1.5))
  const handleZoomOut = () => setScale(prev => Math.max(prev - 0.1, 0.5))
  const handleResetZoom = () => setScale(1)

  const getAgentByType = useCallback((type: string): AgentStatus | undefined => {
    return data.agentStatuses.find(a => a.agentType === type)
  }, [data.agentStatuses])

  const getStepStatus = (stepId: string): 'pending' | 'processing' | 'active' => {
    const runningTask = data.tasks.find(t => t.status === 'running')
    const hasActiveSSE = data.sse.isConnected && data.runningTaskId

    if (!runningTask && !hasActiveSSE) {
      const hasCompletedTask = data.tasks.some(t => t.status === 'completed')
      if (!hasCompletedTask) return 'pending'
    }

    const stepIndex = flowSteps.findIndex(s => s.id === stepId)
    const sseStage = data.sseTaskProgress.stage
    const sseProgressVal = data.sseTaskProgress.progress
    const progress = hasActiveSSE ? sseProgressVal : (runningTask?.progress || 0)

    if (hasActiveSSE && sseStage in stageToStepMap) {
      const currentStepIdx = stageToStepMap[sseStage]
      if (stepIndex < currentStepIdx) return 'active'
      if (stepIndex === currentStepIdx) return 'processing'
      return 'pending'
    }

    if (runningTask) {
      if (runningTask.taskType === 'diagnosis') {
        if (stepIndex <= 1) return progress > 50 ? 'active' : 'processing'
        return 'pending'
      }
      if (runningTask.taskType === 'generation') {
        if (stepIndex <= 3) return 'active'
        if (stepIndex === 4) return progress > 50 ? 'processing' : 'pending'
        return 'pending'
      }
      if (runningTask.taskType === 'review') {
        if (stepIndex <= 4) return 'active'
        if (stepIndex === 5) return progress > 50 ? 'processing' : 'pending'
        return 'pending'
      }
      if (runningTask.taskType === 'full_flow') {
        const stepThreshold = Math.floor(progress / 12.5)
        if (stepIndex < stepThreshold) return 'active'
        if (stepIndex === stepThreshold) return 'processing'
        return 'pending'
      }
    }

    const allCompleted = data.tasks.some(t => t.status === 'completed' && t.taskType === 'full_flow')
    if (allCompleted) return 'active'

    return 'pending'
  }

  const getTaskStatusBadge = (status: string) => {
    const info = statusConfig[status] || statusConfig.pending
    return (
      <Badge variant={status === 'completed' ? 'success' : status === 'failed' ? 'error' : status === 'running' ? 'warning' : 'default'} size="sm">
        {info.label}
      </Badge>
    )
  }

  if (data.loading) {
    return <PageSkeleton />
  }

  if (data.error) {
    return (
      <ErrorState
        type="default"
        onRetry={() => {
          data.setError(null)
          data.setLoading(true)
          Promise.all([data.fetchAgentStatuses(), data.fetchTasks(), data.fetchLearners({ page: 1, pageSize: 50 })]).finally(() => data.setLoading(false))
        }}
      />
    )
  }

  return (
    <div className="space-y-4 animate-fade-in">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="hero-anchor text-xl font-semibold text-text-primary">多智能体协同决策可视化</h1>
          <p className="text-sm text-text-secondary mt-1">完整呈现学情诊断 → 知识生成 → 审核纠偏全闭环流程</p>
        </div>
        <div className="flex items-center gap-3">
          {data.sse.isConnected && data.runningTaskId && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-success-light border border-success/30">
              <div className="w-2 h-2 rounded-full bg-success animate-pulse" />
              <span className="text-xs font-medium text-success-dark">实时连接中</span>
            </div>
          )}
          <Button variant="outline" onClick={() => data.handleReset(clearLogs)}>
            <RefreshCw className="w-4 h-4" /> 刷新
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 lg:col-span-3">
          <Card padding="md" className="mb-4">
            <h3 className="font-semibold text-text-primary mb-4 flex items-center gap-2">
              <Target className="w-5 h-5 text-text-secondary" />
              启动任务
            </h3>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-text-secondary mb-2">选择学习者</label>
                <select
                  value={data.selectedLearnerId || ''}
                  onChange={(e) => data.setSelectedLearnerId(Number(e.target.value))}
                  className="w-full px-3 py-2 text-sm border border-border rounded-lg bg-bg-card text-text-primary focus:outline-none focus:border-primary"
                >
                  {data.learners.map(l => (
                    <option key={l.id} value={l.id}>{l.realName}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-text-secondary mb-2">任务类型</label>
                <div className="grid grid-cols-2 gap-2">
                  {taskTypeOptions.map(tt => (
                    <button
                      key={tt.value}
                      onClick={() => data.setSelectedTaskType(tt.value)}
                      className={`px-3 py-2 text-xs rounded-lg border transition-all ${
                        data.selectedTaskType === tt.value
                          ? 'border-primary bg-primary/10 text-primary font-medium'
                          : 'border-border bg-bg-secondary/30 text-text-secondary hover:border-primary/30'
                      }`}
                    >
                      {tt.label}
                    </button>
                  ))}
                </div>
              </div>

              <Button
                variant="primary"
                className="w-full justify-center"
                onClick={() => data.handleStartTask(addLog)}
                disabled={data.isStarting || !data.selectedLearnerId}
              >
                {data.isStarting ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    启动中...
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4" />
                    启动任务
                  </>
                )}
              </Button>
            </div>
          </Card>

          <Card padding="md">
            <h3 className="font-semibold text-text-primary mb-4 flex items-center gap-2">
              <Brain className="w-5 h-5 text-text-secondary" />
              智能体角色总览
            </h3>

            <div className="space-y-4">
              {data.agentStatuses.length > 0 ? (
                <>
                  <AgentOverviewCard
                    agent={getAgentByType('diagnosis') || {
                      agentType: 'diagnosis',
                      agentName: '学情诊断Agent',
                      state: 'idle',
                      totalTasksHandled: 0,
                      successCount: 0,
                      failureCount: 0,
                    }}
                    icon={User}
                  />

                  <AgentOverviewCard
                    agent={getAgentByType('generation') || {
                      agentType: 'generation',
                      agentName: '领域知识生成Agent',
                      state: 'idle',
                      totalTasksHandled: 0,
                      successCount: 0,
                      failureCount: 0,
                    }}
                    icon={Brain}
                  />

                  <AgentOverviewCard
                    agent={getAgentByType('review') || {
                      agentType: 'review',
                      agentName: '审核裁判Agent',
                      state: 'idle',
                      totalTasksHandled: 0,
                      successCount: 0,
                      failureCount: 0,
                    }}
                    icon={Scale}
                  />
                </>
              ) : (
                <div className="text-center py-8 text-text-tertiary text-sm">暂无智能体数据</div>
              )}
            </div>
          </Card>
        </div>

        <div className="col-span-12 lg:col-span-5">
          <Card padding="md">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-text-primary flex items-center gap-2">
                <Target className="w-5 h-5 text-text-secondary" />
                流程拓扑图
              </h3>
              <div className="flex items-center gap-2">
                <button onClick={handleZoomOut} className="p-1.5 hover:bg-bg-secondary rounded-lg transition-colors">
                  <ZoomOut className="w-4 h-4 text-text-secondary" />
                </button>
                <span className="text-xs text-text-tertiary w-12 text-center">{Math.round(scale * 100)}%</span>
                <button onClick={handleZoomIn} className="p-1.5 hover:bg-bg-secondary rounded-lg transition-colors">
                  <ZoomIn className="w-4 h-4 text-text-secondary" />
                </button>
                <button onClick={handleResetZoom} className="p-1.5 hover:bg-bg-secondary rounded-lg transition-colors">
                  <Maximize2 className="w-4 h-4 text-text-secondary" />
                </button>
              </div>
            </div>

            <div className="relative bg-bg-secondary/30 rounded-xl p-4 overflow-hidden" style={{ height: '500px' }}>
              <svg
                ref={svgRef}
                viewBox="0 0 800 450"
                className="w-full h-full transition-transform duration-250"
                style={{ transform: `scale(${scale})`, transformOrigin: 'center center' }}
              >
                <defs>
                  <linearGradient id="flowGrad1" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="var(--color-viz-1)" stopOpacity="0.6" />
                    <stop offset="100%" stopColor="var(--color-viz-2)" stopOpacity="0.6" />
                  </linearGradient>
                  <linearGradient id="flowGrad2" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="var(--color-viz-2)" stopOpacity="0.6" />
                    <stop offset="100%" stopColor="var(--color-viz-3)" stopOpacity="0.6" />
                  </linearGradient>
                  <linearGradient id="flowGrad3" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="var(--color-viz-3)" stopOpacity="0.6" />
                    <stop offset="100%" stopColor="var(--color-viz-4)" stopOpacity="0.6" />
                  </linearGradient>
                  <filter id="glow">
                    <feGaussianBlur stdDeviation="3" result="coloredBlur" />
                    <feMerge>
                      <feMergeNode in="coloredBlur" />
                      <feMergeNode in="SourceGraphic" />
                    </feMerge>
                  </filter>
                </defs>

                <path d="M 50 225 L 130 225" stroke="url(#flowGrad1)" strokeWidth="2" fill="none" strokeDasharray={getStepStatus('read-profile') === 'active' || getStepStatus('read-profile') === 'processing' ? '6 3' : 'none'} className={getStepStatus('read-profile') === 'processing' ? 'animate-flow-dash' : ''} />
                <path d="M 180 225 L 260 225" stroke="url(#flowGrad1)" strokeWidth="2" fill="none" strokeDasharray={getStepStatus('diagnosis') === 'active' || getStepStatus('diagnosis') === 'processing' ? '6 3' : 'none'} className={getStepStatus('diagnosis') === 'processing' ? 'animate-flow-dash' : ''} />
                <path d="M 310 225 L 390 225" stroke="url(#flowGrad1)" strokeWidth="2" fill="none" strokeDasharray={getStepStatus('fetch-kb') === 'active' || getStepStatus('fetch-kb') === 'processing' ? '6 3' : 'none'} className={getStepStatus('fetch-kb') === 'processing' ? 'animate-flow-dash' : ''} />
                <path d="M 440 225 L 520 225" stroke="url(#flowGrad2)" strokeWidth="2" fill="none" strokeDasharray={getStepStatus('generate') === 'active' || getStepStatus('generate') === 'processing' ? '6 3' : 'none'} className={getStepStatus('generate') === 'processing' ? 'animate-flow-dash' : ''} />
                <path d="M 570 225 L 650 225" stroke="url(#flowGrad2)" strokeWidth="2" fill="none" strokeDasharray={getStepStatus('validate') === 'active' || getStepStatus('validate') === 'processing' ? '6 3' : 'none'} className={getStepStatus('validate') === 'processing' ? 'animate-flow-dash' : ''} />
                <path d="M 700 225 L 750 225" stroke="url(#flowGrad3)" strokeWidth="2" fill="none" strokeDasharray={getStepStatus('correct') === 'active' || getStepStatus('correct') === 'processing' ? '6 3' : 'none'} className={getStepStatus('correct') === 'processing' ? 'animate-flow-dash' : ''} />

                <path d="M 750 275 Q 750 380 400 380 Q 50 380 50 275" stroke="var(--color-text-tertiary)" strokeWidth="1.5" fill="none" strokeDasharray="4 2" className="animate-flow-dash" opacity={0.4} />

                {flowSteps.map((step, index) => {
                  const x = 50 + index * 100
                  const y = 225
                  const status = getStepStatus(step.id)
                  const isAgent = step.type === 'agent'
                  const agentColors = isAgent ? agentColorMap[step.agentId as keyof typeof agentColorMap] : null
                  const agentState = isAgent ? getAgentByType(step.agentId!)?.state : null
                  const isAgentActive = agentState === 'running' || agentState === 'waiting'

                  return (
                    <g key={step.id} transform={`translate(${x}, ${y})`}>
                      <circle
                        r="35"
                        fill={status === 'active' ? (isAgent ? agentColors?.primary : 'var(--color-viz-4)') : status === 'processing' ? (isAgent ? agentColors?.primary : 'var(--color-info)') : 'var(--color-border)'}
                        opacity={status === 'pending' ? 0.6 : 1}
                        className={(status === 'processing' || isAgentActive) ? 'animate-pulse-ring' : ''}
                        filter="url(#glow)"
                      />
                      <circle r="32" fill={status === 'active' ? (isAgent ? agentColors?.primary : 'var(--color-viz-4)') : status === 'processing' ? (isAgent ? agentColors?.primary : 'var(--color-info)') : 'var(--color-bg-tertiary)'} stroke={status === 'active' ? (isAgent ? agentColors?.secondary : 'var(--color-success-dark)') : status === 'processing' ? (isAgent ? agentColors?.secondary : 'var(--color-info)') : 'var(--color-border)'} strokeWidth="2" />

                      {isAgent ? (
                        <>
                          {step.agentId === 'diagnosis' && (
                            <>
                              <circle cx="-8" cy="-5" r="4" fill="white" />
                              <circle cx="8" cy="-5" r="4" fill="white" />
                              <path d="M -6 8 Q 0 15 6 8" stroke="white" strokeWidth="3" fill="none" strokeLinecap="round" />
                            </>
                          )}

                          {step.agentId === 'generation' && (
                            <>
                              <circle cx="0" cy="-8" r="6" fill="white" />
                              <path d="M -12 6 Q -6 0 0 6 Q 6 0 12 6" stroke="white" strokeWidth="3" fill="none" strokeLinecap="round" />
                            </>
                          )}

                          {step.agentId === 'review' && (
                            <>
                              <path d="M -10 -10 L 10 10 M 10 -10 L -10 10" stroke="white" strokeWidth="3" strokeLinecap="round" />
                            </>
                          )}
                        </>
                      ) : step.type === 'input' ? (
                        <path d="M -8 -10 L 8 -10 L 0 10 Z" fill="var(--color-text-tertiary)" />
                      ) : step.type === 'output' ? (
                        <path d="M -8 10 L 8 10 L 0 -10 Z" fill="var(--color-viz-4)" />
                      ) : (
                        <circle r="8" fill={status === 'active' ? 'var(--color-viz-3)' : 'var(--color-text-tertiary)'} />
                      )}

                      <text y="55" textAnchor="middle" fontSize="11" fill="var(--color-text-tertiary)" fontWeight="500">{step.label}</text>
                    </g>
                  )
                })}

                {flowSteps.slice(0, -1).map((_, index) => {
                  const x = 125 + index * 100
                  return (
                    <polygon key={index} points={`${x},220 ${x + 8},225 ${x},230`} fill="var(--color-text-tertiary)" opacity={0.6} />
                  )
                })}
                <polygon points="45,270 55,275 45,280" fill="var(--color-text-tertiary)" opacity={0.4} />
              </svg>

              <div className="absolute bottom-4 left-4 right-4 space-y-2">
                {(data.sse.isConnected || data.sseTaskProgress.progress > 0) && (
                  <div className="bg-bg-card/90 backdrop-blur-sm rounded-lg p-2 border border-border/50">
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="text-text-secondary font-medium">{data.sseTaskProgress.description || '处理中...'}</span>
                      <span className="text-primary font-semibold">{Math.round(data.sseTaskProgress.progress)}%</span>
                    </div>
                    <div className="h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${data.sseTaskProgress.stage === 'failed' ? 'bg-error' : data.sseTaskProgress.stage === 'complete' ? 'bg-success' : 'bg-primary'}`}
                        style={{ width: `${data.sseTaskProgress.progress}%` }}
                      />
                    </div>
                  </div>
                )}
                <div className="flex items-center justify-between text-xs text-text-tertiary">
                  <span>系统状态</span>
                  <span className="flex items-center gap-1">
                    {data.sse.isConnected && <div className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />}
                    {data.agentStatuses.some(a => a.state === 'running') ? '运行中' : data.agentStatuses.some(a => a.state === 'waiting') ? '等待中' : '空闲'}
                  </span>
                </div>
                <div className="flex gap-2">
                  <div className="flex items-center gap-1">
                    <div className="w-2 h-2 rounded-full bg-success" />
                    <span className="text-[10px] text-text-tertiary">空闲 {data.agentStatuses.filter(a => a.state === 'idle' || a.state === 'completed').length}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <div className="w-2 h-2 rounded-full bg-primary animate-pulse" />
                    <span className="text-[10px] text-text-tertiary">运行 {data.agentStatuses.filter(a => a.state === 'running' || a.state === 'waiting').length}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <div className="w-2 h-2 rounded-full bg-error" />
                    <span className="text-[10px] text-text-tertiary">异常 {data.agentStatuses.filter(a => a.state === 'failed' || a.state === 'error').length}</span>
                  </div>
                </div>
              </div>
            </div>
          </Card>
        </div>

        <div className="col-span-12 lg:col-span-4 space-y-4">
          <Card padding="none">
            <div className="p-4 border-b border-border flex items-center gap-2">
              <MessageSquare className="w-5 h-5 text-text-secondary" />
              <h3 className="font-semibold text-text-primary">实时协同日志</h3>
              <Badge variant={data.agentStatuses.some(a => a.state === 'running') ? 'success' : 'default'} size="sm">
                {data.agentStatuses.some(a => a.state === 'running') ? '运行中' : '就绪'}
              </Badge>
            </div>
            <div className="p-4 h-[280px] overflow-y-auto space-y-2">
              {logs.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-text-tertiary">
                  <RefreshCw className="w-8 h-8 mb-2 opacity-50" />
                  <p className="text-sm">选择学习者并启动任务开始</p>
                </div>
              ) : (
                logs.slice(-50).reverse().map((log) => (
                  <div key={log.id} className={`flex gap-2 p-2 rounded-lg text-sm ${log.type === 'system' ? 'bg-bg-secondary' : log.type === 'success' ? 'bg-success/5 border border-success/10' : log.type === 'error' ? 'bg-error-light border border-error/20' : 'bg-primary/5'}`}>
                    <div className={`w-1.5 h-1.5 rounded-full mt-1.5 ${log.type === 'system' ? 'bg-text-tertiary' : log.type === 'success' ? 'bg-success' : log.type === 'error' ? 'bg-error' : 'bg-primary'}`} />
                    <div className="flex-1 min-w-0">
                      <span className="text-xs text-text-tertiary flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {log.timestamp}
                        <span className={`ml-1 px-1 rounded text-[10px] ${log.agent === 'diagnosis' ? 'bg-viz-1/10 text-viz-1' : log.agent === 'generation' ? 'bg-viz-2/10 text-viz-2' : log.agent === 'review' ? 'bg-viz-3/10 text-viz-3' : 'bg-bg-tertiary text-text-secondary'}`}>
                          {log.agent === 'diagnosis' ? '诊断' : log.agent === 'generation' ? '生成' : log.agent === 'review' ? '审核' : '系统'}
                        </span>
                      </span>
                      <p className="text-text-secondary text-xs mt-0.5">{log.content}</p>
                    </div>
                  </div>
                ))
              )}
            </div>
          </Card>

          <Card padding="none">
            <div className="p-4 border-b border-border flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Clock className="w-5 h-5 text-text-secondary" />
                <h3 className="font-semibold text-text-primary">任务列表</h3>
              </div>
              <Badge variant="default" size="sm">{data.tasks.length}</Badge>
            </div>
            <div className="p-4 space-y-3 max-h-[320px] overflow-y-auto">
              {data.tasks.length === 0 ? (
                <div className="text-center py-6 text-text-tertiary text-sm">暂无任务记录</div>
              ) : (
                data.tasks.slice(0, 10).map((task) => (
                  <div
                    key={task.taskId}
                    onClick={() => data.setSelectedTask(task)}
                    className="stagger-item p-3 rounded-xl border border-border bg-bg-secondary/30 hover:border-primary/30 hover:bg-primary/5 transition-all cursor-pointer group"
                  >
                    <div className="flex items-start gap-2">
                      <div className={`w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0 ${
                        task.status === 'completed' ? 'bg-success' :
                        task.status === 'running' ? 'bg-primary animate-pulse' :
                        task.status === 'failed' ? 'bg-error' :
                        'bg-warning'
                      }`} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-xs font-medium text-text-primary truncate">#{task.taskId} {task.taskName}</p>
                          {getTaskStatusBadge(task.status)}
                        </div>
                        <div className="flex items-center gap-2 mt-1.5">
                          <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${getTaskTypeColor(task.taskType)}`}>
                            {getTaskTypeLabel(task.taskType)}
                          </span>
                          <span className="text-[10px] text-text-tertiary">学习者 #{task.learnerId}</span>
                        </div>
                        {task.status === 'running' && (
                          <div className="mt-2">
                            <div className="h-1 bg-bg-tertiary rounded-full overflow-hidden">
                              <div className="h-full bg-primary rounded-full transition-all" style={{ width: `${task.progress}%` }} />
                            </div>
                          </div>
                        )}
                        <div className="flex items-center gap-2 mt-1.5">
                          {task.errorMessage && (
                            <span className="text-[10px] text-error flex items-center gap-0.5">
                              <AlertTriangle className="w-3 h-3" /> 异常
                            </span>
                          )}
                          <span className="text-[10px] text-text-tertiary ml-auto">
                            {task.createdAt ? new Date(task.createdAt).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : ''}
                          </span>
                          <ChevronRight className="w-3 h-3 text-text-tertiary group-hover:text-primary transition-colors" />
                        </div>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </Card>
        </div>
      </div>

      <TaskDetailModal
        isOpen={!!data.selectedTask}
        onClose={() => data.setSelectedTask(undefined)}
        task={data.selectedTask}
      />
    </div>
  )
}
