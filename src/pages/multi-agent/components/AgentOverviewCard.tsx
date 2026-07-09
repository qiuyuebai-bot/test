import type { LucideIcon } from 'lucide-react'
import type { AgentStatus } from '@/types'
import { agentColorMap, statusConfig } from '../constants'

interface Props {
  agent: AgentStatus
  icon: LucideIcon
}

export function AgentOverviewCard({ agent, icon: Icon }: Props) {
  const colors = agentColorMap[agent.agentType as keyof typeof agentColorMap] || agentColorMap.diagnosis
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
