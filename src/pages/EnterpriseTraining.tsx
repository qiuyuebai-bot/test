import { useState, useEffect, useCallback, useRef } from 'react'
import Card from '@/components/Card'
import Modal from '@/components/Modal'
import Badge from '@/components/Badge'
import Button from '@/components/Button'
import LoadingState from '@/components/LoadingState'
import EmptyState from '@/components/EmptyState'
import ErrorState from '@/components/ErrorState'
import { trainingApi, configApi } from '@/api'
import { toast } from '@/components/toastStore'
import type { TrainingTemplate } from '@/api/config'
import type {
  TrainingProject,
  TrainingStats,
  TransferRecord,
  SkillGapItem,
  CreateTrainingData,
} from '@/types'
import {
  Building2,
  Users,
  Target,
  TrendingUp,
  Download,
  Upload,
  FileText,
  ArrowRight,
  ChevronRight,
  UserPlus,
  Search,
  BarChart3,
  GraduationCap,
  Briefcase,
} from 'lucide-react'

const STATUS_LABEL: Record<string, string> = {
  planning: '筹备中',
  ongoing: '进行中',
  completed: '已完成',
  cancelled: '已取消',
}

const STATUS_VARIANT: Record<string, 'info' | 'success' | 'warning' | 'default'> = {
  planning: 'warning',
  ongoing: 'info',
  completed: 'success',
  cancelled: 'default',
}

const DEFAULT_STATS: TrainingStats = {
  companies: 0,
  learners: 0,
  passRate: 0,
  avgScore: 0,
  totalTrainings: 0,
  ongoingTrainings: 0,
  completedTrainings: 0,
}

