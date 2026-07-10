export const flowSteps = [
  { id: 'read-profile', label: '读取学情画像', type: 'input' },
  { id: 'diagnosis', label: '诊断知识盲区', type: 'agent', agentId: 'diagnosis' },
  { id: 'fetch-kb', label: '调取专业知识库', type: 'process' },
  { id: 'generate', label: '产出初稿资源', type: 'agent', agentId: 'generation' },
  { id: 'validate', label: '交叉校验辩论', type: 'agent', agentId: 'review' },
  { id: 'correct', label: '识别幻觉纠偏', type: 'process' },
  { id: 'output', label: '输出个性化资源', type: 'output' },
  { id: 'feedback', label: '接收学习反馈', type: 'process' },
] as const

export const agentColorMap = {
  diagnosis: { primary: 'var(--color-viz-1)', secondary: 'var(--color-viz-1)', bg: 'bg-viz-1/10', border: 'border-viz-1/30', text: 'text-viz-1' },
  generation: { primary: 'var(--color-viz-2)', secondary: 'var(--color-viz-2)', bg: 'bg-viz-2/10', border: 'border-viz-2/30', text: 'text-viz-2' },
  review: { primary: 'var(--color-viz-3)', secondary: 'var(--color-viz-3)', bg: 'bg-viz-3/10', border: 'border-viz-3/30', text: 'text-viz-3' },
} as const

export const statusConfig: Record<string, { label: string; color: string; bgLight: string; textColor: string }> = {
  idle: { label: '空闲', color: 'bg-text-tertiary', bgLight: 'bg-bg-tertiary', textColor: 'text-text-secondary' },
  running: { label: '运行中', color: 'bg-primary', bgLight: 'bg-primary/10', textColor: 'text-primary' },
  waiting: { label: '等待中', color: 'bg-info', bgLight: 'bg-info-light', textColor: 'text-info-dark' },
  completed: { label: '已完成', color: 'bg-success', bgLight: 'bg-success-light', textColor: 'text-success-dark' },
  failed: { label: '异常', color: 'bg-error', bgLight: 'bg-error-light', textColor: 'text-error-dark' },
  error: { label: '错误', color: 'bg-error', bgLight: 'bg-error-light', textColor: 'text-error-dark' },
  pending: { label: '等待中', color: 'bg-warning', bgLight: 'bg-warning-light', textColor: 'text-warning-dark' },
  cancelled: { label: '已取消', color: 'bg-text-tertiary', bgLight: 'bg-bg-tertiary', textColor: 'text-text-secondary' },
}

export const taskTypeOptions = [
  { value: 'diagnosis', label: '学情诊断' },
  { value: 'generation', label: '知识生成' },
  { value: 'review', label: '内容审核' },
  { value: 'full_flow', label: '全流程' },
] as const

export const stageToStepMap: Record<string, number> = {
  init: 0,
  diagnosis: 1,
  knowledge_retrieval: 2,
  generation: 3,
  judge_first: 4,
  debate: 5,
  final_revision: 6,
  complete: 7,
}

export function getTaskTypeLabel(taskType: string): string {
  const found = taskTypeOptions.find(t => t.value === taskType)
  return found ? found.label : taskType
}

export function getTaskTypeColor(taskType: string): string {
  switch (taskType) {
    case 'diagnosis': return 'bg-viz-1/10 text-viz-1'
    case 'generation': return 'bg-viz-2/10 text-viz-2'
    case 'review': return 'bg-viz-3/10 text-viz-3'
    default: return 'bg-bg-tertiary text-text-secondary'
  }
}
