import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useStore } from '@/store'
import { useShallow } from 'zustand/react/shallow'
import type { LearnerProfile } from '@/types'
import { configApi } from '@/api'
import type { DesensitizationRule } from '@/api/config'
import Card from '@/components/Card'
import Modal from '@/components/Modal'
import Badge from '@/components/Badge'
import Button from '@/components/Button'
import { SCORE_EXCELLENT_THRESHOLD, SCORE_GOOD_THRESHOLD } from '@/lib/constants'
import { CHART_COLORS } from '@/lib/chartTheme'
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
} from 'recharts'
import {
  UserPlus,
  Edit2,
  Search,
  BookOpen,
  Target,
  Clock,
  Shield,
  Eye,
  EyeOff,
  GraduationCap,
  Award,
  TrendingUp,
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Trash2,
} from 'lucide-react'
import EmptyState from '@/components/EmptyState'
import ErrorState from '@/components/ErrorState'
import { PageSkeleton } from '@/components/Skeleton'
import LearnerProfileWizard from '@/components/LearnerProfileWizard'

const learningStyleMap: Record<string, string> = {
  visual: '视觉型',
  auditory: '听觉型',
  reading: '阅读型',
  kinesthetic: '动觉型',
}

function getRadarData(learner: LearnerProfile) {
  return [
    { dimension: 'theoretical_foundation', subject: '理论基础', score: learner.theoreticalFoundation || 0 },
    { dimension: 'programming_ability', subject: '编程能力', score: learner.programmingAbility || 0 },
    { dimension: 'algorithm_design', subject: '算法设计', score: learner.algorithmDesign || 0 },
    { dimension: 'system_architecture', subject: '系统架构', score: learner.systemArchitecture || 0 },
    { dimension: 'data_analysis', subject: '数据分析', score: learner.dataAnalysis || 0 },
    { dimension: 'engineering_practice', subject: '工程实践', score: learner.engineeringPractice || 0 },
  ]
}

function formatDate(dateStr?: string) {
  if (!dateStr) return '-'
  try {
    const d = new Date(dateStr)
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  } catch {
    return dateStr
  }
}

function RadarChartCard({
  data,
  onDimensionClick,
}: {
  data: Array<{ dimension: string; subject: string; score: number }>
  onDimensionClick?: (dimension: string) => void
}) {
  const handleChartClick = (state: { activePayload?: Array<{ payload?: { dimension?: string } }> }) => {
    const dimension = state.activePayload?.[0]?.payload?.dimension
    if (dimension) onDimensionClick?.(dimension)
  }

  return (
    <ResponsiveContainer width="100%" height={200}>
      <RadarChart cx="50%" cy="50%" outerRadius="70%" data={data} onClick={handleChartClick}>
        <PolarGrid stroke={CHART_COLORS.grid} strokeWidth={1} />
        <PolarAngleAxis
          dataKey="subject"
          tick={{ fill: CHART_COLORS.text, fontSize: 11, fontWeight: 500 }}
          tickLine={false}
        />
        <PolarRadiusAxis
          angle={30}
          domain={[0, 100]}
          tick={{ fill: CHART_COLORS.text, fontSize: 10 }}
          tickCount={4}
          axisLine={{ stroke: CHART_COLORS.grid }}
        />
        <Radar
          name="能力评分"
          dataKey="score"
          stroke={CHART_COLORS.primary}
          fill={CHART_COLORS.primary}
          fillOpacity={0.15}
          strokeWidth={2}
        />
      </RadarChart>
    </ResponsiveContainer>
  )
}

