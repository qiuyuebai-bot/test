import { test as base, type Page, expect } from '@playwright/test'

/**
 * E2E 测试共享辅助
 * - 通过 API 登录获取 Token，写入 localStorage，跳过登录页
 * - 避免每个流程都走 UI 登录（提升稳定性与速度）
 */

const API_BASE = '/api/v1'

export interface TestUser {
  username: string
  password: string
}

export const ADMIN_USER: TestUser = {
  username: 'admin',
  password: 'admin123',
}

interface LoginResponse {
  code: number
  message: string
  data: {
    user_id: number
    username: string
    role: string
    access_token: string
    refresh_token: string
  }
}

async function loginViaApi(page: Page, user: TestUser): Promise<LoginResponse> {
  const res = await page.request.post(`${API_BASE}/auth/login`, {
    data: { username: user.username, password: user.password },
    timeout: 30_000,
  })
  expect(res.ok(), `登录 API 应返回 2xx，实际：${res.status()}`).toBeTruthy()
  const body = (await res.json()) as LoginResponse
  expect(body.code, `登录业务码应=0，实际：${body.code}`).toBe(0)
  return body
}

async function seedAuthInWindow(page: Page, user: TestUser = ADMIN_USER) {
  const body = await loginViaApi(page, user)
  await page.addInitScript(
    ([token, refresh, info]) => {
      localStorage.setItem('access_token', token)
      localStorage.setItem('refresh_token', refresh)
      localStorage.setItem('user_info', info)
    },
    [
      body.data.access_token,
      body.data.refresh_token,
      JSON.stringify({
        user_id: body.data.user_id,
        username: body.data.username,
        role: body.data.role,
      }),
    ],
  )
}

export const test = base.extend<{ authedPage: Page }>({
  authedPage: async ({ page }, use) => {
    await seedAuthInWindow(page)
    await page.goto('/')
    await use(page)
  },
})

export { expect }
