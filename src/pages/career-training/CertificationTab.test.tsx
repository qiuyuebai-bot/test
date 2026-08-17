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
    getCertification: vi.fn(),
    updateCertification: vi.fn(),
    deleteCertification: vi.fn(),
    listCertificationRules: vi.fn(),
    deleteCertificationRule: vi.fn(),
    getCertificationRecord: vi.fn(),
    createCertification: vi.fn(),
    addCertificationRule: vi.fn(),
    applyCertification: vi.fn(),
    approveCertification: vi.fn(),
    rejectCertification: vi.fn(),
    revokeCertification: vi.fn(),
    verifyCertification: vi.fn(),
  },
}))

import { resetMockStore, setMockStore } from '../../test/mockStore'
import { trainingApi } from '@/api'
import CertificationTab from './CertificationTab'

describe('CertificationTab', () => {
  beforeEach(() => {
    resetMockStore()
    vi.clearAllMocks()
    setMockStore({
      certifications: [
        { id: 1, position_id: 1, name: '前端初级认证', code: 'CERT-FE-J', level: 'junior', validity_period_months: 24, is_active: true, created_at: '', updated_at: '' },
      ],
      certificationRecords: [
        { id: 1, certification_id: 1, user_id: 1, assessment_record_id: 5, status: 'pending', created_at: '', updated_at: '' },
      ],
      certificationRecordsLoading: false,
      assessmentRecords: [
        { id: 5, template_id: 1, user_id: 1, position_id: 1, status: 'completed', overall_score: 80, created_at: '', updated_at: '' },
      ],
      positions: [
        { id: 1, code: 'FE-001', name: '前端工程师', is_active: true, created_at: '', updated_at: '' },
      ],
      fetchPositions: vi.fn(),
      fetchCertifications: vi.fn(),
      fetchCertificationRecords: vi.fn(),
      fetchAssessmentRecords: vi.fn(),
      user: { id: 1, username: 'admin', role: 'admin' },
    })
  })

  it('渲染认证列表与申请记录', () => {
    render(<MemoryRouter><CertificationTab /></MemoryRouter>)
    expect(screen.getAllByText('前端初级认证')[0]).toBeInTheDocument()
    expect(screen.getByText('待审核')).toBeInTheDocument()
  })

  it('管理员可创建认证定义并配置发证规则', async () => {
    vi.mocked(trainingApi.createCertification).mockResolvedValueOnce({
      id: 2, position_id: 1, name: '前端中级认证', code: 'FE-MID-001', level: 'mid',
      validity_period_months: 24, is_active: true, created_at: '', updated_at: '',
    })
    vi.mocked(trainingApi.addCertificationRule).mockResolvedValueOnce({})
    render(<MemoryRouter><CertificationTab /></MemoryRouter>)

    await userEvent.click(screen.getByRole('button', { name: '新增认证定义' }))
    await userEvent.selectOptions(screen.getByLabelText('关联岗位'), '1')
    await userEvent.type(screen.getByLabelText('认证名称'), '前端中级认证')
    await userEvent.type(screen.getByLabelText('认证编码'), 'FE-MID-001')
    await userEvent.selectOptions(screen.getByLabelText('认证级别'), 'mid')
    await userEvent.clear(screen.getByLabelText('有效期（月）'))
    await userEvent.type(screen.getByLabelText('有效期（月）'), '24')
    await userEvent.clear(screen.getByLabelText('最低综合成绩'))
    await userEvent.type(screen.getByLabelText('最低综合成绩'), '80')
    await userEvent.click(screen.getByRole('button', { name: '创建并启用' }))

    await waitFor(() => {
      expect(trainingApi.createCertification).toHaveBeenCalledWith(expect.objectContaining({
        position_id: 1,
        name: '前端中级认证',
        code: 'FE-MID-001',
        level: 'mid',
        validity_period_months: 24,
      }))
      expect(trainingApi.addCertificationRule).toHaveBeenCalledWith({
        certification_id: 2,
        rule_type: 'overall_score',
        rule_config: { min_score: 80 },
      })
    })
  })

  it('管理员可批准认证', async () => {
    vi.mocked(trainingApi.approveCertification).mockResolvedValueOnce({
      id: 1, certification_id: 1, user_id: 1, assessment_record_id: 5, status: 'approved', created_at: '', updated_at: '',
    })
    render(<MemoryRouter><CertificationTab /></MemoryRouter>)
    await userEvent.click(screen.getByText('批准'))
    await waitFor(() => {
      expect(trainingApi.approveCertification).toHaveBeenCalledWith(1, { comment: undefined })
    })
  })

  it('管理员选择学习者后，申请会绑定该学习者的评估记录', async () => {
    vi.mocked(trainingApi.applyCertification).mockResolvedValueOnce({
      id: 2, certification_id: 1, user_id: 2, learner_id: 2, assessment_record_id: 5,
      status: 'pending', created_at: '', updated_at: '',
    })
    setMockStore({
      learners: [{ id: 2, realName: '张三' }],
      assessmentRecords: [
        { id: 5, template_id: 1, user_id: 2, learner_id: 2, position_id: 1, status: 'completed', overall_score: 80, created_at: '', updated_at: '' },
      ],
    })
    render(<MemoryRouter><CertificationTab /></MemoryRouter>)

    await userEvent.selectOptions(screen.getByLabelText('认证学习者'), '2')
    await userEvent.click(screen.getByText('申请'))
    await userEvent.click(screen.getByText('记录 #5'))
    await userEvent.click(screen.getByText('提交申请'))

    await waitFor(() => {
      expect(trainingApi.applyCertification).toHaveBeenCalledWith({
        certification_id: 1,
        assessment_record_id: 5,
        learner_id: 2,
      })
    })
  })

  it('管理员可以验真并撤销已批准证书', async () => {
    vi.mocked(trainingApi.verifyCertification).mockResolvedValueOnce({
      certificate_number: 'CERT-202608-000001',
      status: 'approved',
      is_valid: true,
      certification_name: '前端初级认证',
      learner_name: '张三',
    })
    vi.mocked(trainingApi.revokeCertification).mockResolvedValueOnce({
      id: 1,
      certification_id: 1,
      user_id: 1,
      assessment_record_id: 5,
      status: 'revoked',
      certificate_number: 'CERT-202608-000001',
      created_at: '',
      updated_at: '',
    })
    setMockStore({
      certificationRecords: [
        {
          id: 1,
          certification_id: 1,
          user_id: 1,
          assessment_record_id: 5,
          status: 'approved',
          certificate_number: 'CERT-202608-000001',
          created_at: '',
          updated_at: '',
        },
      ],
    })
    render(<MemoryRouter><CertificationTab /></MemoryRouter>)

    await userEvent.click(screen.getByRole('button', { name: 'verify-certificate' }))
    expect(await screen.findByRole('heading', { name: 'certificate-verification-result' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'close-verification' }))
    await userEvent.click(screen.getByRole('button', { name: 'revoke-certificate' }))

    await waitFor(() => {
      expect(trainingApi.verifyCertification).toHaveBeenCalledWith('CERT-202608-000001')
      expect(trainingApi.revokeCertification).toHaveBeenCalledWith(1, { comment: '管理员撤销证书' })
    })
  })

  it('admin can edit a certification definition', async () => {
    vi.mocked(trainingApi.getCertification).mockResolvedValueOnce({
      id: 1, position_id: 1, name: '前端初级认证', code: 'CERT-FE-J', level: 'junior', validity_period_months: 24, is_active: true, created_at: '', updated_at: '', rules: [],
    })
    vi.mocked(trainingApi.updateCertification).mockResolvedValueOnce({
      id: 1, position_id: 1, name: '前端初级认证', code: 'CERT-FE-J', level: 'junior', validity_period_months: 24, is_active: true, created_at: '', updated_at: '',
    })
    render(<MemoryRouter><CertificationTab /></MemoryRouter>)
    await userEvent.click(screen.getByRole('button', { name: '编辑' }))
    await userEvent.click(await screen.findByRole('button', { name: '保存' }))

    await waitFor(() => {
      expect(trainingApi.getCertification).toHaveBeenCalledWith(1)
      expect(trainingApi.updateCertification).toHaveBeenCalledWith(1, expect.objectContaining({ name: '前端初级认证' }))
    })
  })

  it('can manage certification rules and open record details', async () => {
    vi.mocked(trainingApi.getCertification).mockResolvedValueOnce({
      id: 1, position_id: 1, name: '前端初级认证', code: 'CERT-FE-J', level: 'junior', validity_period_months: 24, is_active: true, created_at: '', updated_at: '', rules: [],
    })
    vi.mocked(trainingApi.listCertificationRules).mockResolvedValueOnce([
      { id: 7, certification_id: 1, rule_type: 'overall_score', rule_config: { min_score: 60 }, created_at: '' },
    ])
    vi.mocked(trainingApi.getCertificationRecord).mockResolvedValueOnce({
      id: 1, certification_id: 1, user_id: 1, assessment_record_id: 5, status: 'pending', created_at: '', updated_at: '',
      certification_name: '前端初级认证', assessment_score: 80,
    })
    render(<MemoryRouter><CertificationTab /></MemoryRouter>)
    await userEvent.click(screen.getByRole('button', { name: '规则' }))
    expect(await screen.findByText('认证规则：前端初级认证')).toBeInTheDocument()
    expect(trainingApi.listCertificationRules).toHaveBeenCalledWith(1)
    await userEvent.click(screen.getAllByRole('button', { name: '关闭' })[0])
    await userEvent.click(screen.getByRole('button', { name: '查看详情' }))

    expect(await screen.findByText('认证记录详情 #1')).toBeInTheDocument()
    expect(trainingApi.getCertificationRecord).toHaveBeenCalledWith(1)
  })
})
