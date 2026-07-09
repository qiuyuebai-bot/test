import { test, expect } from './helpers/auth'

/**
 * E2E 流程 6：健康检查 → 指标 → 报告导出
 * 覆盖：
 *   - 后端健康检查 API（liveness / readiness）
 *   - 指标看板页面加载
 *   - 学习报告页面加载（聚合报告数据）
 *
 * 说明：报告导出在当前版本通过页面展示聚合数据，
 * 后端 /report/learner/{id} 接口返回 JSON 报告。
 */
test.describe('流程6：健康检查→指标→报告', () => {
  test('后端健康检查接口可用', async ({ page }) => {
    const liveRes = await page.request.get('/api/v1/health')
    expect(liveRes.ok()).toBeTruthy()
    const liveBody = await liveRes.json()
    expect(liveBody.code).toBe(200)
    expect(liveBody.data.status).toBe('alive')

    const readyRes = await page.request.get('/api/v1/health/ready')
    expect(readyRes.ok()).toBeTruthy()
    const readyBody = await readyRes.json()
    expect(readyBody.data.status).toBe('ready')
  })

  test('系统信息根接口返回应用元数据', async ({ page }) => {
    const res = await page.request.get('/api/v1/info')
    expect(res.ok()).toBeTruthy()
    const body = await res.json()
    expect(body.data.name).toBeTruthy()
    expect(body.data.version).toBeTruthy()
  })

  test('指标看板页加载并展示核心指标', async ({ authedPage: page }) => {
    await page.goto('/metrics')

    await expect(page.getByText(/指标|看板|监控/i).first()).toBeVisible()

    const metricLabel = page.getByText('幻觉率').or(page.getByText('知识覆盖率')).or(page.getByText('资源匹配度'))
    await expect(metricLabel.first()).toBeVisible({ timeout: 20_000 })
  })

  test('学习报告页加载并展示报告区域', async ({ authedPage: page }) => {
    await page.goto('/report')

    const reportTitle = page.getByText(/学习报告|报告|能力雷达/i).first()
    await expect(reportTitle).toBeVisible({ timeout: 20_000 })

    const learnerSelect = page.locator('select').first()
    const hasLearners = await learnerSelect.locator('option').count().then((n) => n > 1)

    if (hasLearners) {
      await learnerSelect.selectOption({ index: 1 })

      await expect(page.getByText(/核心指标|能力雷达|薄弱知识点|学习路径/i).first()).toBeVisible({
        timeout: 25_000,
      })
    } else {
      await expect(page.getByText(/暂无|空|还没有/i).first()).toBeVisible({ timeout: 15_000 })
    }
  })

  test('系统指标 API 返回结构化数据', async ({ page }) => {
    const res = await page.request.get('/api/v1/metrics')
    expect(res.ok()).toBeTruthy()
    const body = await res.json()
    expect(body.code).toBe(0)
    expect(body.data).toBeTruthy()
  })
})
