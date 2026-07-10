import { Target, AlertTriangle } from 'lucide-react'
import Modal from '@/components/Modal'
import Badge from '@/components/Badge'
import type { AgentTask } from '@/types'
import { statusConfig } from '../constants'

interface Props {
  isOpen: boolean
  onClose: () => void
  task?: AgentTask
}

export function TaskDetailModal({ isOpen, onClose, task }: Props) {
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
          <div className="h-2 bg-bg-tertiary rounded-full overflow-hidden">
            <div className={`h-full rounded-full transition-all duration-500 ${task.status === 'completed' ? 'bg-success' : task.status === 'failed' ? 'bg-error' : 'bg-primary'}`} style={{ width: `${task.progress}%` }} />
          </div>
        </div>

        {task.errorMessage && (
          <div className="p-3 rounded-lg bg-error-light border border-error/30">
            <span className="text-xs text-error-dark font-medium flex items-center gap-1">
              <AlertTriangle className="w-3 h-3" />
              错误信息
            </span>
            <p className="text-error-dark text-xs mt-1">{task.errorMessage}</p>
          </div>
        )}
      </div>
    </Modal>
  )
}
