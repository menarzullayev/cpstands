// Behaviour: navigation, deep links, Telegram's Back button, friends, settings.
import { expect, test } from '@playwright/test'
import { backVisible, mockTelegram, pressBack } from './mock'

test('first launch asks for the handle, and skipping lands on Home', async ({ page }) => {
  await mockTelegram(page, { storage: { me: '' }, noFriends: true })
  // An empty stored value means "skipped"; a missing one means "never asked".
  await page.addInitScript(() => {
    const tg = (window as unknown as { __tg: { store: Record<string, string> } }).__tg
    delete tg.store.me
  })
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Welcome to cpstands' })).toBeVisible()
  await page.getByRole('button', { name: 'I don’t have one yet' }).click()
  await expect(page.getByRole('button', { name: 'Home' })).toHaveAttribute('aria-current', 'page')
})

test('onboarding saves the handle Codeforces confirms', async ({ page }) => {
  await mockTelegram(page)
  await page.addInitScript(() => {
    delete (window as unknown as { __tg: { store: Record<string, string> } }).__tg.store.me
  })
  await page.goto('/')
  await page.getByLabel(/Codeforces handle/).fill('tourist')
  await page.getByRole('button', { name: 'Continue' }).click()
  await expect(page.getByText('My rating')).toBeVisible()
  expect(await page.evaluate(() => (window as unknown as { __tg: { store: Record<string, string> } }).__tg.store.me)).toBe('tourist')
})

test('tabs switch screens', async ({ page }) => {
  await mockTelegram(page)
  await page.goto('/')
  for (const [tab, text] of [
    ['Contests', 'Upcoming'],
    ['Standings', 'Codeforces Round 1133 (Div. 1)'],
    ['Friends', 'Benq'],
    ['Me', 'My handle'],
  ] as const) {
    await page.getByRole('navigation').getByRole('button', { name: tab, exact: true }).click()
    await expect(page.getByText(text).first()).toBeVisible()
  }
})

test('a deep link opens a profile and Back returns to Home', async ({ page }) => {
  await mockTelegram(page, { startParam: 'profile_tourist' })
  await page.goto('/')
  await expect(page.getByText('Rating history')).toBeVisible()
  expect(await backVisible(page)).toBe(true)
  await pressBack(page)
  await expect(page.getByText('My rating')).toBeVisible()
  expect(await backVisible(page)).toBe(false)
})

test('an unknown deep link falls back to Home', async ({ page }) => {
  await mockTelegram(page, { startParam: 'profile_bad handle!' })
  await page.goto('/')
  await expect(page.getByText('My rating')).toBeVisible()
})

test('a compare link opens all handles on one chart', async ({ page }) => {
  await mockTelegram(page, { startParam: 'compare_tourist-jiangly-Petr' })
  await page.goto('/')
  await expect(page.getByText('Head to head')).toBeVisible()
  await expect(page.locator('.recharts-line')).toHaveCount(3)
})

test('adding and removing a friend', async ({ page }) => {
  await mockTelegram(page)
  await page.goto('/')
  await page.getByRole('navigation').getByRole('button', { name: 'Friends', exact: true }).click()
  await page.getByPlaceholder('Handles, separated by spaces').fill('Um_nik')
  await page.getByRole('button', { name: 'Add', exact: true }).click()
  await expect(page.getByText('Added: Um_nik')).toBeVisible()
  await page.getByRole('button', { name: 'Remove' }).first().click() // edit mode
  await page.locator('li', { hasText: 'Um_nik' }).getByRole('button', { name: 'Remove' }).click()
  await expect(page.locator('li', { hasText: 'Um_nik' })).toHaveCount(0)
})

test('without friends, Standings explains what to do', async ({ page }) => {
  await mockTelegram(page, { noFriends: true })
  await page.goto('/')
  await page.getByRole('navigation').getByRole('button', { name: 'Standings', exact: true }).click()
  await expect(page.getByText('Add friends to compare places in contests')).toBeVisible()
})

