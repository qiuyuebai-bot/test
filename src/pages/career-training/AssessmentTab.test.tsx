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
    getPosition: vi.fn(),
    listAssessmentTemplates: vi.fn(),
    getAssessmentTemplate: vi.fn(),
    updateAssessmentTemplate: vi.fn(),
    deleteAssessmentTemplate: vi.fn(),
    getAssessmentRecord: vi.fn(),
    startAssessment: vi.fn(),
    submitAssessment: vi.fn(),
    getGapAnalysis: vi.fn(),
  },
}))

import { resetMockStore, setMockStore } from '../../test/mockStore'
import { trainingApi } from '@/api'
import AssessmentTab from './AssessmentTab'

describe('AssessmentTab', () => {
  beforeEach(() => {
    resetMockStore()
    vi.clearAllMocks()
    setMockStore({
      positions: [
        { id: 1, code: 'FE-001', name: '前端工程师', is_active: true, created_at: '', updated_at: '' },
      ],
      assessmentRecords: [],
      assessmentRecordsLoading: false,
      fetchPositions: vi.fn(),
      fetchAssessmentRecords: vi.fn(),
    })
  })

  it('渲染岗位选择与历史记录区域', () => {
    render(<MemoryRouter><AssessmentTab /></MemoryRouter>)
    expect(screen.getByText('能力评估')).toBeInTheDocument()
    expect(screen.getByText('前端工程师')).toBeInTheDocument()
  })

  it('选择岗位后加载模板列表', async () => {
    vi.mocked(trainingApi.listAssessmentTemplates).mockResolvedValueOnce({
      items: [
        { id: 1, position_id: 1, name: '初级评估', competency_configs: [], pass_threshold: 60, is_active: true, created_at: '', updated_at: '' },
      ],
      total: 1, page: 1, pageSize: 20, totalPages: 1,
    })
    render(<MemoryRouter><AssessmentTab /></MemoryRouter>)
    await userEvent.click(screen.getByText('前端工程师'))
    await waitFor(() => {
      expect(screen.getByText('初级评估')).toBeInTheDocument()
    })
  })

  it('教师选择学习者后开始评估会携带 learner_id', async () => {
    vi.mocked(trainingApi.listAssessmentTemplates).mockResolvedValueOnce({
      items: [
        { id: 1, position_id: 1, name: '初级评估', competency_configs: [{ competency_id: 11, question_count: 3, difficulty: 2, assessment_method: 'quiz' }], pass_threshold: 60, is_active: true, created_at: '', updated_at: '' },
      ],
      total: 1, page: 1, pageSize: 20, totalPages: 1,
    })
    vi.mocked(trainingApi.startAssessment).mockResolvedValueOnce({ id: 4, template_id: 1, user_id: 7, learner_id: 3, position_id: 1, status: 'in_progress', created_at: '', updated_at: '' })
    setMockStore({
      user: { userId: 99, username: 'teacher', role: 'teacher' },
      learners: [{ id: 3, realName: '张三' }],
      currentLearner: null,
    })
    render(<MemoryRouter><AssessmentTab /></MemoryRouter>)
    await userEvent.selectOptions(screen.getByLabelText('评估学习者'), '3')
    await userEvent.click(screen.getByText('前端工程师'))
    await userEvent.click(screen.getByText('初级评估'))
    await userEvent.click(screen.getByRole('button', { name: '开始评估' }))
    await waitFor(() => {
      expect(trainingApi.startAssessment).toHaveBeenCalledWith({ template_id: 1, learner_id: 3 })
    })
  })

  it('学员只能查看评估结果，不能开始或录入成绩', async () => {
    vi.mocked(trainingApi.listAssessmentTemplates).mockResolvedValueOnce({
      items: [
        { id: 1, position_id: 1, name: '初级评估', competency_configs: [], pass_threshold: 60, is_active: true, created_at: '', updated_at: '' },
      ],
      total: 1, page: 1, pageSize: 20, totalPages: 1,
    })
    setMockStore({ user: { userId: 7, username: 'learner', role: 'learner' } })
    render(<MemoryRouter><AssessmentTab /></MemoryRouter>)
    await userEvent.click(screen.getByText('前端工程师'))
    await userEvent.click(screen.getByText('初级评估'))
    expect(screen.queryByRole('button', { name: '开始评估' })).not.toBeInTheDocument()
    expect(screen.getByText('评估成绩由管理员或教师录入，当前账号只能查看评估结果。')).toBeInTheDocument()
  })

  it('teacher can edit an assessment template and save it', async () => {
    vi.mocked(trainingApi.listAssessmentTemplates).mockResolvedValue({
      items: [
        { id: 1, position_id: 1, name: '初级评估', competency_configs: [{ competency_id: 11, question_count: 3, difficulty: 2, assessment_method: 'quiz' }], pass_threshold: 60, is_active: true, created_at: '', updated_at: '' },
      ],
      total: 1, page: 1, pageSize: 20, totalPages: 1,
    })
    vi.mocked(trainingApi.getAssessmentTemplate).mockResolvedValueOnce({
      id: 1, position_id: 1, name: '初级评估', competency_configs: [{ competency_id: 11, question_count: 3, difficulty: 2, assessment_method: 'quiz' }], pass_threshold: 60, is_active: true, created_at: '', updated_at: '',
    })
    vi.mocked(trainingApi.getPosition).mockResolvedValue({
      id: 1, code: 'FE-001', name: '前端工程师', is_active: true, created_at: '', updated_at: '',
      competencies: [{ id: 11, position_id: 1, competency_id: 11, competency_name: 'React', required_level: 3, weight: 1, is_mandatory: true, created_at: '' }],
    })
    vi.mocked(trainingApi.updateAssessmentTemplate).mockResolvedValueOnce({
      id: 1, position_id: 1, name: '初级评估', competency_configs: [{ competency_id: 11, question_count: 3, difficulty: 2, assessment_method: 'quiz' }], pass_threshold: 60, is_active: true, created_at: '', updated_at: '',
    })
    render(<MemoryRouter><AssessmentTab /></MemoryRouter>)
    await userEvent.click(screen.getByText('前端工程师'))
    await userEvent.click(await screen.findByRole('button', { name: '编辑' }))
    await userEvent.click(await screen.findByRole('button', { name: '保存评估模板' }))

    await waitFor(() => {
      expect(trainingApi.getAssessmentTemplate).toHaveBeenCalledWith(1)
      expect(trainingApi.updateAssessmentTemplate).toHaveBeenCalledWith(1, expect.objectContaining({ name: '初级评估' }))
    })
  })

  it('uses the camel-case active state when toggling a template', async () => {
    vi.mocked(trainingApi.listAssessmentTemplates).mockResolvedValue({
      items: [
        { id: 1, position_id: 1, name: '初级评估', competency_configs: [], pass_threshold: 60, is_active: false, isActive: true, created_at: '', updated_at: '' },
      ],
      total: 1, page: 1, pageSize: 20, totalPages: 1,
    })
    vi.mocked(trainingApi.updateAssessmentTemplate).mockResolvedValueOnce({
      id: 1, position_id: 1, name: '初级评估', competency_configs: [], pass_threshold: 60, is_active: false, created_at: '', updated_at: '',
    })

    render(<MemoryRouter><AssessmentTab /></MemoryRouter>)
    await userEvent.click(screen.getByText('前端工程师'))
    await userEvent.click(await screen.findByRole('button', { name: '停用' }))

    await waitFor(() => {
      expect(trainingApi.updateAssessmentTemplate).toHaveBeenCalledWith(1, { is_active: false })
    })
  })

  it('can open assessment record details', async () => {
    setMockStore({
      assessmentRecords: [{ id: 8, template_id: 1, user_id: 1, position_id: 1, status: 'completed', overall_score: 88, created_at: '', updated_at: '' }],
    })
    vi.mocked(trainingApi.getAssessmentRecord).mockResolvedValueOnce({
      id: 8, template_id: 1, user_id: 1, position_id: 1, status: 'completed', overall_score: 88, created_at: '', updated_at: '',
      competency_scores: [{ id: 1, assessment_record_id: 8, competency_id: 11, competency_name: 'React', current_level: 4, current_score: 88, required_level: 3, created_at: '' }],
      template_name: '初级评估', position_name: '前端工程师',
    })
    render(<MemoryRouter><AssessmentTab /></MemoryRouter>)
    await userEvent.click(screen.getByRole('button', { name: '查看详情' }))

    expect(await screen.findByText('评估记录详情 #8')).toBeInTheDocument()
    expect(trainingApi.getAssessmentRecord).toHaveBeenCalledWith(8)
  })
})
