import { test, expect } from './helpers/auth'

/**
 * E2E 流程 4：答题 → 自适应导学 → 推荐
 * 覆盖：
 *   - 自适应导学页加载
 *   - 题目与选项渲染
 *   - 选择答案 → 提交 → 显示判定/推荐
 *
 * 说明：题目数据由后端动态生成，E2E 在题目存在时验证交互闭环，
 * 题目缺失时验证空态降级。
 */
test.describe('流程4：答题→自适应导学→推荐', () => {
  test('自适应导学页加载并展示题目区', async ({ authedPage: page }) => {
    await page.goto('/guidance')

    await expect(page.getByText(/动态自适应导学|开始一轮自适应导学/).first()).toBeVisible()

    const questionCard = page.locator('text=/单选题|多选题/').first()
    const hasQuestion = await questionCard.count().then((n) => n > 0)

    if (hasQuestion) {
      await expect(page.getByText(/共\s*\d+\s*题/)).toBeVisible()
    } else {
      await expect(page.getByLabel('主题关键词')).toBeVisible({ timeout: 15_000 })
      await expect(page.getByLabel('目标难度（1–5，可留空）')).toBeVisible()
      await expect(page.getByLabel('题量（1–10）')).toBeVisible()
    }
  })

  test('选择答案后提交按钮可用', async ({ authedPage: page }) => {
    await page.goto('/guidance')

    await expect(page.getByText(/动态自适应导学|开始一轮自适应导学/).first()).toBeVisible()

    const hasOptions = await page.getByText(/单选题|多选题/).count().then((n) => n > 0)

    if (hasOptions) {
      const firstOption = page.locator('button.w-full.p-4.rounded-xl').first()
      if (await firstOption.count()) {
        await firstOption.click()

        const submitBtn = page.getByRole('button', { name: /提交答案/ })
        await expect(submitBtn).toBeEnabled({ timeout: 5_000 })
      }
    }
  })

  test('提交答案后展示 Agent 决策或判定', async ({ authedPage: page }) => {
    await page.goto('/guidance')

    await expect(page.getByText(/动态自适应导学|开始一轮自适应导学/).first()).toBeVisible()

    const hasQuestion = await page.getByText(/单选题|多选题/).count().then((n) => n > 0)
    if (!hasQuestion) {
      const empty = page.getByText(/暂无|空|还没有/i).first()
      await expect(empty).toBeVisible({ timeout: 15_000 })
      return
    }

    const firstOption = page.locator('button.w-full.p-4.rounded-xl').first()
    await expect(firstOption).toBeVisible({ timeout: 10_000 })
    await firstOption.click()

    const submitBtn = page.getByRole('button', { name: /提交答案/ })
    await submitBtn.click()

    await expect
      .poll(async () => page.getByText(/决策置信度|Agent 决策|答题正确|答题错误|下一题|重新开始/i).count(), {
        timeout: 30_000,
      })
      .toBeGreaterThan(0)
  })

  test('空状态可配置主题并生成题目', async ({ authedPage: page }) => {
    await page.route(/\/api\/v1\/tutoring\/questions\?.*/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          code: 200,
          message: 'ok',
          data: [],
          timestamp: new Date().toISOString(),
        }),
      })
    })

    await page.route(/\/api\/v1\/tutoring\/questions\/generate$/, async (route) => {
      const body = route.request().postDataJSON() as Record<string, unknown>
      expect(body).toMatchObject({
        learner_id: expect.any(Number),
        topic: 'REST API',
        difficulty: 4,
        question_count: 5,
        replace_pending: true,
      })
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          code: 200,
          message: 'ok',
          data: {
            questions: [{
              id: 'e2e-question-1',
              type: 'single',
              topic: 'REST API',
              question: 'REST API 的核心约束是什么？',
              options: ['无状态通信', '只能使用 GET'],
              difficulty: 4,
              generation_method: 'deterministic_fallback',
            }],
            generation_method: 'deterministic_fallback',
          },
          timestamp: new Date().toISOString(),
        }),
      })
    })

    await page.goto('/guidance')
    await expect(page.getByLabel('主题关键词')).toBeVisible({ timeout: 15_000 })
    await page.getByLabel('主题关键词').fill('REST API')
    await page.getByLabel('目标难度（1–5，可留空）').fill('4')
    await page.getByLabel('题量（1–10）').fill('5')
    await page.getByRole('button', { name: '生成导学题目' }).click()

    await expect(page.getByText('REST API 的核心约束是什么？')).toBeVisible({ timeout: 15_000 })
    await expect(page.getByText('0/5')).toBeVisible()
    await expect(page.getByText('题目来源：本地兜底题')).toBeVisible()
    await page.getByRole('button', { name: '退出本轮' }).click()
    await expect(page.getByLabel('主题关键词')).toHaveValue('REST API')
  })
})
