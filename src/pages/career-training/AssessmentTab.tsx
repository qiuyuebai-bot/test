import { useEffect, useState } from 'react'
import { useShallow } from 'zustand/react/shallow'
import { useStore } from '@/store'
import { trainingApi } from '@/api'
import Card from '@/components/Card'
import Badge from '@/components/Badge'
import Button from '@/components/Button'
import Modal from '@/components/Modal'
import { FormField } from '@/components/FormField'
import Input from '@/components/Input'
import Textarea from '@/components/Textarea'
import LoadingState from '@/components/LoadingState'
import CompetencyRadar, { type RadarItem } from '@/components/career-training/CompetencyRadar'
import type { Position, PositionDetail, AssessmentTemplate, AssessmentRecord, GapAnalysis } from '@/types/training'

const STATUS_LABEL: Record<string, string> = {
  draft: '草稿', in_progress: '进行中', completed: '已完成', expired: '已过期',
}

export default function AssessmentTab() {
  const { positions, assessmentRecords, assessmentRecordsLoading, fetchPositions, fetchAssessmentRecords, learners, currentLearner, fetchLearners, setCurrentLearner, user } = useStore(
    useShallow((s) => ({
      positions: s.positions,
      assessmentRecords: s.assessmentRecords,
      assessmentRecordsLoading: s.assessmentRecordsLoading,
      fetchPositions: s.fetchPositions,
      fetchAssessmentRecords: s.fetchAssessmentRecords,
      learners: s.learners,
      currentLearner: s.currentLearner,
      fetchLearners: s.fetchLearners,
      setCurrentLearner: s.setCurrentLearner,
      user: s.user,
    })),
  )
  const [selectedPosition, setSelectedPosition] = useState<Position | null>(null)
  const [templates, setTemplates] = useState<AssessmentTemplate[]>([])
  const [selectedTemplate, setSelectedTemplate] = useState<AssessmentTemplate | null>(null)
  const [templatesLoading, setTemplatesLoading] = useState(false)
  const [activeRecord, setActiveRecord] = useState<AssessmentRecord | null>(null)
  const [gapAnalysis, setGapAnalysis] = useState<GapAnalysis | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [scoreForm, setScoreForm] = useState<Record<number, { level: number; score: number }>>({})
  const [showCreateTemplate, setShowCreateTemplate] = useState(false)
  const [selectedLearnerId, setSelectedLearnerId] = useState<number | null>(null)
  const canEdit = user?.role === 'admin' || user?.role === 'teacher'
  const learnerId = canEdit ? selectedLearnerId : currentLearner?.id

  useEffect(() => {
    void fetchPositions()
    void fetchLearners()
  }, [fetchPositions, fetchLearners])

  useEffect(() => {
    if (!canEdit || learnerId) {
      void fetchAssessmentRecords(canEdit ? { learnerId: learnerId ?? undefined } : undefined)
    }
  }, [canEdit, learnerId, fetchAssessmentRecords])

  const handleSelectPosition = async (p: Position) => {
    setSelectedPosition(p)
    setSelectedTemplate(null)
    setTemplatesLoading(true)
    try {
      const result = await trainingApi.listAssessmentTemplates({ position_id: p.id })
      setTemplates(result.items)
    } catch (err) {
      console.error('listAssessmentTemplates failed:', err)
    } finally {
      setTemplatesLoading(false)
    }
  }

  const handleStartAssessment = async () => {
    if (!selectedTemplate || !learnerId || !canEdit) return
    try {
      const record = await trainingApi.startAssessment({ template_id: selectedTemplate.id, learner_id: learnerId })
      setActiveRecord(record)
      const configs = selectedTemplate.competencyConfigs ?? selectedTemplate.competency_configs
      const initial: Record<number, { level: number; score: number }> = {}
      configs.forEach((c) => {
        const cid = (c.competencyId ?? c.competency_id) as number
        initial[cid] = { level: 1, score: 20 }
      })
      setScoreForm(initial)
    } catch (err) {
      console.error('startAssessment failed:', err)
    }
  }

  const handleSubmit = async () => {
    if (!activeRecord || !selectedTemplate) return
    setSubmitting(true)
    try {
      const configs = selectedTemplate.competencyConfigs ?? selectedTemplate.competency_configs
      const scores = configs.map((c) => ({
        competency_id: (c.competencyId ?? c.competency_id) as number,
        current_level: scoreForm[(c.competencyId ?? c.competency_id) as number]?.level ?? 1,
        current_score: scoreForm[(c.competencyId ?? c.competency_id) as number]?.score ?? 0,
        assessment_method: (c.assessmentMethod ?? c.assessment_method) as string,
      }))
      await trainingApi.submitAssessment(activeRecord.id, { scores })
      const gap = await trainingApi.getGapAnalysis(activeRecord.id)
      setGapAnalysis(gap)
      setActiveRecord(null)
      void fetchAssessmentRecords(canEdit ? { learnerId: learnerId ?? undefined } : undefined)
    } catch (err) {
      console.error('submitAssessment failed:', err)
    } finally {
      setSubmitting(false)
    }
  }

  const handleViewGap = async (record: AssessmentRecord) => {
    try {
      const gap = await trainingApi.getGapAnalysis(record.id)
      setGapAnalysis(gap)
    } catch (err) {
      console.error('getGapAnalysis failed:', err)
    }
  }

  const radarItems: RadarItem[] = (gapAnalysis?.gaps ?? []).map((g) => ({
    name: (g.competencyName ?? g.competency_name) as string,
    current: g.currentLevel ?? g.current_level,
    required: (g.requiredLevel ?? g.required_level) as number,
  }))

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-medium text-text-primary">能力评估</h2>

      {canEdit && (
        <Card>
          <h3 className="text-sm font-medium text-text-primary mb-2">步骤 1：选择学习者</h3>
          <select
            aria-label="评估学习者"
            value={learnerId ?? ''}
            onChange={(event) => {
              const learner = learners.find((item) => item.id === Number(event.target.value))
              setSelectedLearnerId(learner?.id ?? null)
              setCurrentLearner(learner ?? null)
              setActiveRecord(null)
              setGapAnalysis(null)
            }}
            className="w-full max-w-md h-10 px-3 bg-bg-secondary border border-border rounded-input text-text-primary focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
          >
            <option value="">请选择学习者</option>
            {learners.map((learner) => (
              <option key={learner.id} value={learner.id}>{learner.realName}（#{learner.id}）</option>
            ))}
          </select>
          {!learnerId && <p className="text-xs text-text-tertiary mt-2">选择学习者后，才能开始并录入该学习者的能力评估。</p>}
        </Card>
      )}

      {/* 选岗位 */}
      <Card>
        <h3 className="text-sm font-medium text-text-primary mb-2">步骤 {canEdit ? '2' : '1'}：选择岗位</h3>
        <div className="flex flex-wrap gap-2">
          {positions.map((p) => (
            <button
              key={p.id}
              onClick={() => handleSelectPosition(p)}
              className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
                selectedPosition?.id === p.id
                  ? 'border-primary bg-primary-light text-primary'
                  : 'border-border text-text-secondary hover:border-primary'
              }`}
            >
              {p.name}
            </button>
          ))}
        </div>
      </Card>

      {/* 选模板 */}
      {selectedPosition && (
        <Card>
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-medium text-text-primary">步骤 {canEdit ? '3' : '2'}：选择评估模板</h3>
            {canEdit && (
              <Button size="sm" variant="secondary" onClick={() => setShowCreateTemplate(true)}>新增模板</Button>
            )}
          </div>
          {templatesLoading ? (
            <LoadingState />
          ) : templates.length === 0 ? (
            <p className="text-sm text-text-tertiary">该岗位暂无评估模板</p>
          ) : (
            <div className="space-y-2">
              {templates.map((t) => (
                <div
                  key={t.id}
                  className={`p-3 border rounded-lg cursor-pointer transition-colors ${
                    selectedTemplate?.id === t.id ? 'border-primary bg-primary-light' : 'border-border hover:border-primary'
                  }`}
                  onClick={() => setSelectedTemplate(t)}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-text-primary">{t.name}</span>
                    <Badge variant="default">通过线 {t.passThreshold ?? t.pass_threshold}</Badge>
                  </div>
                  <p className="text-xs text-text-tertiary mt-1">
                    {(t.competencyConfigs ?? t.competency_configs).length} 个胜任力维度
                    {(t.durationMinutes ?? t.duration_minutes) ? ` · ${(t.durationMinutes ?? t.duration_minutes)} 分钟` : ''}
                  </p>
                </div>
              ))}
              {canEdit && selectedTemplate && (
                <Button onClick={handleStartAssessment} className="mt-2" disabled={!learnerId}>
                  开始评估
                </Button>
              )}
              {!canEdit && <p className="text-xs text-text-tertiary mt-2">评估成绩由管理员或教师录入，当前账号只能查看评估结果。</p>}
            </div>
          )}
        </Card>
      )}

      {/* 历史记录 */}
      <Card>
        <h3 className="text-sm font-medium text-text-primary mb-2">历史评估记录</h3>
        {assessmentRecordsLoading ? (
          <LoadingState />
        ) : assessmentRecords.length === 0 ? (
          <p className="text-sm text-text-tertiary">暂无评估记录</p>
        ) : (
          <div className="space-y-2">
            {assessmentRecords.map((r) => (
              <div key={r.id} className="flex items-center justify-between py-2 border-b border-border last:border-0">
                <div>
                  <span className="text-sm font-medium text-text-primary">记录 #{r.id}</span>
                  <Badge variant="default" className="ml-2">{STATUS_LABEL[r.status] ?? r.status}</Badge>
                </div>
                <div className="flex items-center gap-3">
                  {canEdit && (r.learnerId ?? r.learner_id) != null && (
                    <span className="text-xs text-text-tertiary">学习者 #{r.learnerId ?? r.learner_id}</span>
                  )}
                  {(r.overallScore ?? r.overall_score) != null && (
                    <span className="text-sm text-text-secondary">综合分：{r.overallScore ?? r.overall_score}</span>
                  )}
                  {r.status === 'completed' && (
                    <Button variant="ghost" size="sm" onClick={() => handleViewGap(r)}>查看差距</Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* 评估录入 Modal */}
      <Modal
        isOpen={!!activeRecord}
        onClose={() => setActiveRecord(null)}
        maxWidth="max-w-lg"
        className="p-6"
      >
        {activeRecord && selectedTemplate && (
          <div className="space-y-3">
            <h3 className="text-lg font-semibold text-text-primary pr-8">录入评估得分</h3>
            {(selectedTemplate.competencyConfigs ?? selectedTemplate.competency_configs).map((c) => {
              const cid = (c.competencyId ?? c.competency_id) as number
              return (
              <div key={cid} className="grid grid-cols-3 gap-2 items-center">
                <span className="text-sm text-text-primary">胜任力 #{cid}</span>
                <div>
                  <label className="text-xs text-text-tertiary">当前等级(1-5)</label>
                  <input
                    type="number" min={1} max={5}
                    className="w-full px-2 py-1 border border-border rounded text-sm"
                    value={scoreForm[cid]?.level ?? 1}
                    onChange={(e) => setScoreForm({
                      ...scoreForm,
                      [cid]: {
                        level: Math.max(1, Math.min(5, Number(e.target.value) || 1)),
                        score: scoreForm[cid]?.score ?? 0,
                      },
                    })}
                  />
                </div>
                <div>
                  <label className="text-xs text-text-tertiary">得分(0-100)</label>
                  <input
                    type="number" min={0} max={100}
                    className="w-full px-2 py-1 border border-border rounded text-sm"
                    value={scoreForm[cid]?.score ?? 0}
                    onChange={(e) => setScoreForm({
                      ...scoreForm,
                      [cid]: {
                        level: scoreForm[cid]?.level ?? 1,
                        score: Math.max(0, Math.min(100, Number(e.target.value) || 0)),
                      },
                    })}
                  />
                </div>
              </div>
              )
            })}
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="ghost" onClick={() => setActiveRecord(null)}>取消</Button>
              <Button onClick={handleSubmit} loading={submitting}>提交评估</Button>
            </div>
          </div>
        )}
      </Modal>

      {/* 差距分析 Modal */}
      <Modal
        isOpen={!!gapAnalysis}
        onClose={() => setGapAnalysis(null)}
        maxWidth="max-w-2xl"
        className="p-6 max-h-[90vh] overflow-y-auto"
      >
        {gapAnalysis && (
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-text-primary pr-8">差距分析报告</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
              <div><span className="text-text-tertiary">综合分：</span>{gapAnalysis.overallScore ?? gapAnalysis.overall_score ?? '-'}</div>
              <div><span className="text-text-tertiary">综合等级：</span>L{gapAnalysis.overallLevel ?? gapAnalysis.overall_level ?? '-'}</div>
              <div><span className="text-text-tertiary">通过线：</span>{gapAnalysis.passThreshold ?? gapAnalysis.pass_threshold}</div>
              <div>
                <span className="text-text-tertiary">结果：</span>
                <Badge variant={(gapAnalysis.isPassed ?? gapAnalysis.is_passed) ? 'success' : 'error'}>
                  {(gapAnalysis.isPassed ?? gapAnalysis.is_passed) ? '通过' : '未通过'}
                </Badge>
              </div>
            </div>
            {radarItems.length >= 3 && <CompetencyRadar items={radarItems} />}
            <div>
              <h4 className="text-sm font-medium text-text-primary mb-2">差距明细（{gapAnalysis.gapCount ?? gapAnalysis.gap_count} 项未达标）</h4>
              <div className="space-y-1">
                {gapAnalysis.gaps.map((g) => (
                  <div key={(g.competencyId ?? g.competency_id) as number} className="flex items-center justify-between py-2 border-b border-border last:border-0">
                    <span className="text-sm text-text-primary">{g.competencyName ?? g.competency_name}</span>
                    <div className="text-sm">
                      <span className="text-text-secondary">当前 L{g.currentLevel ?? g.current_level ?? '-'}</span>
                      <span className="text-text-tertiary mx-2">→</span>
                      <span className="text-primary">要求 L{g.requiredLevel ?? g.required_level}</span>
                      {g.gap > 0 && <Badge variant="error" className="ml-2">差 {g.gap} 级</Badge>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </Modal>

      {/* 新增评估模板 Modal */}
      {canEdit && showCreateTemplate && selectedPosition && (
        <CreateAssessmentTemplateModal
          position={selectedPosition}
          onClose={() => setShowCreateTemplate(false)}
          onCreated={() => {
            setShowCreateTemplate(false)
            // 复用选岗位逻辑刷新模板列表
            void handleSelectPosition(selectedPosition)
          }}
        />
      )}
    </div>
  )
}

const ASSESSMENT_METHOD_LABEL: Record<string, string> = {
  quiz: '测验', self_report: '自评', interview: '面试', project: '项目',
}

function CreateAssessmentTemplateModal({
  position, onClose, onCreated,
}: {
  position: Position
  onClose: () => void
  onCreated: () => void
}) {
  const [form, setForm] = useState({
    name: '', description: '',
    pass_threshold: '60', duration_minutes: '',
  })
  // 加载岗位详情获取胜任力矩阵
  const [positionDetail, setPositionDetail] = useState<PositionDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  // 选中参与评估的胜任力配置：competency_id -> config
  const [configs, setConfigs] = useState<Record<number, {
    question_count: number; difficulty: number; assessment_method: string
  }>>({})
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    setDetailLoading(true)
    trainingApi.getPosition(position.id)
      .then((detail) => {
        setPositionDetail(detail)
        // 默认全选所有胜任力
        const initial: Record<number, {
          question_count: number; difficulty: number; assessment_method: string
        }> = {}
        detail.competencies.forEach((c) => {
          const cid = (c.competencyId ?? c.competency_id) as number
          initial[cid] = { question_count: 5, difficulty: 3, assessment_method: 'quiz' }
        })
        setConfigs(initial)
      })
      .catch((err) => console.error('getPosition failed:', err))
      .finally(() => setDetailLoading(false))
  }, [position.id])

  const toggleCompetency = (competencyId: number) => {
    setConfigs((prev) => {
      const next = { ...prev }
      if (next[competencyId]) {
        delete next[competencyId]
      } else {
        next[competencyId] = { question_count: 5, difficulty: 3, assessment_method: 'quiz' }
      }
      return next
    })
  }

  const updateConfig = (competencyId: number, field: 'question_count' | 'difficulty' | 'assessment_method', value: string) => {
    setConfigs((prev) => ({
      ...prev,
      [competencyId]: {
        ...prev[competencyId],
        [field]: field === 'assessment_method' ? value : Number(value),
      },
    }))
  }

  const handleSubmit = async () => {
    const competencyConfigs = Object.entries(configs).map(([cid, cfg]) => ({
      competency_id: Number(cid),
      question_count: cfg.question_count,
      difficulty: cfg.difficulty,
      assessment_method: cfg.assessment_method,
    }))
    if (competencyConfigs.length === 0) {
      alert('请至少选择一项胜任力进行评估')
      return
    }
    setSubmitting(true)
    try {
      await trainingApi.createAssessmentTemplate({
        position_id: position.id,
        name: form.name,
        description: form.description || undefined,
        competency_configs: competencyConfigs,
        pass_threshold: Number(form.pass_threshold) || 60,
        duration_minutes: form.duration_minutes ? Number(form.duration_minutes) : undefined,
      })
      onCreated()
    } catch (err) {
      console.error('createAssessmentTemplate failed:', err)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal isOpen onClose={onClose} maxWidth="max-w-2xl" className="p-6 max-h-[90vh] overflow-y-auto">
      <h3 className="text-lg font-semibold text-text-primary mb-1 pr-8">新增评估模板</h3>
      <p className="text-xs text-text-tertiary mb-4">关联岗位：{position.name}（{position.code}）</p>

      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <FormField label="模板名称" required>
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="如 前端工程师L2评估" />
          </FormField>
          <FormField label="通过分数线（0-100）">
            <Input type="number" min={0} max={100} value={form.pass_threshold} onChange={(e) => setForm({ ...form, pass_threshold: e.target.value })} />
          </FormField>
        </div>
        <FormField label="描述">
          <Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={2} placeholder="模板用途说明（可选）" />
        </FormField>
        <FormField label="评估时长（分钟，可选）">
          <Input type="number" min={1} value={form.duration_minutes} onChange={(e) => setForm({ ...form, duration_minutes: e.target.value })} placeholder="留空表示不限时" />
        </FormField>

        <div className="pt-2 border-t border-border">
          <h4 className="text-sm font-medium text-text-primary mb-2">胜任力评估配置</h4>
          {detailLoading ? (
            <LoadingState />
          ) : !positionDetail || positionDetail.competencies.length === 0 ? (
            <p className="text-sm text-text-tertiary py-2">
              该岗位尚未关联胜任力，请先在"岗位与胜任力"中关联胜任力后再创建评估模板。
            </p>
          ) : (
            <div className="space-y-2">
              {positionDetail.competencies.map((c) => {
                const cid = (c.competencyId ?? c.competency_id) as number
                const checked = !!configs[cid]
                return (
                  <div key={cid} className={`p-3 border rounded-lg transition-colors ${checked ? 'border-primary bg-primary-light/30' : 'border-border'}`}>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleCompetency(cid)}
                        className="w-4 h-4 rounded border-border"
                      />
                      <span className="text-sm font-medium text-text-primary flex-1">
                        {c.competencyName ?? c.competency_name}
                      </span>
                      {(c.isMandatory ?? c.is_mandatory) && <Badge variant="info">必修</Badge>}
                      <span className="text-xs text-text-tertiary">要求 L{c.requiredLevel ?? c.required_level}</span>
                    </label>
                    {checked && (
                      <div className="grid grid-cols-3 gap-2 mt-2 ml-6">
                        <div>
                          <label className="text-xs text-text-tertiary">题数</label>
                          <input
                            type="number" min={1}
                            value={configs[cid].question_count}
                            onChange={(e) => updateConfig(cid, 'question_count', e.target.value)}
                            className="w-full h-8 px-2 bg-bg-secondary border border-border rounded-input text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
                          />
                        </div>
                        <div>
                          <label className="text-xs text-text-tertiary">难度(1-5)</label>
                          <input
                            type="number" min={1} max={5}
                            value={configs[cid].difficulty}
                            onChange={(e) => updateConfig(cid, 'difficulty', e.target.value)}
                            className="w-full h-8 px-2 bg-bg-secondary border border-border rounded-input text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
                          />
                        </div>
                        <div>
                          <label className="text-xs text-text-tertiary">评估方式</label>
                          <select
                            value={configs[cid].assessment_method}
                            onChange={(e) => updateConfig(cid, 'assessment_method', e.target.value)}
                            className="w-full h-8 px-2 bg-bg-secondary border border-border rounded-input text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
                          >
                            {Object.entries(ASSESSMENT_METHOD_LABEL).map(([value, label]) => (
                              <option key={value} value={value}>{label}</option>
                            ))}
                          </select>
                        </div>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2 pt-2 border-t border-border">
          <Button variant="ghost" onClick={onClose}>取消</Button>
          <Button
            onClick={handleSubmit}
            loading={submitting}
            disabled={!form.name || Object.keys(configs).length === 0}
          >
            创建
          </Button>
        </div>
      </div>
    </Modal>
  )
}
