import { useEffect, useState } from 'react'
import { AlertCircle, Loader2 } from 'lucide-react'
import { desktopApi } from '../api/desktop'
import DesktopBootstrap from '../pages/DesktopBootstrap'
import Button from './Button'

export default function DesktopBootstrapGate({ children }: { children: React.ReactNode }) {
  const [required, setRequired] = useState<boolean | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = () => {
    if (!window.zhiyuDesktop?.isDesktop) {
      setRequired(false)
      return
    }
    setError(null)
    setRequired(null)
    void desktopApi
      .status()
      .then((status) => setRequired(status.required))
      .catch(() => setError('无法读取本机初始化状态，请重启软件后重试。'))
  }

  useEffect(load, [])

  if (required === null && !error) {
    return (
      <div className="flex min-h-screen items-center justify-center gap-3 bg-bg-secondary text-sm text-text-secondary" role="status">
        <Loader2 className="h-5 w-5 animate-spin text-primary" aria-hidden="true" />
        正在准备本机工作台...
      </div>
    )
  }
  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg-secondary px-4">
        <div className="w-full max-w-md rounded-lg border border-border bg-bg-primary p-6 text-center">
          <AlertCircle className="mx-auto h-8 w-8 text-error" aria-hidden="true" />
          <p className="mt-3 text-sm text-text-secondary" role="alert">{error}</p>
          <Button className="mt-5" onClick={load}>重试</Button>
        </div>
      </div>
    )
  }
  return required ? <DesktopBootstrap onCompleted={() => setRequired(false)} /> : <>{children}</>
}
