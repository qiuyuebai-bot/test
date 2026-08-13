import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import CompetencyRadar from './CompetencyRadar'

describe('CompetencyRadar', () => {
  it('空数据渲染占位提示', () => {
    render(<CompetencyRadar items={[]} />)
    expect(screen.getByText('暂无胜任力数据')).toBeInTheDocument()
  })

  it('渲染 SVG 与各维度标签', () => {
    render(
      <CompetencyRadar
        items={[
          { name: 'Python', current: 2, required: 4 },
          { name: '算法', current: 3, required: 4 },
          { name: '架构', current: 1, required: 3 },
        ]}
      />,
    )
    expect(screen.getByText('Python')).toBeInTheDocument()
    expect(screen.getByText('算法')).toBeInTheDocument()
    expect(screen.getByText('架构')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: '胜任力雷达图' })).toBeInTheDocument()
  })
})
