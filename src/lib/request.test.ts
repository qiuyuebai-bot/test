import { describe, expect, it, vi } from 'vitest'
import { ApiError, NetworkError, http } from './request'

function response(status: number, contentType: string, body: string): Response {
  return {
    status,
    ok: status >= 200 && status < 300,
    headers: { get: (name: string) => name === 'content-type' ? contentType : null } as Headers,
    text: async () => body,
  } as Response
}

describe('request server error classification', () => {
  it('treats a non-JSON proxy 500 as an unavailable backend', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(500, 'text/plain', '')))

    await expect(http.post('/auth/login', { username: 'probe', password: 'probe' }))
      .rejects.toBeInstanceOf(NetworkError)
  })

  it('preserves a structured backend 500 as an API error', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(response(500, 'application/json', JSON.stringify({
        code: 500,
        message: 'backend failure',
        data: null,
        timestamp: '',
      }))),
    )

    const error = await http.post('/auth/login', { username: 'probe', password: 'probe' })
      .catch((err: unknown) => err)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).code).toBe(500)
  })
})
