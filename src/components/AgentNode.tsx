import { clsx } from 'clsx'
import { Activity, Brain, Scale } from 'lucide-react'

interface AgentNodeProps {
  id: 'diagnosis' | 'knowledge' | 'judge'
  name: string
  status: 'idle' | 'working' | 'completed'
  currentTask?: string
  progress?: number
  className?: string
}

const agentConfig = {
  diagnosis: {
    icon: Activity,
    color: 'bg-[#3d5a80]',
    lightColor: 'bg-[#3d5a80]/10',
    borderColor: 'border-[#3d5a80]/30',
    textColor: 'text-[#3d5a80]',
    label: '学情诊断',
  },
  knowledge: {
    icon: Brain,
    color: 'bg-[#6366f1]',
    lightColor: 'bg-[#6366f1]/10',
    borderColor: 'border-[#6366f1]/30',
    textColor: 'text-[#6366f1]',
    label: '知识生成',
  },
  judge: {
    icon: Scale,
    color: 'bg-[#f59e0b]',
    lightColor: 'bg-[#f59e0b]/10',
    borderColor: 'border-[#f59e0b]/30',
    textColor: 'text-[#f59e0b]',
    label: '审核裁判',
  },
}

export default function AgentNode({
  id,
  name,
  status,
  currentTask,
  progress,
  className,
}: AgentNodeProps) {
  const config = agentConfig[id]
  const Icon = config.icon

  const statusStyles = {
    idle: 'opacity-60',
    working: 'node-pulse',
    completed: 'ring-2 ring-success/30',
  }

  return (
    <div
      className={clsx(
        'relative flex flex-col items-center p-6 bg-bg-card rounded-xl border shadow-soft',
        'w-[200px] transition-all duration-300',
        config.borderColor,
        statusStyles[status],
        className
      )}
    >
      {/* 状态指示器 */}
      <div className="absolute top-3 right-3">
        <div
          className={clsx(
            'w-2 h-2 rounded-full',
            status === 'idle' && 'bg-gray-300',
            status === 'working' && 'bg-primary animate-pulse',
            status === 'completed' && 'bg-success'
          )}
        />
      </div>

      {/* Agent 图标 */}
      <div
        className={clsx(
          'w-14 h-14 rounded-xl flex items-center justify-center mb-4',
          config.color
        )}
      >
        <Icon className="w-7 h-7 text-white" />
      </div>

      {/* Agent 名称 */}
      <h3 className="text-base font-semibold text-text-primary mb-1">{name}</h3>
      <p className="text-xs text-text-tertiary mb-3">{config.label}Agent</p>

      {/* 当前任务 */}
      {currentTask && (
        <div className="w-full">
          <p className="text-xs text-text-secondary text-center mb-2 line-clamp-1">
            {currentTask}
          </p>
          {progress !== undefined && status === 'working' && (
            <div className="w-full h-1 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
              <div
                className={clsx('h-full rounded-full transition-all duration-500', config.color)}
                style={{ width: `${progress}%` }}
              />
            </div>
          )}
        </div>
      )}

      {/* 状态标签 */}
      <div
        className={clsx(
          'mt-3 px-2 py-0.5 rounded-full text-xs font-medium',
          status === 'idle' && 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400',
          status === 'working' && `${config.lightColor} ${config.textColor}`,
          status === 'completed' && 'bg-success-light text-success-dark'
        )}
      >
        {status === 'idle' && '等待中'}
        {status === 'working' && '工作中'}
        {status === 'completed' && '已完成'}
      </div>
    </div>
  )
}