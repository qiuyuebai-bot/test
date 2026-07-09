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
  diagnosis: { primary: '#3d5a80', secondary: '#5a7aa5', bg: 'bg-[#3d5a80]/10', border: 'border-[#3d5a80]/30', text: 'text-[#3d5a80]' },
  generation: { primary: '#5b8def', secondary: '#7ba6f5', bg: 'bg-[#5b8def]/10', border: 'border-[#5b8def]/30', text: 'text-[#5b8def]' },
  review: { primary: '#f59e0b', secondary: '#fbbf24', bg: 'bg-[#f59e0b]/10', border: 'border-[#f59e0b]/30', text: 'text-[#f59e0b]' },
} as const

export const statusConfig: Record<string, { label: string; color: string; bgLight: string; textColor: string }> = {
  idle: { label: '空闲', color: 'bg-gray-400', bgLight: 'bg-gray-100 dark:bg-gray-800', textColor: 'text-gray-600' },
  running: { label: '运行中', color: 'bg-primary', bgLight: 'bg-primary/10', textColor: 'text-primary' },
  waiting: { label: '等待中', color: 'bg-blue-400', bgLight: 'bg-blue-50', textColor: 'text-blue-600' },
  completed: { label: '已完成', color: 'bg-green-400', bgLight: 'bg-green-50', textColor: 'text-green-600' },
  failed: { label: '异常', color: 'bg-red-400', bgLight: 'bg-red-50', textColor: 'text-red-600' },
  error: { label: '错误', color: 'bg-red-500', bgLight: 'bg-red-50', textColor: 'text-red-600' },
  pending: { label: '等待中', color: 'bg-amber-400', bgLight: 'bg-amber-50', textColor: 'text-amber-600' },
  cancelled: { label: '已取消', color: 'bg-gray-400', bgLight: 'bg-gray-100 dark:bg-gray-800', textColor: 'text-gray-600' },
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
    case 'diagnosis': return 'bg-[#3d5a80]/10 text-[#3d5a80]'
    case 'generation': return 'bg-[#5b8def]/10 text-[#5b8def]'
    case 'review': return 'bg-[#f59e0b]/10 text-[#f59e0b]'
    default: return 'bg-purple-100 text-purple-600'
  }
}