function SkillTagCloud({ skills }: { skills: string[] }) {
  const colors = ['bg-viz-1/10 text-viz-1 border-viz-1/20', 'bg-viz-2/10 text-viz-2 border-viz-2/20', 'bg-viz-3/10 text-viz-3 border-viz-3/20', 'bg-viz-4/10 text-viz-4 border-viz-4/20']
  return (
    <div className="flex flex-wrap gap-2">
      {skills.length === 0 ? (
        <span className="text-xs text-text-tertiary">暂无</span>
      ) : (
        skills.map((skill, index) => (
          <span
            key={skill}
            className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-all hover:shadow-lift ${colors[index % colors.length]}`}
          >
            {skill}
          </span>
        ))
      )}
    </div>
  )
}

function LearnerCard({
  learner,
  isSelected,
  onClick,
  onEdit,
  onDelete,
  onDimensionClick,
}: {
  learner: LearnerProfile
  isSelected: boolean
  onClick: () => void
  onEdit?: () => void
  onDelete?: () => void
  onDimensionClick?: (dimension: string) => void
}) {
  const radarData = getRadarData(learner)
  const avgAbility = learner.averageAbility || Math.round(
    (learner.theoreticalFoundation + learner.programmingAbility + learner.algorithmDesign +
      learner.systemArchitecture + learner.dataAnalysis + learner.engineeringPractice) / 6
  ) || 0

  return (
    <Card
      padding="md"
      className={`cursor-pointer transition-all duration-250 hover:shadow-lift hover:-translate-y-0.5 ${isSelected ? 'ring-2 ring-primary/30 border-primary/30' : ''}`}
      onClick={onClick}
    >
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-xl bg-primary/10 flex items-center justify-center transition-transform hover:scale-105">
            <span className="text-lg font-semibold text-primary">{learner.realName?.slice(0, 1) || '?'}</span>
          </div>
          <div>
            <h3 className="font-semibold text-text-primary">{learner.realName || '未命名'}</h3>
            <p className="text-sm text-text-secondary">{learner.educationLevel || '-'} · {learner.major || '-'}</p>
          </div>
        </div>
        {(onEdit || onDelete) && (
          <div className="flex items-center gap-1">
            {onEdit && (
              <button
                onClick={(e) => { e.stopPropagation(); onEdit() }}
                className="p-2 rounded-lg hover:bg-bg-secondary transition-colors"
                title="编辑画像"
              >
                <Edit2 className="w-4 h-4 text-text-tertiary" />
              </button>
            )}
            {onDelete && (
              <button
                onClick={(e) => { e.stopPropagation(); onDelete() }}
                className="p-2 rounded-lg hover:bg-error-light transition-colors"
                title="删除画像"
              >
                <Trash2 className="w-4 h-4 text-error" />
              </button>
            )}
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4 mb-4">
        <div>
          <div className="flex items-center gap-1.5 mb-2">
            <Award className="w-3.5 h-3.5 text-text-tertiary" />
            <span className="text-xs text-text-secondary">先验能力底盘</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex-1 h-2 bg-bg-tertiary rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-500 bg-primary"
                style={{ width: `${avgAbility}%` }}
              />
            </div>
            <span className="metric-number text-sm font-semibold text-primary">{avgAbility.toFixed(2)}</span>
          </div>
        </div>
        <div>
          <div className="flex items-center gap-1.5 mb-2">
            <Target className="w-3.5 h-3.5 text-text-tertiary" />
            <span className="text-xs text-text-secondary">知识盲区</span>
          </div>
          <span className="text-sm font-medium text-warning">{learner.knowledgeBlindAreas?.length || 0} 个</span>
        </div>
      </div>

      <div className="mb-4">
        <RadarChartCard data={radarData} onDimensionClick={onDimensionClick} />
      </div>

      <div className="pt-3 border-t border-border">
        <div className="flex items-center gap-1.5 mb-2">
          <AlertTriangle className="w-3.5 h-3.5 text-warning" />
          <span className="text-xs text-text-secondary">知识盲区标签云</span>
        </div>
        <SkillTagCloud skills={(learner.knowledgeBlindAreas || []).slice(0, 4)} />
      </div>

      <div className="flex items-center justify-between mt-4 pt-3 border-t border-border text-xs text-text-tertiary">
        <span className="flex items-center gap-1">
          <Clock className="w-3 h-3" />
          {formatDate(learner.createdAt)}
        </span>
        <span className="flex items-center gap-1">
          <BookOpen className="w-3 h-3" />
          {learningStyleMap[learner.learningStyle || 'visual'] || '未评估'}
        </span>
      </div>
    </Card>
  )
}

function DesensitizationPanel({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const [desensitizationRules, setDesensitizationRules] = useState<DesensitizationRule[]>([])

  useEffect(() => {
    configApi.getOptions().then(opts => setDesensitizationRules(opts.desensitizationRules)).catch(() => {})
  }, [])

  if (!isOpen) return null

  return (
    <Modal isOpen={isOpen} onClose={onClose} maxWidth="max-w-xl" className="p-8">
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-lg font-semibold text-text-primary flex items-center gap-2">
            <Shield className="w-5 h-5 text-success" />
            数据脱敏设置
          </h3>
        </div>

        <div className="mb-4 p-3 rounded-lg bg-success/5 border border-success/20">
          <p className="text-sm text-text-secondary">
            所有学习者画像数据均按照《个人信息保护法》及赛事数据合规要求进行脱敏处理，确保隐私安全。
          </p>
        </div>

        <div className="space-y-2">
          {desensitizationRules.map((rule) => (
            <div key={rule.field} className="flex items-center justify-between p-3 rounded-lg bg-bg-secondary/50">
              <div className="flex items-center gap-3">
                <span className="text-sm font-medium text-text-primary">{rule.field}</span>
                <span className="text-xs text-text-tertiary">{rule.rule}</span>
              </div>
              <div className="flex items-center gap-2">
                {rule.enabled ? (
                  <Eye className="w-4 h-4 text-success" />
                ) : (
                  <EyeOff className="w-4 h-4 text-text-tertiary" />
                )}
                <Badge variant={rule.enabled ? 'success' : 'default'} size="sm">
                  {rule.enabled ? '启用' : '禁用'}
                </Badge>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-6 pt-4 border-t border-border">
          <div className="flex items-center gap-2 text-xs text-text-tertiary">
            <Shield className="w-4 h-4" />
            <span>脱敏规则符合赛事数据伦理规范要求</span>
          </div>
        </div>

        <div className="flex justify-end mt-4">
          <Button variant="outline" onClick={onClose}>关闭</Button>
        </div>
    </Modal>
  )
}

function Pagination({
  page,
  total,
  totalPages,
  onPageChange,
}: {
  page: number
  total: number
  totalPages: number
  onPageChange: (page: number) => void
}) {
  if (totalPages <= 1) return null

  const pages: number[] = []
  const maxVisible = 5
  let start = Math.max(1, page - Math.floor(maxVisible / 2))
  const end = Math.min(totalPages, start + maxVisible - 1)
  if (end - start < maxVisible - 1) {
    start = Math.max(1, end - maxVisible + 1)
  }
  for (let i = start; i <= end; i++) {
    pages.push(i)
  }

  return (
    <div className="flex items-center justify-between mt-4 pt-4 border-t border-border">
      <span className="text-sm text-text-secondary">
        共 <span className="font-semibold text-primary">{total}</span> 位学习者，
        第 {page}/{totalPages} 页
      </span>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          className="p-2 rounded-lg border border-border hover:bg-bg-secondary disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>
        {start > 1 && (
          <>
            <button
              onClick={() => onPageChange(1)}
              className="w-9 h-9 rounded-lg border border-border text-sm hover:bg-bg-secondary transition-colors"
            >
              1
            </button>
            {start > 2 && <span className="px-1 text-text-tertiary">...</span>}
          </>
        )}
        {pages.map((p) => (
          <button
            key={p}
            onClick={() => onPageChange(p)}
            className={`w-9 h-9 rounded-lg border text-sm transition-colors ${
              p === page
                ? 'bg-primary border-primary text-white'
                : 'border-border hover:bg-bg-secondary'
            }`}
          >
            {p}
          </button>
        ))}
        {end < totalPages && (
          <>
            {end < totalPages - 1 && <span className="px-1 text-text-tertiary">...</span>}
            <button
              onClick={() => onPageChange(totalPages)}
              className="w-9 h-9 rounded-lg border border-border text-sm hover:bg-bg-secondary transition-colors"
            >
              {totalPages}
            </button>
          </>
        )}
        <button
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
          className="p-2 rounded-lg border border-border hover:bg-bg-secondary disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}

export default function LearnerProfilePage() {
  const navigate = useNavigate()
  const { user, learners, learnerLoading, learnersLoading, learnerError, pagination, currentLearner } = useStore(
    useShallow((s) => ({
      user: s.user,
      learners: s.learners,
      learnerLoading: s.learnerLoading,
      learnersLoading: s.learnersLoading,
      learnerError: s.learnerError,
      pagination: s.pagination,
      currentLearner: s.currentLearner,
    }))
  )
  const { fetchLearners, fetchLearnerById, addLearner, updateLearner, deleteLearner, setCurrentLearner } = useStore(
    useShallow((s) => ({
      fetchLearners: s.fetchLearners,
      fetchLearnerById: s.fetchLearnerById,
      addLearner: s.addLearner,
      updateLearner: s.updateLearner,
      deleteLearner: s.deleteLearner,
      setCurrentLearner: s.setCurrentLearner,
    }))
  )
  const [searchQuery, setSearchQuery] = useState('')
  const [showEditModal, setShowEditModal] = useState(false)
  const [showDesensitization, setShowDesensitization] = useState(false)
  const [editingLearner, setEditingLearner] = useState<LearnerProfile | undefined>()
  const [error, setError] = useState<string | null>(null)
  const [currentPage, setCurrentPage] = useState(1)
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const isAdmin = user?.role === 'admin'
  const canEditLearners = isAdmin || user?.role === 'learner'

  const loading = learnerLoading || learnersLoading

  useEffect(() => {
    fetchLearners({ page: 1, pageSize: 20 })
  }, [fetchLearners])

  useEffect(() => {
    return () => {
      if (searchTimerRef.current) {
        clearTimeout(searchTimerRef.current)
        searchTimerRef.current = null
      }
    }
  }, [])

  useEffect(() => {
    setCurrentPage(pagination.page)
  }, [pagination.page])

  const handlePageChange = (page: number) => {
    setCurrentPage(page)
    fetchLearners({
      page,
      pageSize: pagination.pageSize,
      keyword: searchQuery || undefined,
    })
  }

  const handleSearch = (value: string) => {
    setSearchQuery(value)
    setCurrentPage(1)
    if (searchTimerRef.current) {
      clearTimeout(searchTimerRef.current)
    }
    searchTimerRef.current = setTimeout(() => {
      fetchLearners({
        page: 1,
        pageSize: pagination.pageSize,
        keyword: value || undefined,
      })
    }, 300)
  }

  const handleEdit = (learner: LearnerProfile) => {
    setEditingLearner(learner)
    setShowEditModal(true)
  }

  const handleDimensionClick = (learnerId: number, dimension: string) => {
    navigate(`/guidance?dimension=${encodeURIComponent(dimension)}&learnerId=${learnerId}`)
  }

  const handleDelete = async (learner: LearnerProfile) => {
    if (window.confirm(`确定要删除学习者「${learner.realName}」的画像吗？`)) {
      try {
        await deleteLearner(learner.id)
      } catch {
        setError('删除失败，请重试')
      }
    }
  }

  const handleSave = async (
    data: Partial<LearnerProfile> & { manualAbilityAdjustments?: Record<string, number> },
    options: { close?: boolean } = {},
  ): Promise<LearnerProfile | undefined> => {
    try {
      let savedLearner: LearnerProfile
      if (editingLearner) {
        await updateLearner(editingLearner.id, data)
        savedLearner = await fetchLearnerById(editingLearner.id)
      } else {
        const result = await addLearner({
          realName: data.realName || '',
          educationLevel: data.educationLevel || '本科',
          major: data.major || '',
          learningStyle: data.learningStyle || 'visual',
          theoreticalFoundation: data.theoreticalFoundation || 0,
          programmingAbility: data.programmingAbility || 0,
          algorithmDesign: data.algorithmDesign || 0,
          systemArchitecture: data.systemArchitecture || 0,
          dataAnalysis: data.dataAnalysis || 0,
          engineeringPractice: data.engineeringPractice || 0,
          knowledgeBlindAreas: data.knowledgeBlindAreas || [],
          manualAbilityAdjustments: data.manualAbilityAdjustments,
        })
        savedLearner = await fetchLearnerById(result.id)
      }
      if (options.close !== false) {
        setShowEditModal(false)
        setEditingLearner(undefined)
      } else {
        setEditingLearner(savedLearner)
      }
      return savedLearner
    } catch (err) {
      throw new Error(
        err instanceof Error
          ? err.message
          : editingLearner
            ? '更新失败，请重试'
            : '创建失败，请重试',
      )
    }
  }

  if (loading && learners.length === 0) return <PageSkeleton type="table" />
  if (error) return <ErrorState type="default" onRetry={() => { setError(null); fetchLearners({ page: currentPage, pageSize: pagination.pageSize }) }} />
  if (learnerError && user?.role === 'learner') {
    return (
      <EmptyState
        type="users"
        title="请先完成学习者画像"
        description="完成画像设置后，才能使用导学、资源生成和学情报告。"
        action={<Button variant="outline" onClick={() => navigate('/onboarding/name')}>开始设置</Button>}
      />
    )
  }
  if (learnerError) {
    return <ErrorState type="default" details={learnerError} onRetry={() => { void fetchLearners({ page: currentPage, pageSize: pagination.pageSize }) }} />
  }

  const currentRadarData = currentLearner ? getRadarData(currentLearner) : []
  const currentAvgAbility = currentLearner
    ? (currentLearner.averageAbility || Math.round(
        (currentLearner.theoreticalFoundation + currentLearner.programmingAbility +
          currentLearner.algorithmDesign + currentLearner.systemArchitecture +
          currentLearner.dataAnalysis + currentLearner.engineeringPractice) / 6
      ) || 0)
    : 0

  return (
    <div className="space-y-4 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="hero-anchor text-xl font-semibold text-text-primary">学习者画像管理</h1>
          <p className="text-sm text-text-secondary mt-1">录入/读取学习者背景数据，生成标准化用户学情画像</p>
        </div>
        <div className="flex items-center gap-3">
          {isAdmin && (
            <>
              <Button variant="outline" onClick={() => setShowDesensitization(true)}>
                <Shield className="w-4 h-4" />
                脱敏设置
              </Button>
              <Button variant="primary" onClick={() => { setEditingLearner(undefined); setShowEditModal(true) }}>
                <UserPlus className="w-4 h-4" />
                新建画像
              </Button>
            </>
          )}
        </div>
      </div>

      <Card padding="md">
        <div className="flex items-center gap-4">
          <div className="relative flex-1 max-w-xs">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-tertiary" />
            <input
              type="text"
              placeholder="搜索学习者姓名/专业..."
              value={searchQuery}
              onChange={(e) => handleSearch(e.target.value)}
              className="w-full h-10 pl-10 pr-4 bg-bg-secondary border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
            />
          </div>
          <span className="text-sm text-text-secondary">
            共 <span className="font-semibold text-primary">{pagination.total || learners.length}</span> 位学习者画像
          </span>
        </div>
      </Card>

      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 lg:col-span-8">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {learners.map((learner) => (
              <LearnerCard
                key={learner.id}
                learner={learner}
                isSelected={currentLearner?.id === learner.id}
                onClick={() => setCurrentLearner(learner)}
                onEdit={canEditLearners ? () => handleEdit(learner) : undefined}
                onDelete={isAdmin ? () => handleDelete(learner) : undefined}
                onDimensionClick={(dimension) => handleDimensionClick(learner.id, dimension)}
              />
            ))}
          </div>

          {learners.length === 0 && !loading && <EmptyState.Users />}

          <Pagination
            page={currentPage}
            total={pagination.total}
            totalPages={pagination.totalPages}
            onPageChange={handlePageChange}
          />
        </div>

        <div className="col-span-12 lg:col-span-4">
          <Card padding="none" className="sticky top-4">
            {currentLearner ? (
              <>
                <div className="p-5 border-b border-border bg-primary/5">
                  <div className="flex items-center gap-3">
                    <div className="w-14 h-14 rounded-xl bg-primary flex items-center justify-center">
                      <span className="text-xl font-semibold text-white">{currentLearner.realName?.slice(0, 1) || '?'}</span>
                    </div>
                    <div>
                      <h3 className="text-lg font-semibold text-text-primary">{currentLearner.realName || '未命名'}</h3>
                      <p className="text-sm text-text-secondary">{currentLearner.educationLevel || '-'} · {currentLearner.major || '-'}</p>
                      <Badge variant="info" size="sm" className="mt-1">
                        {learningStyleMap[currentLearner.learningStyle || 'visual'] || '未评估'}
                      </Badge>
                    </div>
                  </div>
                </div>

                <div className="p-5 space-y-5">
                  <div>
                    <h4 className="text-sm font-medium text-text-primary mb-3 flex items-center gap-2">
                      <Award className="w-4 h-4 text-text-secondary" />
                      综合能力评分
                    </h4>
                    <div className="flex items-center gap-3 mb-3">
                      <div className="flex-1 h-3 bg-bg-tertiary rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full bg-primary transition-all duration-500"
                          style={{ width: `${currentAvgAbility}%` }}
                        />
                      </div>
                      <span className="metric-number text-lg font-bold text-primary">{currentAvgAbility.toFixed(2)}</span>
                    </div>
                    <RadarChartCard
                      data={currentRadarData}
                      onDimensionClick={(dimension) => handleDimensionClick(currentLearner.id, dimension)}
                    />
                  </div>

                  <div className="pt-4 border-t border-border">
                    <h4 className="text-sm font-medium text-text-primary mb-3 flex items-center gap-2">
                      <TrendingUp className="w-4 h-4 text-text-secondary" />
                      能力维度详情
                    </h4>
                    <div className="space-y-2">
                      {currentRadarData.map((dim) => (
                        <button
                          key={dim.subject}
                          type="button"
                          onClick={() => handleDimensionClick(currentLearner.id, dim.dimension)}
                          aria-label={`进入${dim.subject}导学练习`}
                          className="group flex w-full items-center justify-between rounded-lg px-2 py-1 text-left transition-colors hover:bg-bg-secondary focus:outline-none focus:ring-2 focus:ring-primary/30"
                        >
                          <span className="text-xs text-text-secondary">{dim.subject}</span>
                          <div className="flex items-center gap-2">
                            <div className="w-24 h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
                              <div
                                className={`h-full rounded-full ${dim.score >= SCORE_EXCELLENT_THRESHOLD ? 'bg-success' : dim.score >= SCORE_GOOD_THRESHOLD ? 'bg-primary' : 'bg-warning'}`}
                                style={{ width: `${dim.score}%` }}
                              />
                            </div>
                            <span className={`text-xs font-semibold w-8 text-right ${dim.score >= SCORE_EXCELLENT_THRESHOLD ? 'text-success' : dim.score >= SCORE_GOOD_THRESHOLD ? 'text-primary' : 'text-warning'}`}>
                              {dim.score}
                            </span>
                            <ChevronRight className="h-3.5 w-3.5 text-text-tertiary transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="pt-4 border-t border-border">
                    <h4 className="text-sm font-medium text-text-primary mb-3 flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 text-warning" />
                      全部知识盲区
                    </h4>
                    <SkillTagCloud skills={currentLearner.knowledgeBlindAreas || []} />
                  </div>

                  {currentLearner.targetIndustry && (
                    <div className="pt-4 border-t border-border">
                      <h4 className="text-sm font-medium text-text-primary mb-2">目标行业</h4>
                      <Badge variant="default">{currentLearner.targetIndustry}</Badge>
                    </div>
                  )}
                </div>

                <div className="p-5 border-t border-border bg-bg-secondary/30">
                  <div className="flex gap-2">
                    {canEditLearners && (
                      <Button variant="outline" className="flex-1" onClick={() => handleEdit(currentLearner)}>
                        <Edit2 className="w-4 h-4" />
                        编辑
                      </Button>
                    )}
                    {isAdmin && (
                      <Button variant="outline" className="text-error hover:bg-error-light hover:border-error/30" onClick={() => handleDelete(currentLearner)}>
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    )}
                  </div>
                </div>
              </>
            ) : (
              <div className="p-8 text-center">
                <div className="w-14 h-14 rounded-full bg-bg-tertiary flex items-center justify-center mx-auto mb-3">
                  <GraduationCap className="w-7 h-7 text-text-tertiary" />
                </div>
                <p className="text-text-secondary">选择学习者查看详情</p>
              </div>
            )}
          </Card>
        </div>
      </div>

      <LearnerProfileWizard
        isOpen={showEditModal}
        onClose={() => { setShowEditModal(false); setEditingLearner(undefined) }}
        learner={editingLearner}
        onSave={handleSave}
      />

      <DesensitizationPanel
        isOpen={showDesensitization}
        onClose={() => setShowDesensitization(false)}
      />
    </div>
  )
}
