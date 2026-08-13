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

  it('generatePlan 调用 POST /training-enrollments/:id/generate-plan', async () => {
    vi.mocked(http.post).mockResolvedValueOnce({ id: 1 })
    await trainingApi.generatePlan(7, { assessment_record_id: 9 })
    expect(http.post).toHaveBeenCalledWith('/training-enrollments/7/generate-plan', { assessment_record_id: 9 }, { timeout: 120000, silent: true })
  })
})
