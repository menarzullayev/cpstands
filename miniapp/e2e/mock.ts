// A stand-in for telegram-web-app.js: the app talks to it exactly as to the real one, and
// Serverless.call answers from fixtures captured from the real endpoints (e2e/capture.mjs).
import type { Page } from '@playwright/test'
import contests from './fixtures/contests.json' with { type: 'json' }
import profile from './fixtures/profile.json' with { type: 'json' }
import compareOne from './fixtures/compareOne.json' with { type: 'json' }
import compare from './fixtures/compare.json' with { type: 'json' }
import friends from './fixtures/friends.json' with { type: 'json' }
import activity from './fixtures/activity.json' with { type: 'json' }
import standings from './fixtures/standings.json' with { type: 'json' }
import upsolve from './fixtures/upsolve.json' with { type: 'json' }
import leaderboard from './fixtures/leaderboard.json' with { type: 'json' }

/** The moment the fixtures were captured; the page clock is frozen here. */
export const NOW = new Date('2026-11-08T10:06:00Z')

export interface MockOptions {
  storage?: Record<string, string>
  startParam?: string
  lang?: string
  colorScheme?: 'dark' | 'light'
  noFriends?: boolean
}

export async function mockTelegram(page: Page, opts: MockOptions = {}) {
  await page.route('https://telegram.org/**', (r) => r.fulfill({ status: 200, contentType: 'text/javascript', body: '' }))
  await page.clock.setFixedTime(NOW)
  const data = { contests, profile, compareOne, compare, friends, activity, standings, upsolve, leaderboard }
  await page.addInitScript(
    ([data, opts]) => {
      const store: Record<string, string> = { me: 'tourist', effects: '0', ...(opts.storage ?? {}) }
      let list = opts.noFriends ? [] : [...data.friends.friends]
      const calls: { name: string; input: unknown }[] = []
      const back = { visible: false, handlers: [] as (() => void)[] }
      const answer = (name: string, input: Record<string, unknown>) => {
        switch (name) {
          case 'contests':
            return data.contests
          case 'profile':
            return data.profile
          case 'compare':
            return (input.handles as string[]).length === 1 ? data.compareOne : data.compare
          case 'friends': {
            const hs = ((input.handles as string[]) ?? []).map((h) => h.toLowerCase())
            if (input.action === 'remove') list = list.filter((f) => !hs.includes(f.handle.toLowerCase()))
            if (input.action === 'add') {
              for (const h of input.handles as string[]) {
                if (!list.some((f) => f.handle.toLowerCase() === h.toLowerCase()))
                  list.push({ handle: h, rating: 1500, maxRating: 1600, rank: 'specialist', avatar: null, lastOnline: null })
              }
            }
            return { friends: list, max: 200, added: input.action === 'add' ? input.handles : undefined }
          }
          case 'cards': {
            const hs = (input.handles as string[]) ?? []
            return {
              cards: hs.map(
                (h) =>
                  list.find((f) => f.handle.toLowerCase() === h.toLowerCase()) ?? {
                    handle: h, rating: 1500, maxRating: 1600, rank: 'specialist', avatar: null, lastOnline: null,
                  },
              ),
            }
          }
          case 'activity':
            return list.length ? data.activity : { events: [], pending: 0, handles: 1 }
          case 'upsolve':
            return data.upsolve
          case 'leaderboard':
            if (!list.length) throw { type: 'ENDPOINT_ERROR', message: 'No friends', parameters: { code: 'NO_FRIENDS' } }
            return { ...data.leaderboard, period: input.period }
          case 'standings':
            if (!list.length) throw { type: 'ENDPOINT_ERROR', message: 'No friends', parameters: { code: 'NO_FRIENDS' } }
            return data.standings
        }
        throw { type: 'ENDPOINT_ERROR', message: 'unknown', parameters: { code: 'NOT_FOUND' } }
      }
      // Supabase REST: the app_* functions of migration 0005, over the same in-memory state.
      const settings = {
        status: 'active', language: 'en', timeZone: 'Asia/Tashkent', tone: 'playful',
        reminders: [1440, 60, 10], alerts: true, notifyLevel: 4, tableCols: 16, summary: true,
      }
      const now = () => Math.floor(Date.now() / 1000)
      const rpcAnswer = (fn: string, body: Record<string, unknown>) => {
        const names = () => ({ max: 200, friends: list.map((f) => f.handle) })
        switch (fn) {
          case 'app_friends':
            return names()
          case 'app_friends_add': {
            const added: string[] = []
            for (const h of body.handles as string[]) {
              if (!list.some((f) => f.handle.toLowerCase() === h.toLowerCase())) {
                list.push({ handle: h, rating: 1500, maxRating: 1600, rank: 'specialist', avatar: null, lastOnline: null })
                added.push(h)
              }
            }
            return { ...names(), added, already: (body.handles as string[]).length - added.length, overLimit: 0 }
          }
          case 'app_friends_remove': {
            const hs = (body.handles as string[]).map((h) => h.toLowerCase())
            list = list.filter((f) => !hs.includes(f.handle.toLowerCase()))
            return names()
          }
          case 'app_settings':
            return settings
          case 'app_settings_update':
            Object.assign(settings, body.patch)
            return settings
          case 'app_group':
            if (!/^g\d+_[0-9a-f]{16}/.test(opts.startParam ?? '')) return null
            return {
              chatId: -1001234567890, title: 'Toshkent CP klubi', language: 'uz', timeZone: 'Asia/Tashkent',
              contestId: 2279, viewer: 1, handles: data.friends.friends.map((f) => f.handle),
            }
          case 'app_status':
            return {
              now: now(), chats: 2, handles: 3, remindersSent24h: 1, liveContests: 0,
              heartbeat: { at: now() - 30, commit: '5d7fc59a8c00', version: '0.1.0', startedAt: now() - 3600 },
              nextContest: { name: 'Codeforces Round 1134 (Div. 4)', startsAt: now() + 4 * 86400 },
            }
        }
        return null
      }
      const realFetch = window.fetch.bind(window)
      window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input instanceof Request ? input.url : input)
        const m = url.match(/\/rest\/v1\/rpc\/([a-z_]+)$/)
        if (!m) return realFetch(input, init)
        const body = JSON.parse(String(init?.body ?? '{}'))
        calls.push({ name: `rpc:${m[1]}`, input: body })
        const result = rpcAnswer(m[1], body)
        return new Response(JSON.stringify(result ?? { message: 'not found' }), {
          status: result === null ? 404 : 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      const noop = () => {}
      ;(window as unknown as { __tg: unknown }).__tg = { calls, back, store }
      ;(window as unknown as { Telegram: unknown }).Telegram = {
        WebApp: {
          initData: 'query_id=TEST&user=%7B%22id%22%3A1%7D&hash=test',
          initDataUnsafe: {
            user: { id: 1, first_name: 'Test', language_code: opts.lang ?? 'en' },
            start_param: opts.startParam,
          },
          version: '9.1',
          platform: 'tdesktop',
          colorScheme: opts.colorScheme ?? 'dark',
          ready: noop,
          expand: noop,
          disableVerticalSwipes: noop,
          setHeaderColor: noop,
          setBackgroundColor: noop,
          setBottomBarColor: noop,
          onEvent: noop,
          offEvent: noop,
          openLink: noop,
          openTelegramLink: noop,
          isVersionAtLeast: () => true,
          HapticFeedback: { selectionChanged: noop, impactOccurred: noop, notificationOccurred: noop },
          BackButton: {
            show: () => (back.visible = true),
            hide: () => (back.visible = false),
            onClick: (cb: () => void) => back.handlers.push(cb),
            offClick: (cb: () => void) => (back.handlers = back.handlers.filter((h) => h !== cb)),
          },
          CloudStorage: {
            getItems: (keys: string[], cb: (e: unknown, v: Record<string, string>) => void) =>
              cb(null, Object.fromEntries(keys.map((k) => [k, store[k] ?? '']))),
            getItem: (k: string, cb: (e: unknown, v: string) => void) => cb(null, store[k] ?? ''),
            setItem: (k: string, v: string) => (store[k] = v),
          },
          Serverless: {
            call: (name: string, input: Record<string, unknown>, cb: (e: unknown, r?: unknown) => void) => {
              calls.push({ name, input })
              setTimeout(() => {
                try {
                  cb(null, JSON.parse(JSON.stringify(answer(name, input ?? {}))))
                } catch (e) {
                  cb(e)
                }
              }, 30)
            },
          },
        },
      }
    },
    [data, opts] as const,
  )
}

/** Presses Telegram's Back button as the client would. */
export async function pressBack(page: Page) {
  await page.evaluate(() => {
    const tg = (window as unknown as { __tg: { back: { handlers: (() => void)[] } } }).__tg
    tg.back.handlers.forEach((h) => h())
  })
}

export async function backVisible(page: Page) {
  return page.evaluate(() => (window as unknown as { __tg: { back: { visible: boolean } } }).__tg.back.visible)
}
