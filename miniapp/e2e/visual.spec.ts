// Visual regression: every screen at phone and tablet width, dark and light.
// Baselines come from the Playwright Linux image (npm run test:visual:update).
import { expect, test } from '@playwright/test'
import { mockTelegram, type MockOptions } from './mock'

const screens: { name: string; opts?: MockOptions; tab?: string; wait: string }[] = [
  { name: 'onboarding', opts: { storage: {} }, wait: 'Welcome to cpstands' },
  { name: 'home', wait: 'My rating' },
  { name: 'contests', tab: 'Contests', wait: 'Upcoming' },
  { name: 'standings', tab: 'Standings', wait: 'Codeforces Round 1133 (Div. 1)' },
  { name: 'friends', tab: 'Friends', wait: 'Benq' },
  { name: 'me', tab: 'Me', wait: 'My handle' },
  { name: 'profile', opts: { startParam: 'profile_tourist' }, wait: 'Recent submissions' },
  { name: 'compare', opts: { startParam: 'compare_tourist-jiangly-Petr' }, wait: 'Head to head' },
  { name: 'home-light', opts: { storage: { theme: 'light' } }, wait: 'My rating' },
  { name: 'profile-light', opts: { startParam: 'profile_tourist', storage: { theme: 'light' } }, wait: 'Recent submissions' },
]

for (const s of screens) {
  test(`screen ${s.name}`, async ({ page }) => {
    await mockTelegram(page, s.opts)
    if (s.name === 'onboarding') {
      await page.addInitScript(() => {
        delete (window as unknown as { __tg: { store: Record<string, string> } }).__tg.store.me
      })
    }
    await page.goto('/')
    if (s.tab) await page.getByRole('navigation').getByRole('button', { name: s.tab, exact: true }).click()
    await expect(page.getByText(s.wait).first()).toBeVisible()
    await page.evaluate(() => document.fonts.ready)
    await page.waitForTimeout(300) // charts measure their container once
    await expect(page).toHaveScreenshot(`${s.name}.png`, { fullPage: true })
  })
}
