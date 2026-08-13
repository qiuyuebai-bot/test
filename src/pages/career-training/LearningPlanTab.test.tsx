import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

vi.mock('@/store', async () => {
  const { useStoreMock } = await import('../../test/mockStore')
  return { useStore: useStoreMock }
})

vi.mock('@/api', () => ({
  trainingApi: {
    getEnrollment: vi.fn(),
    enrollProject: vi.fn(),
    generatePlan: vi.fn(),
    getPlan: vi.fn(),
    updateProgress: vi.fn(),
    completeTraining: vi.fn(),
  },
}))

import { resetMockStore, setMockStore } from '../../test/mockStore'
import { trainingApi } from '@/api'
import LearningPlanTab from './LearningPlanTab'

describe('LearningPlanTab', () => {
  beforeEach(() => {
    resetMockStore()
    vi.clearAllMocks()
    setMockStore({
      trainingProjects: [
        { id: 1, name: '前端入职培训', position_id: 1, status: 'active', created_at: '', updated_at: '' },
      ],
      assessmentRecords: [
        { id: 5, template_id: 1, user_id: 1, position_id: 1, status: 'completed', overall_score: 72, created_at: '', updated_at: '' },
      ],
    trainingProjectsLoading: false,
    fetchTrainingProjects: vi.fn(),
    fetchAssessmentRecords: vi.fn(),
      user: { id: 1, userId: 1, username: 'learner', role: 'learner' },
    })
  })

  it('渲染培训项目卡片', () => {
    render(<MemoryRouter><LearningPlanTab /></MemoryRouter>)
    expect(screen.getByText('前端入职培训')).toBeInTheDocument()
  })

  it('点击项目只查看报名状态，不会自动报名', async () => {
    vi.mocked(trainingApi.getEnrollment).mockResolvedValueOnce(null)
    render(<MemoryRouter><LearningPlanTab /></MemoryRouter>)
    await userEvent.click(screen.getByText('前端入职培训'))
    expect(await screen.findByRole('button', { name: '报名培训项目' })).toBeInTheDocument()
    expect(trainingApi.enrollProject).not.toHaveBeenCalled()
  })

  it('显式报名后可选择匹配评估并生成计划', async () => {
    vi.mocked(trainingApi.getEnrollment).mockResolvedValueOnce(null)
    vi.mocked(trainingApi.enrollProject).mockResolvedValueOnce({ id: 9, project_id: 1, user_id: 1, status: 'enrolled', created_at: '', updated_at: '' })
    vi.mocked(trainingApi.generatePlan).mockResolvedValueOnce({
      id: 1, project_id: 1, enrollment_id: 9, user_id: 1, assessment_record_id: 5,
      plan_content: [{ stage: 1, title: '阶段1', competency_ids: [], resources: [], estimated_hours: 4, target_level: 3 }],
      total_stages: 1, completed_stages: 0, progress: 0, status: 'active', generated_by_ai: true,
      created_at: '', updated_at: '',
    })
    render(<MemoryRouter><LearningPlanTab /></MemoryRouter>)
    await userEvent.click(screen.getByText('前端入职培训'))
    await userEvent.click(await screen.findByRole('button', { name: '报名培训项目' }))
    await userEvent.click(await screen.findByRole('button', { name: '选择评估记录并生成计划' }))
    await userEvent.click(screen.getByText('记录 #5'))
    await userEvent.click(screen.getByRole('button', { name: '生成计划' }))
    await waitFor(() => {
      expect(screen.getByText('阶段1')).toBeInTheDocument()
    })
  })
})
