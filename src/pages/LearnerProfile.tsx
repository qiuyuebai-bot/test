import { useState, useEffect, useRef } from 'react'
import { useStore } from '@/store'
import type { LearnerProfile } from '@/types'
import { configApi } from '@/api'
import type { DesensitizationRule } from '@/api/config'
import Card from '@/components/Card'
import Modal from '@/components/Modal'
import Badge from '@/components/Badge'
import Button from '@/components/Button'
import { SCORE_EXCELLENT_THRESHOLD, SCORE_GOOD_THRESHOLD } from '@/lib/constants'
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
import LoadingState from '@/components/LoadingState'
import EmptyState from '@/components/EmptyState'
import ErrorState from '@/components/ErrorState'

const educationOptions = [
  { value: '高中', label: '高中' },
  { value: '大专', label: '大专' },
  { value: '本科', label: '本科' },
  { value: '硕士', label: '硕士研究生' },
  { value: '博士', label: '博士研究生' },
]

const learningStyleOptions: { value: 'visual' | 'auditory' | 'reading' | 'kinesthetic'; label: string }[] = [
  { value: 'visual', label: '视觉型' },
  { value: 'auditory', label: '听觉型' },
  { value: 'reading', label: '阅读型' },
  { value: 'kinesthetic', label: '动觉型' },
]

const learningStyleMap: Record<string, string> = {
  visual: '视觉型',
  auditory: '听觉型',
  reading: '阅读型',
  kinesthetic: '动觉型',
}

function getRadarData(learner: LearnerProfile) {
  return [
    { subject: '理论基础', score: learner.theoreticalFoundation || 0 },
    { subject: '编程能力', score: learner.programmingAbility || 0 },
    { subject: '算法设计', score: learner.algorithmDesign || 0 },
    { subject: '系统架构', score: learner.systemArchitecture || 0 },
    { subject: '数据分析', score: learner.dataAnalysis || 0 },
    { subject: '工程实践', score: learner.engineeringPractice || 0 },
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

function RadarChartCard({ data }: { data: Array<{ subject: string; score: number }> }) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <RadarChart cx="50%" cy="50%" outerRadius="70%" data={data}>
        <PolarGrid stroke="#e2e8f0" strokeWidth={1} />
        <PolarAngleAxis
          dataKey="subject"
          tick={{ fill: '#64748b', fontSize: 11, fontWeight: 500 }}
          tickLine={false}
        />
        <PolarRadiusAxis
          angle={30}
          domain={[0, 100]}
          tick={{ fill: '#94a3b8', fontSize: 10 }}
          tickCount={4}
          axisLine={{ stroke: '#e2e8f0' }}
        />
        <Radar
          name="能力评分"
          dataKey="score"
          stroke="#3d5a80"
          fill="#3d5a80"
          fillOpacity={0.15}
          strokeWidth={2}
        />
      </RadarChart>
    </ResponsiveContainer>
  )
}

