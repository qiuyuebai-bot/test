import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import PlanTimeline from './PlanTimeline'

describe('PlanTimeline', () => {
  it('空数据渲染提示', () => {
    render(<PlanTimeline stages={[]} completedStages={0} />)
    expect(screen.getByText('暂无学习计划')).toBeInTheDocument()
  })

  it('渲染阶段与完成状态', () => {
    render(
      <PlanTimeline
        stages={[
          { stage: 1, title: '阶段1', competency_ids: [], resources: [], estimated_hours: 4, target_level: 3 },
          { stage: 2, title: '阶段2', competency_ids: [], resources: [], estimated_hours: 6, target_level: 4 },
        ]}
        completedStages={1}
      />,
    )
    expect(screen.getByText('阶段1')).toBeInTheDocument()
    expect(screen.getByText('阶段2')).toBeInTheDocument()
    expect(screen.getByText('1 / 2')).toBeInTheDocument()
  })

  it('点击阶段触发回调', async () => {
    const onStageClick = vi.fn()
    render(
      <PlanTimeline
        stages={[{ stage: 1, title: '阶段1', competency_ids: [], resources: [], estimated_hours: 4, target_level: 3 }]}
        completedStages={0}
        onStageClick={onStageClick}
      />,
    )
    await userEvent.click(screen.getByText('阶段1'))
    expect(onStageClick).toHaveBeenCalledWith(1)
  })
})
