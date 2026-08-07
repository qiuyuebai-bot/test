import { defineConfig, devices } from '@playwright/test'

const e2eBaseURL = process.env.E2E_BASE_URL || 'http://127.0.0.1:5173'
const customWebServerCommand = process.env.E2E_WEB_SERVER_COMMAND

/**
 * Playwright E2E 配置
 * 6 条核心业务流程：登录画像、知识检索、Agent 协同、自适应导学、企业培训、健康指标
 *
 * 运行方式：
 *   npx playwright test              # 全量运行
 *   npx playwright test --ui         # 交互式 UI 模式
 *   npx playwright test --reporter=line
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: [
    ['list'],
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
  ],
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  use: {
    baseURL: e2eBaseURL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
    // 统一中文环境
    locale: 'zh-CN',
    timezoneId: 'Asia/Shanghai',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: customWebServerCommand
    ? {
        command: customWebServerCommand,
        url: e2eBaseURL,
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
        retries: 2,
      }
    : [
        {
          command: 'npm run start:backend',
          url: 'http://127.0.0.1:8000/api/v1/health',
          reuseExistingServer: !process.env.CI,
          timeout: 120_000,
          retries: 2,
        },
        {
          command: 'npm run serve',
          url: e2eBaseURL,
          reuseExistingServer: !process.env.CI,
          timeout: 120_000,
          retries: 2,
        },
      ],
})