function SkillTagCloud({ skills }: { skills: string[] }) {
  const colors = ['bg-[#3d5a80]/10 text-[#3d5a80] border-[#3d5a80]/20', 'bg-[#5b8def]/10 text-[#5b8def] border-[#5b8def]/20', 'bg-[#f59e0b]/10 text-[#f59e0b] border-[#f59e0b]/20', 'bg-[#10b981]/10 text-[#10b981] border-[#10b981]/20']
  return (
    <div className="flex flex-wrap gap-2">
      {skills.length === 0 ? (
        <span className="text-xs text-text-tertiary">暂无</span>
      ) : (
        skills.map((skill, index) => (
          <span
            key={skill}
            className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-all hover:shadow-soft ${colors[index % colors.length]}`}
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
}: {
  learner: LearnerProfile
  isSelected: boolean
  onClick: () => void
  onEdit: () => void
  onDelete: () => void
}) {
  const radarData = getRadarData(learner)
  const avgAbility = learner.averageAbility || Math.round(
    (learner.theoreticalFoundation + learner.programmingAbility + learner.algorithmDesign +
      learner.systemArchitecture + learner.dataAnalysis + learner.engineeringPractice) / 6
  ) || 0

  return (
    <Card
      padding="md"
      className={`cursor-pointer transition-all duration-300 hover:shadow-medium hover:-translate-y-0.5 ${isSelected ? 'ring-2 ring-primary/30 border-primary/30' : ''}`}
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
        <div className="flex items-center gap-1">
          <button
            onClick={(e) => { e.stopPropagation(); onEdit() }}
            className="p-2 rounded-lg hover:bg-bg-secondary transition-colors"
          >
            <Edit2 className="w-4 h-4 text-text-tertiary" />
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); onDelete() }}
            className="p-2 rounded-lg hover:bg-red-50 transition-colors"
          >
            <Trash2 className="w-4 h-4 text-red-400" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-4">
        <div>
          <div className="flex items-center gap-1.5 mb-2">
            <Award className="w-3.5 h-3.5 text-text-tertiary" />
            <span className="text-xs text-text-secondary">先验能力底盘</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-500 bg-primary"
                style={{ width: `${avgAbility}%` }}
              />
            </div>
            <span className="text-sm font-semibold text-primary">{avgAbility}</span>
          </div>
        </div>
        <div>
          <div className="flex items-center gap-1.5 mb-2">
            <Target className="w-3.5 h-3.5 text-text-tertiary" />
            <span className="text-xs text-text-secondary">知识盲区</span>
          </div>
          <span className="text-sm font-medium text-amber-500">{learner.knowledgeBlindAreas?.length || 0} 个</span>
        </div>
      </div>

      <div className="mb-4">
        <RadarChartCard data={radarData} />
      </div>

      <div className="pt-3 border-t border-border">
        <div className="flex items-center gap-1.5 mb-2">
          <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
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

function EditModal({
  isOpen,
  onClose,
  learner,
  onSave,
}: {
  isOpen: boolean
  onClose: () => void
  learner?: LearnerProfile
  onSave: (data: Partial<LearnerProfile>) => void
}) {
  const [formData, setFormData] = useState({
    realName: learner?.realName || '',
    educationLevel: educationOptions.find(e => e.value === learner?.educationLevel)?.value || '本科',
    major: learner?.major || '',
    averageAbility: learner?.averageAbility || learner?.theoreticalFoundation || 50,
    theoreticalFoundation: learner?.theoreticalFoundation || 50,
    programmingAbility: learner?.programmingAbility || 50,
    algorithmDesign: learner?.algorithmDesign || 50,
    systemArchitecture: learner?.systemArchitecture || 50,
    dataAnalysis: learner?.dataAnalysis || 50,
    engineeringPractice: learner?.engineeringPractice || 50,
    learningStyle: (learner?.learningStyle as 'visual' | 'auditory' | 'reading' | 'kinesthetic') || 'visual',
    knowledgeBlindAreas: (learner?.knowledgeBlindAreas || []).join(', '),
  })

  useEffect(() => {
    if (isOpen) {
      setFormData({
        realName: learner?.realName || '',
        educationLevel: educationOptions.find(e => e.value === learner?.educationLevel)?.value || '本科',
        major: learner?.major || '',
        averageAbility: learner?.averageAbility || learner?.theoreticalFoundation || 50,
        theoreticalFoundation: learner?.theoreticalFoundation || 50,
        programmingAbility: learner?.programmingAbility || 50,
        algorithmDesign: learner?.algorithmDesign || 50,
        systemArchitecture: learner?.systemArchitecture || 50,
        dataAnalysis: learner?.dataAnalysis || 50,
        engineeringPractice: learner?.engineeringPractice || 50,
        learningStyle: (learner?.learningStyle as 'visual' | 'auditory' | 'reading' | 'kinesthetic') || 'visual',
        knowledgeBlindAreas: (learner?.knowledgeBlindAreas || []).join(', '),
      })
    }
  }, [isOpen, learner])

  if (!isOpen) return null

  const handleSave = () => {
    const blindAreas = formData.knowledgeBlindAreas
      .split(/[,，]/)
      .map(s => s.trim())
      .filter(Boolean)
    const avgScore = Math.round(
      (formData.theoreticalFoundation + formData.programmingAbility + formData.algorithmDesign +
        formData.systemArchitecture + formData.dataAnalysis + formData.engineeringPractice) / 6
    )
    onSave({
      realName: formData.realName,
      educationLevel: formData.educationLevel,
      major: formData.major,
      learningStyle: formData.learningStyle,
      theoreticalFoundation: formData.theoreticalFoundation,
      programmingAbility: formData.programmingAbility,
      algorithmDesign: formData.algorithmDesign,
      systemArchitecture: formData.systemArchitecture,
      dataAnalysis: formData.dataAnalysis,
      engineeringPractice: formData.engineeringPractice,
      averageAbility: avgScore,
      knowledgeBlindAreas: blindAreas,
    })
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} maxWidth="max-w-lg" className="p-8 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-lg font-semibold text-text-primary flex items-center gap-2">
            <Edit2 className="w-5 h-5 text-text-secondary" />
            {learner ? '编辑画像' : '新建画像'}
          </h3>
        </div>

        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-text-primary mb-1.5">姓名</label>
              <input
                type="text"
                value={formData.realName}
                onChange={(e) => setFormData({ ...formData, realName: e.target.value })}
                className="w-full h-10 px-3 bg-bg-secondary border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
                placeholder="请输入姓名"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-text-primary mb-1.5">学历</label>
              <select
                value={formData.educationLevel}
                onChange={(e) => setFormData({ ...formData, educationLevel: e.target.value })}
                className="w-full h-10 px-3 bg-bg-secondary border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
              >
                {educationOptions.map((e) => (
                  <option key={e.value} value={e.value}>{e.label}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-text-primary mb-1.5">专业</label>
            <input
              type="text"
              value={formData.major}
              onChange={(e) => setFormData({ ...formData, major: e.target.value })}
              className="w-full h-10 px-3 bg-bg-secondary border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
              placeholder="请输入专业方向"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-text-primary mb-1.5">学习风格</label>
            <div className="grid grid-cols-4 gap-2">
              {learningStyleOptions.map((s) => (
                <button
                  key={s.value}
                  onClick={() => setFormData({ ...formData, learningStyle: s.value })}
                  className={`p-2.5 rounded-lg border text-sm font-medium transition-all ${
                    formData.learningStyle === s.value
                      ? 'border-primary bg-primary/5 text-primary'
                      : 'border-border text-text-secondary hover:border-primary/30'
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-text-primary mb-2">六维能力评分</label>
            <div className="space-y-3 p-3 bg-bg-secondary/50 rounded-lg">
              {[
                { key: 'theoreticalFoundation', label: '理论基础' },
                { key: 'programmingAbility', label: '编程能力' },
                { key: 'algorithmDesign', label: '算法设计' },
                { key: 'systemArchitecture', label: '系统架构' },
                { key: 'dataAnalysis', label: '数据分析' },
                { key: 'engineeringPractice', label: '工程实践' },
              ].map((dim) => (
                <div key={dim.key}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs text-text-secondary">{dim.label}</span>
                    <span className="text-xs font-semibold text-primary">
                      {formData[dim.key as keyof typeof formData] as number}
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={formData[dim.key as keyof typeof formData] as number}
                    onChange={(e) => setFormData({ ...formData, [dim.key]: Number(e.target.value) })}
                    className="w-full h-1.5 bg-gray-200 rounded-full appearance-none cursor-pointer accent-primary"
                  />
                </div>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-text-primary mb-1.5">知识盲区（逗号分隔）</label>
            <input
              type="text"
              value={formData.knowledgeBlindAreas}
              onChange={(e) => setFormData({ ...formData, knowledgeBlindAreas: e.target.value })}
              className="w-full h-10 px-3 bg-bg-secondary border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
              placeholder="例如：模型蒸馏, 分布式训练, 超参数调优"
            />
          </div>
        </div>

        <div className="flex justify-end gap-3 mt-6">
          <Button variant="outline" onClick={onClose}>取消</Button>
          <Button variant="primary" onClick={handleSave}>
            {learner ? '保存修改' : '创建画像'}
          </Button>
        </div>
    </Modal>
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
  const learners = useStore((s) => s.learners)
  const learnerLoading = useStore((s) => s.learnerLoading)
  const learnersLoading = useStore((s) => s.learnersLoading)
  const pagination = useStore((s) => s.pagination)
  const fetchLearners = useStore((s) => s.fetchLearners)
  const addLearner = useStore((s) => s.addLearner)
  const updateLearner = useStore((s) => s.updateLearner)
  const deleteLearner = useStore((s) => s.deleteLearner)
  const currentLearner = useStore((s) => s.currentLearner)
  const setCurrentLearner = useStore((s) => s.setCurrentLearner)
  const [searchQuery, setSearchQuery] = useState('')
  const [showEditModal, setShowEditModal] = useState(false)
  const [showDesensitization, setShowDesensitization] = useState(false)
  const [editingLearner, setEditingLearner] = useState<LearnerProfile | undefined>()
  const [error, setError] = useState<string | null>(null)
  const [currentPage, setCurrentPage] = useState(1)
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

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

  const handleDelete = async (learner: LearnerProfile) => {
    if (window.confirm(`确定要删除学习者「${learner.realName}」的画像吗？`)) {
      try {
        await deleteLearner(learner.id)
      } catch {
        setError('删除失败，请重试')
      }
    }
  }

  const handleSave = async (data: Partial<LearnerProfile>) => {
    try {
      if (editingLearner) {
        await updateLearner(editingLearner.id, data)
      } else {
        await addLearner({
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
        })
      }
      setShowEditModal(false)
      setEditingLearner(undefined)
    } catch {
      setError(editingLearner ? '更新失败，请重试' : '创建失败，请重试')
    }
  }

  if (loading && learners.length === 0) return <LoadingState.Analyzing />
  if (error) return <ErrorState type="default" onRetry={() => { setError(null); fetchLearners({ page: currentPage, pageSize: pagination.pageSize }) }} />

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
          <h1 className="text-xl font-semibold text-text-primary">学习者画像管理</h1>
          <p className="text-sm text-text-secondary mt-1">录入/读取学习者背景数据，生成标准化用户学情画像</p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline" onClick={() => setShowDesensitization(true)}>
            <Shield className="w-4 h-4" />
            脱敏设置
          </Button>
          <Button variant="primary" onClick={() => { setEditingLearner(undefined); setShowEditModal(true) }}>
            <UserPlus className="w-4 h-4" />
            新建画像
          </Button>
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
                onEdit={() => handleEdit(learner)}
                onDelete={() => handleDelete(learner)}
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
                      <div className="flex-1 h-3 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full bg-primary transition-all duration-500"
                          style={{ width: `${currentAvgAbility}%` }}
                        />
                      </div>
                      <span className="text-lg font-bold text-primary">{currentAvgAbility}</span>
                    </div>
                    <RadarChartCard data={currentRadarData} />
                  </div>

                  <div className="pt-4 border-t border-border">
                    <h4 className="text-sm font-medium text-text-primary mb-3 flex items-center gap-2">
                      <TrendingUp className="w-4 h-4 text-text-secondary" />
                      能力维度详情
                    </h4>
                    <div className="space-y-2">
                      {currentRadarData.map((dim) => (
                        <div key={dim.subject} className="flex items-center justify-between">
                          <span className="text-xs text-text-secondary">{dim.subject}</span>
                          <div className="flex items-center gap-2">
                            <div className="w-24 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                              <div
                                className={`h-full rounded-full ${dim.score >= SCORE_EXCELLENT_THRESHOLD ? 'bg-success' : dim.score >= SCORE_GOOD_THRESHOLD ? 'bg-primary' : 'bg-amber-500'}`}
                                style={{ width: `${dim.score}%` }}
                              />
                            </div>
                            <span className={`text-xs font-semibold w-8 text-right ${dim.score >= SCORE_EXCELLENT_THRESHOLD ? 'text-success' : dim.score >= SCORE_GOOD_THRESHOLD ? 'text-primary' : 'text-amber-500'}`}>
                              {dim.score}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="pt-4 border-t border-border">
                    <h4 className="text-sm font-medium text-text-primary mb-3 flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 text-amber-500" />
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
                    <Button variant="outline" className="flex-1" onClick={() => handleEdit(currentLearner)}>
                      <Edit2 className="w-4 h-4" />
                      编辑
                    </Button>
                    <Button variant="outline" className="text-red-500 hover:bg-red-50 hover:border-red-200" onClick={() => handleDelete(currentLearner)}>
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              </>
            ) : (
              <div className="p-8 text-center">
                <div className="w-14 h-14 rounded-full bg-gray-100 flex items-center justify-center mx-auto mb-3">
                  <GraduationCap className="w-7 h-7 text-text-tertiary" />
                </div>
                <p className="text-text-secondary">选择学习者查看详情</p>
              </div>
            )}
          </Card>
        </div>
      </div>

      <EditModal
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
