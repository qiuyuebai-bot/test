import { test, expect } from './helpers/auth'

/**
 * E2E 流程 3：Agent 任务 → 实时进度 → 生成资源
 * 覆盖：
 *   - 多智能体可视化页加载
 *   - 启动任务表单可用（学习者选择 + 任务类型 + 启动按钮）
 *   - 任务列表/实时日志区域可见
 *
 * 说明：真实 LLM 调用成本高且不稳定，E2E 仅验证 UI 流转与
 * 控件可用性，不强制等待完整 pipeline 完成。
 */
test.describe('流程3：Agent任务→实时进度→资源生成', () => {
  test('可视化页加载并展示任务启动区', async ({ authedPage: page }) => {
    await page.goto('/multi-agent')

    await expect(page.getByText('多智能体协同决策可视化')).toBeVisible()
    await expect(page.getByText('启动任务').first()).toBeVisible()
    await expect(page.getByText('选择学习者')).toBeVisible()
    await expect(page.getByText('任务类型')).toBeVisible()
  })

  test('选择学习者与任务类型后可点击启动', async ({ authedPage: page }) => {
    await page.goto('/multi-agent')

    await expect(page.getByText('启动任务').first()).toBeVisible()

    const learnerSelect = page.locator('select').first()
    const hasLearners = await learnerSelect.locator('option').count().then((n) => n > 1)

    if (hasLearners) {
      await learnerSelect.selectOption({ index: 1 })

      await page.getByRole('button', { name: /学情诊断/ }).click()

      const startBtn = page.getByRole('button', { name: /启动任务$/ }).first()
      await expect(startBtn).toBeEnabled({ timeout: 10_000 })

      await startBtn.click()

      await expect(page.getByText(/实时协同日志|任务列表|已启动任务/i).first()).toBeVisible({
        timeout: 15_000,
      })
    } else {
      const empty = page.getByText(/暂无|空|还没有|选择学习者并启动/i).first()
      await expect(empty).toBeVisible({ timeout: 10_000 })
    }
  })

  test('刷新按钮可用', async ({ authedPage: page }) => {
    await page.goto('/multi-agent')
    const refreshBtn = page.getByRole('button', { name: /刷新/ }).first()
    await expect(refreshBtn).toBeVisible()
    await refreshBtn.click()
    await expect(page.getByText('多智能体协同决策可视化')).toBeVisible()
  })
})
