import { defineConfig, devices } from '@playwright/test'

// Visual baselines are rendered in the official Playwright Linux image, locally and in CI,
// so screenshots match pixel for pixel (see README: "Quality gates").
export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  fullyParallel: true,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  expect: { toHaveScreenshot: { maxDiffPixelRatio: 0.002, animations: 'disabled' } },
  snapshotPathTemplate: '{testDir}/__screenshots__/{testFilePath}/{arg}-{projectName}{ext}',
  use: { baseURL: 'http://127.0.0.1:4173', deviceScaleFactor: 1 },
  projects: [
    { name: 'phone', use: { ...devices['Desktop Chrome'], viewport: { width: 375, height: 812 }, deviceScaleFactor: 1 } },
    { name: 'tablet', use: { ...devices['Desktop Chrome'], viewport: { width: 768, height: 1024 }, deviceScaleFactor: 1 } },
  ],
  webServer: {
    command: 'npx vite preview --host 127.0.0.1 --port 4173 --strictPort',
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: !process.env.CI,
  },
})
