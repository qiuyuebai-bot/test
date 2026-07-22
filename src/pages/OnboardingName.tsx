import { ArrowRight, Brain } from 'lucide-react'
import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import Button from '../components/Button'
import Input from '../components/Input'
import { toast } from '../components/toastStore'
import { authApi } from '../api'
import { ApiError } from '../lib/request'
import { onboardingNameSchema } from '../lib/validations'
import { useStore } from '../store'

export default function OnboardingName() {
  const navigate = useNavigate()
  const location = useLocation()
  const user = useStore((s) => s.user)
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const [isSaving, setIsSaving] = useState(false)

  const state = location.state as { from?: string; username?: string } | null
  const from = state?.from || '/dashboard'
  const username = state?.username || user?.username || ''

  const enterApp = () => {
    navigate(from, { replace: true })
  }

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const parsed = onboardingNameSchema.safeParse({ name })

    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message || '请输入你的称呼')
      return
    }

    setError('')
    setIsSaving(true)

    try {
      await authApi.setOnboardingName({ name: parsed.data.name })
      toast.success('设置成功', `欢迎你，${parsed.data.name}`)
      enterApp()
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        toast.error('设置失败', err.message)
      } else {
        toast.error('设置失败', '请稍后重试')
      }
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-gradient-to-br from-white via-[#f8fafc] to-[#eef4ff] px-5 py-10 text-slate-950">
      <section className="w-full max-w-3xl text-center">
        <div className="mx-auto mb-10 flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-600 text-white shadow-lg shadow-indigo-500/20">
          <Brain className="h-7 w-7" />
        </div>

        <p className="mb-4 text-sm font-medium text-slate-500">
          {username ? `账号 ${username} 已创建` : '账号已创建'}
        </p>

        <h1 className="text-4xl font-semibold leading-tight tracking-normal text-slate-950 sm:text-5xl">
          欢迎来到千早AI音
          <br />
          请问怎么称呼你
        </h1>

        <form onSubmit={handleSubmit} className="mx-auto mt-12 w-full max-w-2xl">
          <div className="relative">
            <Input
              value={name}
              onChange={(event) => {
                setName(event.target.value)
                if (error) setError('')
              }}
              placeholder="输入你的称呼"
              autoFocus
              aria-label="称呼"
              error={error}
              className="h-16 rounded-full border-slate-200 bg-white px-8 pr-20 text-lg text-slate-950 shadow-[0_18px_50px_rgba(15,23,42,0.10)] placeholder:text-slate-400 focus:border-slate-400 focus:ring-slate-500/10"
            />
            <Button
              type="submit"
              aria-label="进入"
              loading={isSaving}
              className="absolute right-2 top-2 h-12 w-12 rounded-full bg-slate-950 p-0 text-white shadow-md hover:bg-slate-800"
            >
              {!isSaving && <ArrowRight className="h-5 w-5" />}
            </Button>
          </div>

          <button
            type="button"
            onClick={enterApp}
            className="mt-10 text-sm font-medium text-slate-500 transition hover:text-slate-900"
          >
            跳过
          </button>
        </form>
      </section>
    </main>
  )
}
