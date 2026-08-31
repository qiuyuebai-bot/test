import { useEffect, useState } from 'react'
import { trainingApi } from '@/api'
import Card from '@/components/Card'
import Badge from '@/components/Badge'
import LoadingState from '@/components/LoadingState'
import type { TrainingDashboardOverview } from '@/types/training'

export default function TrainingDashboardTab() {
  const [data, setData] = useState<TrainingDashboardOverview | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    trainingApi.getTrainingDashboard()
      .then((result) => { if (active) setData(result) })
      .catch(() => { if (active) setData(null) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  if (loading) return <LoadingState />
  if (!data) return <p className="text-sm text-text-tertiary">暂无培训效果数据</p>

  const metrics = [
    ['培训项目', data.projectCount ?? data.project_count],
    ['报名人数', data.enrollmentCount ?? data.enrollment_count],
    ['已完成培训', data.completedCount ?? data.completed_count],
    ['任务提交', data.submissionCount ?? data.submission_count],
    ['通过提交', data.passedSubmissionCount ?? data.passed_submission_count],
    ['平均实操分', data.average_score ?? '-'],
  ]

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {metrics.map(([label, value]) => (
          <Card key={label} className="p-4">
            <p className="text-xs text-text-tertiary">{label}</p>
            <p className="mt-1 text-2xl font-semibold text-text-primary">{value}</p>
          </Card>
        ))}
      </div>
      <Card>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium text-text-primary">项目效果明细</h3>
          <Badge variant="info">实时汇总</Badge>
        </div>
        {data.projects.length === 0 ? (
          <p className="text-sm text-text-tertiary">暂无可展示项目</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-text-tertiary border-b border-border">
                <th className="py-2 pr-3">培训项目</th><th className="py-2 pr-3">报名</th><th className="py-2 pr-3">完成</th><th className="py-2 pr-3">任务包</th><th className="py-2 pr-3">提交/通过</th><th className="py-2">平均分</th>
              </tr></thead>
              <tbody>{data.projects.map((project) => (
                <tr key={project.project_id ?? project.projectId} className="border-b border-border last:border-0">
                  <td className="py-2 pr-3 font-medium text-text-primary">{project.project_name ?? project.projectName}</td>
                  <td className="py-2 pr-3">{project.enrollment_count ?? project.enrollmentCount}</td>
                  <td className="py-2 pr-3">{project.completed_count ?? project.completedCount}</td>
                  <td className="py-2 pr-3">{project.package_count ?? project.packageCount}</td>
                  <td className="py-2 pr-3">{project.submission_count ?? project.submissionCount} / {project.passed_submission_count ?? project.passedSubmissionCount}</td>
                  <td className="py-2">{project.average_score ?? project.averageScore ?? '-'}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
