import { test, expect } from '@playwright/test'

test.describe('production preview smoke', () => {
  for (const viewport of [
    { name: 'desktop', width: 1440, height: 900 },
    { name: 'mobile', width: 375, height: 812 },
  ]) {
    test(`${viewport.name} renders the application shell`, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height })

      const pageErrors: string[] = []
      const brokenAssets: string[] = []
      page.on('pageerror', (error) => pageErrors.push(error.message))
      page.on('response', (response) => {
        const resourceType = response.request().resourceType()
        if (['document', 'script', 'stylesheet'].includes(resourceType) && response.status() >= 400) {
          brokenAssets.push(`${response.status()} ${response.url()}`)
        }
      })

      const response = await page.goto('/', { waitUntil: 'networkidle' })

      expect(response?.ok()).toBeTruthy()
      await expect(page.locator('#root')).not.toBeEmpty()
      expect(pageErrors).toEqual([])
      expect(brokenAssets).toEqual([])
    })
  }
})
