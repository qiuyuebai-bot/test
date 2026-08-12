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
    applyCertification: vi.fn(),
    approveCertification: vi.fn(),
    rejectCertification: vi.fn(),
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
      fetchCertifications: vi.fn(),
      fetchCertificationRecords: vi.fn(),
      fetchAssessmentRecords: vi.fn(),
      user: { id: 1, username: 'admin', role: 'admin' },
    })
  })

  it('渲染认证列表与申请记录', () => {
    render(<MemoryRouter><CertificationTab /></MemoryRouter>)
    expect(screen.getByText('前端初级认证')).toBeInTheDocument()
    expect(screen.getByText('待审核')).toBeInTheDocument()
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
})
