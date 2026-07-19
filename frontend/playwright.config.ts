import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false, // 串行执行避免后端状态冲突
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1, // 单线程避免冲突
  reporter: 'list',
  timeout: 60000,
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'off',
    launchOptions: {
      executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH || undefined,
      args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
    },
  },
  projects: [
    {
      name: 'robustness',
      testMatch: /robustness\.spec\.ts/,
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'combo-regression',
      testMatch: /combo-regression\.spec\.ts/,
      dependencies: ['robustness'],
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'user-journey',
      testMatch: /user-journey\.spec\.ts/,
      dependencies: ['combo-regression'],
      use: { ...devices['Desktop Chrome'] },
    },
    {
      // 重度：长时间反复启停会话（默认 15 轮，数分钟），仅在显式选择时运行
      name: 'long-session',
      testMatch: /long-session\.spec\.ts/,
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'other-e2e',
      testIgnore: /(robustness|combo-regression|user-journey|long-session)\.spec\.ts/,
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  // 使用已运行的 Docker 服务，不自动启动
  // webServer: {
  //   command: 'npm run dev',
  //   url: 'http://localhost:5173',
  //   reuseExistingServer: true,
  //   timeout: 120 * 1000,
  // },
});