test('language and theme switch at once and are remembered', async ({ page }) => {
  await mockTelegram(page)
  await page.goto('/')
  await page.getByRole('navigation').getByRole('button', { name: 'Me', exact: true }).click()
  await page.getByRole('button', { name: 'O‘zbekcha' }).click()
  await expect(page.getByRole('button', { name: 'Do‘stlar', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Yorug‘' }).click()
  await expect(page.locator('html')).toHaveClass(/light/)
  const store = await page.evaluate(() => (window as unknown as { __tg: { store: Record<string, string> } }).__tg.store)
  expect(store.lang).toBe('uz')
  expect(store.theme).toBe('light')
})

test('Russian Telegram users get Russian text', async ({ page }) => {
  await mockTelegram(page, { lang: 'ru' })
  await page.goto('/')
  await expect(page.getByRole('button', { name: 'Друзья', exact: true })).toBeVisible()
})

test('outside Telegram the app says where to open it', async ({ page }) => {
  await page.route('https://telegram.org/**', (r) => r.fulfill({ status: 200, contentType: 'text/javascript', body: '' }))
  await page.addInitScript(() => localStorage.setItem('me', 'tourist'))
  await page.goto('/')
  await expect(page.getByText('Open this app from @cpstandsbot in Telegram.').first()).toBeVisible()
})

test('an upsolve link opens the upsolve list', async ({ page }) => {
  await mockTelegram(page, { startParam: 'upsolve_tourist' })
  await page.goto('/')
  await expect(page.getByText('Problems you tried in a contest but did not solve there')).toBeVisible()
  await page.getByRole('button', { name: 'All', exact: true }).click()
  await expect(page.locator('li button').first()).toBeVisible()
})

test('the friends leaderboard switches between week and month', async ({ page }) => {
  await mockTelegram(page)
  await page.goto('/')
  await page.getByRole('navigation').getByRole('button', { name: 'Friends', exact: true }).click()
  await page.getByRole('button', { name: 'Leaderboard', exact: true }).click()
  await expect(page.getByText('jiangly').first()).toBeVisible()
  await page.getByRole('button', { name: 'Month', exact: true }).click()
  const calls = await page.evaluate(() => (window as unknown as { __tg: { calls: { name: string; input: { period?: string } }[] } }).__tg.calls)
  expect(calls.filter((c) => c.name === 'leaderboard').map((c) => c.input.period)).toEqual(['week', 'month'])
})

test('the status page reports the Mini App backend and Codeforces', async ({ page }) => {
  await mockTelegram(page, { startParam: 'status' })
  await page.goto('/')
  await expect(page.getByText('Codeforces API: Answering')).toBeVisible()
  await expect(page.getByText('app9170246912.tgcloud.ai')).toBeVisible()
})

test('friends come from the bot database and adding goes through Codeforces first', async ({ page }) => {
  await mockTelegram(page)
  await page.goto('/')
  await page.getByRole('navigation').getByRole('button', { name: 'Friends', exact: true }).click()
  await expect(page.getByText('Benq').first()).toBeVisible()
  await page.getByPlaceholder('Handles, separated by spaces').fill('Um_nik')
  await page.getByRole('button', { name: 'Add', exact: true }).click()
  await expect(page.getByText('Added: Um_nik')).toBeVisible()
  const names = await page.evaluate(() => (window as unknown as { __tg: { calls: { name: string }[] } }).__tg.calls.map((c) => c.name))
  // The handle is checked on Codeforces (cards), then stored in the bot's list (rpc).
  expect(names.indexOf('cards')).toBeLessThan(names.indexOf('rpc:app_friends_add'))
})

test('bot settings are read and saved through the database API', async ({ page }) => {
  await mockTelegram(page)
  await page.goto('/')
  await page.getByRole('navigation').getByRole('button', { name: 'Me', exact: true }).click()
  await expect(page.getByText('Bot settings')).toBeVisible()
  await page.getByRole('button', { name: '3d', exact: true }).click()
  await expect(page.getByText('Saved')).toBeVisible()
  const update = await page.evaluate(() =>
    (window as unknown as { __tg: { calls: { name: string; input: { patch?: unknown; init_data?: string } }[] } }).__tg.calls.find(
      (c) => c.name === 'rpc:app_settings_update',
    ),
  )
  expect(update?.input.patch).toEqual({ reminders: [1440, 60, 10, 4320] })
  expect(update?.input.init_data).toContain('hash=') // every call carries the signed init data
})

test('the status page shows the bot heartbeat from the database', async ({ page }) => {
  await mockTelegram(page, { startParam: 'status' })
  await page.goto('/')
  await expect(page.getByText('Bot: Running')).toBeVisible()
  await expect(page.getByText('Active chats')).toBeVisible()
})

test('a signed group link opens the group view with its standings, leaderboard and handles', async ({ page }) => {
  await mockTelegram(page, { startParam: 'g1001234567890_0123456789abcdef_s2279' })
  await page.goto('/')
  await expect(page.getByText('Toshkent CP klubi')).toBeVisible()
  await expect(page.getByText('Codeforces Round 1133 (Div. 1)').first()).toBeVisible()
  await page.getByRole('button', { name: 'Leaderboard', exact: true }).click()
  await expect(page.getByText('jiangly').first()).toBeVisible()
  await page.getByRole('button', { name: 'Handles', exact: true }).click()
  await expect(page.getByText('Benq').first()).toBeVisible()
  // The group's handles are sent, never the viewer's own handle.
  const calls = await page.evaluate(() => (window as unknown as { __tg: { calls: { name: string; input: { me?: string } }[] } }).__tg.calls)
  expect(calls.filter((c) => c.name === 'standings' || c.name === 'leaderboard').every((c) => c.input.me === undefined)).toBe(true)
})

test('a malformed group link opens Home instead', async ({ page }) => {
  await mockTelegram(page, { startParam: 'g12_nothex' })
  await page.goto('/')
  await expect(page.getByText('My rating')).toBeVisible()
})

