import { test, expect } from './helpers/auth'
import path from 'path'

/**
 * E2E 流程 5：企业培训 → 批量导入 → 统计
 * 覆盖：
 *   - 企业培训页加载
 *   - 统计看板（合作企业/培训学员/通过率/平均评分）
 *   - 批量导入弹窗打开 + CSV 上传 + 导入按钮
 */
test.describe('流程5：企业培训→批量导入→统计', () => {
  test('企业培训页加载并展示统计看板', async ({ authedPage: page }) => {
    await page.goto('/enterprise')

    await expect(page.getByText('企业标准化内训')).toBeVisible()

    await expect(page.getByText('合作企业')).toBeVisible()
    await expect(page.getByText('培训学员')).toBeVisible()
    await expect(page.getByText('通过率')).toBeVisible()
    await expect(page.getByText('平均评分')).toBeVisible()
  })

  test('打开批量导入弹窗并支持 CSV 上传', async ({ authedPage: page }) => {
    await page.goto('/enterprise')

    await page.getByRole('button', { name: /批量导入/ }).click()

    await expect(page.getByText('批量导入学员')).toBeVisible({ timeout: 10_000 })

    const csvPath = path.join(__dirname, 'fixtures', 'sample-training.csv')
    const fileInput = page.locator('input[type="file"]').first()

    await fileInput.setInputFiles(csvPath)

    await expect(page.getByText('sample-training.csv')).toBeVisible({ timeout: 5_000 })

    await expect(page.getByRole('button', { name: /开始导入/ })).toBeEnabled()
  })

  test('培训项目搜索框可用', async ({ authedPage: page }) => {
    await page.goto('/enterprise')

    const search = page.getByPlaceholder('搜索培训项目...')
    await search.fill('测试')
    await expect(search).toHaveValue('测试')
  })

  test('新建培训按钮可打开创建弹窗', async ({ authedPage: page }) => {
    await page.goto('/enterprise')

    await page.getByRole('button', { name: /新建培训/ }).click()

    await expect(page.getByText(/创建培训|新建培训项目|企业名称/i).first()).toBeVisible({ timeout: 10_000 })
  })
})
