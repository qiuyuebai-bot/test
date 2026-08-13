import { describe, expect, it, vi, beforeEach } from 'vitest'

vi.mock('../lib/request', () => ({
  http: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
  PagedData: {} as never,
}))

import { http } from '../lib/request'
import { trainingApi } from './training'

describe('trainingApi', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('listPositions 调用 /positions', async () => {
    vi.mocked(http.get).mockResolvedValueOnce({ items: [], total: 0, page: 1, pageSize: 20, totalPages: 0 })
    await trainingApi.listPositions({ page: 1, page_size: 20 })
    expect(http.get).toHaveBeenCalledWith('/positions', { page: 1, page_size: 20 })
  })

  it('createPosition 调用 POST /positions', async () => {
    vi.mocked(http.post).mockResolvedValueOnce({ id: 1 })
    await trainingApi.createPosition({ code: 'FE-001', name: '前端工程师' })
    expect(http.post).toHaveBeenCalledWith('/positions', { code: 'FE-001', name: '前端工程师' })
  })

  it('enrollProject 调用 POST /training-projects/:id/enroll', async () => {
    vi.mocked(http.post).mockResolvedValueOnce({ id: 1 })
    await trainingApi.enrollProject(5, { learner_id: 3 })
    expect(http.post).toHaveBeenCalledWith('/training-projects/5/enroll', { learner_id: 3 })
  })

  it('getEnrollment 查询报名状态而不触发报名', async () => {
    vi.mocked(http.get).mockResolvedValueOnce({ id: 7 })
    await trainingApi.getEnrollment(5, 3)
    expect(http.get).toHaveBeenCalledWith('/training-projects/5/enrollment', { learner_id: 3 })
  })

  it('generatePlan 调用 POST /training-enrollments/:id/generate-plan', async () => {
    vi.mocked(http.post).mockResolvedValueOnce({ id: 1 })
    await trainingApi.generatePlan(7, { assessment_record_id: 9 })
    expect(http.post).toHaveBeenCalledWith('/training-enrollments/7/generate-plan', { assessment_record_id: 9 }, { timeout: 120000, silent: true })
  })

  it('addCertificationRule 调用认证规则接口', async () => {
    vi.mocked(http.post).mockResolvedValueOnce({ id: 1 })
    await trainingApi.addCertificationRule({
      certification_id: 2,
      rule_type: 'overall_score',
      rule_config: { min_score: 80 },
    })
    expect(http.post).toHaveBeenCalledWith('/certifications/rules', {
      certification_id: 2,
      rule_type: 'overall_score',
      rule_config: { min_score: 80 },
    })
  })

  it('applyCertification 传递学习者与评估记录', async () => {
    vi.mocked(http.post).mockResolvedValueOnce({ id: 1 })
    await trainingApi.applyCertification({
      certification_id: 2,
      assessment_record_id: 9,
      learner_id: 7,
    })
    expect(http.post).toHaveBeenCalledWith('/certifications/apply', {
      certification_id: 2,
      assessment_record_id: 9,
      learner_id: 7,
    })
  })

  it('listCertificationRecords 支持按学习者筛选', async () => {
    vi.mocked(http.get).mockResolvedValueOnce({ items: [], total: 0 })
    await trainingApi.listCertificationRecords({ learner_id: 7 })
    expect(http.get).toHaveBeenCalledWith('/certifications/records/list', {
      page: 1,
      page_size: 20,
      status: undefined,
      user_id: undefined,
      learner_id: 7,
    })
  })

  it('revokeCertification 调用撤销接口', async () => {
    vi.mocked(http.post).mockResolvedValueOnce({ id: 1 })
    await trainingApi.revokeCertification(1, { comment: '撤销原因' })
    expect(http.post).toHaveBeenCalledWith('/certifications/records/1/revoke', { comment: '撤销原因' })
  })

  it('verifyCertification 对证书编号进行编码后查询', async () => {
    vi.mocked(http.get).mockResolvedValueOnce({ certificate_number: 'CERT/001', is_valid: true })
    await trainingApi.verifyCertification('CERT/001')
    expect(http.get).toHaveBeenCalledWith('/certifications/verify/CERT%2F001')
  })
})
