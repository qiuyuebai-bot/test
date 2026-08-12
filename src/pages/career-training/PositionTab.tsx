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
import EmptyState from '@/components/EmptyState'
import LoadingState from '@/components/LoadingState'
import CompetencyRadar, { type RadarItem } from '@/components/career-training/CompetencyRadar'
import type { Position, PositionDetail, Competency } from '@/types/training'

const CATEGORY_LABEL: Record<string, string> = {
  technical: '技术', management: '管理', operation: '运营', design: '设计', other: '其他',
}

export default function PositionTab() {
  const { positions, positionsLoading, fetchPositions, fetchCompetencies, competencies, user } = useStore(
    useShallow((s) => ({
      positions: s.positions,
      positionsLoading: s.positionsLoading,
      fetchPositions: s.fetchPositions,
      fetchCompetencies: s.fetchCompetencies,
      competencies: s.competencies,
      user: s.user,
    })),
  )
  const [selected, setSelected] = useState<PositionDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [showCreatePosition, setShowCreatePosition] = useState(false)
  const [showCreateCompetency, setShowCreateCompetency] = useState(false)
  const [showLinkCompetency, setShowLinkCompetency] = useState(false)
  const canEdit = user?.role === 'admin' || user?.role === 'teacher'

  useEffect(() => {
    void fetchPositions()
    void fetchCompetencies()
  }, [fetchPositions, fetchCompetencies])

  const handleSelectPosition = async (p: Position) => {
    setDetailLoading(true)
    try {
      const detail = await trainingApi.getPosition(p.id)
      setSelected(detail)
    } catch (err) {
      console.error('getPosition failed:', err)
    } finally {
      setDetailLoading(false)
    }
  }

  const radarItems: RadarItem[] = (selected?.competencies ?? []).map((c) => ({
    name: c.competency_name ?? `#${c.competency_id}`,
    required: c.required_level,
  }))

  if (positionsLoading && positions.length === 0) return <LoadingState />
  if (positions.length === 0) {
    return <EmptyState type="default" title="暂无岗位" description="请先创建岗位定义" />
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-medium text-text-primary">岗位列表</h2>
        {canEdit && (
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" onClick={() => setShowCreateCompetency(true)}>新增胜任力</Button>
            <Button size="sm" onClick={() => setShowCreatePosition(true)}>新增岗位</Button>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {positions.map((p) => (
          <Card
            key={p.id}
            className="cursor-pointer hover:border-primary transition-colors"
            onClick={() => handleSelectPosition(p)}
          >
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="font-medium text-text-primary">{p.name}</h3>
                {p.category && <Badge variant="default">{CATEGORY_LABEL[p.category] ?? p.category}</Badge>}
              </div>
              <p className="text-xs text-text-tertiary">编码：<span>{p.code}</span></p>
              {p.level && <p className="text-xs text-text-secondary">层级：{p.level}</p>}
              {p.industry && <p className="text-xs text-text-secondary">行业：{p.industry}</p>}
            </div>
          </Card>
        ))}
      </div>

      {/* 岗位详情 Modal */}
      <Modal
        isOpen={!!selected || detailLoading}
        onClose={() => setSelected(null)}
        maxWidth="max-w-2xl"
        className="p-6 max-h-[90vh] overflow-y-auto"
      >
        {detailLoading ? (
          <LoadingState />
        ) : selected ? (
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-text-primary pr-8">{selected.name}</h3>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div><span className="text-text-tertiary">编码：</span>{selected.code}</div>
              <div><span className="text-text-tertiary">类别：</span>{CATEGORY_LABEL[selected.category ?? ''] ?? selected.category}</div>
              <div><span className="text-text-tertiary">层级：</span>{selected.level ?? '-'}</div>
              <div><span className="text-text-tertiary">行业：</span>{selected.industry ?? '-'}</div>
            </div>
            {selected.description && (
              <div className="text-sm text-text-secondary">{selected.description}</div>
            )}
            <div>
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-sm font-medium text-text-primary">胜任力矩阵</h4>
                {canEdit && (
                  <Button size="sm" variant="ghost" onClick={() => setShowLinkCompetency(true)}>关联胜任力</Button>
                )}
              </div>
              {selected.competencies.length >= 3 && (
                <CompetencyRadar items={radarItems} />
              )}
              <div className="mt-3 space-y-1">
                {selected.competencies.map((c) => (
                  <div key={c.id} className="flex items-center justify-between py-2 border-b border-border last:border-0">
                    <div>
                      <span className="text-sm font-medium text-text-primary">{c.competency_name}</span>
                      {c.is_mandatory && <Badge variant="info" className="ml-2">必修</Badge>}
                    </div>
                    <div className="text-sm text-text-secondary">
                      要求等级：<span className="text-primary font-medium">L{c.required_level}</span>
                      <span className="text-text-tertiary ml-2">(权重 {c.weight})</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : null}
      </Modal>

      {canEdit && showCreatePosition && (
        <CreatePositionModal
          onClose={() => setShowCreatePosition(false)}
          onCreated={() => {
            setShowCreatePosition(false)
            void fetchPositions()
          }}
        />
      )}
      {canEdit && showCreateCompetency && (
        <CreateCompetencyModal
          onClose={() => setShowCreateCompetency(false)}
          onCreated={() => {
            setShowCreateCompetency(false)
            void fetchCompetencies()
          }}
        />
      )}
      {canEdit && showLinkCompetency && selected && (
        <LinkCompetencyModal
          positionId={selected.id}
          existingCompetencyIds={selected.competencies.map((c) => c.competency_id)}
          allCompetencies={competencies}
          onClose={() => setShowLinkCompetency(false)}
          onLinked={async () => {
            // 重新拉取岗位详情以刷新胜任力矩阵
            try {
              const detail = await trainingApi.getPosition(selected.id)
              setSelected(detail)
            } catch (err) {
              console.error('refresh position failed:', err)
            }
            setShowLinkCompetency(false)
          }}
        />
      )}
    </div>
  )
}

function CreatePositionModal({ onClose, onCreated }: {
  onClose: () => void
  onCreated: () => void
}) {
  const [form, setForm] = useState({
    code: '', name: '', category: 'technical', level: 'junior',
    industry: '', description: '',
  })
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async () => {
    setSubmitting(true)
    try {
      await trainingApi.createPosition({
        code: form.code, name: form.name, category: form.category,
        level: form.level, industry: form.industry || undefined,
        description: form.description || undefined,
      })
      onCreated()
    } catch (err) {
      console.error('createPosition failed:', err)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal isOpen onClose={onClose} maxWidth="max-w-lg" className="p-6">
      <h3 className="text-lg font-semibold text-text-primary mb-4 pr-8">新增岗位</h3>
      <div className="space-y-3">
        <FormField label="岗位编码" required>
          <Input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} placeholder="如 FE-001" />
        </FormField>
        <FormField label="岗位名称" required>
          <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </FormField>
        <div className="grid grid-cols-2 gap-3">
          <FormField label="类别">
            <Input value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} />
          </FormField>
          <FormField label="层级">
            <Input value={form.level} onChange={(e) => setForm({ ...form, level: e.target.value })} placeholder="junior/mid/senior/expert" />
          </FormField>
        </div>
        <FormField label="行业">
          <Input value={form.industry} onChange={(e) => setForm({ ...form, industry: e.target.value })} />
        </FormField>
        <FormField label="描述">
          <Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={3} />
        </FormField>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="ghost" onClick={onClose}>取消</Button>
          <Button onClick={handleSubmit} loading={submitting} disabled={!form.code || !form.name}>创建</Button>
        </div>
      </div>
    </Modal>
  )
}

function CreateCompetencyModal({ onClose, onCreated }: {
  onClose: () => void
  onCreated: () => void
}) {
  const [form, setForm] = useState({ code: '', name: '', category: 'technical', description: '' })
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async () => {
    setSubmitting(true)
    try {
      await trainingApi.createCompetency({
        code: form.code, name: form.name, category: form.category,
        description: form.description || undefined,
      })
      onCreated()
    } catch (err) {
      console.error('createCompetency failed:', err)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal isOpen onClose={onClose} maxWidth="max-w-lg" className="p-6">
      <h3 className="text-lg font-semibold text-text-primary mb-4 pr-8">新增胜任力</h3>
      <div className="space-y-3">
        <FormField label="编码" required>
          <Input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} placeholder="如 PROG-PY" />
        </FormField>
        <FormField label="名称" required>
          <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </FormField>
        <FormField label="类别">
          <Input value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} placeholder="technical/soft_skill/domain/engineering" />
        </FormField>
        <FormField label="描述">
          <Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={3} />
        </FormField>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="ghost" onClick={onClose}>取消</Button>
          <Button onClick={handleSubmit} loading={submitting} disabled={!form.code || !form.name}>创建</Button>
        </div>
      </div>
    </Modal>
  )
}

function LinkCompetencyModal({
  positionId, existingCompetencyIds, allCompetencies, onClose, onLinked,
}: {
  positionId: number
  existingCompetencyIds: number[]
  allCompetencies: Competency[]
  onClose: () => void
  onLinked: () => void
}) {
  // 可选胜任力 = 全部 - 已关联
  const available = allCompetencies.filter((c) => !existingCompetencyIds.includes(c.id))
  const [competencyId, setCompetencyId] = useState('')
  const [requiredLevel, setRequiredLevel] = useState('3')
  const [weight, setWeight] = useState('1.0')
  const [isMandatory, setIsMandatory] = useState(true)
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async () => {
    if (!competencyId) return
    setSubmitting(true)
    try {
      await trainingApi.addPositionCompetency(positionId, {
        competency_id: Number(competencyId),
        required_level: Number(requiredLevel) || 3,
        weight: Number(weight) || 1.0,
        is_mandatory: isMandatory,
      })
      onLinked()
    } catch (err) {
      console.error('addPositionCompetency failed:', err)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal isOpen onClose={onClose} maxWidth="max-w-lg" className="p-6">
      <h3 className="text-lg font-semibold text-text-primary mb-4 pr-8">关联胜任力</h3>
      {available.length === 0 ? (
        <div className="text-sm text-text-secondary py-4 text-center">
          所有胜任力已关联，请先在右上角"新增胜任力"创建更多胜任力项。
        </div>
      ) : (
        <div className="space-y-3">
          <FormField label="胜任力" required>
            <select
              value={competencyId}
              onChange={(e) => setCompetencyId(e.target.value)}
              className="w-full h-10 px-3 bg-bg-secondary border border-border rounded-input text-text-primary focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
            >
              <option value="">请选择胜任力</option>
              {available.map((c) => (
                <option key={c.id} value={c.id}>{c.name}（{c.code}）</option>
              ))}
            </select>
          </FormField>
          <div className="grid grid-cols-2 gap-3">
            <FormField label="要求等级（1-5）" required>
              <Input type="number" min={1} max={5} value={requiredLevel} onChange={(e) => setRequiredLevel(e.target.value)} />
            </FormField>
            <FormField label="权重">
              <Input type="number" min={0} step={0.1} value={weight} onChange={(e) => setWeight(e.target.value)} />
            </FormField>
          </div>
          <label className="flex items-center gap-2 text-sm text-text-primary cursor-pointer">
            <input
              type="checkbox"
              checked={isMandatory}
              onChange={(e) => setIsMandatory(e.target.checked)}
              className="w-4 h-4 rounded border-border"
            />
            必修胜任力
          </label>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" onClick={onClose}>取消</Button>
            <Button onClick={handleSubmit} loading={submitting} disabled={!competencyId}>关联</Button>
          </div>
        </div>
      )}
    </Modal>
  )
}
