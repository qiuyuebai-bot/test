import { clsx } from 'clsx'
import Card from './Card'
import Button from './Button'
import { AlertCircle, WifiOff, Server, RefreshCw, Home } from 'lucide-react'

interface ErrorStateProps {
  type?: 'default' | 'network' | 'server' | 'logic'
  title?: string
  description?: string
  details?: string
  onRetry?: () => void
  onGoHome?: () => void
  className?: string
}

const errorConfig = {
  default: {
    title: '出错了',
    description: '加载失败，请稍后重试',
    icon: AlertCircle,
  },
  network: {
    title: '网络连接异常',
    description: '请检查网络连接后重试',
    icon: WifiOff,
  },
  server: {
    title: '服务器错误',
    description: '服务端处理异常，请稍后重试',
    icon: Server,
  },
  logic: {
    title: '数据处理异常',
    description: '系统逻辑处理出现偏差，请联系管理员',
    icon: AlertCircle,
  },
}

export default function ErrorState({
  type = 'default',
  title,
  description,
  details,
  onRetry,
  onGoHome,
  className,
}: ErrorStateProps) {
  const config = errorConfig[type]
  const IconComponent = config.icon

  return (
    <Card className={clsx('flex flex-col items-center justify-center py-10 px-6 text-center', className)}>
      <div className="w-16 h-16 rounded-2xl bg-warning-light flex items-center justify-center mb-5 transition-all duration-250">
        <IconComponent className="w-8 h-8 text-warning" />
      </div>
      <h3 className="text-base font-medium text-text-primary mb-2">{title || config.title}</h3>
      <p className="text-sm text-text-secondary max-w-sm mb-4 leading-relaxed">
        {description || config.description}
      </p>
      {details && (
        <p className="text-xs text-text-tertiary bg-bg-secondary px-3 py-2 rounded-lg mb-5 font-mono">
          {details}
        </p>
      )}
      <div className="flex items-center gap-2">
        {onRetry && (
          <Button variant="outline" size="sm" onClick={onRetry}>
            <RefreshCw className="w-4 h-4 mr-1" />
            重试
          </Button>
        )}
        {onGoHome && (
          <Button variant="ghost" size="sm" onClick={onGoHome}>
            <Home className="w-4 h-4 mr-1" />
            返回首页
          </Button>
        )}
      </div>
    </Card>
  )
}

// 预设的错误场景
ErrorState.Network = function NetworkError({ onRetry, onGoHome }: { onRetry?: () => void; onGoHome?: () => void }) {
  return <ErrorState type="network" onRetry={onRetry} onGoHome={onGoHome} />
}

ErrorState.Server = function ServerError({ onRetry }: { onRetry?: () => void }) {
  return <ErrorState type="server" onRetry={onRetry} />
}

ErrorState.Logic = function LogicError({ onRetry }: { onRetry?: () => void }) {
  return <ErrorState type="logic" onRetry={onRetry} />
}