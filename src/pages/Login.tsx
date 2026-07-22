import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Brain, Lock, LogIn, Network, Sparkles, User, UserPlus } from 'lucide-react'
import Button from '../components/Button'
import Input from '../components/Input'
import { Form, FormField } from '../components'
import { loginSchema, registerSchema, type LoginFormValues, type RegisterFormValues } from '../lib/validations'
import { toast } from '../components/toastStore'
import { ApiError } from '../lib/request'
import { useStore } from '../store'

type AuthMode = 'login' | 'register'

const inputClassName =
  'h-12 rounded-xl border-indigo-100 bg-white pl-11 text-slate-950 placeholder:text-slate-400 focus:border-emerald-500 focus:ring-emerald-500/15'

function reportAuthError(title: string, err: unknown, fallback: string) {
  if (err instanceof ApiError) {
    toast.error(title, err.message)
    return
  }
  toast.error(title, fallback)
}

export default function Login() {
  const login = useStore((s) => s.login)
  const registerAccount = useStore((s) => s.register)
  const navigate = useNavigate()
  const location = useLocation()
  const [mode, setMode] = useState<AuthMode>('login')

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/'
  const isLogin = mode === 'login'

  const handleLogin = async (data: LoginFormValues) => {
    try {
      await login(data.username, data.password)
      toast.success('登录成功', `欢迎回来，${data.username}`)
      navigate(from, { replace: true })
    } catch (err: unknown) {
      reportAuthError('登录失败', err, '请检查用户名和密码')
    }
  }

  const handleRegister = async (data: RegisterFormValues) => {
    try {
      await registerAccount({
        username: data.username,
        password: data.password,
        role: 'learner',
      })
      toast.success('注册成功', `欢迎加入，${data.username}`)
      navigate('/onboarding/name', {
        replace: true,
        state: { from, username: data.username },
      })
    } catch (err: unknown) {
      reportAuthError('注册失败', err, '请检查用户名是否已被占用，密码是否符合要求')
    }
  }

  return (
    <div className="min-h-screen bg-[#f5f7fb] px-3 py-4 text-slate-950 lg:px-6 lg:py-5">
      <div className="relative mx-auto grid min-h-[calc(100vh-2.5rem)] w-full max-w-[1500px] overflow-hidden rounded-[2rem] bg-white shadow-[0_24px_80px_rgba(15,23,42,0.14)] lg:grid-cols-[1.08fr_0.92fr]">
        <section
          className="relative flex min-h-[430px] flex-col justify-between overflow-hidden bg-cover bg-center p-8 sm:p-10 lg:mr-[-10rem] lg:p-16 lg:pr-[14rem]"
          style={{ backgroundImage: "url('/login-cover.jpg')" }}
        >
          <div className="absolute inset-0 bg-gradient-to-br from-white/90 via-indigo-400/22 to-white/88" />
          <div className="absolute inset-0 bg-gradient-to-r from-white/10 via-white/35 to-white/98" />
          <div className="absolute inset-0 bg-gradient-to-t from-sky-100/30 via-transparent to-transparent" />
          <div className="pointer-events-none absolute inset-y-0 right-[-1px] hidden w-[76%] bg-gradient-to-r from-transparent via-white/86 to-white lg:block" />
          <div className="pointer-events-none absolute inset-x-0 bottom-0 h-28 bg-gradient-to-b from-transparent via-white/55 to-white lg:hidden" />

          <div className="relative z-20 max-w-[620px]">
            <h1 className="text-[3rem] font-bold leading-[1.08] tracking-normal text-indigo-950 sm:text-6xl lg:text-[4.15rem]">
              智体协同
              <br />
              精进研学
            </h1>
          </div>

          <div className="relative z-20 mt-8 max-w-[590px] space-y-10 text-slate-950 lg:-translate-y-8">
            <div className="flex gap-6">
              <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-white/45 text-indigo-800 shadow-sm ring-1 ring-white/55 backdrop-blur-sm">
                <Network className="h-7 w-7" />
              </div>
              <div>
                <h2 className="text-2xl font-semibold text-slate-950">多智能体协同交互</h2>
                <p className="mt-3 text-base font-medium leading-7 text-slate-800">
                  通过多智能体分工协作，完成问题拆解、知识梳理、资料校验和学习资源生成，让研学过程更系统、更清晰。
                </p>
              </div>
            </div>

            <div className="flex gap-6">
              <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-white/45 text-emerald-700 shadow-sm ring-1 ring-white/55 backdrop-blur-sm">
                <Sparkles className="h-7 w-7" />
              </div>
              <div>
                <h2 className="text-2xl font-semibold text-slate-950">个性化知识构建</h2>
                <p className="mt-3 text-base font-medium leading-7 text-slate-800">
                  根据学习者状态生成专属学习路径，定位薄弱点并沉淀本地知识数据，帮助每个账号形成独立的学习记录。
                </p>
              </div>
            </div>
          </div>

          <div className="relative z-20 mt-14 flex items-center gap-3 text-indigo-950">
            <Brain className="h-7 w-7 text-indigo-700" />
            <span className="text-2xl font-bold">千早AI音</span>
          </div>
        </section>

        <section className="relative z-20 flex items-center justify-center bg-gradient-to-r from-white/88 via-white/98 to-white px-6 py-10 sm:px-10 lg:px-14">
          <div className="relative z-10 w-full max-w-xl rounded-[2rem] border border-slate-100 bg-white px-9 py-14 shadow-[0_24px_70px_rgba(15,23,42,0.10)] ring-1 ring-white sm:px-12 sm:py-16 lg:translate-y-8 lg:px-14">
            <div className="mb-8 text-center">
              <div className="mx-auto mb-6 inline-flex rounded-full bg-slate-100 p-1 text-sm font-semibold text-slate-500">
                <button
                  type="button"
                  onClick={() => setMode('login')}
                  className={`inline-flex h-10 items-center gap-2 rounded-full px-5 transition ${
                    isLogin ? 'bg-white text-indigo-700 shadow-sm' : 'hover:text-slate-800'
                  }`}
                >
                  <LogIn className="h-4 w-4" />
                  登录
                </button>
                <button
                  type="button"
                  onClick={() => setMode('register')}
                  className={`inline-flex h-10 items-center gap-2 rounded-full px-5 transition ${
                    !isLogin ? 'bg-white text-indigo-700 shadow-sm' : 'hover:text-slate-800'
                  }`}
                >
                  <UserPlus className="h-4 w-4" />
                  注册
                </button>
              </div>

              <h2 className="text-2xl font-semibold tracking-normal text-slate-950">
                {isLogin ? '登录账号' : '创建账号'}
              </h2>
              <p className="mt-2 text-sm text-slate-500">
                {isLogin ? '进入知识智能体工作台' : '每个人都可以创建自己的本地账号'}
              </p>
            </div>

            {isLogin ? (
              <Form<LoginFormValues>
                key="login"
                schema={loginSchema}
                defaultValues={{ username: '', password: '' }}
                onSubmit={handleLogin}
                className="space-y-5"
              >
                {({ register, formState: { errors, isSubmitting } }) => (
                  <>
                    <FormField label="用户名" error={errors.username?.message}>
                      <div className="relative">
                        <User className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-indigo-400" />
                        <Input
                          type="text"
                          placeholder="请输入用户名"
                          className={inputClassName}
                          autoComplete="username"
                          error={errors.username?.message}
                          {...register('username')}
                        />
                      </div>
                    </FormField>

                    <FormField label="密码" error={errors.password?.message}>
                      <div className="relative">
                        <Lock className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-indigo-400" />
                        <Input
                          type="password"
                          placeholder="请输入密码"
                          className={inputClassName}
                          autoComplete="current-password"
                          error={errors.password?.message}
                          {...register('password')}
                        />
                      </div>
                    </FormField>

                    <Button
                      type="submit"
                      loading={isSubmitting}
                      className="h-12 w-full rounded-xl bg-gradient-to-r from-indigo-600 via-blue-500 to-sky-500 text-sm font-semibold text-white shadow-lg shadow-blue-500/20 transition-all hover:from-indigo-500 hover:via-blue-400 hover:to-sky-400 disabled:opacity-60"
                    >
                      {isSubmitting ? '登录中...' : '登录'}
                    </Button>
                  </>
                )}
              </Form>
            ) : (
              <Form<RegisterFormValues>
                key="register"
                schema={registerSchema}
                defaultValues={{ username: '', password: '', confirmPassword: '' }}
                onSubmit={handleRegister}
                className="space-y-5"
              >
                {({ register, formState: { errors, isSubmitting } }) => (
                  <>
                    <FormField label="用户名" error={errors.username?.message}>
                      <div className="relative">
                        <User className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-indigo-400" />
                        <Input
                          type="text"
                          placeholder="3-50 位字母、数字或下划线"
                          className={inputClassName}
                          autoComplete="username"
                          error={errors.username?.message}
                          {...register('username')}
                        />
                      </div>
                    </FormField>

                    <FormField label="密码" error={errors.password?.message} description="至少 8 位，并包含字母和数字">
                      <div className="relative">
                        <Lock className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-indigo-400" />
                        <Input
                          type="password"
                          placeholder="请输入新密码"
                          className={inputClassName}
                          autoComplete="new-password"
                          error={errors.password?.message}
                          {...register('password')}
                        />
                      </div>
                    </FormField>

                    <FormField label="确认密码" error={errors.confirmPassword?.message}>
                      <div className="relative">
                        <Lock className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-indigo-400" />
                        <Input
                          type="password"
                          placeholder="请再次输入密码"
                          className={inputClassName}
                          autoComplete="new-password"
                          error={errors.confirmPassword?.message}
                          {...register('confirmPassword')}
                        />
                      </div>
                    </FormField>

                    <Button
                      type="submit"
                      loading={isSubmitting}
                      className="h-12 w-full rounded-xl bg-gradient-to-r from-indigo-600 via-blue-500 to-sky-500 text-sm font-semibold text-white shadow-lg shadow-blue-500/20 transition-all hover:from-indigo-500 hover:via-blue-400 hover:to-sky-400 disabled:opacity-60"
                    >
                      {isSubmitting ? '创建中...' : '创建账号'}
                    </Button>
                  </>
                )}
              </Form>
            )}

            <div className="mt-8 border-t border-slate-100 pt-5 text-center">
              <p className="text-xs text-slate-400">
                {isLogin ? '默认账号：admin / admin123，也可以注册自己的账号' : '注册账号会写入本地数据库，保留 Docker 卷即可持久保存'}
              </p>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
