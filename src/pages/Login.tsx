import { useNavigate, useLocation } from 'react-router-dom'
import { useStore } from '../store'
import { Brain, Lock, User } from 'lucide-react'
import Button from '../components/Button'
import Input from '../components/Input'
import { Form, FormField } from '../components'
import { loginSchema, LoginFormValues } from '../lib/validations'
import { toast } from '../components/toastStore'
import { ApiError } from '../lib/request'

export default function Login() {
  const login = useStore((s) => s.login)
  const navigate = useNavigate()
  const location = useLocation()

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/'

  const handleSubmit = async (data: LoginFormValues) => {
    try {
      await login(data.username, data.password)
      toast.success('登录成功', `欢迎回来，${data.username}`)
      navigate(from, { replace: true })
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        toast.error('登录失败', err.message)
      } else {
        toast.error('登录失败', '请检查用户名和密码')
      }
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 px-4">
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-blue-500/5 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-cyan-500/5 rounded-full blur-3xl" />
      </div>

      <div className="relative w-full max-w-md">
        <div className="bg-white/5 backdrop-blur-xl rounded-2xl border border-white/10 p-8 shadow-2xl">
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-500 mb-4 shadow-lg shadow-blue-500/20">
              <Brain className="w-8 h-8 text-white" />
            </div>
            <h1 className="text-2xl font-semibold text-white tracking-tight">
              领域知识个性化生成系统
            </h1>
            <p className="text-slate-400 mt-2 text-sm">多智能体协同决策平台</p>
          </div>

          <Form<LoginFormValues>
            schema={loginSchema}
            defaultValues={{ username: '', password: '' }}
            onSubmit={handleSubmit}
            className="space-y-5"
          >
            {({ register, formState: { errors, isSubmitting } }) => (
              <>
                <FormField
                  label="用户名"
                  error={errors.username?.message}
                >
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                    <Input
                      type="text"
                      placeholder="请输入用户名"
                      className="pl-10 bg-white/5 border-white/10 text-white placeholder:text-slate-500 focus:border-blue-500/50 focus:ring-blue-500/20"
                      autoComplete="username"
                      error={errors.username?.message}
                      {...register('username')}
                    />
                  </div>
                </FormField>

                <FormField
                  label="密码"
                  error={errors.password?.message}
                >
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                    <Input
                      type="password"
                      placeholder="请输入密码"
                      className="pl-10 bg-white/5 border-white/10 text-white placeholder:text-slate-500 focus:border-blue-500/50 focus:ring-blue-500/20"
                      autoComplete="current-password"
                      error={errors.password?.message}
                      {...register('password')}
                    />
                  </div>
                </FormField>

                <Button
                  type="submit"
                  loading={isSubmitting}
                  className="w-full py-2.5 bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white font-medium rounded-lg transition-all duration-200 shadow-lg shadow-blue-500/20 disabled:opacity-50"
                >
                  {isSubmitting ? '登录中...' : '登 录'}
                </Button>
              </>
            )}
          </Form>

          <div className="mt-6 pt-6 border-t border-white/5 text-center">
            <p className="text-xs text-slate-500">
              默认管理员账号请参考系统部署文档
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
