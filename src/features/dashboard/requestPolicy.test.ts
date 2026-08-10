import { describe, expect, it } from 'vitest'
import { allowedDashboardRequests } from './requestPolicy'

describe('dashboard request policy', () => {
  it('keeps learner requests personal and excludes system endpoints', () => {
    const requests = allowedDashboardRequests('learner')
    expect(requests).toEqual(['/dashboard/learner'])
    expect(requests.some((path) => path.includes('/agent') || path.includes('/metrics'))).toBe(
      false,
    )
  })

  it('routes teacher requests through the scoped aggregate endpoint', () => {
    expect(allowedDashboardRequests('teacher')).toEqual(['/dashboard/teacher'])
  })

  it('keeps admin system requests separate from learner and teacher requests', () => {
    expect(allowedDashboardRequests('admin')).toEqual([
      '/report/metrics',
      '/agent/status',
      '/agent/tasks',
    ])
  })
})
