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

    await expect(page.getByText('领域知识个性化生成系统')).toBeVisible()

    await page.getByPlaceholder('请输入用户名').fill('admin')
    await page.getByPlaceholder('请输入密码').fill('admin123')
    await page.getByRole('button', { name: /登\s*录/ }).click()

    await expect(page).toHaveURL(/\/dashboard/)

    await expect(page.getByText(/多智能体协同|学习者|知识/i).first()).toBeVisible()
  })

  test('学习者画像页加载列表并渲染能力雷达', async ({ authedPage: page }) => {
    await page.goto('/profile')

    await expect(page.getByText(/学习者|画像|能力/i)).toBeVisible()

    await expect(page.getByPlaceholder(/搜索学习者/)).toBeVisible()

    const radar = page.locator('.recharts-surface').first()
    await expect(radar).toBeVisible({ timeout: 20_000 })
  })

  test('未登录访问受保护路由应重定向到登录页', async ({ page }) => {
    await page.goto('/profile')
    await expect(page).toHaveURL(/\/login/)
  })
})
