// WCAG AA contrast of the design tokens in both themes, and first-paint speed.
import { expect, test } from '@playwright/test'
import { mockTelegram } from './mock'

function luminance(hex: string) {
  const v = hex.replace('#', '')
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(v.slice(i, i + 2), 16) / 255)
  const lin = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4)
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
}

export function contrast(a: string, b: string) {
  const [x, y] = [luminance(a), luminance(b)].sort((p, q) => q - p)
  return (x + 0.05) / (y + 0.05)
}

// Text colour on background colour; every pair is used for normal-size text.
const PAIRS: [string, string][] = [
  ['--foreground', '--background'],
  ['--foreground', '--card'],
  ['--muted-foreground', '--background'],
  ['--muted-foreground', '--card'],
  ['--muted-foreground', '--muted'],
  ['--primary', '--background'],
  ['--primary', '--card'],
  ['--primary-foreground', '--primary'],
  ['--success', '--card'],
  ['--destructive', '--card'],
  ['--warning', '--card'],
  ['--violet', '--card'],
]

test('the contrast check itself catches a weak pair', () => {
  expect(contrast('#777777', '#888888')).toBeLessThan(4.5)
  expect(contrast('#000000', '#ffffff')).toBeCloseTo(21, 0)
})

for (const theme of ['dark', 'light'] as const) {
  test(`WCAG AA contrast, ${theme} theme`, async ({ page }, info) => {
    test.skip(info.project.name !== 'phone', 'tokens do not depend on width')
    await mockTelegram(page, { storage: { theme } })
    await page.goto('/')
    await expect(page.getByText('My rating')).toBeVisible()
    const colors = await page.evaluate((names) => {
      const css = getComputedStyle(document.documentElement)
      return Object.fromEntries(names.map((n) => [n, css.getPropertyValue(n).trim()]))
    }, [...new Set(PAIRS.flat())])
    const failures = PAIRS.map(([fg, bg]) => ({ fg, bg, ratio: contrast(colors[fg], colors[bg]) })).filter((p) => p.ratio < 4.5)
    expect(failures, JSON.stringify(failures)).toEqual([])
  })
}

test('largest contentful paint stays under 1.5 s', async ({ page }, info) => {
  test.skip(info.project.name !== 'phone', 'measured once')
  await mockTelegram(page)
  await page.goto('/')
  await expect(page.getByText('My rating')).toBeVisible()
  const lcp = await page.evaluate(
    () =>
      new Promise<number>((resolve) => {
        new PerformanceObserver((list) => {
          const entries = list.getEntries()
          resolve(entries[entries.length - 1].startTime)
        }).observe({ type: 'largest-contentful-paint', buffered: true })
      }),
  )
  console.log(`LCP ${Math.round(lcp)} ms`)
  expect(lcp).toBeLessThan(1500)
})
