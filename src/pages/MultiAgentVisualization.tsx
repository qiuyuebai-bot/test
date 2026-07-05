import { useState, useEffect, useRef, useCallback } from 'react'
import { useStore } from '@/store'
import type { AgentStatus, AgentTask } from '@/types'
import Card from '@/components/Card'
import Modal from '@/components/Modal'
import Badge from '@/components/Badge'
import Button from '@/components/Button'
import { PageSkeleton } from '@/components/Skeleton'
import ErrorState from '@/components/ErrorState'
import { useTaskSSE } from '@/hooks'
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

const flowSteps = [
  { id: 'read-profile', label: '读取学情画像', type: 'input' },
  { id: 'diagnosis', label: '诊断知识盲区', type: 'agent', agentId: 'diagnosis' },
  { id: 'fetch-kb', label: '调取专业知识库', type: 'process' },
  { id: 'generate', label: '产出初稿资源', type: 'agent', agentId: 'generation' },
  { id: 'validate', label: '交叉校验辩论', type: 'agent', agentId: 'review' },
  { id: 'correct', label: '识别幻觉纠偏', type: 'process' },
  { id: 'output', label: '输出个性化资源', type: 'output' },
  { id: 'feedback', label: '接收学习反馈', type: 'process' },
]

const agentColorMap = {
  diagnosis: { primary: '#3d5a80', secondary: '#5a7aa5', bg: 'bg-[#3d5a80]/10', border: 'border-[#3d5a80]/30', text: 'text-[#3d5a80]' },
  generation: { primary: '#5b8def', secondary: '#7ba6f5', bg: 'bg-[#5b8def]/10', border: 'border-[#5b8def]/30', text: 'text-[#5b8def]' },
  review: { primary: '#f59e0b', secondary: '#fbbf24', bg: 'bg-[#f59e0b]/10', border: 'border-[#f59e0b]/30', text: 'text-[#f59e0b]' },
}

const statusConfig: Record<string, { label: string; color: string; bgLight: string; textColor: string }> = {
  idle: { label: '空闲', color: 'bg-gray-400', bgLight: 'bg-gray-100', textColor: 'text-gray-600' },
  running: { label: '运行中', color: 'bg-primary', bgLight: 'bg-primary/10', textColor: 'text-primary' },
  waiting: { label: '等待中', color: 'bg-blue-400', bgLight: 'bg-blue-50', textColor: 'text-blue-600' },
  completed: { label: '已完成', color: 'bg-green-400', bgLight: 'bg-green-50', textColor: 'text-green-600' },
  failed: { label: '异常', color: 'bg-red-400', bgLight: 'bg-red-50', textColor: 'text-red-600' },
  error: { label: '错误', color: 'bg-red-500', bgLight: 'bg-red-50', textColor: 'text-red-600' },
  pending: { label: '等待中', color: 'bg-amber-400', bgLight: 'bg-amber-50', textColor: 'text-amber-600' },
  cancelled: { label: '已取消', color: 'bg-gray-400', bgLight: 'bg-gray-100', textColor: 'text-gray-600' },
}

