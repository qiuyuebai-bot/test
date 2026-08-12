import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useShallow } from 'zustand/react/shallow'
import { useStore } from '@/store'
import Card from '@/components/Card'
import { FileText, GraduationCap } from 'lucide-react'

export default function PracticeTab() {
  const { positions, fetchPositions } = useStore(
    useShallow((s) => ({
      positions: s.positions,
      fetchPositions: s.fetchPositions,
    })),
  )
  const navigate = useNavigate()

  useEffect(() => {
    void fetchPositions()
  }, [fetchPositions])

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-medium text-text-primary">学习与练习</h2>
      <p className="text-sm text-text-secondary">选择学习方式，复用现有资源生成与自适应导学能力</p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Card
          className="cursor-pointer hover:border-primary transition-colors"
          onClick={() => navigate('/resources')}
        >
          <div className="flex items-start gap-3">
            <div className="p-2 bg-primary-light rounded-lg">
              <FileText className="w-6 h-6 text-primary" />
            </div>
            <div className="flex-1">
              <h3 className="font-medium text-text-primary">培训资料生成</h3>
              <p className="text-xs text-text-secondary mt-1">
                通过多智能体协同生成个性化学习资料，含审核与辩论纠偏机制
              </p>
            </div>
          </div>
        </Card>

        <Card
          className="cursor-pointer hover:border-primary transition-colors"
          onClick={() => navigate('/guidance')}
        >
          <div className="flex items-start gap-3">
            <div className="p-2 bg-primary-light rounded-lg">
              <GraduationCap className="w-6 h-6 text-primary" />
            </div>
            <div className="flex-1">
              <h3 className="font-medium text-text-primary">自适应练习</h3>
              <p className="text-xs text-text-secondary mt-1">
                按岗位胜任力维度动态出题，难度自适应调整
              </p>
            </div>
          </div>
        </Card>
      </div>

      {positions.length > 0 && (
        <Card>
          <h3 className="text-sm font-medium text-text-primary mb-2">可选岗位</h3>
          <div className="flex flex-wrap gap-2">
            {positions.map((p) => (
              <span key={p.id} className="px-2 py-1 text-xs bg-bg-secondary rounded text-text-secondary">
                {p.name}
              </span>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}
