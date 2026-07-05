import { useState, useEffect, useMemo } from 'react'
import { useStore } from '@/store'
import Card from '@/components/Card'
import Badge from '@/components/Badge'
import Button from '@/components/Button'
import LoadingState from '@/components/LoadingState'
import EmptyState from '@/components/EmptyState'
import ErrorState from '@/components/ErrorState'
import {
  Rocket,
  Server,
  Cloud,
  Database,
  GitBranch,
  FileCode,
  Copy,
  CheckCircle,
  Link as LinkIcon,
  Book,
} from 'lucide-react'

export default function Deployment() {
  const learners = useStore((s) => s.learners)
  const learnersLoading = useStore((s) => s.learnersLoading)
  const fetchLearners = useStore((s) => s.fetchLearners)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchLearners({ page: 1, pageSize: 50 })
      .catch((err) => setError(err instanceof Error ? err.message : '加载学习者失败'))
      .finally(() => setLoading(false))
  }, [fetchLearners])

  const deploymentSteps = [
    {
      step: 1,
      title: '环境准备',
      description: '安装 Docker 和 Docker Compose',
      code: 'curl -fsSL https://get.docker.com | sh',
    },
    {
      step: 2,
      title: '配置环境变量',
      description: '复制并配置环境变量文件',
      code: 'cp .env.example .env',
    },
    {
      step: 3,
      title: '启动服务',
      description: '使用 Docker Compose 启动所有服务',
      code: 'docker-compose up -d',
    },
    {
      step: 4,
      title: '验证部署',
      description: '检查所有服务运行状态',
      code: 'docker-compose ps',
    },
  ]

  // 系统架构信息（对齐实际项目技术栈）
  const architecture = [
    { name: '前端服务', icon: Server, desc: 'React 18 + Vite + TypeScript + TailwindCSS', port: '5173' },
    { name: '后端 API', icon: Server, desc: 'FastAPI + SQLAlchemy + Pydantic', port: '8000' },
    { name: '向量数据库', icon: Database, desc: 'ChromaDB（可降级为关键词检索）', port: '8000' },
    { name: '缓存服务', icon: Server, desc: 'Redis（可选，用于 Celery 异步队列）', port: '6379' },
  ]

  const handleCopy = (code: string) => {
    navigator.clipboard.writeText(code)
  }

  // 按能力等级筛选 3 类样本：初学者 / 进阶者 / 专家
  const getSampleLevel = (avg: number): { type: string; description: string } => {
    if (avg < 50) return { type: '初学者样本', description: '理论基础薄弱，需要从基础开始' }
    if (avg < 80) return { type: '进阶者样本', description: '有一定基础，需要专项突破' }
    return { type: '专家样本', description: '理论基础扎实，挑战高阶内容' }
  }

  // 选出代表性样本（每个等级取一人）
  const sampleLearners = useMemo(() => {
    if (learners.length === 0) return []
    const sorted = [...learners].sort((a, b) => a.averageAbility - b.averageAbility)
    const beginner = sorted.find((l) => l.averageAbility < 50) || sorted[0]
    const intermediate = sorted.find((l) => l.averageAbility >= 50 && l.averageAbility < 80)
    const expert = [...sorted].reverse().find((l) => l.averageAbility >= 80)
    const picks = [beginner, intermediate, expert].filter(Boolean) as typeof learners
    return picks.slice(0, 3)
  }, [learners])

  if (loading || learnersLoading) {
    return <LoadingState type="default" />
  }

  if (error) {
    return <ErrorState type="default" onRetry={() => { setError(null); setLoading(true) }} />
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* 头部 */}
      <Card padding="md">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-xl bg-primary/10 flex items-center justify-center">
              <Rocket className="w-7 h-7 text-primary" />
            </div>
            <div>
              <h1 className="text-xl font-semibold text-text-primary">系统部署说明</h1>
              <p className="text-sm text-text-secondary mt-1">快速部署指南与架构说明</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="success">
              <CheckCircle className="w-3 h-3 mr-1" />
              v1.0.0
            </Badge>
          </div>
        </div>
      </Card>

      {/* 系统架构 */}
      <Card padding="md">
        <h2 className="text-lg font-semibold text-text-primary mb-4">系统架构</h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {architecture.map((item) => (
            <div key={item.name} className="p-4 rounded-xl border border-border">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                  <item.icon className="w-5 h-5 text-primary" />
                </div>
                <div>
                  <p className="font-medium text-text-primary">{item.name}</p>
                  <p className="text-xs text-text-tertiary">端口: {item.port}</p>
                </div>
              </div>
              <p className="text-sm text-text-secondary">{item.desc}</p>
            </div>
          ))}
        </div>
      </Card>

      {/* 部署步骤 */}
      <Card padding="md">
        <h2 className="text-lg font-semibold text-text-primary mb-4">部署步骤</h2>
        <div className="space-y-4">
          {deploymentSteps.map((item) => (
            <div key={item.step} className="flex gap-4">
              <div className="flex flex-col items-center">
                <div className="w-10 h-10 rounded-full bg-primary flex items-center justify-center text-white font-semibold">
                  {item.step}
                </div>
                {item.step < deploymentSteps.length && (
                  <div className="w-0.5 h-full bg-border mt-2" />
                )}
              </div>
              <div className="flex-1 pb-6">
                <h3 className="font-medium text-text-primary mb-1">{item.title}</h3>
                <p className="text-sm text-text-secondary mb-3">{item.description}</p>
                <div className="relative">
                  <code className="block p-3 rounded-lg bg-gray-900 text-gray-100 text-sm font-mono overflow-x-auto">
                    {item.code}
                  </code>
                  <button
                    onClick={() => handleCopy(item.code)}
                    className="absolute right-2 top-2 p-1.5 rounded hover:bg-gray-700 transition-colors"
                  >
                    <Copy className="w-4 h-4 text-gray-400" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 源码管理 */}
        <Card padding="md">
          <div className="flex items-center gap-2 mb-4">
            <GitBranch className="w-5 h-5 text-text-secondary" />
            <h2 className="text-lg font-semibold text-text-primary">源码管理</h2>
          </div>
          <div className="space-y-3">
            <div className="p-4 rounded-xl border border-border">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <FileCode className="w-4 h-4 text-primary" />
                  <span className="font-medium text-text-primary">前端源码</span>
                </div>
                <Badge variant="default">TypeScript</Badge>
              </div>
              <p className="text-sm text-text-secondary mb-3">React 18 + Vite + TailwindCSS</p>
              <Button variant="outline" size="sm" className="w-full">
                <LinkIcon className="w-4 h-4 mr-1" />
                查看源码
              </Button>
            </div>
            <div className="p-4 rounded-xl border border-border">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Server className="w-4 h-4 text-success" />
                  <span className="font-medium text-text-primary">后端源码</span>
                </div>
                <Badge variant="default">Python</Badge>
              </div>
              <p className="text-sm text-text-secondary mb-3">FastAPI + SQLAlchemy + Pydantic</p>
              <Button variant="outline" size="sm" className="w-full">
                <LinkIcon className="w-4 h-4 mr-1" />
                查看源码
              </Button>
            </div>
          </div>
        </Card>

        {/* 相关文档 */}
        <Card padding="md">
          <div className="flex items-center gap-2 mb-4">
            <Book className="w-5 h-5 text-text-secondary" />
            <h2 className="text-lg font-semibold text-text-primary">相关文档</h2>
          </div>
          <div className="space-y-3">
            {[
              { name: 'API 接口文档', desc: 'FastAPI 自动生成的 OpenAPI 文档', url: '/docs' },
              { name: 'ReDoc 文档', desc: 'ReDoc 风格的 API 文档', url: '/redoc' },
              { name: '系统信息接口', desc: '系统基础信息与功能列表', url: '/api/v1/info' },
              { name: '健康检查', desc: 'K8s 风格的存活与就绪探针', url: '/api/v1/health/ready' },
            ].map((doc) => (
              <div
                key={doc.url}
                className="flex items-center justify-between p-3 rounded-lg hover:bg-bg-secondary transition-colors cursor-pointer"
                onClick={() => window.open(doc.url, '_blank')}
              >
                <div className="flex items-center gap-3">
                  <FileCode className="w-5 h-5 text-text-tertiary" />
                  <div>
                    <span className="text-sm text-text-primary block">{doc.name}</span>
                    <span className="text-xs text-text-tertiary">{doc.desc}</span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <code className="text-xs text-text-tertiary">{doc.url}</code>
                  <Button variant="ghost" size="sm">
                    <LinkIcon className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* 学习者画像样本 */}
      <Card padding="md">
        <h2 className="text-lg font-semibold text-text-primary mb-4">学习者画像样本</h2>
        <p className="text-sm text-text-secondary mb-4">
          基于系统中真实学习者数据，展示不同能力等级的画像样本输入输出，用于演示和测试系统功能
        </p>
        {sampleLearners.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {sampleLearners.map((learner) => {
              const level = getSampleLevel(learner.averageAbility)
              return (
                <div
                  key={learner.id}
                  className="p-4 rounded-xl border border-border hover:border-primary/30 hover:bg-primary/5 transition-all cursor-pointer"
                >
                  <Badge variant="info" size="sm" className="mb-3">{level.type}</Badge>
                  <h3 className="font-medium text-text-primary mb-1">{learner.realName}</h3>
                  <p className="text-xs text-text-secondary mb-2">{learner.educationLevel} · {learner.major}</p>
                  <p className="text-xs text-text-tertiary mb-3">{level.description}</p>
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-text-secondary w-16">理论基础</span>
                      <div className="flex-1 h-1.5 bg-gray-100 dark:bg-gray-700 rounded-full">
                        <div
                          className="h-full bg-primary rounded-full transition-all"
                          style={{ width: `${learner.theoreticalFoundation}%` }}
                        />
                      </div>
                      <span className="text-xs font-medium w-8 text-right">{learner.theoreticalFoundation.toFixed(0)}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-text-secondary w-16">编程能力</span>
                      <div className="flex-1 h-1.5 bg-gray-100 dark:bg-gray-700 rounded-full">
                        <div
                          className="h-full bg-success rounded-full transition-all"
                          style={{ width: `${learner.programmingAbility}%` }}
                        />
                      </div>
                      <span className="text-xs font-medium w-8 text-right">{learner.programmingAbility.toFixed(0)}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-text-secondary w-16">综合能力</span>
                      <div className="flex-1 h-1.5 bg-gray-100 dark:bg-gray-700 rounded-full">
                        <div
                          className="h-full bg-info rounded-full transition-all"
                          style={{ width: `${learner.averageAbility}%` }}
                        />
                      </div>
                      <span className="text-xs font-medium w-8 text-right">{learner.averageAbility.toFixed(0)}</span>
                    </div>
                  </div>
                  {learner.knowledgeBlindAreas && learner.knowledgeBlindAreas.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-border/50">
                      <p className="text-xs text-text-tertiary mb-1.5">知识盲区</p>
                      <div className="flex flex-wrap gap-1">
                        {learner.knowledgeBlindAreas.slice(0, 3).map((area) => (
                          <span
                            key={area}
                            className="px-1.5 py-0.5 rounded text-[10px] bg-amber-50 text-amber-600 border border-amber-200"
                          >
                            {area}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        ) : (
          <div className="py-8">
            <EmptyState type="default" title="暂无学习者数据" description="请先添加学习者画像" />
          </div>
        )}
        <div className="mt-4 flex justify-end">
          <Button variant="outline">
            <Cloud className="w-4 h-4 mr-1" />
            下载完整数据
          </Button>
        </div>
      </Card>
    </div>
  )
}