function AgentOverviewCard({ agent, icon: Icon }: {
  agent: AgentStatus
  icon: typeof Brain
}) {
  const colors = agentColorMap[agent.agentType] || agentColorMap.diagnosis
  const statusInfo = statusConfig[agent.state] || statusConfig.idle
  const isActive = agent.state === 'running' || agent.state === 'waiting'
  const currentTaskName = agent.currentTaskId ? `任务 #${agent.currentTaskId}` : undefined

  return (
    <div className={`relative p-4 rounded-xl border ${colors.border} bg-bg-card shadow-soft transition-all duration-300 hover:shadow-medium hover:-translate-y-0.5`}>
      <div className="absolute top-2 right-2">
        <div className={`w-2.5 h-2.5 rounded-full ${statusInfo.color} ${isActive ? 'animate-pulse' : ''}`} />
      </div>
      
      <div className="w-12 h-12 rounded-xl flex items-center justify-center mb-3" style={{ backgroundColor: colors.primary }}>
        <Icon className="w-6 h-6 text-white" />
      </div>
      
      <h3 className="font-semibold text-text-primary text-sm mb-1">{agent.agentName}</h3>
      <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${statusInfo.bgLight} ${statusInfo.textColor}`}>
        {statusInfo.label}
      </span>
      
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <div className="flex justify-between">
          <span className="text-text-tertiary">处理任务</span>
          <span className="font-medium text-text-primary">{agent.totalTasksHandled}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-text-tertiary">成功</span>
          <span className="font-medium text-green-600">{agent.successCount}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-text-tertiary">失败</span>
          <span className="font-medium text-red-500">{agent.failureCount}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-text-tertiary">平均耗时</span>
          <span className="font-medium text-text-primary">{agent.avgLatencyMs ? `${(agent.avgLatencyMs / 1000).toFixed(1)}s` : '-'}</span>
        </div>
      </div>
      
      {currentTaskName && (
        <div className="mt-3 pt-3 border-t border-border/50">
          <p className="text-xs text-text-secondary truncate">{currentTaskName}</p>
        </div>
      )}
    </div>
  )
}

function TaskDetailModal({ isOpen, onClose, task }: { isOpen: boolean; onClose: () => void; task?: AgentTask }) {
  if (!isOpen || !task) return null

  const taskStatusInfo = statusConfig[task.status] || statusConfig.pending

  return (
    <Modal isOpen={isOpen} onClose={onClose} maxWidth="max-w-2xl">
        <div className="flex items-center justify-between p-5 border-b border-border">
          <div className="flex items-center gap-2">
            <Target className="w-5 h-5 text-primary" />
            <h3 className="font-semibold text-text-primary">任务详情</h3>
          </div>
        </div>
        
        <div className="p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="font-medium text-text-primary">{task.taskName}</h4>
            <Badge variant={task.status === 'completed' ? 'success' : task.status === 'failed' ? 'error' : 'warning'}>
              {taskStatusInfo.label}
            </Badge>
          </div>
          
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="p-3 rounded-lg bg-bg-secondary/30">
              <span className="text-xs text-text-tertiary block mb-1">任务ID</span>
              <p className="text-text-primary font-medium">#{task.taskId}</p>
            </div>
            <div className="p-3 rounded-lg bg-bg-secondary/30">
              <span className="text-xs text-text-tertiary block mb-1">任务类型</span>
              <p className="text-text-primary font-medium">{task.taskType}</p>
            </div>
            <div className="p-3 rounded-lg bg-bg-secondary/30">
              <span className="text-xs text-text-tertiary block mb-1">学习者ID</span>
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
          </div>
          
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-text-tertiary">执行进度</span>
              <span className="text-sm font-medium text-text-primary">{Math.round(task.progress)}%</span>
            </div>
            <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
              <div className={`h-full rounded-full transition-all duration-500 ${task.status === 'completed' ? 'bg-green-500' : task.status === 'failed' ? 'bg-red-500' : 'bg-primary'}`} style={{ width: `${task.progress}%` }} />
            </div>
          </div>
          
          {task.errorMessage && (
            <div className="p-3 rounded-lg bg-red-50 border border-red-200">
              <span className="text-xs text-red-600 font-medium flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" />
                错误信息
              </span>
              <p className="text-red-600 text-xs mt-1">{task.errorMessage}</p>
            </div>
          )}
        </div>
    </Modal>
  )
}

export default function MultiAgentVisualization() {
  const agentStatuses = useStore((s) => s.agentStatuses)
  const tasks = useStore((s) => s.tasks)
  const learners = useStore((s) => s.learners)
  const fetchAgentStatuses = useStore((s) => s.fetchAgentStatuses)
  const fetchTasks = useStore((s) => s.fetchTasks)
  const fetchLearners = useStore((s) => s.fetchLearners)
  const startAgentTask = useStore((s) => s.startAgentTask)
  
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedLearnerId, setSelectedLearnerId] = useState<number | null>(null)
  const [selectedTaskType, setSelectedTaskType] = useState<string>('full_flow')
  const [isStarting, setIsStarting] = useState(false)
  const [scale, setScale] = useState(1)
  const [selectedTask, setSelectedTask] = useState<AgentTask>()
  const [logs, setLogs] = useState<Array<{ id: number; agent: string; content: string; timestamp: string; type: string }>>([])
  const [runningTaskId, setRunningTaskId] = useState<number | null>(null)
  const [sseTaskProgress, setSseTaskProgress] = useState<{ stage: string; progress: number; description: string }>({ stage: 'init', progress: 0, description: '' })
  
  const svgRef = useRef<SVGSVGElement>(null)
  const [sseTaskId, setSseTaskId] = useState<number | null>(null)

  const addLog = useCallback((agent: string, content: string, type: string = 'info') => {
    setLogs(prev => {
      const newLog = {
        id: Date.now() + Math.random(),
        agent,
        content,
        timestamp: new Date().toLocaleTimeString('zh-CN', { hour12: false }),
        type,
      }
      const exists = prev.some(l => l.content === content && Date.now() - Math.floor(l.id) < 6000)
      if (exists) return prev
      return [...prev.slice(-80), newLog]
    })
  }, [])

  const handleSSEEvent = useCallback((event: { event: string; data: unknown; timestamp: number }) => {
    const data = (event.data as Record<string, unknown>) || {}
    switch (event.event) {
      case 'connected':
        setSseTaskProgress({
          stage: (data.stage as string) || 'init',
          progress: (data.progress as number) || 0,
          description: (data.description as string) || '已连接',
        })
        break
      case 'stage_update':
        setSseTaskProgress({
          stage: (data.stage as string) || 'init',
          progress: (data.progress as number) || 0,
          description: (data.description as string) || '',
        })
        {
          const stage = data.stage as string
          const agentType = stage === 'diagnosis' ? 'diagnosis' :
            stage === 'generation' || stage === 'knowledge_retrieval' ? 'generation' :
            stage === 'judge_first' || stage === 'debate' || stage === 'final_revision' ? 'review' : 'system'
          addLog(agentType, (data.description as string) || '', 'info')
        }
        fetchTasks()
        fetchAgentStatuses()
        break
      case 'debate_round':
        addLog('review', (data.description as string) || '', 'info')
        break
      case 'debate_result':
        addLog('review', (data.description as string) || '', data.decision === 'approved' ? 'success' : 'info')
        break
      case 'task_failed':
        setSseTaskProgress({ stage: 'failed', progress: 0, description: (data.error as string) || '任务失败' })
        addLog('system', `任务失败: ${(data.error as string) || '未知错误'}`, 'error')
        setRunningTaskId(null)
        setSseTaskId(null)
        fetchTasks()
        fetchAgentStatuses()
        break
    }
  }, [addLog, fetchTasks, fetchAgentStatuses])

  const sse = useTaskSSE(sseTaskId, {
    onEvent: handleSSEEvent,
    onComplete: (result) => {
      const data = result as { taskId?: number }
      setSseTaskProgress({ stage: 'complete', progress: 100, description: '任务完成' })
      addLog('system', `任务 #${data?.taskId || sseTaskId} 完成`, 'success')
      setRunningTaskId(null)
      setSseTaskId(null)
      fetchTasks()
      fetchAgentStatuses()
    },
    onError: () => {
      addLog('system', 'SSE连接断开，将通过轮询继续更新', 'error')
    },
  })

  const connectToRunningTask = useCallback((taskId: number) => {
    setRunningTaskId(taskId)
    setSseTaskId(taskId)
  }, [])

  useEffect(() => {
    const loadData = async () => {
      setLoading(true)
      try {
        await Promise.all([
          fetchAgentStatuses(),
          fetchTasks(),
          fetchLearners({ page: 1, pageSize: 50 }),
        ])
        setError(null)
      } catch (err) {
        setError('加载数据失败')
      } finally {
        setLoading(false)
      }
    }
    loadData()
    
    const refreshInterval = setInterval(() => {
      fetchAgentStatuses()
      fetchTasks()
    }, 15000)
    
    return () => {
      clearInterval(refreshInterval)
    }
  }, [fetchAgentStatuses, fetchTasks, fetchLearners])

  useEffect(() => {
    const runningTask = tasks.find(t => t.status === 'running')
    if (runningTask && !runningTaskId && !sseTaskId) {
      connectToRunningTask(runningTask.taskId)
    }
    if (!runningTask && runningTaskId && !sseTaskId) {
      setRunningTaskId(null)
    }
  }, [tasks, runningTaskId, sseTaskId, connectToRunningTask])
  
  useEffect(() => {
    if (learners.length > 0 && !selectedLearnerId) {
      setSelectedLearnerId(learners[0].id)
    }
  }, [learners, selectedLearnerId])
  
  const handleStartTask = async () => {
    if (!selectedLearnerId || isStarting) return
    
    setIsStarting(true)
    try {
      const result = await startAgentTask({
        learnerId: selectedLearnerId,
        taskType: selectedTaskType,
      })
      addLog('system', `已启动任务 #${result.taskId}`, 'success')
      setSseTaskProgress({ stage: 'init', progress: 0, description: '任务初始化中...' })
      await fetchTasks()
      await fetchAgentStatuses()
      connectToRunningTask(result.taskId)
    } catch (err) {
      setError('启动任务失败')
      addLog('system', '启动任务失败', 'error')
    } finally {
      setIsStarting(false)
    }
  }
  
  const handleReset = () => {
    setLogs([])
    fetchAgentStatuses()
    fetchTasks()
  }
  
  const handleZoomIn = () => setScale(prev => Math.min(prev + 0.1, 1.5))
  const handleZoomOut = () => setScale(prev => Math.max(prev - 0.1, 0.5))
  const handleResetZoom = () => setScale(1)
  
  const getAgentByType = (type: string): AgentStatus | undefined => {
    return agentStatuses.find(a => a.agentType === type)
  }
  
  const getStepStatus = (stepId: string): 'pending' | 'processing' | 'active' => {
    const runningTask = tasks.find(t => t.status === 'running')
    const hasActiveSSE = sse.isConnected && runningTaskId
    
    if (!runningTask && !hasActiveSSE) {
      const hasCompletedTask = tasks.some(t => t.status === 'completed')
      if (!hasCompletedTask) return 'pending'
    }
    
    const stepIndex = flowSteps.findIndex(s => s.id === stepId)
    const sseStage = sseTaskProgress.stage
    const sseProgressVal = sseTaskProgress.progress
    const progress = hasActiveSSE ? sseProgressVal : (runningTask?.progress || 0)
    
    const stageToStepMap: Record<string, number> = {
      'init': 0,
      'diagnosis': 1,
      'knowledge_retrieval': 2,
      'generation': 3,
      'judge_first': 4,
      'debate': 5,
      'final_revision': 6,
      'complete': 7,
    }
    
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
    
    const allCompleted = tasks.some(t => t.status === 'completed' && t.taskType === 'full_flow')
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
  
  if (loading) {
    return <PageSkeleton />
  }

  if (error) {
    return (
      <ErrorState
        type="default"
        onRetry={() => {
          setError(null)
          setLoading(true)
          Promise.all([fetchAgentStatuses(), fetchTasks(), fetchLearners({ page: 1, pageSize: 50 })]).finally(() => setLoading(false))
        }}
      />
    )
  }

  return (
    <div className="space-y-4 animate-fade-in">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">多智能体协同决策可视化</h1>
          <p className="text-sm text-text-secondary mt-1">完整呈现学情诊断 → 知识生成 → 审核纠偏全闭环流程</p>
        </div>
        <div className="flex items-center gap-3">
          {sse.isConnected && runningTaskId && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-green-50 border border-green-200">
              <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
              <span className="text-xs font-medium text-green-700">实时连接中</span>
            </div>
          )}
          <Button variant="outline" onClick={handleReset}>
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
                  value={selectedLearnerId || ''}
                  onChange={(e) => setSelectedLearnerId(Number(e.target.value))}
                  className="w-full px-3 py-2 text-sm border border-border rounded-lg bg-bg-card text-text-primary focus:outline-none focus:border-primary"
                >
                  {learners.map(l => (
                    <option key={l.id} value={l.id}>{l.realName}</option>
                  ))}
                </select>
              </div>
              
              <div>
                <label className="block text-xs font-medium text-text-secondary mb-2">任务类型</label>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { value: 'diagnosis', label: '学情诊断' },
                    { value: 'generation', label: '知识生成' },
                    { value: 'review', label: '内容审核' },
                    { value: 'full_flow', label: '全流程' },
                  ].map(tt => (
                    <button
                      key={tt.value}
                      onClick={() => setSelectedTaskType(tt.value)}
                      className={`px-3 py-2 text-xs rounded-lg border transition-all ${
                        selectedTaskType === tt.value
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
                onClick={handleStartTask}
                disabled={isStarting || !selectedLearnerId}
              >
                {isStarting ? (
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
              {agentStatuses.length > 0 ? (
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
                className="w-full h-full transition-transform duration-300"
                style={{ transform: `scale(${scale})`, transformOrigin: 'center center' }}
              >
                <defs>
                  <linearGradient id="flowGrad1" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="#3d5a80" stopOpacity="0.6" />
                    <stop offset="100%" stopColor="#5b8def" stopOpacity="0.6" />
                  </linearGradient>
                  <linearGradient id="flowGrad2" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="#5b8def" stopOpacity="0.6" />
                    <stop offset="100%" stopColor="#f59e0b" stopOpacity="0.6" />
                  </linearGradient>
                  <linearGradient id="flowGrad3" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="#f59e0b" stopOpacity="0.6" />
                    <stop offset="100%" stopColor="#10b981" stopOpacity="0.6" />
                  </linearGradient>
                  <filter id="glow">
                    <feGaussianBlur stdDeviation="3" result="coloredBlur" />
                    <feMerge>
                      <feMergeNode in="coloredBlur" />
                      <feMergeNode in="SourceGraphic" />
                    </feMerge>
                  </filter>
                </defs>
                
                <path
                  d="M 50 225 L 130 225"
                  stroke="url(#flowGrad1)"
                  strokeWidth="2"
                  fill="none"
                  strokeDasharray={getStepStatus('read-profile') === 'active' || getStepStatus('read-profile') === 'processing' ? '6 3' : 'none'}
                  className={getStepStatus('read-profile') === 'processing' ? 'animate-flow-dash' : ''}
                />
                <path
                  d="M 180 225 L 260 225"
                  stroke="url(#flowGrad1)"
                  strokeWidth="2"
                  fill="none"
                  strokeDasharray={getStepStatus('diagnosis') === 'active' || getStepStatus('diagnosis') === 'processing' ? '6 3' : 'none'}
                  className={getStepStatus('diagnosis') === 'processing' ? 'animate-flow-dash' : ''}
                />
                <path
                  d="M 310 225 L 390 225"
                  stroke="url(#flowGrad1)"
                  strokeWidth="2"
                  fill="none"
                  strokeDasharray={getStepStatus('fetch-kb') === 'active' || getStepStatus('fetch-kb') === 'processing' ? '6 3' : 'none'}
                  className={getStepStatus('fetch-kb') === 'processing' ? 'animate-flow-dash' : ''}
                />
                <path
                  d="M 440 225 L 520 225"
                  stroke="url(#flowGrad2)"
                  strokeWidth="2"
                  fill="none"
                  strokeDasharray={getStepStatus('generate') === 'active' || getStepStatus('generate') === 'processing' ? '6 3' : 'none'}
                  className={getStepStatus('generate') === 'processing' ? 'animate-flow-dash' : ''}
                />
                <path
                  d="M 570 225 L 650 225"
                  stroke="url(#flowGrad2)"
                  strokeWidth="2"
                  fill="none"
                  strokeDasharray={getStepStatus('validate') === 'active' || getStepStatus('validate') === 'processing' ? '6 3' : 'none'}
                  className={getStepStatus('validate') === 'processing' ? 'animate-flow-dash' : ''}
                />
                <path
                  d="M 700 225 L 750 225"
                  stroke="url(#flowGrad3)"
                  strokeWidth="2"
                  fill="none"
                  strokeDasharray={getStepStatus('correct') === 'active' || getStepStatus('correct') === 'processing' ? '6 3' : 'none'}
                  className={getStepStatus('correct') === 'processing' ? 'animate-flow-dash' : ''}
                />
                
                <path
                  d="M 750 275 Q 750 380 400 380 Q 50 380 50 275"
                  stroke="#94a3b8"
                  strokeWidth="1.5"
                  fill="none"
                  strokeDasharray="4 2"
                  className="animate-flow-dash"
                  opacity={0.4}
                />
                
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
                        fill={status === 'active' ? (isAgent ? agentColors?.primary : '#10b981') : status === 'processing' ? (isAgent ? agentColors?.primary : '#60a5fa') : '#e2e8f0'}
                        opacity={status === 'pending' ? 0.6 : 1}
                        className={(status === 'processing' || isAgentActive) ? 'animate-pulse-ring' : ''}
                        filter="url(#glow)"
                      />
                      <circle r="32" fill={status === 'active' ? (isAgent ? agentColors?.primary : '#10b981') : status === 'processing' ? (isAgent ? agentColors?.primary : '#3b82f6') : '#f8fafc'} stroke={status === 'active' ? (isAgent ? agentColors?.secondary : '#059669') : status === 'processing' ? (isAgent ? agentColors?.secondary : '#60a5fa') : '#cbd5e1'} strokeWidth="2" />
                      
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
                        <path d="M -8 -10 L 8 -10 L 0 10 Z" fill="#64748b" />
                      ) : step.type === 'output' ? (
                        <path d="M -8 10 L 8 10 L 0 -10 Z" fill="#10b981" />
                      ) : (
                        <circle r="8" fill={status === 'active' ? '#f59e0b' : '#94a3b8'} />
                      )}
                      
                      <text y="55" textAnchor="middle" fontSize="11" fill="#64748b" fontWeight="500">{step.label}</text>
                    </g>
                  )
                })}
                
                {flowSteps.slice(0, -1).map((_, index) => {
                  const x = 125 + index * 100
                  return (
                    <polygon key={index} points={`${x},220 ${x + 8},225 ${x},230`} fill="#64748b" opacity={0.6} />
                  )
                })}
                <polygon points="45,270 55,275 45,280" fill="#94a3b8" opacity={0.4} />
              </svg>
              
              <div className="absolute bottom-4 left-4 right-4 space-y-2">
                {(sse.isConnected || sseTaskProgress.progress > 0) && (
                  <div className="bg-bg-card/90 backdrop-blur-sm rounded-lg p-2 border border-border/50">
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="text-text-secondary font-medium">{sseTaskProgress.description || '处理中...'}</span>
                      <span className="text-primary font-semibold">{Math.round(sseTaskProgress.progress)}%</span>
                    </div>
                    <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                      <div 
                        className={`h-full rounded-full transition-all duration-500 ${sseTaskProgress.stage === 'failed' ? 'bg-red-500' : sseTaskProgress.stage === 'complete' ? 'bg-green-500' : 'bg-primary'}`}
                        style={{ width: `${sseTaskProgress.progress}%` }}
                      />
                    </div>
                  </div>
                )}
                <div className="flex items-center justify-between text-xs text-text-tertiary">
                  <span>系统状态</span>
                  <span className="flex items-center gap-1">
                    {sse.isConnected && <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />}
                    {agentStatuses.some(a => a.state === 'running') ? '运行中' : agentStatuses.some(a => a.state === 'waiting') ? '等待中' : '空闲'}
                  </span>
                </div>
                <div className="flex gap-2">
                  <div className="flex items-center gap-1">
                    <div className="w-2 h-2 rounded-full bg-green-400" />
                    <span className="text-[10px] text-text-tertiary">空闲 {agentStatuses.filter(a => a.state === 'idle' || a.state === 'completed').length}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <div className="w-2 h-2 rounded-full bg-primary animate-pulse" />
                    <span className="text-[10px] text-text-tertiary">运行 {agentStatuses.filter(a => a.state === 'running' || a.state === 'waiting').length}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <div className="w-2 h-2 rounded-full bg-red-400" />
                    <span className="text-[10px] text-text-tertiary">异常 {agentStatuses.filter(a => a.state === 'failed' || a.state === 'error').length}</span>
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
              <Badge variant={agentStatuses.some(a => a.state === 'running') ? 'success' : 'default'} size="sm">
                {agentStatuses.some(a => a.state === 'running') ? '运行中' : '就绪'}
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
                  <div key={log.id} className={`flex gap-2 p-2 rounded-lg text-sm ${log.type === 'system' ? 'bg-bg-secondary' : log.type === 'success' ? 'bg-success/5 border border-success/10' : log.type === 'error' ? 'bg-red-50 border border-red-100' : 'bg-primary/5'}`}>
                    <div className={`w-1.5 h-1.5 rounded-full mt-1.5 ${log.type === 'system' ? 'bg-gray-400' : log.type === 'success' ? 'bg-success' : log.type === 'error' ? 'bg-red-500' : 'bg-primary'}`} />
                    <div className="flex-1 min-w-0">
                      <span className="text-xs text-text-tertiary flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {log.timestamp}
                        <span className={`ml-1 px-1 rounded text-[10px] ${log.agent === 'diagnosis' ? 'bg-[#3d5a80]/10 text-[#3d5a80]' : log.agent === 'generation' ? 'bg-[#5b8def]/10 text-[#5b8def]' : log.agent === 'review' ? 'bg-[#f59e0b]/10 text-[#f59e0b]' : 'bg-gray-100 text-gray-600'}`}>
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
                <Target className="w-5 h-5 text-text-secondary" />
                <h3 className="font-semibold text-text-primary">任务列表</h3>
              </div>
              <span className="text-xs text-text-tertiary">共 {tasks.length} 个任务</span>
            </div>
            <div className="p-4 space-y-3 max-h-[320px] overflow-y-auto">
              {tasks.length === 0 ? (
                <div className="text-center py-6 text-text-tertiary text-sm">暂无任务记录</div>
              ) : (
                tasks.slice(0, 10).map((task) => (
                  <div
                    key={task.taskId}
                    onClick={() => setSelectedTask(task)}
                    className="p-3 rounded-xl border border-border bg-bg-secondary/30 hover:border-primary/30 hover:bg-primary/5 transition-all cursor-pointer group"
                  >
                    <div className="flex items-start gap-2">
                      <div className={`w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0 ${
                        task.status === 'completed' ? 'bg-green-400' :
                        task.status === 'running' ? 'bg-primary animate-pulse' :
                        task.status === 'failed' ? 'bg-red-400' :
                        'bg-amber-400'
                      }`} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-xs font-medium text-text-primary truncate">#{task.taskId} {task.taskName}</p>
                          {getTaskStatusBadge(task.status)}
                        </div>
                        <div className="flex items-center gap-2 mt-1.5">
                          <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                            task.taskType === 'diagnosis' ? 'bg-[#3d5a80]/10 text-[#3d5a80]' :
                            task.taskType === 'generation' ? 'bg-[#5b8def]/10 text-[#5b8def]' :
                            task.taskType === 'review' ? 'bg-[#f59e0b]/10 text-[#f59e0b]' :
                            'bg-purple-100 text-purple-600'
                          }`}>
                            {task.taskType === 'diagnosis' ? '诊断' : task.taskType === 'generation' ? '生成' : task.taskType === 'review' ? '审核' : '全流程'}
                          </span>
                          <span className="text-[10px] text-text-tertiary">学习者 #{task.learnerId}</span>
                        </div>
                        {task.status === 'running' && (
                          <div className="mt-2">
                            <div className="h-1 bg-gray-100 rounded-full overflow-hidden">
                              <div className="h-full bg-primary rounded-full transition-all" style={{ width: `${task.progress}%` }} />
                            </div>
                          </div>
                        )}
                        <div className="flex items-center gap-2 mt-1.5">
                          {task.errorMessage && (
                            <span className="text-[10px] text-red-500 flex items-center gap-0.5">
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
      
      <TaskDetailModal isOpen={!!selectedTask} onClose={() => setSelectedTask(undefined)} task={selectedTask} />
    </div>
  )
}
