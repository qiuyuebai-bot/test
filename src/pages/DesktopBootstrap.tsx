import { useRef, useState } from 'react'
import { BrainCircuit, LockKeyhole, ShieldCheck, UserRound } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import Button from '../components/Button'
import Input from '../components/Input'
import { desktopApi } from '../api/desktop'
import { authApi } from '../api'
import { ApiError } from '../lib/request'
import { setTokens, setUserInfo } from '../lib/request'
import { useStore } from '../store'

const fieldClassName =
  'h-12 rounded-lg border-border bg-bg-secondary pl-11 text-text-primary placeholder:text-text-tertiary focus:border-primary focus:ring-primary/20'

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message || '创建管理员失败，请稍后重试'
  return '无法创建管理员，请确认桌面服务正在运行'
}

export default function DesktopBootstrap({ onCompleted = () => undefined }: { onCompleted?: () => void }) {
  const navigate = useNavigate()
  const usernameRef = useRef<HTMLInputElement>(null)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError(null)
    if (!/^[a-zA-Z0-9_]{3,50}$/.test(username)) {
      setError('用户名应为 3-50 位字母、数字或下划线')
      usernameRef.current?.focus()
      return
    }
    if (password.length < 8 || !/[A-Za-z]/.test(password) || !/[0-9]/.test(password)) {
      setError('密码至少 8 位，并同时包含字母和数字')
      return
    }
    if (password !== confirmPassword) {
      setError('两次输入的密码不一致')
      return
    }
    setSubmitting(true)
    try {
      const result = await desktopApi.bootstrap({ username, password })
      setTokens(result.accessToken, result.refreshToken)
      setUserInfo({ user_id: result.userId, username: result.username, role: result.role })
      const user = await authApi.getCurrentUser()
      useStore.setState({ user, isLoggedIn: true, isLoading: false })
      onCompleted()
      navigate('/dashboard', { replace: true })
    } catch (requestError) {
      setError(errorMessage(requestError))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg-secondary px-4 py-8 text-text-primary">
      <section className="w-full max-w-md rounded-lg border border-border bg-bg-primary p-6 shadow-lg sm:p-8">
        <div className="mb-7 flex items-start gap-4">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-primary text-white">
            <BrainCircuit className="h-6 w-6" aria-hidden="true" />
          </div>
          <div>
            <p className="text-sm font-medium text-primary">知域引擎</p>
            <h1 className="mt-1 text-xl font-semibold">创建本机管理员</h1>
            <p className="mt-2 text-sm leading-6 text-text-secondary">
              此账号只保存在当前设备，用于管理本地学习数据和 AI 服务配置。
            </p>
          </div>
        </div>

        <form className="space-y-5" onSubmit={submit} noValidate>
          <label className="block text-sm font-medium text-text-primary" htmlFor="desktop-admin-username">
            管理员用户名
            <span className="relative mt-1.5 block">
              <UserRound className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-text-tertiary" aria-hidden="true" />
              <Input
                ref={usernameRef}
                id="desktop-admin-username"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                className={fieldClassName}
                placeholder="例如：admin_local"
                autoComplete="username"
                disabled={submitting}
              />
            </span>
          </label>

          <label className="block text-sm font-medium text-text-primary" htmlFor="desktop-admin-password">
            密码
            <span className="relative mt-1.5 block">
              <LockKeyhole className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-text-tertiary" aria-hidden="true" />
              <Input
                id="desktop-admin-password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className={fieldClassName}
                placeholder="至少 8 位，包含字母和数字"
                autoComplete="new-password"
                disabled={submitting}
              />
            </span>
          </label>

          <label className="block text-sm font-medium text-text-primary" htmlFor="desktop-admin-confirm-password">
            确认密码
            <span className="relative mt-1.5 block">
              <LockKeyhole className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-text-tertiary" aria-hidden="true" />
              <Input
                id="desktop-admin-confirm-password"
                type="password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                className={fieldClassName}
                placeholder="再次输入密码"
                autoComplete="new-password"
                disabled={submitting}
              />
            </span>
          </label>

          {error && (
            <p className="rounded-lg border border-error/25 bg-error-light px-3 py-2 text-sm text-error" role="alert">
              {error}
            </p>
          )}

          <Button type="submit" className="h-12 w-full" loading={submitting}>
            <ShieldCheck className="h-4 w-4" aria-hidden="true" />
            {submitting ? '正在创建...' : '创建并进入工作台'}
          </Button>
        </form>
      </section>
    </main>
  )
}
