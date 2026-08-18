import { useEffect, useState } from 'react'
import { useShallow } from 'zustand/react/shallow'
import { useStore } from '@/store'
import { trainingApi } from '@/api'
import { toast } from '@/components/toastStore'
import { ApiError } from '@/lib/request'
import { reportError } from '@/lib/sentry'
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
  const { trainingProjects, trainingProjectsLoading, assessmentRecords, fetchTrainingProjects, fetchAssessmentRecords, positions, certifications, fetchPositions, fetchCertifications, learners, currentLearner, fetchLearners, setCurrentLearner, setTrainingContext, clearTrainingContext, user } = useStore(
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
      learners: s.learners,
      currentLearner: s.currentLearner,
      fetchLearners: s.fetchLearners,
      setCurrentLearner: s.setCurrentLearner,
      setTrainingContext: s.setTrainingContext,
      clearTrainingContext: s.clearTrainingContext,
      user: s.user,
    })),
  )
  const [selectedProject, setSelectedProject] = useState<TrainingProject | null>(null)
  const [enrollment, setEnrollment] = useState<TrainingEnrollment | null>(null)
  const [plan, setPlan] = useState<TrainingPlan | null>(null)
  const [busy, setBusy] = useState(false)
  const [showAssessmentPicker, setShowAssessmentPicker] = useState(false)
  const [showCreateProject, setShowCreateProject] = useState(false)
  const [editingProject, setEditingProject] = useState<TrainingProject | null>(null)
  const [showEnrollments, setShowEnrollments] = useState(false)
  const [projectEnrollments, setProjectEnrollments] = useState<TrainingEnrollment[]>([])
  const [enrollmentsLoading, setEnrollmentsLoading] = useState(false)
  const [projectEnrollmentCount, setProjectEnrollmentCount] = useState<number | null>(null)
  const [selectedAssessmentRecord, setSelectedAssessmentRecord] = useState<AssessmentRecord | null>(null)
  const [selectedStageNumber, setSelectedStageNumber] = useState(1)
  const canEdit = user?.role === 'admin' || user?.role === 'teacher'
  const learnerId = currentLearner?.id
  const currentUserId = user?.userId ?? (user as { id?: number } | null)?.id

  useEffect(() => {
    void fetchTrainingProjects()
    void fetchAssessmentRecords()
    void fetchLearners()
    if (canEdit) {
      void fetchPositions()
      void fetchCertifications()
    }
  }, [fetchTrainingProjects, fetchAssessmentRecords, fetchPositions, fetchCertifications, fetchLearners, canEdit])

  const handleSelectProject = async (p: TrainingProject) => {
    setSelectedProject(p)
    setEnrollment(null)
    setPlan(null)
    setSelectedAssessmentRecord(null)
    setSelectedStageNumber(1)
    setProjectEnrollmentCount(null)
    clearTrainingContext()
    let project = p
    if (canEdit) {
      try {
        const detail = await trainingApi.getTrainingProject(p.id)
        project = detail
        setSelectedProject(detail)
        setProjectEnrollmentCount(detail.enrollmentCount ?? detail.enrollment_count ?? null)
      } catch (err) {
        reportError(err, { tags: { area: 'training_plan', action: 'get_project' } })
      }
    }
    try {
      const existingEnrollment = await trainingApi.getEnrollment(project.id, learnerId)
      if (!existingEnrollment) return
      setEnrollment(existingEnrollment)
      try {
        const existingPlan = await trainingApi.getPlan(existingEnrollment.id)
        if (existingPlan) {
          setPlan(existingPlan)
          syncTrainingContext(existingPlan, 1, project, existingEnrollment)
          return
        }
      } catch {
        // 尚未生成计划
      }
    } catch (err) {
      reportError(err, { tags: { area: 'training_plan', action: 'get_enrollment' } })
    }
  }

  const syncTrainingContext = (
    nextPlan: TrainingPlan,
    stageNumber: number,
    project: TrainingProject,
    nextEnrollment: TrainingEnrollment,
  ) => {
    const stages = nextPlan.planContent ?? nextPlan.plan_content ?? []
    const stage = stages.find((item) => item.stage === stageNumber) ?? stages[0]
    if (!stage) return
    setSelectedStageNumber(stage.stage)
    setTrainingContext({
      projectId: project.id,
      enrollmentId: nextEnrollment.id,
      planId: nextPlan.id,
      positionId: project.positionId ?? project.position_id,
      learnerId: nextEnrollment.learnerId ?? nextEnrollment.learner_id,
      assessmentRecordId: nextPlan.assessmentRecordId ?? nextPlan.assessment_record_id,
      stage,
    })
  }

  const handleEnroll = async () => {
    if (!selectedProject) return
    if (canEdit && !learnerId) {
      toast.warning('请先选择学习者', '为他人报名时需要先指定学习者画像')
      return
    }
    setBusy(true)
    try {
      const nextEnrollment = await trainingApi.enrollProject(selectedProject.id, {
        learner_id: learnerId,
      })
      setEnrollment(nextEnrollment)
      toast.success('报名成功', '现在可以选择匹配的评估记录生成计划')
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : '报名失败，请稍后重试'
      toast.error('报名失败', msg)
    } finally {
      setBusy(false)
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
      if (selectedProject && enrollment) syncTrainingContext(newPlan, 1, selectedProject, enrollment)
      setShowAssessmentPicker(false)
      toast.success('计划已生成', '学习计划已根据评估结果生成')
    } catch (err) {
      reportError(err, { tags: { area: 'training_plan', action: 'generate' } })
      const msg = err instanceof ApiError ? err.message : '生成学习计划失败，请稍后重试'
      toast.error('生成失败', msg)
    } finally {
      setBusy(false)
    }
  }

  const handlePublishProject = async () => {
    if (!selectedProject || selectedProject.status !== 'draft') return
    setBusy(true)
    try {
      const published = await trainingApi.updateTrainingProject(selectedProject.id, { status: 'active' })
      setSelectedProject(published)
      await fetchTrainingProjects()
      toast.success('项目已发布', '学习者现在可以报名该培训项目')
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : '发布失败，请稍后重试'
      toast.error('发布失败', msg)
    } finally {
      setBusy(false)
    }
  }

  const handleLoadEnrollments = async () => {
    if (!selectedProject) return
    setEnrollmentsLoading(true)
    try {
      const result = await trainingApi.listProjectEnrollments(selectedProject.id)
      setProjectEnrollments(result.items)
      setProjectEnrollmentCount(result.total)
      setShowEnrollments(true)
    } catch (err) {
      toast.error('获取项目学员失败', err instanceof ApiError ? err.message : '请稍后重试')
    } finally {
      setEnrollmentsLoading(false)
    }
  }

  const handleDeleteProject = async () => {
    if (!selectedProject || !confirm(`确定要删除培训项目"${selectedProject.name}"吗？`)) return
    setBusy(true)
    try {
      const enrollments = await trainingApi.listProjectEnrollments(selectedProject.id)
      if (enrollments.total > 0) {
        if (!confirm(`该项目已有 ${enrollments.total} 名学员报名，是否改为归档？`)) return
        const archived = await trainingApi.updateTrainingProject(selectedProject.id, { status: 'archived' })
        setSelectedProject(archived)
        toast.success('项目已归档', '已有报名记录的项目不会被强制删除')
      } else {
        await trainingApi.deleteTrainingProject(selectedProject.id)
        setSelectedProject(null)
        setEnrollment(null)
        setPlan(null)
        clearTrainingContext()
        toast.success('项目已删除')
      }
      await fetchTrainingProjects()
    } catch (err) {
      toast.error('删除培训项目失败', err instanceof ApiError ? err.message : '请稍后重试')
    } finally {
      setBusy(false)
    }
  }

  const handleUpdateProgress = async (completedStages: number) => {
    if (!plan) return
    try {
      const updated = await trainingApi.updateProgress(plan.id, { completed_stages: completedStages })
      setPlan(updated)
      if (selectedProject && enrollment) syncTrainingContext(updated, Math.min(completedStages + 1, updated.totalStages ?? updated.total_stages), selectedProject, enrollment)
    } catch (err) {
      reportError(err, { tags: { area: 'training_plan', action: 'update_progress' } })
    }
  }

  const handleComplete = async () => {
    if (!enrollment) return
    try {
      const updated = await trainingApi.completeTraining(enrollment.id)
      setEnrollment(updated)
    } catch (err) {
      reportError(err, { tags: { area: 'training_plan', action: 'complete' } })
    }
  }

  const matchingAssessmentRecords = selectedProject && enrollment
    ? assessmentRecords.filter((record) => {
      if (record.status !== 'completed') return false
      const recordPositionId = record.positionId ?? record.position_id
      if (recordPositionId !== (selectedProject.positionId ?? selectedProject.position_id)) return false
      const recordLearnerId = record.learnerId ?? record.learner_id
      const enrollmentLearnerId = enrollment.learnerId ?? enrollment.learner_id
      if (enrollmentLearnerId != null) return recordLearnerId === enrollmentLearnerId
      return recordLearnerId == null && (record.userId ?? record.user_id) === currentUserId
    })
    : []

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
        <div className="flex items-center gap-2">
          {canEdit && learners.length > 0 && (
            <select
              aria-label="当前学习者"
              value={learnerId ?? ''}
              onChange={(event) => {
                const learner = learners.find((item) => item.id === Number(event.target.value))
                if (learner) setCurrentLearner(learner)
              }}
              className="h-9 px-2 border border-border rounded-input bg-bg-secondary text-sm"
            >
              <option value="">选择学习者</option>
              {learners.map((learner) => <option key={learner.id} value={learner.id}>{learner.realName}</option>)}
            </select>
          )}
          {canEdit && <Button size="sm" variant="secondary" onClick={() => setShowCreateProject(true)}>新增培训项目</Button>}
        </div>
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
            <Button variant="ghost" size="sm" onClick={() => { setSelectedProject(null); setEnrollment(null); setPlan(null); setSelectedAssessmentRecord(null); clearTrainingContext() }}>← 返回</Button>
            <h3 className="text-base font-medium text-text-primary">{selectedProject.name}</h3>
            {canEdit && (
              <div className="flex items-center gap-2">
                <Button variant="ghost" size="sm" onClick={() => setEditingProject(selectedProject)}>编辑</Button>
                <Button variant="ghost" size="sm" onClick={() => void handleLoadEnrollments()} loading={enrollmentsLoading}>学员列表</Button>
                {projectEnrollmentCount != null && <span className="text-xs text-text-tertiary">{projectEnrollmentCount} 名学员</span>}
                <Button variant="ghost" size="sm" onClick={() => void handleDeleteProject()} loading={busy} className="text-error hover:text-error-dark">删除</Button>
              </div>
            )}
            {canEdit && selectedProject.status === 'draft' && (
              <Button size="sm" onClick={handlePublishProject} loading={busy}>发布项目</Button>
            )}
          </div>

          {!plan && (
            <Card>
              <div className="text-center py-6">
                {selectedProject.status === 'draft' ? (
                  <>
                    <p className="text-sm text-text-secondary mb-3">该培训项目尚未发布，发布后学习者可报名</p>
                    {canEdit && <Button onClick={handlePublishProject} loading={busy}>发布项目</Button>}
                  </>
                ) : !enrollment ? (
                  <>
                    <p className="text-sm text-text-secondary mb-3">尚未报名该培训项目</p>
                    <Button onClick={handleEnroll} loading={busy} disabled={canEdit && !learnerId}>报名培训项目</Button>
                  </>
                ) : (
                  <>
                    <p className="text-sm text-text-secondary mb-3">已报名，选择同岗位的已完成评估生成学习计划</p>
                    <Button onClick={() => setShowAssessmentPicker(true)}>选择评估记录并生成计划</Button>
                  </>
                )}
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
                onStageClick={(stage) => {
                  setSelectedStageNumber(stage)
                  if (selectedProject && enrollment) syncTrainingContext(plan, stage, selectedProject, enrollment)
                }}
              />
              <div className="flex justify-end gap-2 mt-4 pt-3 border-t border-border">
            {selectedStageNumber === (plan.completedStages ?? plan.completed_stages) + 1 && (plan.completedStages ?? plan.completed_stages) < (plan.totalStages ?? plan.total_stages) && (
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
          {matchingAssessmentRecords.length === 0 ? (
            <p className="text-sm text-text-tertiary py-4 text-center">
              暂无已完成的评估记录。请先到&quot;能力评估&quot;完成一次评估，再来生成学习计划。
            </p>
          ) : (
            matchingAssessmentRecords.map((r) => (
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
              disabled={!selectedAssessmentRecord || matchingAssessmentRecords.length === 0}
              title={!selectedAssessmentRecord ? '请先选择一条评估记录' : undefined}
            >
              生成计划
            </Button>
          </div>
        </div>
      </Modal>

      {/* 新增培训项目 Modal */}
      <Modal
        isOpen={showEnrollments}
        onClose={() => setShowEnrollments(false)}
        maxWidth="max-w-2xl"
        className="p-6"
      >
        <h3 className="text-lg font-semibold text-text-primary mb-4 pr-8">项目学员</h3>
        {projectEnrollments.length === 0 ? (
          <p className="text-sm text-text-tertiary">暂无报名学员</p>
        ) : (
          <div className="space-y-1">
            {projectEnrollments.map((item) => (
              <div key={item.id} className="flex items-center justify-between py-2 border-b border-border last:border-0 text-sm">
                <span>学员 #{item.learnerId ?? item.learner_id ?? item.userId ?? item.user_id}</span>
                <span className="text-text-secondary">{item.status}{item.finalScore != null || item.final_score != null ? ` / 成绩 ${item.finalScore ?? item.final_score}` : ''}</span>
              </div>
            ))}
          </div>
        )}
      </Modal>
      {canEdit && editingProject && (
        <CreateTrainingProjectModal
          project={editingProject}
          positions={positions}
          certifications={certifications}
          onClose={() => setEditingProject(null)}
          onSaved={(updated) => {
            setEditingProject(null)
            setSelectedProject(updated)
            setProjectEnrollmentCount(updated.enrollmentCount ?? updated.enrollment_count ?? projectEnrollmentCount)
            void fetchTrainingProjects()
          }}
        />
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

const PROJECT_TYPE_OPTIONS = [
  { value: 'onboarding', label: '新人入职' },
  { value: 'reskilling', label: '转岗培训' },
  { value: 'upskilling', label: '能力提升' },
  { value: 'certification', label: '认证培训' },
]

function CreateTrainingProjectModal({
  project, positions, certifications, onClose, onCreated, onSaved,
}: {
  project?: TrainingProject
  positions: Position[]
  certifications: Certification[]
  onClose: () => void
  onCreated?: () => void
  onSaved?: (updated: TrainingProject) => void
}) {
  const isEditing = !!project
  const projectType = project?.projectType ?? project?.project_type
  const [form, setForm] = useState(() => ({
    name: project?.name ?? '',
    description: project?.description ?? '',
    position_id: project ? String(project.positionId ?? project.position_id) : '',
    certification_id: project?.certificationId != null
      ? String(project.certificationId)
      : project?.certification_id != null ? String(project.certification_id) : '',
    project_type: projectType === 'onboard' ? 'onboarding'
      : projectType === 'transfer' ? 'reskilling'
        : projectType === 'upskill' ? 'upskilling'
          : projectType === 'compliance' ? 'certification' : projectType ?? 'onboarding',
    enterprise_name: project?.enterpriseName ?? project?.enterprise_name ?? '',
    start_date: project?.startDate ?? project?.start_date ?? '',
    end_date: project?.endDate ?? project?.end_date ?? '',
  }))
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async () => {
    if (!form.name || !form.position_id) return
    setSubmitting(true)
    try {
      const data = {
        name: form.name,
        description: form.description || undefined,
        certification_id: form.certification_id ? Number(form.certification_id) : undefined,
        project_type: form.project_type || undefined,
        enterprise_name: form.enterprise_name || undefined,
        start_date: form.start_date || undefined,
        end_date: form.end_date || undefined,
      }
      if (project) {
        const updated = await trainingApi.updateTrainingProject(project.id, data)
        onSaved?.(updated)
      } else {
        await trainingApi.createTrainingProject({ ...data, position_id: Number(form.position_id) })
        onCreated?.()
      }
    } catch (err) {
      toast.error(isEditing ? '培训项目更新失败' : '培训项目创建失败', err instanceof ApiError ? err.message : '请稍后重试')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal isOpen onClose={onClose} maxWidth="max-w-2xl" className="p-6 max-h-[90vh] overflow-y-auto">
       <h3 className="text-lg font-semibold text-text-primary mb-4 pr-8">{isEditing ? '编辑培训项目' : '新增培训项目'}</h3>
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
              disabled={isEditing}
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
           <Button
             onClick={handleSubmit}
             loading={submitting}
             disabled={!form.name || !form.position_id}
             aria-label={isEditing ? '保存培训项目' : '创建培训项目'}
             title={isEditing ? '保存培训项目' : '创建培训项目'}
           >
             {isEditing ? '保存' : '创建'}
           </Button>
        </div>
      </div>
    </Modal>
  )
}
