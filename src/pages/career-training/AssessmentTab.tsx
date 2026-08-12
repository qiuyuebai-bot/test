import { useEffect, useState } from 'react'
import { useShallow } from 'zustand/react/shallow'
import { useStore } from '@/store'
import { trainingApi } from '@/api'
import Card from '@/components/Card'
import Badge from '@/components/Badge'
import Button from '@/components/Button'
import Modal from '@/components/Modal'
import LoadingState from '@/components/LoadingState'
import CompetencyRadar, { type RadarItem } from '@/components/career-training/CompetencyRadar'
import type { Position, AssessmentTemplate, AssessmentRecord, GapAnalysis } from '@/types/training'

const STATUS_LABEL: Record<string, string> = {
  draft: '草稿', in_progress: '进行中', completed: '已完成', expired: '已过期',
}

export default function AssessmentTab() {
  const { positions, assessmentRecords, assessmentRecordsLoading, fetchPositions, fetchAssessmentRecords } = useStore(
    useShallow((s) => ({
      positions: s.positions,
      assessmentRecords: s.assessmentRecords,
      assessmentRecordsLoading: s.assessmentRecordsLoading,
      fetchPositions: s.fetchPositions,
      fetchAssessmentRecords: s.fetchAssessmentRecords,
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

  useEffect(() => {
    void fetchPositions()
    void fetchAssessmentRecords()
  }, [fetchPositions, fetchAssessmentRecords])

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
    if (!selectedTemplate) return
    try {
      const record = await trainingApi.startAssessment({ template_id: selectedTemplate.id })
      setActiveRecord(record)
      const initial: Record<number, { level: number; score: number }> = {}
      selectedTemplate.competency_configs.forEach((c) => {
        initial[c.competency_id] = { level: 1, score: 20 }
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
      const scores = selectedTemplate.competency_configs.map((c) => ({
        competency_id: c.competency_id,
        current_level: scoreForm[c.competency_id]?.level ?? 1,
        current_score: scoreForm[c.competency_id]?.score ?? 0,
        assessment_method: c.assessment_method,
      }))
      await trainingApi.submitAssessment(activeRecord.id, { scores })
      const gap = await trainingApi.getGapAnalysis(activeRecord.id)
      setGapAnalysis(gap)
      setActiveRecord(null)
      void fetchAssessmentRecords()
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
    name: g.competency_name,
    current: g.current_level,
    required: g.required_level,
  }))

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-medium text-text-primary">能力评估</h2>

      {/* 步骤 1：选岗位 */}
      <Card>
        <h3 className="text-sm font-medium text-text-primary mb-2">步骤 1：选择岗位</h3>
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

      {/* 步骤 2：选模板 */}
      {selectedPosition && (
        <Card>
          <h3 className="text-sm font-medium text-text-primary mb-2">步骤 2：选择评估模板</h3>
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
                    <Badge variant="default">通过线 {t.pass_threshold}</Badge>
                  </div>
                  <p className="text-xs text-text-tertiary mt-1">
                    {t.competency_configs.length} 个胜任力维度
                    {t.duration_minutes ? ` · ${t.duration_minutes} 分钟` : ''}
                  </p>
                </div>
              ))}
              {selectedTemplate && (
                <Button onClick={handleStartAssessment} className="mt-2">开始评估</Button>
              )}
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
                  {r.overall_score != null && (
                    <span className="text-sm text-text-secondary">综合分：{r.overall_score}</span>
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
            {selectedTemplate.competency_configs.map((c) => (
              <div key={c.competency_id} className="grid grid-cols-3 gap-2 items-center">
                <span className="text-sm text-text-primary">胜任力 #{c.competency_id}</span>
                <div>
                  <label className="text-xs text-text-tertiary">当前等级(1-5)</label>
                  <input
                    type="number" min={1} max={5}
                    className="w-full px-2 py-1 border border-border rounded text-sm"
                    value={scoreForm[c.competency_id]?.level ?? 1}
                    onChange={(e) => setScoreForm({
                      ...scoreForm,
                      [c.competency_id]: {
                        level: Math.max(1, Math.min(5, Number(e.target.value) || 1)),
                        score: scoreForm[c.competency_id]?.score ?? 0,
                      },
                    })}
                  />
                </div>
                <div>
                  <label className="text-xs text-text-tertiary">得分(0-100)</label>
                  <input
                    type="number" min={0} max={100}
                    className="w-full px-2 py-1 border border-border rounded text-sm"
                    value={scoreForm[c.competency_id]?.score ?? 0}
                    onChange={(e) => setScoreForm({
                      ...scoreForm,
                      [c.competency_id]: {
                        level: scoreForm[c.competency_id]?.level ?? 1,
                        score: Math.max(0, Math.min(100, Number(e.target.value) || 0)),
                      },
                    })}
                  />
                </div>
              </div>
            ))}
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
              <div><span className="text-text-tertiary">综合分：</span>{gapAnalysis.overall_score ?? '-'}</div>
              <div><span className="text-text-tertiary">综合等级：</span>L{gapAnalysis.overall_level ?? '-'}</div>
              <div><span className="text-text-tertiary">通过线：</span>{gapAnalysis.pass_threshold}</div>
              <div>
                <span className="text-text-tertiary">结果：</span>
                <Badge variant={gapAnalysis.is_passed ? 'success' : 'error'}>
                  {gapAnalysis.is_passed ? '通过' : '未通过'}
                </Badge>
              </div>
            </div>
            {radarItems.length >= 3 && <CompetencyRadar items={radarItems} />}
            <div>
              <h4 className="text-sm font-medium text-text-primary mb-2">差距明细（{gapAnalysis.gap_count} 项未达标）</h4>
              <div className="space-y-1">
                {gapAnalysis.gaps.map((g) => (
                  <div key={g.competency_id} className="flex items-center justify-between py-2 border-b border-border last:border-0">
                    <span className="text-sm text-text-primary">{g.competency_name}</span>
                    <div className="text-sm">
                      <span className="text-text-secondary">当前 L{g.current_level ?? '-'}</span>
                      <span className="text-text-tertiary mx-2">→</span>
                      <span className="text-primary">要求 L{g.required_level}</span>
                      {g.gap > 0 && <Badge variant="error" className="ml-2">差 {g.gap} 级</Badge>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
