import { Link, useNavigate } from 'react-router-dom'
import {
  ArrowRight,
  BookOpen,
  CheckCircle2,
  AlertCircle,
  Clock3,
  FileText,
  Gauge,
  History,
  RefreshCw,
  UserRound,
} from 'lucide-react'
import Badge from '@/components/Badge'
import Button from '@/components/Button'
import Card from '@/components/Card'
import EmptyState from '@/components/EmptyState'
import ErrorState from '@/components/ErrorState'
import { PageSkeleton } from '@/components/Skeleton'
import type { GuidanceAction, GuidanceStage } from '@/api/dashboard'
import type { LearnerDashboardData } from '@/api/dashboard'
import { getGuidanceStageLabel } from '@/features/dashboard/guidance'

interface LearnerDashboardProps {
  data: LearnerDashboardData | null
  loading: boolean
  error: string | null
  onRetry: () => void
  onGuidanceAction: (action: GuidanceAction) => Promise<void>
}

const stageDescriptions: Record<GuidanceStage, string> = {
  profile: '先补齐画像，系统才能为你安排合适的学习内容。',
  diagnosis: '完成一次短诊断，定位当前最值得投入的知识点。',
  resource: '根据诊断结果生成第一份个性化学习资源。',
  guidance: '从推荐主题开始一轮自适应练习。',
  feedback: '查看上一轮反馈，再进入下一个知识点。',
}

const stagePaths: Record<GuidanceStage, string> = {
  profile: '/profile',
  diagnosis: '/guidance',
  resource: '/resources',
  guidance: '/guidance',
  feedback: '/report',
}

const phaseLabels: Record<string, string> = {
  entry: '入门期',
  foundation: '基础期',
  growth: '成长期',
  advanced: '进阶期',
  expert: '专家期',
}

function formatDate(value?: string | null): string {
  if (!value) return '暂无记录'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '暂无记录'
  return date.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })
}

function ModuleError({ label, onRetry }: { label: string; onRetry: () => void }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-warning/30 bg-warning-light px-3 py-2 text-xs text-warning-dark">
      <span>{label}暂时不可用</span>
      <button
        type="button"
        className="inline-flex items-center gap-1 font-medium hover:text-text-primary"
        onClick={onRetry}
      >
        <RefreshCw className="h-3.5 w-3.5" />
        重试
      </button>
    </div>
  )
}