export default function EnterpriseTraining() {
  const [searchQuery, setSearchQuery] = useState('')
  const [showImport, setShowImport] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [stats, setStats] = useState<TrainingStats>(DEFAULT_STATS)
  const [trainings, setTrainings] = useState<TrainingProject[]>([])
  const [transfers, setTransfers] = useState<TransferRecord[]>([])
  const [skillGaps, setSkillGaps] = useState<SkillGapItem[]>([])

  // 新建培训表单
  const [createForm, setCreateForm] = useState({
    companyName: '',
    trainingName: '',
    industry: '',
    participantCount: 0,
    responsiblePerson: '',
    description: '',
    modules: '',
  })
  const [creating, setCreating] = useState(false)
  const [importFile, setImportFile] = useState<File | null>(null)
  const [statusTemplates, setStatusTemplates] = useState<TrainingTemplate[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    configApi.getOptions().then(opts => setStatusTemplates(opts.trainingTemplates)).catch(() => {})
  }, [])

  const loadAllData = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true)
    } else {
      setLoading(true)
    }
    setError(null)
    try {
      const [statsRes, listRes, transfersRes, gapsRes] = await Promise.all([
        trainingApi.getStats(),
        trainingApi.getList({ page: 1, pageSize: 50, keyword: searchQuery || undefined }),
        trainingApi.getTransfers(),
        trainingApi.getSkillGaps(),
      ])
      setStats(statsRes ?? DEFAULT_STATS)
      setTrainings(listRes?.items ?? [])
      setTransfers(transfersRes ?? [])
      setSkillGaps(gapsRes ?? [])
    } catch (err) {
      const message = err instanceof Error ? err.message : '加载失败'
      setError(message)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [searchQuery])

  useEffect(() => {
    loadAllData()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 搜索防抖：输入停止 500ms 后再查询
  useEffect(() => {
    const t = setTimeout(() => {
      if (searchQuery !== '') {
        trainingApi
          .getList({ page: 1, pageSize: 50, keyword: searchQuery || undefined })
          .then((res) => setTrainings(res?.items ?? []))
          .catch(() => {})
      }
    }, 500)
    return () => clearTimeout(t)
  }, [searchQuery])

  const handleCreate = async () => {
    if (!createForm.companyName || !createForm.trainingName) {
      return
    }
    setCreating(true)
    try {
      const payload: CreateTrainingData = {
        companyName: createForm.companyName,
        trainingName: createForm.trainingName,
        industry: createForm.industry || undefined,
        participantCount: Number(createForm.participantCount) || 0,
        responsiblePerson: createForm.responsiblePerson || undefined,
        description: createForm.description || undefined,
        modules: createForm.modules
          ? createForm.modules.split(/[,，]/).map((s) => s.trim()).filter(Boolean)
          : [],
        trainingType: 'standard',
      }
      await trainingApi.create(payload)
      setShowCreate(false)
      setCreateForm({
        companyName: '',
        trainingName: '',
        industry: '',
        participantCount: 0,
        responsiblePerson: '',
        description: '',
        modules: '',
      })
      await loadAllData(true)
    } catch (err) {
      // 错误已由 request 层 toast 提示
    } finally {
      setCreating(false)
    }
  }

  const handleBatchImport = async () => {
    if (!importFile) {
      toast.warning('请先上传学员名单文件')
      return
    }
    try {
      const text = await importFile.text()
      const lines = text.split('\n').filter(l => l.trim())
      if (lines.length < 2) {
        toast.warning('文件内容为空或格式不正确')
        return
      }
      const headers = lines[0].split(',').map(h => h.trim().toLowerCase())
      const records = lines.slice(1).map(line => {
        const values = line.split(',').map(v => v.trim())
        const obj: Record<string, string> = {}
        headers.forEach((h, i) => { obj[h] = values[i] || '' })
        return {
          companyName: obj['companyname'] || obj['公司名称'] || '',
          trainingName: obj['trainingname'] || obj['培训名称'] || '',
          trainingType: obj['trainingtype'] || obj['培训类型'] || 'standard',
          industry: obj['industry'] || obj['行业'] || '',
          participantCount: parseInt(obj['participantcount'] || obj['参与人数'] || '0', 10) || 0,
          responsiblePerson: obj['responsibleperson'] || obj['负责人'] || '',
        }
      }).filter(r => r.companyName && r.trainingName)

      if (records.length === 0) {
        toast.warning('未解析到有效数据', '请检查文件格式（需包含 companyName 和 trainingName 列）')
        return
      }

      await trainingApi.batchImport(records)
      setShowImport(false)
      setImportFile(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
      await loadAllData(true)
    } catch (err) {
      // 错误已由 request 层 toast 提示
    }
  }

  if (loading) return <LoadingState />

  if (error) {
    return (
      <ErrorState
        type="default"
        onRetry={() => {
          loadAllData()
        }}
      />
    )
  }

  return (
    <div className="space-y-5 animate-fade-in">
      {/* 企业培训数据总览看板 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card padding="md" className="hover:shadow-soft transition-all">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
              <Building2 className="w-5 h-5 text-primary" />
            </div>
            <div>
              <p className="text-xl font-semibold text-text-primary">{stats.companies}</p>
              <p className="text-xs text-text-tertiary">合作企业</p>
            </div>
          </div>
        </Card>
        <Card padding="md" className="hover:shadow-soft transition-all">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-success/10 flex items-center justify-center">
              <Users className="w-5 h-5 text-success" />
            </div>
            <div>
              <p className="text-xl font-semibold text-text-primary">{stats.learners.toLocaleString()}</p>
              <p className="text-xs text-text-tertiary">培训学员</p>
            </div>
          </div>
        </Card>
        <Card padding="md" className="hover:shadow-soft transition-all">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
              <Target className="w-5 h-5 text-primary" />
            </div>
            <div>
              <p className="text-xl font-semibold text-text-primary">{stats.passRate}%</p>
              <p className="text-xs text-text-tertiary">通过率</p>
            </div>
          </div>
        </Card>
        <Card padding="md" className="hover:shadow-soft transition-all">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-info/10 flex items-center justify-center">
              <TrendingUp className="w-5 h-5 text-info" />
            </div>
            <div>
              <p className="text-xl font-semibold text-text-primary">{stats.avgScore}</p>
              <p className="text-xs text-text-tertiary">平均评分</p>
            </div>
          </div>
        </Card>
      </div>

      {/* 操作栏 */}
      <Card padding="md">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold text-text-primary">企业标准化内训</h2>
            <span className="text-xs text-text-tertiary px-2 py-0.5 bg-bg-secondary rounded">批量管理</span>
            {refreshing && (
              <span className="text-xs text-text-tertiary">刷新中...</span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-tertiary" />
              <input
                type="text"
                placeholder="搜索培训项目..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-9 pl-9 pr-4 bg-bg-secondary border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
              />
            </div>
            <Button variant="outline" onClick={() => setShowImport(true)}>
              <Download className="w-4 h-4" />
              批量导入
            </Button>
            <Button variant="primary" onClick={() => setShowCreate(true)}>
              <UserPlus className="w-4 h-4" />
              新建培训
            </Button>
          </div>
        </div>
      </Card>

      {/* 主内容区 */}
      <div className="grid grid-cols-12 gap-4">
        {/* 培训项目列表 */}
        <div className="col-span-12 lg:col-span-8">
          <Card padding="none">
            <div className="p-4 border-b border-border">
              <h3 className="text-sm font-semibold text-text-primary">培训任务管理</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border/50">
                    <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary">培训项目</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary">参与人数</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary">进度</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary">状态</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-text-secondary">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {trainings.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-4 py-8">
                        <EmptyState type="default" title="暂无培训任务" description="点击右上角新建培训开始管理" />
                      </td>
                    </tr>
                  ) : (
                    trainings.map((project, idx) => (
                      <tr key={project.id} className={`border-b border-border/30 transition-colors hover:bg-bg-secondary/30 ${idx % 2 === 1 ? 'bg-bg-secondary/10' : ''}`}>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-3">
                            <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center">
                              <GraduationCap className="w-4 h-4 text-primary" />
                            </div>
                            <div>
                              <p className="text-sm font-medium text-text-primary">{project.trainingName}</p>
                              <p className="text-xs text-text-tertiary">{project.companyName}</p>
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-sm text-text-secondary">{project.participantCount} 人</td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <div className="w-20 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                              <div className="h-full bg-primary rounded-full" style={{ width: `${project.progressPercentage}%` }} />
                            </div>
                            <span className="text-xs text-text-secondary">{project.progressPercentage}%</span>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant={STATUS_VARIANT[project.status] ?? 'default'} size="sm">
                            {STATUS_LABEL[project.status] ?? project.status}
                          </Badge>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button className="p-1.5 rounded-lg hover:bg-bg-secondary transition-colors">
                            <ChevronRight className="w-4 h-4 text-text-tertiary" />
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </Card>

          {/* 培训标准模板 */}
          <Card padding="md" className="mt-4">
            <h4 className="text-sm font-semibold text-text-primary mb-3">培训标准模板</h4>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {statusTemplates.map((t) => (
                <div key={t.title} className="p-3 rounded-xl border border-border hover:border-primary/20 hover:bg-primary/5 transition-all cursor-pointer">
                  <div className="flex items-center gap-2 mb-2">
                    <FileText className="w-4 h-4 text-primary" />
                    <span className="text-sm font-medium text-text-primary">{t.title}</span>
                  </div>
                  <p className="text-xs text-text-tertiary">{t.duration} · {t.courses} 课程</p>
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* 右侧：转岗培训 & 技能差距分析 */}
        <div className="col-span-12 lg:col-span-4 space-y-4">
          {/* 转岗适配 */}
          <Card padding="none">
            <div className="p-4 border-b border-border">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
                  <Briefcase className="w-4 h-4 text-text-secondary" />
                  员工转岗适配
                </h3>
                <Button variant="ghost" size="sm">添加</Button>
              </div>
            </div>
            <div className="p-4 space-y-3">
              {transfers.length === 0 ? (
                <EmptyState.Users />
              ) : (
                transfers.map((t) => (
                <div key={t.id} className="p-3 rounded-xl border border-border bg-bg-secondary/20">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                        <span className="text-xs font-medium text-primary">{t.name.slice(0, 1)}</span>
                      </div>
                      <div>
                        <p className="text-sm font-medium text-text-primary">{t.name}</p>
                        <p className="text-xs text-text-tertiary">{t.company}</p>
                      </div>
                    </div>
                    <Badge variant="warning" size="sm">进行中</Badge>
                  </div>
                  <div className="flex items-center gap-1.5 text-xs mb-2">
                    <span className="px-1.5 py-0.5 bg-bg-secondary rounded text-text-tertiary">{t.from}</span>
                    <ArrowRight className="w-3 h-3 text-text-tertiary" />
                    <span className="px-1.5 py-0.5 bg-primary/10 rounded text-primary">{t.to}</span>
                  </div>
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="text-text-tertiary">完成度</span>
                    <span className="text-text-primary font-medium">{t.completion}%</span>
                  </div>
                  <div className="h-1 bg-gray-100 rounded-full overflow-hidden">
                    <div className="h-full bg-primary rounded-full" style={{ width: `${t.completion}%` }} />
                  </div>
                </div>
              ))
              )}
            </div>
          </Card>

          {/* 技能差距分析 */}
          <Card padding="md">
            <h4 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-text-secondary" />
              转岗技能差距分析
            </h4>
            <div className="space-y-3">
              {skillGaps.length === 0 ? (
                <p className="text-xs text-text-tertiary text-center py-4">暂无技能差距数据</p>
              ) : (
                skillGaps.map((skill) => (
                <div key={skill.skill} className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-text-primary">{skill.skill}</span>
                    <span className="text-xs text-text-tertiary">差距 {skill.gap}%</span>
                  </div>
                  <div className="relative h-1.5 bg-gray-100 rounded-full overflow-hidden">
                    <div className="absolute inset-y-0 left-0 bg-success/40 rounded-full" style={{ width: `${skill.current}%` }} />
                    <div className="absolute inset-y-0 bg-primary rounded-full" style={{ width: `${skill.required}%` }} />
                  </div>
                </div>
              ))
              )}
              <div className="flex items-center justify-between text-xs pt-2 border-t border-border/50">
                <span className="flex items-center gap-1">
                  <div className="w-3 h-1.5 bg-success/40 rounded" />
                  <span className="text-text-tertiary">当前水平</span>
                </span>
                <span className="flex items-center gap-1">
                  <div className="w-3 h-1.5 bg-primary rounded" />
                  <span className="text-text-tertiary">目标水平</span>
                </span>
              </div>
            </div>
          </Card>
        </div>
      </div>

      {/* 新建培训弹窗 */}
      {showCreate && (
        <Modal isOpen={showCreate} onClose={() => setShowCreate(false)} maxWidth="max-w-md" className="p-8">
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-base font-semibold text-text-primary">新建培训任务</h3>
            </div>
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-text-tertiary mb-1">企业名称 <span className="text-error">*</span></label>
                <input
                  type="text"
                  value={createForm.companyName}
                  onChange={(e) => setCreateForm({ ...createForm, companyName: e.target.value })}
                  placeholder="例如：华东重机集团"
                  className="w-full h-9 px-3 bg-bg-secondary border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                />
              </div>
              <div>
                <label className="block text-xs text-text-tertiary mb-1">培训名称 <span className="text-error">*</span></label>
                <input
                  type="text"
                  value={createForm.trainingName}
                  onChange={(e) => setCreateForm({ ...createForm, trainingName: e.target.value })}
                  placeholder="例如：智能制造工艺优化培训"
                  className="w-full h-9 px-3 bg-bg-secondary border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-text-tertiary mb-1">所属行业</label>
                  <input
                    type="text"
                    value={createForm.industry}
                    onChange={(e) => setCreateForm({ ...createForm, industry: e.target.value })}
                    placeholder="technology"
                    className="w-full h-9 px-3 bg-bg-secondary border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                  />
                </div>
                <div>
                  <label className="block text-xs text-text-tertiary mb-1">参与人数</label>
                  <input
                    type="number"
                    value={createForm.participantCount}
                    onChange={(e) => setCreateForm({ ...createForm, participantCount: Number(e.target.value) })}
                    min={0}
                    className="w-full h-9 px-3 bg-bg-secondary border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs text-text-tertiary mb-1">负责人</label>
                <input
                  type="text"
                  value={createForm.responsiblePerson}
                  onChange={(e) => setCreateForm({ ...createForm, responsiblePerson: e.target.value })}
                  placeholder="例如：刘工"
                  className="w-full h-9 px-3 bg-bg-secondary border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                />
              </div>
              <div>
                <label className="block text-xs text-text-tertiary mb-1">培训模块（逗号分隔）</label>
                <input
                  type="text"
                  value={createForm.modules}
                  onChange={(e) => setCreateForm({ ...createForm, modules: e.target.value })}
                  placeholder="例如：工艺基础,设备操作,质量控制"
                  className="w-full h-9 px-3 bg-bg-secondary border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                />
              </div>
              <div>
                <label className="block text-xs text-text-tertiary mb-1">培训描述</label>
                <textarea
                  value={createForm.description}
                  onChange={(e) => setCreateForm({ ...createForm, description: e.target.value })}
                  rows={2}
                  placeholder="培训目标与简介"
                  className="w-full px-3 py-2 bg-bg-secondary border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 resize-none"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <Button variant="outline" onClick={() => setShowCreate(false)}>取消</Button>
              <Button
                variant="primary"
                onClick={handleCreate}
                disabled={creating || !createForm.companyName || !createForm.trainingName}
              >
                {creating ? '创建中...' : '创建培训'}
              </Button>
            </div>
        </Modal>
      )}

      {/* 批量导入弹窗 */}
      {showImport && (
        <Modal isOpen={showImport} onClose={() => setShowImport(false)} maxWidth="max-w-md" className="p-8">
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-base font-semibold text-text-primary">批量导入学员</h3>
            </div>
            <div
              className="border-2 border-dashed border-border rounded-xl p-8 text-center bg-bg-secondary/30 mb-4 cursor-pointer hover:border-primary/50 transition-colors"
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv"
                className="hidden"
                onChange={(e) => setImportFile(e.target.files?.[0] ?? null)}
              />
              <Upload className="w-8 h-8 text-text-tertiary mx-auto mb-2" />
              {importFile ? (
                <p className="text-sm text-primary mb-1">{importFile.name}</p>
              ) : (
                <p className="text-sm text-text-secondary mb-1">点击上传学员名单</p>
              )}
              <p className="text-xs text-text-tertiary">支持 CSV 格式，列：companyName, trainingName, industry, participantCount, responsiblePerson</p>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowImport(false)}>取消</Button>
              <Button variant="primary" onClick={handleBatchImport}>开始导入</Button>
            </div>
        </Modal>
      )}
    </div>
  )
}
