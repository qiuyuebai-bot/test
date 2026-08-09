import { test, expect } from './helpers/auth'

/**
 * E2E 流程 1：登录 → 学习者画像 → 能力雷达
 * 覆盖：
 *   - 登录页 UI 登录（验证表单与跳转）
 *   - 学习者画像列表加载
 *   - 能力雷达图渲染（SVG radar 出现）
 */
test.describe('流程1：登录→学习者画像→能力雷达', () => {
  test('通过 UI 完成登录并进入仪表盘', async ({ page }) => {
    await page.goto('/login')

    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()

    await page.getByPlaceholder('请输入用户名').fill('admin')
    await page.getByPlaceholder('请输入密码').fill('admin123')
    await page.locator('form').getByRole('button', { name: '登录' }).click()

    await expect(page).toHaveURL(/\/dashboard/)

    await expect(page.getByText(/多智能体协同|学习者|知识/i).first()).toBeVisible()
  })

  test('学习者画像页加载列表并渲染能力雷达', async ({ authedPage: page }) => {
    await page.goto('/profile')

    await expect(page.getByRole('heading', { name: /学习者画像/ })).toBeVisible()

    await expect(page.getByPlaceholder(/搜索学习者/)).toBeVisible()

    const radar = page.locator('.recharts-surface').first()
    await expect(radar).toBeVisible({ timeout: 20_000 })
  })

  test('学习者注册完成引导后只读取自己的画像', async ({ page }) => {
    const username = `e2e_learner_${Date.now()}`
    const registerResponse = await page.request.post('/api/v1/auth/register', {
      data: { username, password: 'Test1234', role: 'learner' },
    })
    expect(registerResponse.ok()).toBeTruthy()
    const body = await registerResponse.json() as {
      data: {
        user_id: number
        username: string
        role: string
        access_token: string
        refresh_token: string
      }
    }

    await page.addInitScript(([token, refreshToken, userInfo]) => {
      localStorage.setItem('access_token', token)
      localStorage.setItem('refresh_token', refreshToken)
      localStorage.setItem('user_info', userInfo)
    }, [
      body.data.access_token,
      body.data.refresh_token,
      JSON.stringify({ user_id: body.data.user_id, username: body.data.username, role: body.data.role }),
    ])

    const learnerResponses: number[] = []
    page.on('response', (response) => {
      if (response.url().includes('/api/v1/learners')) learnerResponses.push(response.status())
    })

    await page.goto('/onboarding/name')
    await page.getByLabel('称呼').fill('E2E学习者')
    await page.getByRole('button', { name: '进入' }).click()
    await expect(page).toHaveURL(/\/dashboard/)

    await page.goto('/profile')
    await expect(page.getByRole('heading', { name: 'E2E学习者' }).first()).toBeVisible({ timeout: 20_000 })
    expect(learnerResponses).not.toContain(403)
  })

  test('未登录访问受保护路由应重定向到登录页', async ({ page }) => {
    await page.goto('/profile')
    await expect(page).toHaveURL(/\/login/)
  })
})
