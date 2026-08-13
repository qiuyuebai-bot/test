import { useEffect, useState } from 'react'
import { useShallow } from 'zustand/react/shallow'
import { useStore } from '@/store'
import { trainingApi } from '@/api'
import { toast } from '@/components/toastStore'
import { ApiError } from '@/lib/request'
import Card from '@/components/Card'
import Badge from '@/components/Badge'
import Button from '@/components/Button'
import Modal from '@/components/Modal'
import { FormField } from '@/components/FormField'
import Input from '@/components/Input'
import Textarea from '@/components/Textarea'
import EmptyState from '@/components/EmptyState'
import LoadingState from '@/components/LoadingState'
import PlanTimeline from '@/components/career-training/PlanTimeline'
import type { TrainingProject, AssessmentRecord, TrainingPlan, TrainingEnrollment, Position, Certification } from '@/types/training'

const PROJECT_STATUS_LABEL: Record<string, string> = {
  draft: '草稿', active: '进行中', completed: '已完成', archived: '已归档',
}

export default function LearningPlanTab() {
  const { trainingProjects, trainingProjectsLoading, assessmentRecords, fetchTrainingProjects, fetchAssessmentRecords, positions, certifications, fetchPositions, fetchCertifications, user } = useStore(
    useShallow((s) => ({
      trainingProjects: s.trainingProjects,
      trainingProjectsLoading: s.trainingProjectsLoading,
      assessmentRecords: s.assessmentRecords,
      fetchTrainingProjects: s.fetchTrainingProjects,
      fetchAssessmentRecords: s.fetchAssessmentRecords,
      positions: s.positions,
      certifications: s.certifications,
      fetchPositions: s.fetchPositions,
      fetchCertifications: s.fetchCertifications,
      user: s.user,
    })),
  )
  const [selectedProject, setSelectedProject] = useState<TrainingProject | null>(null)
  const [enrollment, setEnrollment] = useState<TrainingEnrollment | null>(null)
  const [plan, setPlan] = useState<TrainingPlan | null>(null)
  const [busy, setBusy] = useState(false)
  const [showAssessmentPicker, setShowAssessmentPicker] = useState(false)
  const [showCreateProject, setShowCreateProject] = useState(false)
  const [selectedAssessmentRecord, setSelectedAssessmentRecord] = useState<AssessmentRecord | null>(null)
  const canEdit = user?.role === 'admin' || user?.role === 'teacher'

  useEffect(() => {
    void fetchTrainingProjects()
    void fetchAssessmentRecords()
    if (canEdit) {
      void fetchPositions()
      void fetchCertifications()
    }
  }, [fetchTrainingProjects, fetchAssessmentRecords, fetchPositions, fetchCertifications, canEdit])

  const handleSelectProject = async (p: TrainingProject) => {
    setSelectedProject(p)
    setEnrollment(null)
    setPlan(null)
    try {
      const enroll = await trainingApi.enrollProject(p.id, {})
      setEnrollment(enroll)
      try {
        const existingPlan = await trainingApi.getPlan(enroll.id)
        if (existingPlan) {
          setPlan(existingPlan)
          return
        }
      } catch {
        // 尚未生成计划
      }
      // 无已有计划，尝试用已完成评估记录自动生成
      const completedRecord = assessmentRecords.find((r) => r.status === 'completed')
      if (completedRecord) {
        try {
          const newPlan = await trainingApi.generatePlan(enroll.id, {
            assessment_record_id: completedRecord.id,
          })
          setPlan(newPlan)
        } catch (err) {
          console.error('auto generatePlan failed:', err)
          // 自动生成失败时静默，用户可手动选择评估记录生成
        }
      }
    } catch (err) {
      console.error('enrollProject failed:', err)
    }
  }

  const handleGeneratePlan = async () => {
    if (!enrollment || !selectedAssessmentRecord) {
      toast.warning('请先选择评估记录', '需要基于一次已完成的评估来生成学习计划')
      return
    }
    setBusy(true)
    try {
      const newPlan = await trainingApi.generatePlan(enrollment.id, {
        assessment_record_id: selectedAssessmentRecord.id,
      })
      setPlan(newPlan)
      setShowAssessmentPicker(false)
      toast.success('计划已生成', '学习计划已根据评估结果生成')
    } catch (err) {
      console.error('generatePlan failed:', err)
      const msg = err instanceof ApiError ? err.message : '生成学习计划失败，请稍后重试'
      toast.error('生成失败', msg)
    } finally {
      setBusy(false)
    }
  }

  const handleUpdateProgress = async (completedStages: number) => {
    if (!plan) return
    try {
      const updated = await trainingApi.updateProgress(plan.id, { completed_stages: completedStages })
      setPlan(updated)
    } catch (err) {
      console.error('updateProgress failed:', err)
    }
  }

  const handleComplete = async () => {
    if (!enrollment) return
    try {
      const updated = await trainingApi.completeTraining(enrollment.id)
      setEnrollment(updated)
    } catch (err) {
      console.error('completeTraining failed:', err)
    }
  }

  if (trainingProjectsLoading && trainingProjects.length === 0) return <LoadingState />
  if (trainingProjects.length === 0) {
    return (
      <div className="space-y-4">
        <EmptyState type="default" title="暂无培训项目" description={canEdit ? '点击下方按钮创建第一个培训项目' : '请联系管理员创建培训项目'} />
        {canEdit && (
          <div className="flex justify-center">
            <Button onClick={() => setShowCreateProject(true)}>新增培训项目</Button>
          </div>
        )}
        {canEdit && showCreateProject && (
          <CreateTrainingProjectModal
            positions={positions}
            certifications={certifications}
            onClose={() => setShowCreateProject(false)}
            onCreated={() => {
              setShowCreateProject(false)
              void fetchTrainingProjects()
            }}
          />
        )}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-medium text-text-primary">学习计划</h2>
        {canEdit && (
          <Button size="sm" variant="secondary" onClick={() => setShowCreateProject(true)}>新增培训项目</Button>
        )}
      </div>

      {/* 项目列表 */}
      {!selectedProject && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {trainingProjects.map((p) => (
            <Card
              key={p.id}
              className="cursor-pointer hover:border-primary transition-colors"
              onClick={() => handleSelectProject(p)}
            >
              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <h3 className="font-medium text-text-primary">{p.name}</h3>
                  <Badge variant="default">{PROJECT_STATUS_LABEL[p.status] ?? p.status}</Badge>
                </div>
                {(p.enterpriseName ?? p.enterprise_name) && <p className="text-xs text-text-tertiary">{p.enterpriseName ?? p.enterprise_name}</p>}
                {(p.projectType ?? p.project_type) && <p className="text-xs text-text-secondary">类型：{p.projectType ?? p.project_type}</p>}
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* 项目详情与计划 */}
      {selectedProject && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <Button variant="ghost" size="sm" onClick={() => { setSelectedProject(null); setPlan(null) }}>← 返回</Button>
            <h3 className="text-base font-medium text-text-primary">{selectedProject.name}</h3>
          </div>

          {!plan && (
            <Card>
              <div className="text-center py-6">
                <p className="text-sm text-text-secondary mb-3">尚未生成学习计划</p>
                <Button onClick={() => setShowAssessmentPicker(true)}>选择评估记录并生成计划</Button>
              </div>
            </Card>
          )}

          {plan && (
            <Card>
              <div className="flex items-center justify-between mb-3">
                <h4 className="text-sm font-medium text-text-primary">学习计划</h4>
                <div className="flex items-center gap-2">
                  {(plan.generatedByAi ?? plan.generated_by_ai) && <Badge variant="info">AI 生成</Badge>}
                  <Badge variant="default">进度 {plan.progress.toFixed(0)}%</Badge>
                </div>
              </div>
              <PlanTimeline
                stages={plan.planContent ?? plan.plan_content}
                completedStages={plan.completedStages ?? plan.completed_stages}
                onStageClick={(stage) => handleUpdateProgress(stage)}
              />
              <div className="flex justify-end gap-2 mt-4 pt-3 border-t border-border">
                {(plan.completedStages ?? plan.completed_stages) < (plan.totalStages ?? plan.total_stages) && (
                  <Button variant="secondary" size="sm" onClick={() => handleUpdateProgress((plan.completedStages ?? plan.completed_stages) + 1)}>
                    标记下一阶段完成
                  </Button>
                )}
                {(plan.completedStages ?? plan.completed_stages) >= (plan.totalStages ?? plan.total_stages) && enrollment?.status !== 'completed' && (
                  <Button size="sm" onClick={handleComplete}>完成培训</Button>
                )}
                {enrollment?.status === 'completed' && (
                  <Badge variant="success">培训已完成</Badge>
                )}
              </div>
            </Card>
          )}
        </div>
      )}

      {/* 评估记录选择 Modal */}
      <Modal
        isOpen={showAssessmentPicker}
        onClose={() => setShowAssessmentPicker(false)}
        maxWidth="max-w-lg"
        className="p-6"
      >
        <h3 className="text-lg font-semibold text-text-primary mb-4 pr-8">选择评估记录</h3>
        <div className="space-y-2">
          {assessmentRecords.filter((r) => r.status === 'completed').length === 0 ? (
            <p className="text-sm text-text-tertiary py-4 text-center">
              暂无已完成的评估记录。请先到"能力评估"完成一次评估，再来生成学习计划。
            </p>
          ) : (
            assessmentRecords.filter((r) => r.status === 'completed').map((r) => (
              <div
                key={r.id}
                className={`p-3 border rounded-lg cursor-pointer transition-colors ${
                  selectedAssessmentRecord?.id === r.id ? 'border-primary bg-primary-light' : 'border-border hover:border-primary'
                }`}
                onClick={() => setSelectedAssessmentRecord(r)}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm">记录 #{r.id}</span>
                  {(r.overallScore ?? r.overall_score) != null && <span className="text-sm text-text-secondary">综合分：{r.overallScore ?? r.overall_score}</span>}
                </div>
              </div>
            ))
          )}
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" onClick={() => setShowAssessmentPicker(false)}>取消</Button>
            <Button
              onClick={handleGeneratePlan}
              loading={busy}
              disabled={!selectedAssessmentRecord || assessmentRecords.filter((r) => r.status === 'completed').length === 0}
              title={!selectedAssessmentRecord ? '请先选择一条评估记录' : undefined}
            >
              生成计划
            </Button>
          </div>
        </div>
      </Modal>

      {/* 新增培训项目 Modal */}
      {canEdit && showCreateProject && (
        <CreateTrainingProjectModal
          positions={positions}
          certifications={certifications}
          onClose={() => setShowCreateProject(false)}
          onCreated={() => {
            setShowCreateProject(false)
            void fetchTrainingProjects()
          }}
        />
      )}
    </div>
  )
}

const PROJECT_TYPE_OPTIONS = [
  { value: 'onboarding', label: '新人入职' },
  { value: 'reskilling', label: '转岗培训' },
  { value: 'upskilling', label: '能力提升' },
  { value: 'certification', label: '认证培训' },
]

function CreateTrainingProjectModal({
  positions, certifications, onClose, onCreated,
}: {
  positions: Position[]
  certifications: Certification[]
  onClose: () => void
  onCreated: () => void
}) {
  const [form, setForm] = useState({
    name: '', description: '',
    position_id: '', certification_id: '',
    project_type: 'onboarding', enterprise_name: '',
    start_date: '', end_date: '',
  })
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async () => {
    if (!form.name || !form.position_id) return
    setSubmitting(true)
    try {
      await trainingApi.createTrainingProject({
        name: form.name,
        description: form.description || undefined,
        position_id: Number(form.position_id),
        certification_id: form.certification_id ? Number(form.certification_id) : undefined,
        project_type: form.project_type || undefined,
        enterprise_name: form.enterprise_name || undefined,
        start_date: form.start_date || undefined,
        end_date: form.end_date || undefined,
      })
      onCreated()
    } catch (err) {
      console.error('createTrainingProject failed:', err)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal isOpen onClose={onClose} maxWidth="max-w-2xl" className="p-6 max-h-[90vh] overflow-y-auto">
      <h3 className="text-lg font-semibold text-text-primary mb-4 pr-8">新增培训项目</h3>
      <div className="space-y-3">
        <FormField label="项目名称" required>
          <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="如 2026年Q1前端工程师入职培训" />
        </FormField>
        <FormField label="描述">
          <Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={2} />
        </FormField>
        <div className="grid grid-cols-2 gap-3">
          <FormField label="关联岗位" required>
            <select
              value={form.position_id}
              onChange={(e) => setForm({ ...form, position_id: e.target.value })}
              className="w-full h-10 px-3 bg-bg-secondary border border-border rounded-input text-text-primary focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
            >
              <option value="">请选择岗位</option>
              {positions.map((p) => (
                <option key={p.id} value={p.id}>{p.name}（{p.code}）</option>
              ))}
            </select>
          </FormField>
          <FormField label="关联认证（可选）">
            <select
              value={form.certification_id}
              onChange={(e) => setForm({ ...form, certification_id: e.target.value })}
              className="w-full h-10 px-3 bg-bg-secondary border border-border rounded-input text-text-primary focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
            >
              <option value="">不关联认证</option>
              {certifications.map((c) => (
                <option key={c.id} value={c.id}>{c.name}（{c.code}）</option>
              ))}
            </select>
          </FormField>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <FormField label="项目类型">
            <select
              value={form.project_type}
              onChange={(e) => setForm({ ...form, project_type: e.target.value })}
              className="w-full h-10 px-3 bg-bg-secondary border border-border rounded-input text-text-primary focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
            >
              {PROJECT_TYPE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </FormField>
          <FormField label="企业名称（可选）">
            <Input value={form.enterprise_name} onChange={(e) => setForm({ ...form, enterprise_name: e.target.value })} />
          </FormField>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <FormField label="开始日期（可选）">
            <Input type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} />
          </FormField>
          <FormField label="结束日期（可选）">
            <Input type="date" value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} />
          </FormField>
        </div>
        <div className="flex justify-end gap-2 pt-2 border-t border-border">
          <Button variant="ghost" onClick={onClose}>取消</Button>
          <Button onClick={handleSubmit} loading={submitting} disabled={!form.name || !form.position_id}>创建</Button>
        </div>
      </div>
    </Modal>
  )
}
