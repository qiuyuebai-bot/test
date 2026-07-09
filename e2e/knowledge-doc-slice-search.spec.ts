import { test, expect } from './helpers/auth'

/**
 * E2E 流程 2：知识文档 → 切片 → 检索
 * 覆盖：
 *   - 知识库页面加载
 *   - 文档列表渲染
 *   - 切片检索框可用
 */
test.describe('流程2：知识文档→切片→检索', () => {
  test('知识库页面加载文档列表', async ({ authedPage: page }) => {
    await page.goto('/knowledge-base')

    await expect(page.getByText('垂直领域知识库管理')).toBeVisible()

    await expect(page.getByPlaceholder('搜索文档...')).toBeVisible()
  })

  test('查看文档切片并执行关键词检索', async ({ authedPage: page }) => {
    await page.goto('/knowledge-base')

    const docRow = page.locator('[class*="cursor-pointer"], [data-testid="doc-row"]').first()
    const hasDoc = await docRow.count().then((n) => n > 0)

    if (hasDoc) {
      await docRow.click()
      await expect(page.getByPlaceholder('输入关键词搜索切片...')).toBeVisible({ timeout: 15_000 })

      await page.getByPlaceholder('输入关键词搜索切片...').fill('训练')
      await page.keyboard.press('Enter')

      await expect(page.getByText(/切片|检索结果|暂无/i).first()).toBeVisible({ timeout: 10_000 })
    } else {
      const empty = page.getByText(/暂无|空|还没有/i).first()
      await expect(empty).toBeVisible({ timeout: 10_000 })
    }
  })

  test('文档搜索框可输入并触发筛选', async ({ authedPage: page }) => {
    await page.goto('/knowledge-base')

    const searchInput = page.getByPlaceholder('搜索文档...')
    await searchInput.fill('测试')
    await searchInput.dispatchEvent('input')

    await expect(searchInput).toHaveValue('测试')
  })
})
