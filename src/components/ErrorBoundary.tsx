import { Component, ErrorInfo, ReactNode } from 'react'
import { AlertTriangle, RefreshCw, Home } from 'lucide-react'
import Button from './Button'

interface ErrorBoundaryProps {
  children: ReactNode
  fallback?: ReactNode
  onError?: (error: Error, errorInfo: ErrorInfo) => void
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

export default class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error('ErrorBoundary caught an error:', error, errorInfo)
    this.props.onError?.(error, errorInfo)
  }

  handleReset = (): void => {
    this.setState({ hasError: false, error: null })
  }

  handleGoHome = (): void => {
    this.setState({ hasError: false, error: null })
    window.location.href = '/'
  }

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <div className="min-h-screen flex items-center justify-center bg-bg-primary p-4">
          <div className="max-w-md w-full bg-bg-card rounded-2xl border border-border p-8 shadow-lg text-center">
            <div className="w-16 h-16 rounded-2xl bg-rose-50 dark:bg-rose-500/10 flex items-center justify-center mx-auto mb-5">
              <AlertTriangle className="w-8 h-8 text-rose-500" />
            </div>
            <h2 className="text-lg font-semibold text-text-primary mb-2">
              页面出现异常
            </h2>
            <p className="text-sm text-text-secondary mb-4 leading-relaxed">
              很抱歉，当前页面发生了意外错误。您可以尝试刷新页面或返回首页。
            </p>
            {this.state.error && !import.meta.env.PROD && (
              <details className="text-left mb-5">
                <summary className="text-xs text-text-tertiary cursor-pointer hover:text-text-secondary transition-colors mb-2">
                  错误详情
                </summary>
                <pre className="text-xs text-text-tertiary bg-bg-secondary p-3 rounded-lg overflow-auto max-h-40 font-mono">
                  {this.state.error.message}
                  {this.state.error.stack && (
                    <>
                      {'\n\n'}
                      {this.state.error.stack}
                    </>
                  )}
                </pre>
              </details>
            )}
            <div className="flex items-center justify-center gap-3">
              <Button variant="outline" size="sm" onClick={this.handleReset}>
                <RefreshCw className="w-4 h-4 mr-1" />
                尝试恢复
              </Button>
              <Button variant="primary" size="sm" onClick={this.handleGoHome}>
                <Home className="w-4 h-4 mr-1" />
                返回首页
              </Button>
            </div>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}

export function withErrorBoundary<P extends object>(
  Component: React.ComponentType<P>,
  errorBoundaryProps?: Omit<ErrorBoundaryProps, 'children'>
): React.FC<P> {
  const Wrapped: React.FC<P> = (props) => (
    <ErrorBoundary {...errorBoundaryProps}>
      <Component {...props} />
    </ErrorBoundary>
  )
  Wrapped.displayName = `withErrorBoundary(${Component.displayName || Component.name || 'Component'})`
  return Wrapped
}
