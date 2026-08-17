import { test, expect } from '@playwright/test'

interface RegisterResponse {
  code: number
  data: {
    user_id: number
    username: string
    role: string
    access_token: string
    refresh_token: string
  }
}

test.describe('career training teacher maintenance', () => {
  test('teacher can create and edit a position from the UI', async ({ page }) => {
    const username = `e2e_teacher_${Date.now()}`
    const password = 'Test1234'
    const positionCode = `E2E-${Date.now()}`
    const positionName = `E2E Frontend Position ${Date.now()}`
    const updatedPositionName = `${positionName} Updated`
    let createdPositionId: number | undefined

    const registerResponse = await page.request.post('/api/v1/auth/register', {
      data: { username, password, role: 'teacher' },
    })
    expect(registerResponse.ok()).toBeTruthy()
    const registerBody = await registerResponse.json() as RegisterResponse
    expect(registerBody.code).toBe(200)

    await page.addInitScript(([token, refreshToken, userInfo]) => {
      localStorage.setItem('access_token', token)
      localStorage.setItem('refresh_token', refreshToken)
      localStorage.setItem('user_info', userInfo)
    }, [
      registerBody.data.access_token,
      registerBody.data.refresh_token,
      JSON.stringify({
        user_id: registerBody.data.user_id,
        username: registerBody.data.username,
        role: registerBody.data.role,
      }),
    ])

    try {
      await page.goto('/career-training/position')
      await expect(page.getByRole('main').getByRole('heading', { name: '就业培训' })).toBeVisible()
      await expect(page.getByRole('button', { name: '新增岗位' })).toBeVisible()

      await page.getByRole('button', { name: '新增岗位' }).click()
      const createDialog = page.getByRole('dialog').last()
      const createInputs = createDialog.locator('input')
      await createInputs.nth(0).fill(positionCode)
      await createInputs.nth(1).fill(positionName)

      const createResponsePromise = page.waitForResponse((response) => (
        response.url().includes('/api/v1/positions')
        && response.request().method() === 'POST'
      ))
      await createDialog.getByRole('button', { name: '创建', exact: true }).click()
      const createResponse = await createResponsePromise
      const createBody = await createResponse.json() as { data?: { id?: number } }
      createdPositionId = createBody.data?.id

      await expect(page.getByText(positionName, { exact: true })).toBeVisible()
      await page.getByText(positionName, { exact: true }).click()

      const detailDialog = page.getByRole('dialog').last()
      await detailDialog.getByRole('button', { name: '编辑岗位', exact: true }).click()
      const editDialog = page.getByRole('dialog').last()
      await editDialog.locator('input').first().fill(updatedPositionName)
      await editDialog.getByRole('button', { name: '保存', exact: true }).click()

      await expect(
        page.getByRole('dialog').last().getByRole('heading', { name: updatedPositionName, exact: true }),
      ).toBeVisible()
    } finally {
      if (createdPositionId) {
        await page.request.delete(`/api/v1/positions/${createdPositionId}`, {
          headers: { Authorization: `Bearer ${registerBody.data.access_token}` },
        })
      }
    }
  })
})
