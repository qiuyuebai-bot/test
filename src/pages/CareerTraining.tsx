import { useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { clsx } from 'clsx'
import PositionTab from './career-training/PositionTab'
import AssessmentTab from './career-training/AssessmentTab'
import LearningPlanTab from './career-training/LearningPlanTab'
import PracticeTab from './career-training/PracticeTab'
import CertificationTab from './career-training/CertificationTab'

type TabKey = 'position' | 'assessment' | 'plan' | 'practice' | 'certification'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'position', label: '岗位与胜任力' },
  { key: 'assessment', label: '能力评估' },
  { key: 'plan', label: '学习计划' },
  { key: 'practice', label: '学习与练习' },
  { key: 'certification', label: '认证发证' },
]

export default function CareerTraining() {
  const { tab } = useParams<{ tab?: string }>()
  const navigate = useNavigate()

  const currentTab: TabKey = (TABS.find((t) => t.key === tab)?.key ?? 'position') as TabKey

  useEffect(() => {
    if (!tab || !TABS.some((t) => t.key === tab)) {
      navigate('/career-training/position', { replace: true })
    }
  }, [tab, navigate])

  const handleTabChange = (key: TabKey) => {
    navigate(`/career-training/${key}`)
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-text-primary">就业培训</h1>
        <p className="text-sm text-text-secondary mt-1">岗位-胜任力-学习-认证 全流程能力培养</p>
      </div>

      <nav aria-label="就业培训 Tab" className="flex gap-1 border-b border-border overflow-x-auto">
        {TABS.map((t) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={currentTab === t.key}
            onClick={() => handleTabChange(t.key)}
            className={clsx(
              'px-4 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 -mb-px transition-colors',
              currentTab === t.key
                ? 'border-primary text-primary'
                : 'border-transparent text-text-secondary hover:text-text-primary',
            )}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <div className="mt-4">
        {currentTab === 'position' && <PositionTab />}
        {currentTab === 'assessment' && <AssessmentTab />}
        {currentTab === 'plan' && <LearningPlanTab />}
        {currentTab === 'practice' && <PracticeTab />}
        {currentTab === 'certification' && <CertificationTab />}
      </div>
    </div>
  )
}