function GuidanceCard({
  data,
  onAction,
}: {
  data: LearnerDashboardData
  onAction: (action: GuidanceAction) => Promise<void>
}) {
  const navigate = useNavigate()
  const stage = data.guidance.stage
  const dismissed = Boolean(data.guidance.dashboardGuidanceDismissedAt)
  const completed = Boolean(data.guidance.onboardingCompletedAt)
  const primaryLabel = getGuidanceStageLabel(stage)
  const primaryPath = stagePaths[stage]

  const handleContinue = async () => {
    if (dismissed) await onAction('resume')
    navigate(primaryPath)
  }

  return (
    <Card padding="none" className="overflow-hidden border-primary/20">
      <div className="grid gap-0 lg:grid-cols-[minmax(0,1fr)_260px]">
        <div className="p-6 md:p-7">
          <div className="mb-4 flex items-center gap-2 text-sm font-medium text-primary">
            {completed ? <CheckCircle2 className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
            <span>{completed ? '本轮引导已完成' : '下一步该做什么'}</span>
          </div>
          <h2 className="text-xl font-semibold text-text-primary">{primaryLabel}</h2>
          <p className="mt-2 max-w-xl text-sm leading-6 text-text-secondary">
            {stageDescriptions[stage]}
          </p>
          <div className="mt-6 flex flex-wrap items-center gap-2">
            <Button onClick={() => void handleContinue()}>
              {dismissed ? '继续引导' : primaryLabel}
              <ArrowRight className="h-4 w-4" />
            </Button>
            {!completed && (
              <Button variant="outline" onClick={() => void onAction('snooze')}>
                稍后处理
              </Button>
            )}
            {!completed && stage === 'feedback' && (
              <Button variant="ghost" onClick={() => void onAction('complete')}>
                标记已完成
              </Button>
            )}
            <Link
              to={primaryPath}
              className="inline-flex h-10 items-center gap-1 rounded-button px-3 text-sm font-medium text-text-secondary hover:bg-bg-secondary hover:text-text-primary"
            >
              查看详情
            </Link>
          </div>
        </div>
        <div className="flex flex-col justify-center gap-3 border-t border-border bg-bg-secondary/50 p-6 lg:border-l lg:border-t-0">
          <p className="text-xs font-medium uppercase tracking-wide text-text-tertiary">引导阶段</p>
          <div className="space-y-2">
            {(['profile', 'diagnosis', 'resource', 'guidance', 'feedback'] as GuidanceStage[]).map(
              (item) => (
                <div key={item} className="flex items-center gap-2">
                  <span
                    className={`h-2 w-2 rounded-full ${item === stage ? 'bg-primary' : 'bg-border'}`}
                  />
                  <span
                    className={`text-xs ${item === stage ? 'font-medium text-text-primary' : 'text-text-tertiary'}`}
                  >
                    {getGuidanceStageLabel(item)}
                  </span>
                </div>
              ),
            )}
          </div>
        </div>
      </div>
    </Card>
  )
}

export default function LearnerDashboard({
  data,
  loading,
  error,
  onRetry,
  onGuidanceAction,
}: LearnerDashboardProps) {
  const navigate = useNavigate()

  if (loading && !data) return <PageSkeleton type="dashboard" />
  if (error && !data) {
    return (
      <ErrorState
        title="学习工作台加载失败"
        description="个人学习数据暂时无法读取，请稍后重试。"
        details={error}
        onRetry={onRetry}
      />
    )
  }
  if (!data)
    return (
      <EmptyState
        title="暂时没有学习数据"
        description="完成画像设置后，学习工作台会显示你的下一步行动。"
      />
    )

  const profile = data.profile
  const summary = data.summary
  const stage = data.guidance.stage
  const progressLabel =
    stage === 'profile' || !summary ? '尚未建立' : `${summary.progress.toFixed(0)}%`
  const hasResourceError = Boolean(data.moduleErrors.resources)
  const hasTaskError = Boolean(data.moduleErrors.tasks)
  const hasFeedbackError = Boolean(data.moduleErrors.feedback)
  const displayName = profile?.realName || '学习者'
  const accuracyLabel =
    summary?.accuracy === null || summary?.accuracy === undefined
      ? '暂无数据'
      : `${summary.accuracy.toFixed(1)}%`
  const phaseLabel = summary
    ? phaseLabels[summary.learningPhase] || summary.learningPhase
    : '待建立'
  const recentFeedback = data.recentFeedback.slice(0, 3)

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex flex-col gap-1">
        <p className="text-sm font-medium text-primary">学习工作台</p>
        <h1 className="text-2xl font-semibold text-text-primary">你好，{displayName}</h1>
        <p className="text-sm text-text-secondary">把今天的学习目标压缩成一个清晰动作。</p>
      </div>

      <GuidanceCard data={data} onAction={onGuidanceAction} />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Card padding="md">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
              <Gauge className="h-5 w-5 text-primary" />
            </div>
            <div>
              <p className="text-xs text-text-tertiary">当前学习阶段</p>
              <p className="mt-1 text-lg font-semibold text-text-primary">{phaseLabel}</p>
            </div>
          </div>
        </Card>
        <Card padding="md">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-info/10">
              <BookOpen className="h-5 w-5 text-info" />
            </div>
            <div>
              <p className="text-xs text-text-tertiary">个人进度</p>
              <p className="mt-1 text-lg font-semibold text-text-primary">{progressLabel}</p>
            </div>
          </div>
        </Card>
        <Card padding="md">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-success/10">
              <CheckCircle2 className="h-5 w-5 text-success" />
            </div>
            <div>
              <p className="text-xs text-text-tertiary">答题准确率</p>
              <p className="mt-1 text-lg font-semibold text-text-primary">{accuracyLabel}</p>
            </div>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1.15fr)_minmax(300px,0.85fr)]">
        <Card padding="none">
          <div className="flex items-center justify-between border-b border-border px-5 py-4">
            <div>
              <h2 className="font-semibold text-text-primary">推荐资源</h2>
              <p className="mt-1 text-xs text-text-tertiary">根据你的画像和最近学习记录整理</p>
            </div>
            <Link
              to="/resources"
              className="text-xs font-medium text-primary hover:text-primary-dark"
            >
              查看全部
            </Link>
          </div>
          <div className="space-y-3 p-4">
            {hasResourceError ? (
              <ModuleError label="推荐资源" onRetry={onRetry} />
            ) : data.recentResources.length > 0 ? (
              data.recentResources.slice(0, 3).map((resource) => (
                <Link
                  key={resource.id}
                  to={`/resources?resourceId=${resource.id}`}
                  className="flex items-start gap-3 rounded-lg p-3 transition-colors hover:bg-bg-secondary"
                >
                  <div className="mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-primary/10">
                    <FileText className="h-4 w-4 text-primary" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-text-primary">
                      {resource.title}
                    </p>
                    <p className="mt-1 text-xs text-text-tertiary">
                      {resource.resourceType} ·{' '}
                      {resource.difficultyLevel ? `难度 ${resource.difficultyLevel}` : '个性化资源'}
                    </p>
                  </div>
                  <ArrowRight className="mt-1 h-4 w-4 flex-shrink-0 text-text-tertiary" />
                </Link>
              ))
            ) : (
              <div className="py-6 text-center text-sm text-text-tertiary">
                还没有资源，完成下一步后会在这里出现。
              </div>
            )}
          </div>
        </Card>

        <Card padding="none">
          <div className="flex items-center justify-between border-b border-border px-5 py-4">
            <div>
              <h2 className="font-semibold text-text-primary">最近反馈</h2>
              <p className="mt-1 text-xs text-text-tertiary">答题后的判断与建议</p>
            </div>
            <History className="h-4 w-4 text-text-tertiary" />
          </div>
          <div className="space-y-3 p-4">
            {hasFeedbackError ? (
              <ModuleError label="最近反馈" onRetry={onRetry} />
            ) : recentFeedback.length > 0 ? (
              recentFeedback.map((feedback) => (
                <div
                  key={feedback.recordId}
                  className="flex items-start gap-3 rounded-lg bg-bg-secondary/60 p-3"
                >
                  <Badge
                    variant={
                      feedback.result === 'correct'
                        ? 'success'
                        : feedback.result === 'wrong'
                          ? 'error'
                          : 'warning'
                    }
                  >
                    {feedback.result === 'correct'
                      ? '正确'
                      : feedback.result === 'wrong'
                        ? '待巩固'
                        : '部分掌握'}
                  </Badge>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-text-primary">
                      {feedback.questionTopic || '未命名知识点'}
                    </p>
                    <p className="mt-1 line-clamp-2 text-xs text-text-secondary">
                      {feedback.feedbackContent || feedback.decisionReason || '暂无文字反馈'}
                    </p>
                  </div>
                  <span className="whitespace-nowrap text-xs text-text-tertiary">
                    {formatDate(feedback.createdAt)}
                  </span>
                </div>
              ))
            ) : (
              <div className="py-6 text-center text-sm text-text-tertiary">
                完成一次导学后，这里会保留最近反馈。
              </div>
            )}
          </div>
        </Card>
      </div>

      <Card padding="none">
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <div>
            <h2 className="font-semibold text-text-primary">我的学习任务</h2>
            <p className="mt-1 text-xs text-text-tertiary">只显示当前学习者的任务</p>
          </div>
          <Clock3 className="h-4 w-4 text-text-tertiary" />
        </div>
        <div className="p-4">
          {hasTaskError ? (
            <ModuleError label="学习任务" onRetry={onRetry} />
          ) : data.currentTasks.length > 0 ? (
            <div className="grid gap-2 md:grid-cols-2">
              {data.currentTasks.slice(0, 4).map((task) => (
                <div
                  key={task.taskId}
                  className="flex items-center gap-3 rounded-lg border border-border px-3 py-3"
                >
                  <div
                    className={`h-2.5 w-2.5 rounded-full ${task.status === 'completed' ? 'bg-success' : task.status === 'failed' ? 'bg-error' : 'bg-warning'}`}
                  />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm text-text-primary">{task.taskName}</p>
                    <p className="mt-1 text-xs text-text-tertiary">
                      {task.flowDescription || task.status} · {task.progress.toFixed(0)}%
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center gap-3 py-6 text-center">
              <UserRound className="h-6 w-6 text-text-tertiary" />
              <p className="text-sm text-text-tertiary">当前没有待处理的个人任务。</p>
              <Button variant="outline" size="sm" onClick={() => navigate('/guidance')}>
                开始导学
              </Button>
            </div>
          )}
        </div>
      </Card>
    </div>
  )
}
