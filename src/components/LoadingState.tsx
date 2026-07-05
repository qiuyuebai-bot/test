import { clsx } from 'clsx'
import Card from './Card'
import { Loader2, Sparkles } from 'lucide-react'

interface LoadingStateProps {
  type?: 'default' | 'generating' | 'analyzing'
  message?: string
  className?: string
  showCard?: boolean
}

const defaultMessages = {
  default: '加载中...',
  generating: '正在生成资源，请稍候',
  analyzing: '正在分析学情数据',
}

export default function LoadingState({
  type = 'default',
  message,
  className,
  showCard = true,
}: LoadingStateProps) {
  const displayMessage = message || defaultMessages[type]

  const content = (
    <div className={clsx('flex flex-col items-center justify-center py-10 px-6', className)}>
      <div className="relative">
        <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center mb-5">
          {type === 'generating' ? (
            <Sparkles className="w-7 h-7 text-primary animate-pulse" />
          ) : (
            <Loader2 className="w-7 h-7 text-primary animate-spin" />
          )}
        </div>
      </div>
      <p className="text-sm text-text-secondary mb-4">{displayMessage}</p>
      {type === 'generating' && (
        <div className="w-48 h-1.5 bg-bg-secondary rounded-full overflow-hidden">
          <div className="h-full bg-primary rounded-full animate-pulse" style={{ width: '60%' }} />
        </div>
      )}
    </div>
  )

  return showCard ? <Card className="w-full">{content}</Card> : content
}

// 预设的加载场景
LoadingState.Generating = function GeneratingLoading() {
  return <LoadingState type="generating" message="多 Agent 协同生成中，请稍候..." />
}

LoadingState.Analyzing = function AnalyzingLoading() {
  return <LoadingState type="analyzing" message="正在分析学习者画像..." />
}