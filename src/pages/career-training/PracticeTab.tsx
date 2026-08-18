import { useEffect, useState } from 'react'
import { useShallow } from 'zustand/react/shallow'
import { useStore } from '@/store'
import { trainingApi } from '@/api'
import { reportError } from '@/lib/sentry'
import Card from '@/components/Card'
import Badge from '@/components/Badge'
import Select from '@/components/Select'
import type { Position, PositionDetail } from '@/types/training'
import EmbeddedResourceGeneration from './EmbeddedResourceGeneration'
import EmbeddedAdaptivePractice from './EmbeddedAdaptivePractice'

type SubTab = 'resource' | 'practice'

export default function PracticeTab() {
  const { positions, fetchPositions, learners, currentLearner, fetchLearners, setCurrentLearner, user } = useStore(
    useShallow((s) => ({
      positions: s.positions,
      fetchPositions: s.fetchPositions,
      learners: s.learners,
      currentLearner: s.currentLearner,
      fetchLearners: s.fetchLearners,
      setCurrentLearner: s.setCurrentLearner,
      user: s.user,
    })),
  )
  const [selectedPositionId, setSelectedPositionId] = useState<number | null>(null)
  const [positionDetail, setPositionDetail] = useState<PositionDetail | null>(null)
  const [subTab, setSubTab] = useState<SubTab>('resource')

  useEffect(() => {
    void fetchPositions()
    if (user?.role === 'admin' || user?.role === 'teacher') {
      void fetchLearners()
    }
  }, [fetchPositions, fetchLearners, user?.role])

  useEffect(() => {
    if (positions.length > 0 && selectedPositionId === null) {
      void handleSelectPosition(positions[0])
    }
  }, [positions, selectedPositionId])

  const handleSelectPosition = async (p: Position) => {
    setSelectedPositionId(p.id)
    try {
      const detail = await trainingApi.getPosition(p.id)
      setPositionDetail(detail)
    } catch (err) {
      reportError(err, { tags: { area: 'practice', action: 'get_position' } })
      setPositionDetail(null)
    }
  }

  const learnerId = currentLearner?.id ?? null
  const canSelectLearner = user?.role === 'admin' || user?.role === 'teacher'

  const subTabs: Array<{ key: SubTab; label: string }> = [
    { key: 'resource', label: '资料生成' },
    { key: 'practice', label: '自适应练习' },
  ]

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-medium text-text-primary">学习与练习</h2>
        <p className="text-sm text-text-secondary mt-1">选择岗位后，生成个性化学习资料或进行自适应练习</p>
      </div>

      <Card>
        <div className="flex flex-wrap items-end gap-4">
          <div className="flex-1 min-w-[200px]">
            <Select
              label="目标岗位"
              value={selectedPositionId ?? ''}
              options={positions.map((p) => ({ value: String(p.id), label: p.name }))}
              onChange={(e) => {
                const p = positions.find((x) => x.id === Number(e.target.value))
                if (p) void handleSelectPosition(p)
              }}
            />
          </div>
          {canSelectLearner && (
            <div className="flex-1 min-w-[200px]">
              <Select
                label="学习者"
                value={currentLearner?.id ?? ''}
                options={learners.map((l) => ({ value: String(l.id), label: l.realName }))}
                onChange={(e) => {
                  const l = learners.find((x) => x.id === Number(e.target.value))
                  if (l) setCurrentLearner(l)
                }}
              />
            </div>
          )}
          {positionDetail?.industry && (
            <Badge variant="info">{positionDetail.industry}</Badge>
          )}
        </div>
      </Card>

      <nav aria-label="学习与练习子模块" className="flex gap-1 border-b border-border">
        {subTabs.map((t) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={subTab === t.key}
            onClick={() => setSubTab(t.key)}
            className={`px-4 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 -mb-px transition-colors ${
              subTab === t.key
                ? 'border-primary text-primary'
                : 'border-transparent text-text-secondary hover:text-text-primary'
            }`}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <div className="mt-4">
        {subTab === 'resource' && (
          <EmbeddedResourceGeneration position={positionDetail} learnerId={learnerId} />
        )}
        {subTab === 'practice' && (
          <EmbeddedAdaptivePractice position={positionDetail} learnerId={learnerId} />
        )}
      </div>
    </div>
  )
}
