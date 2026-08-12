import { useEffect, useState } from 'react'
import { useShallow } from 'zustand/react/shallow'
import { useStore } from '@/store'
import { trainingApi } from '@/api'
import Card from '@/components/Card'
import Badge from '@/components/Badge'
import Button from '@/components/Button'
import Modal from '@/components/Modal'
import EmptyState from '@/components/EmptyState'
import LoadingState from '@/components/LoadingState'
import PlanTimeline from '@/components/career-training/PlanTimeline'
import type { TrainingProject, AssessmentRecord, TrainingPlan, TrainingEnrollment } from '@/types/training'

const PROJECT_STATUS_LABEL: Record<string, string> = {
  draft: '草稿', active: '进行中', completed: '已完成', archived: '已归档',
}

export default function LearningPlanTab() {
  const { trainingProjects, trainingProjectsLoading, assessmentRecords, fetchTrainingProjects, fetchAssessmentRecords } = useStore(
    useShallow((s) => ({
      trainingProjects: s.trainingProjects,
      trainingProjectsLoading: s.trainingProjectsLoading,
      assessmentRecords: s.assessmentRecords,
      fetchTrainingProjects: s.fetchTrainingProjects,
      fetchAssessmentRecords: s.fetchAssessmentRecords,
    })),
  )
  const [selectedProject, setSelectedProject] = useState<TrainingProject | null>(null)
  const [enrollment, setEnrollment] = useState<TrainingEnrollment | null>(null)
  const [plan, setPlan] = useState<TrainingPlan | null>(null)
  const [busy, setBusy] = useState(false)
  const [showAssessmentPicker, setShowAssessmentPicker] = useState(false)
  const [selectedAssessmentRecord, setSelectedAssessmentRecord] = useState<AssessmentRecord | null>(null)

  useEffect(() => {
    void fetchTrainingProjects()
    void fetchAssessmentRecords()
  }, [fetchTrainingProjects, fetchAssessmentRecords])

  const handleSelectProject = async (p: TrainingProject) => {
    setSelectedProject(p)
    setEnrollment(null)
    setPlan(null)
    try {
      // 先尝试获取已有计划
      // 由于 enrollment_id 未知，这里通过报名接口获取
      const enroll = await trainingApi.enrollProject(p.id, {})
      setEnrollment(enroll)
      try {
        const existingPlan = await trainingApi.getPlan(enroll.id)
        if (existingPlan) {
          setPlan(existingPlan)
        } else {
          // 无已有计划，尝试用已完成评估记录自动生成
          const completedRecord = assessmentRecords.find((r) => r.status === 'completed')
          if (completedRecord) {
            const newPlan = await trainingApi.generatePlan(enroll.id, {
              assessment_record_id: completedRecord.id,
            })
            setPlan(newPlan)
          }
        }
      } catch {
        // 尚未生成计划
      }
    } catch (err) {
      console.error('enrollProject failed:', err)
    }
  }

  const handleGeneratePlan = async () => {
    if (!enrollment || !selectedAssessmentRecord) return
    setBusy(true)
    try {
      const newPlan = await trainingApi.generatePlan(enrollment.id, {
        assessment_record_id: selectedAssessmentRecord.id,
      })
      setPlan(newPlan)
      setShowAssessmentPicker(false)
    } catch (err) {
      console.error('generatePlan failed:', err)
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
    return <EmptyState type="default" title="暂无培训项目" description="请联系管理员创建培训项目" />
  }

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-medium text-text-primary">学习计划</h2>

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
                {p.enterprise_name && <p className="text-xs text-text-tertiary">{p.enterprise_name}</p>}
                {p.project_type && <p className="text-xs text-text-secondary">类型：{p.project_type}</p>}
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
                  {plan.generated_by_ai && <Badge variant="info">AI 生成</Badge>}
                  <Badge variant="default">进度 {plan.progress.toFixed(0)}%</Badge>
                </div>
              </div>
              <PlanTimeline
                stages={plan.plan_content}
                completedStages={plan.completed_stages}
                onStageClick={(stage) => handleUpdateProgress(stage)}
              />
              <div className="flex justify-end gap-2 mt-4 pt-3 border-t border-border">
                {plan.completed_stages < plan.total_stages && (
                  <Button variant="secondary" size="sm" onClick={() => handleUpdateProgress(plan.completed_stages + 1)}>
                    标记下一阶段完成
                  </Button>
                )}
                {plan.completed_stages >= plan.total_stages && enrollment?.status !== 'completed' && (
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
          {assessmentRecords.filter((r) => r.status === 'completed').map((r) => (
            <div
              key={r.id}
              className={`p-3 border rounded-lg cursor-pointer transition-colors ${
                selectedAssessmentRecord?.id === r.id ? 'border-primary bg-primary-light' : 'border-border hover:border-primary'
              }`}
              onClick={() => setSelectedAssessmentRecord(r)}
            >
              <div className="flex items-center justify-between">
                <span className="text-sm">记录 #{r.id}</span>
                {r.overall_score != null && <span className="text-sm text-text-secondary">综合分：{r.overall_score}</span>}
              </div>
            </div>
          ))}
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" onClick={() => setShowAssessmentPicker(false)}>取消</Button>
            <Button onClick={handleGeneratePlan} loading={busy} disabled={!selectedAssessmentRecord}>
              生成计划
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
