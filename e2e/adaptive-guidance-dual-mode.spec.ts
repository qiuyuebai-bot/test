import { test, expect } from './helpers/auth'

const learner = {
  id: 901,
  user_id: 1,
  real_name: '双模式测试学习者',
  education_level: '本科',
  major: '计算机科学',
  theoretical_foundation: 60,
  programming_ability: 60,
  algorithm_design: 60,
  system_architecture: 60,
  data_analysis: 60,
  engineering_practice: 60,
  average_ability: 60,
  knowledge_blind_areas: [],
  is_data_anonymized: false,
}

function apiResponse(data: unknown) {
  return JSON.stringify({
    code: 200,
    message: 'ok',
    data,
    timestamp: new Date().toISOString(),
  })
}

async function mockGuidanceBootstrap(page: import('@playwright/test').Page) {
  await page.addInitScript(() => {
    localStorage.removeItem('adaptive-guidance-session:901')
    localStorage.removeItem('adaptive-guidance-exited:901')
  })
  await page.route(/\/api\/v1\/learners(?:\?.*)?$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: apiResponse({ items: [learner], total: 1, page: 1, page_size: 20, total_pages: 1 }),
    })
  })
  await page.route(/\/api\/v1\/tutoring\/questions(?:\?.*)?$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: apiResponse([]),
    })
  })
  await page.route(/\/api\/v1\/tutoring\/recommendations\/\d+$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: apiResponse({
        primary_topic: 'REST API',
        alternatives: [],
        recommended_difficulty: 3,
        reason: '测试推荐',
        source: 'fallback',
      }),
    })
  })
}

test.describe('自适应导学双模式', () => {
  test('逐题模式提交后立即显示判定', async ({ authedPage: page }) => {
    await mockGuidanceBootstrap(page)
    await page.route(/\/api\/v1\/tutoring\/questions\/generate$/, async (route) => {
      const body = route.request().postDataJSON() as Record<string, unknown>
      expect(body).toMatchObject({
        learner_id: 901,
        topic: 'REST API',
        difficulty: 3,
        question_count: 1,
        replace_pending: true,
      })
      expect(body.assessment_mode).toBeUndefined()
      expect(body.session_id).toBeUndefined()
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: apiResponse({
          questions: [
            {
              id: 'adaptive-e2e-1',
              type: 'single',
              topic: 'REST API',
              question: '逐题模式题目',
              options: ['Option A', 'Option B'],
              difficulty: 3,
              generation_method: 'deterministic_fallback',
            },
          ],
          generation_method: 'deterministic_fallback',
        }),
      })
    })
    await page.route(/\/api\/v1\/tutoring\/answer$/, async (route) => {
      const body = route.request().postDataJSON() as Record<string, unknown>
      expect(body).toMatchObject({
        learner_id: 901,
        question_id: 'adaptive-e2e-1',
        user_answer: 'A',
      })
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: apiResponse({
          is_correct: true,
          score: 100,
          agent_decision: { decision: 'advance' },
        }),
      })
    })

    await page.goto('/guidance')
    await page.getByText('高级设置', { exact: true }).click()
    await expect(page.getByLabel('主题关键词')).toBeVisible()
    await page.getByLabel('主题关键词').fill('REST API')
    await page.getByLabel('目标难度（1–5，可留空）').fill('3')
    await page.getByLabel('题量（1–10）').fill('1')
    await page.getByRole('button', { name: '生成导学题目' }).click()

    await expect(page.getByText('逐题模式题目')).toBeVisible()
    await page.getByRole('button', { name: /Option A/ }).click()
    await page.getByRole('button', { name: '提交答案' }).click()
    await expect(page.getByText('判定结果：回答正确', { exact: true })).toBeVisible()
  })

  test('整卷模式一次生成、自由切题并统一提交结果', async ({ authedPage: page }) => {
    await mockGuidanceBootstrap(page)
    let sessionId = ''
    await page.route(/\/api\/v1\/tutoring\/questions\/generate$/, async (route) => {
      const body = route.request().postDataJSON() as Record<string, unknown>
      sessionId = String(body.session_id)
      expect(body).toMatchObject({
        learner_id: 901,
        topic: 'REST API',
        difficulty: 3,
        question_count: 2,
        replace_pending: true,
        assessment_mode: 'batch_practice',
      })
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: apiResponse({
          questions: [
            {
              id: 'batch-e2e-1',
              type: 'single',
              topic: 'REST API',
              question: '整卷题目一',
              options: ['Option A', 'Option B'],
              difficulty: 3,
              generation_method: 'deterministic_fallback',
              assessment_mode: 'batch_practice',
              session_id: sessionId,
            },
            {
              id: 'batch-e2e-2',
              type: 'single',
              topic: 'REST API',
              question: '整卷题目二',
              options: ['Option A', 'Option B'],
              difficulty: 3,
              generation_method: 'deterministic_fallback',
              assessment_mode: 'batch_practice',
              session_id: sessionId,
            },
          ],
          generation_method: 'deterministic_fallback',
        }),
      })
    })
    await page.route(/\/api\/v1\/tutoring\/answers\/batch$/, async (route) => {
      const body = route.request().postDataJSON() as Record<string, unknown>
      expect(body).toMatchObject({ learner_id: 901, session_id: sessionId })
      expect(body.answers).toEqual([
        { question_id: 'batch-e2e-1', user_answer: 'A', sequence_index: 1 },
        { question_id: 'batch-e2e-2', user_answer: 'B', sequence_index: 2 },
      ])
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: apiResponse({
          session_id: sessionId,
          total: 2,
          correct_count: 1,
          score: 50,
          dimension_summary: [
            { dimension: 'algorithm_design', answered_count: 2, correct_count: 1, score: 50 },
          ],
          questions: [
            {
              question_id: 'batch-e2e-1',
              is_correct: true,
              score: 100,
              user_answer: ['A'],
              correct_answer: ['A'],
              explanation: '整卷第一题解析',
              knowledge_points: [],
            },
            {
              question_id: 'batch-e2e-2',
              is_correct: false,
              score: 0,
              user_answer: ['B'],
              correct_answer: ['A'],
              explanation: '整卷第二题解析',
              knowledge_points: [],
            },
          ],
        }),
      })
    })

    await page.goto('/guidance')
    await expect(page.getByRole('button', { name: /整卷练习/ })).toBeVisible()
    await page.getByRole('button', { name: /整卷练习/ }).click()
    await page.getByText('高级设置', { exact: true }).click()
    await page.getByLabel('主题关键词').fill('REST API')
    await page.getByLabel('目标难度（1–5，可留空）').fill('3')
    await page.getByLabel('题量（1–10）').fill('2')
    await page.getByRole('button', { name: '生成导学题目' }).click()

    await expect(page.getByText('整卷题目一')).toBeVisible()
    await page.getByRole('button', { name: /Option A/ }).click()
    await page.getByRole('button', { name: '下一题' }).click()
    await expect(page.getByText('整卷题目二')).toBeVisible()
    await page.getByRole('button', { name: /Option B/ }).click()
    await page.getByRole('button', { name: '提交整卷' }).click()

    await expect(page.getByText('整卷练习结果')).toBeVisible()
    await expect(page.getByText('整卷第一题解析')).toBeVisible()
  })
})
