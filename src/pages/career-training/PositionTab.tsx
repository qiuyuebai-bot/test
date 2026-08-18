import { useEffect, useState } from 'react'
import { useShallow } from 'zustand/react/shallow'
import { useStore } from '@/store'
import { trainingApi } from '@/api'
import { ApiError } from '@/lib/request'
import { toast } from '@/components/toastStore'
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
import CompetencyRadar, { type RadarItem } from '@/components/career-training/CompetencyRadar'
import type { Position, PositionDetail, PositionCompetency, Competency } from '@/types/training'

const CATEGORY_LABEL: Record<string, string> = {
  technical: '技术', management: '管理', operation: '运营', design: '设计', other: '其他',
}

const CATEGORY_OPTIONS = Object.entries(CATEGORY_LABEL).map(([value, label]) => ({ value, label }))
const LEVEL_OPTIONS = [
  { value: 'junior', label: '初级' },
  { value: 'mid', label: '中级' },
  { value: 'senior', label: '高级' },
  { value: 'expert', label: '专家' },
]

const selectClassName = 'w-full h-10 px-3 bg-bg-secondary border border-border rounded-input text-text-primary focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary'

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
  const [showCompetencyManager, setShowCompetencyManager] = useState(false)
  const [editingPosition, setEditingPosition] = useState<PositionDetail | null>(null)
  const [editingCompetency, setEditingCompetency] = useState<Competency | null>(null)
  const [editingRequirement, setEditingRequirement] = useState<PositionCompetency | null>(null)
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
      reportError(err, { tags: { area: 'position', action: 'get' } })
    } finally {
      setDetailLoading(false)
    }
  }

  const handleRemoveCompetency = async (positionId: number, competencyId: number) => {
    if (!selected) return
    if (!confirm('确定要移除该胜任力关联吗？')) return
    try {
      await trainingApi.removePositionCompetency(positionId, competencyId)
      const detail = await trainingApi.getPosition(positionId)
      setSelected(detail)
    } catch (err) {
      reportError(err, { tags: { area: 'position', action: 'remove_competency' } })
      toast.error('移除关联失败', err instanceof ApiError ? err.message : '请稍后重试')
    }
  }

  const handleDeletePosition = async (positionId: number) => {
    if (!confirm(`确定要删除岗位"${selected?.name}"吗？此操作不可撤销。`)) return
    try {
      await trainingApi.deletePosition(positionId)
      setSelected(null)
      void fetchPositions()
    } catch (err) {
      reportError(err, { tags: { area: 'position', action: 'delete' } })
      toast.error('删除岗位失败', err instanceof ApiError ? err.message : '请稍后重试')
    }
  }

  const radarItems: RadarItem[] = (selected?.competencies ?? []).map((c) => ({
    name: (c.competencyName ?? c.competency_name) ?? `#${c.competencyId ?? c.competency_id}`,
    required: c.requiredLevel ?? c.required_level ?? 0,
  }))

  if (positionsLoading && positions.length === 0) return <LoadingState />

  return (
    <div className="space-y-4">
      {positions.length === 0 ? (
        <EmptyState
          type="default"
          title="暂无岗位"
          description="请先创建岗位定义"
          action={canEdit ? (
            <div className="flex gap-2">
              <Button variant="secondary" size="sm" onClick={() => setShowCompetencyManager(true)}>胜任力管理</Button>
              <Button variant="secondary" size="sm" onClick={() => setShowCreateCompetency(true)}>新增胜任力</Button>
              <Button size="sm" onClick={() => setShowCreatePosition(true)}>新增岗位</Button>
            </div>
          ) : undefined}
        />
      ) : (
        <>
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-medium text-text-primary">岗位列表</h2>
            {canEdit && (
              <div className="flex gap-2">
                <Button variant="secondary" size="sm" onClick={() => setShowCompetencyManager(true)}>胜任力管理</Button>
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
        </>
      )}

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
             {canEdit && (
               <Button size="sm" variant="secondary" onClick={() => setEditingPosition(selected)}>编辑岗位</Button>
             )}
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
                      <span className="text-sm font-medium text-text-primary">{c.competencyName ?? c.competency_name}</span>
                      {(c.isMandatory ?? c.is_mandatory) && <Badge variant="info" className="ml-2">必修</Badge>}
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="text-sm text-text-secondary">
                        要求等级：<span className="text-primary font-medium">L{c.requiredLevel ?? c.required_level}</span>
                        <span className="text-text-tertiary ml-2">(权重 {c.weight})</span>
                      </div>
                      {canEdit && (
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => setEditingRequirement(c)}
                            className="text-xs text-primary hover:text-primary-hover transition-colors"
                          >
                            编辑
                          </button>
                          <button
                            onClick={() => void handleRemoveCompetency(selected.id, (c.competencyId ?? c.competency_id) as number)}
                            className="text-xs text-error hover:text-error-dark transition-colors"
                          >
                            移除
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {canEdit && (
              <div className="flex justify-end pt-4 border-t border-border">
                <Button variant="ghost" onClick={() => void handleDeletePosition(selected.id)}>删除岗位</Button>
              </div>
            )}
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
          existingCompetencyIds={selected.competencies.map((c) => (c.competencyId ?? c.competency_id) as number)}
          allCompetencies={competencies}
          onClose={() => setShowLinkCompetency(false)}
          onLinked={async () => {
            // 重新拉取岗位详情以刷新胜任力矩阵
            try {
              const detail = await trainingApi.getPosition(selected.id)
              setSelected(detail)
            } catch (err) {
              reportError(err, { tags: { area: 'position', action: 'refresh' } })
            }
            setShowLinkCompetency(false)
          }}
        />
      )}
      {canEdit && showCompetencyManager && (
        <CompetencyManagerModal
          competencies={competencies}
          onClose={() => setShowCompetencyManager(false)}
          onChanged={() => { void fetchCompetencies() }}
          onEdit={setEditingCompetency}
        />
      )}
      {canEdit && editingPosition && (
        <EditPositionModal
          position={editingPosition}
          onClose={() => setEditingPosition(null)}
          onSaved={(updated) => {
            setSelected((current) => current ? { ...current, ...updated } : current)
            setEditingPosition(null)
            void fetchPositions()
          }}
        />
      )}
      {canEdit && editingCompetency && (
        <EditCompetencyModal
          competency={editingCompetency}
          onClose={() => setEditingCompetency(null)}
          onSaved={() => {
            setEditingCompetency(null)
            void fetchCompetencies()
            if (selected) void handleSelectPosition(selected)
          }}
        />
      )}
      {canEdit && editingRequirement && selected && (
        <EditPositionCompetencyModal
          requirement={editingRequirement}
          onClose={() => setEditingRequirement(null)}
          onSaved={() => {
            setEditingRequirement(null)
            void handleSelectPosition(selected)
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
      reportError(err, { tags: { area: 'position', action: 'create' } })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      isOpen
      onClose={onClose}
      maxWidth="max-w-2xl"
      className="px-6 py-5"
      header={<h3 className="text-lg font-semibold text-text-primary">新增岗位</h3>}
      footer={(
        <div className="flex justify-end gap-2 px-6 py-4">
          <Button variant="ghost" onClick={onClose}>取消</Button>
          <Button onClick={handleSubmit} loading={submitting} disabled={!form.code || !form.name}>创建</Button>
        </div>
      )}
    >
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <FormField label="岗位编码" required>
          <Input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} placeholder="如 FE-001" />
        </FormField>
        <FormField label="岗位名称" required>
          <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </FormField>
        <FormField label="类别">
          <select
            aria-label="类别"
            value={form.category}
            onChange={(e) => setForm({ ...form, category: e.target.value })}
            className={selectClassName}
          >
            {CATEGORY_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </FormField>
        <FormField label="层级">
          <select
            aria-label="层级"
            value={form.level}
            onChange={(e) => setForm({ ...form, level: e.target.value })}
            className={selectClassName}
          >
            {LEVEL_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </FormField>
        <FormField label="行业">
          <Input value={form.industry} onChange={(e) => setForm({ ...form, industry: e.target.value })} />
        </FormField>
        <FormField label="描述">
          <Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={2} />
        </FormField>
      </div>
    </Modal>
  )
}

function EditPositionModal({ position, onClose, onSaved }: {
  position: Position
  onClose: () => void
  onSaved: (updated: Position) => void
}) {
  const [form, setForm] = useState({
    name: position.name,
    category: position.category ?? '',
    level: position.level ?? '',
    industry: position.industry ?? '',
    description: position.description ?? '',
  })
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async () => {
    if (!form.name.trim()) return
    setSubmitting(true)
    try {
      const updated = await trainingApi.updatePosition(position.id, {
        name: form.name.trim(),
        category: form.category || undefined,
        level: form.level || undefined,
        industry: form.industry || undefined,
        description: form.description || undefined,
      })
      onSaved(updated)
    } catch (err) {
      toast.error('岗位更新失败', err instanceof ApiError ? err.message : '请稍后重试')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal isOpen onClose={onClose} maxWidth="max-w-lg" className="p-6">
      <h3 className="text-lg font-semibold text-text-primary mb-4 pr-8">编辑岗位</h3>
      <div className="space-y-3">
        <p className="text-xs text-text-tertiary">编码：{position.code}（编码不可修改）</p>
        <FormField label="岗位名称" required>
          <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </FormField>
        <div className="grid grid-cols-2 gap-3">
          <FormField label="类别">
            <Input value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} />
          </FormField>
          <FormField label="层级">
            <Input value={form.level} onChange={(e) => setForm({ ...form, level: e.target.value })} />
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
          <Button onClick={handleSubmit} loading={submitting} disabled={!form.name.trim()}>保存</Button>
        </div>
      </div>
    </Modal>
  )
}

function EditCompetencyModal({ competency, onClose, onSaved }: {
  competency: Competency
  onClose: () => void
  onSaved: () => void
}) {
  const [form, setForm] = useState({
    name: competency.name,
    category: competency.category ?? '',
    description: competency.description ?? '',
    isActive: competency.isActive ?? competency.is_active,
  })
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async () => {
    if (!form.name.trim()) return
    setSubmitting(true)
    try {
      await trainingApi.updateCompetency(competency.id, {
        name: form.name.trim(),
        category: form.category || undefined,
        description: form.description || undefined,
        is_active: form.isActive,
      })
      onSaved()
    } catch (err) {
      toast.error('胜任力更新失败', err instanceof ApiError ? err.message : '请稍后重试')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal isOpen onClose={onClose} maxWidth="max-w-lg" className="p-6">
      <h3 className="text-lg font-semibold text-text-primary mb-4 pr-8">编辑胜任力</h3>
      <div className="space-y-3">
        <p className="text-xs text-text-tertiary">编码：{competency.code}（编码不可修改）</p>
        <FormField label="名称" required>
          <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </FormField>
        <FormField label="类别">
          <Input value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} />
        </FormField>
        <FormField label="描述">
          <Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={3} />
        </FormField>
        <label className="flex items-center gap-2 text-sm text-text-primary cursor-pointer">
          <input
            type="checkbox"
            checked={form.isActive}
            onChange={(e) => setForm({ ...form, isActive: e.target.checked })}
            className="w-4 h-4 rounded border-border"
          />
          启用胜任力
        </label>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="ghost" onClick={onClose}>取消</Button>
          <Button onClick={handleSubmit} loading={submitting} disabled={!form.name.trim()}>保存</Button>
        </div>
      </div>
    </Modal>
  )
}

function EditPositionCompetencyModal({ requirement, onClose, onSaved }: {
  requirement: PositionCompetency
  onClose: () => void
  onSaved: () => void
}) {
  const positionId = requirement.positionId ?? requirement.position_id
  const competencyId = requirement.competencyId ?? requirement.competency_id
  const [requiredLevel, setRequiredLevel] = useState(String(requirement.requiredLevel ?? requirement.required_level))
  const [weight, setWeight] = useState(String(requirement.weight))
  const [isMandatory, setIsMandatory] = useState(requirement.isMandatory ?? requirement.is_mandatory)
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async () => {
    setSubmitting(true)
    try {
      await trainingApi.updatePositionCompetency(positionId, competencyId, {
        required_level: Number(requiredLevel),
        weight: Number(weight),
        is_mandatory: isMandatory,
      })
      onSaved()
    } catch (err) {
      toast.error('岗位胜任力要求更新失败', err instanceof ApiError ? err.message : '请稍后重试')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal isOpen onClose={onClose} maxWidth="max-w-md" className="p-6">
      <h3 className="text-lg font-semibold text-text-primary mb-4 pr-8">编辑胜任力要求</h3>
      <div className="space-y-3">
        <p className="text-sm text-text-primary">{requirement.competencyName ?? requirement.competency_name}</p>
        <div className="grid grid-cols-2 gap-3">
          <FormField label="要求等级（1-5）" required>
            <Input type="number" min={1} max={5} value={requiredLevel} onChange={(e) => setRequiredLevel(e.target.value)} />
          </FormField>
          <FormField label="权重" required>
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
          <Button onClick={handleSubmit} loading={submitting} disabled={!requiredLevel || !weight}>保存</Button>
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
      reportError(err, { tags: { area: 'position', action: 'create_competency' } })
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
      reportError(err, { tags: { area: 'position', action: 'add_competency' } })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal isOpen onClose={onClose} maxWidth="max-w-lg" className="p-6">
      <h3 className="text-lg font-semibold text-text-primary mb-4 pr-8">关联胜任力</h3>
      {available.length === 0 ? (
        <div className="text-sm text-text-secondary py-4 text-center">
          所有胜任力已关联，请先点击“新增胜任力”创建更多胜任力项。
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

function CompetencyManagerModal({
  competencies, onClose, onChanged, onEdit,
}: {
  competencies: Competency[]
  onClose: () => void
  onChanged: () => void
  onEdit: (competency: Competency) => void
}) {
  const [deletingId, setDeletingId] = useState<number | null>(null)

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`确定要删除胜任力"${name}"吗？此操作不可撤销，已关联该胜任力的岗位将同时解除关联。`)) return
    setDeletingId(id)
    try {
      await trainingApi.deleteCompetency(id)
      onChanged()
    } catch (err) {
      reportError(err, { tags: { area: 'position', action: 'delete_competency' } })
      toast.error('删除胜任力失败', err instanceof ApiError ? err.message : '请稍后重试')
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <Modal isOpen onClose={onClose} maxWidth="max-w-2xl" className="p-6 max-h-[80vh] overflow-y-auto">
      <h3 className="text-lg font-semibold text-text-primary mb-4 pr-8">胜任力管理</h3>
      {competencies.length === 0 ? (
        <div className="text-sm text-text-secondary py-6 text-center">
          暂无胜任力，请先点击“新增胜任力”创建。
        </div>
      ) : (
        <div className="space-y-1">
          {competencies.map((c) => (
            <div
              key={c.id}
              className="flex items-center justify-between py-2 px-3 border border-border rounded-input hover:bg-bg-secondary/50 transition-colors"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-text-primary truncate">{c.name}</span>
                  {c.category && (
                    <Badge variant="default">{CATEGORY_LABEL[c.category] ?? c.category}</Badge>
                  )}
                  {!(c.isActive ?? c.is_active) && <Badge variant="error">已停用</Badge>}
                </div>
                <div className="text-xs text-text-tertiary mt-0.5">
                  编码：<span>{c.code}</span>
                  {c.description && <span className="ml-2">· {c.description}</span>}
                </div>
              </div>
              <div className="ml-3 flex items-center gap-2">
                <button
                  onClick={() => onEdit(c)}
                  className="text-xs text-primary hover:text-primary-hover transition-colors"
                >
                  编辑
                </button>
                <button
                onClick={() => void handleDelete(c.id, c.name)}
                disabled={deletingId === c.id}
                className="ml-3 text-xs text-error hover:text-error-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {deletingId === c.id ? '删除中…' : '删除'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </Modal>
  )
}
