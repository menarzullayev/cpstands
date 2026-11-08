// Typed wrapper over the official telegram-web-app.js (loaded in index.html).

type Callback<T> = (err: ServerlessError | null, result: T) => void

export interface ServerlessError {
  type: string
  message?: string
  parameters?: { code?: string; [key: string]: unknown }
}

interface Insets {
  top: number
  bottom: number
  left: number
  right: number
}

interface WebApp {
  initData: string
  initDataUnsafe: {
    user?: { id: number; first_name: string; username?: string; language_code?: string; photo_url?: string }
    start_param?: string
  }
  version: string
  platform: string
  colorScheme: 'light' | 'dark'
  isFullscreen?: boolean
  safeAreaInset?: Insets
  contentSafeAreaInset?: Insets
  ready(): void
  expand(): void
  requestFullscreen?(): void
  disableVerticalSwipes?(): void
  setHeaderColor?(color: string): void
  setBackgroundColor?(color: string): void
  setBottomBarColor?(color: string): void
  onEvent(event: string, cb: (...args: unknown[]) => void): void
  offEvent(event: string, cb: (...args: unknown[]) => void): void
  openLink(url: string, options?: { try_instant_view?: boolean }): void
  openTelegramLink(url: string): void
  shareToStory?(mediaUrl: string, params?: { text?: string; widget_link?: { url: string; name?: string } }): void
  addToHomeScreen?(): void
  checkHomeScreenStatus?(cb: (status: string) => void): void
  isVersionAtLeast(version: string): boolean
  HapticFeedback?: {
    selectionChanged(): void
    impactOccurred(style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft'): void
    notificationOccurred(type: 'error' | 'success' | 'warning'): void
  }
  BackButton?: { show(): void; hide(): void; onClick(cb: () => void): void; offClick(cb: () => void): void }
  CloudStorage?: {
    getItem(key: string, cb: (err: unknown, value?: string) => void): void
    getItems(keys: string[], cb: (err: unknown, values?: Record<string, string>) => void): void
    setItem(key: string, value: string, cb?: (err: unknown) => void): void
  }
  Serverless?: { call<T>(name: string, input: object, cb: Callback<T>): void }
}

declare global {
  interface Window {
    Telegram?: { WebApp?: WebApp }
  }
}

export const tg: WebApp | undefined = window.Telegram?.WebApp
export const insideTelegram = Boolean(tg && tg.initData)
export const BOT = 'cpstandsbot'
export const tgUser = tg?.initDataUnsafe.user
export const startParam = tg?.initDataUnsafe.start_param ?? new URLSearchParams(location.search).get('startapp') ?? ''

const at = (v: string) => Boolean(tg?.isVersionAtLeast?.(v))
export const can = {
  fullscreen: () => at('8.0') && Boolean(tg?.requestFullscreen),
  homeScreen: () => at('8.0') && Boolean(tg?.addToHomeScreen),
  // Stories can only be posted from the phone apps.
  story: () => at('7.8') && Boolean(tg?.shareToStory) && (tg?.platform === 'ios' || tg?.platform === 'android'),
  cloud: () => insideTelegram && at('6.9') && Boolean(tg?.CloudStorage),
  back: () => at('6.1') && Boolean(tg?.BackButton),
}

/** Mobile clients get fullscreen; desktop keeps the window it opened in. */
export function setupChrome(background: string) {
  if (!tg) return
  tg.ready()
  tg.expand()
  if (at('7.7')) tg.disableVerticalSwipes?.()
  if (at('6.1')) {
    tg.setHeaderColor?.(background)
    tg.setBackgroundColor?.(background)
  }
  if (at('7.10')) tg.setBottomBarColor?.(background)
  const mobile = tg.platform === 'android' || tg.platform === 'ios'
  if (mobile && can.fullscreen()) {
    try {
      tg.requestFullscreen?.()
    } catch {
      /* older client */
    }
  }
}

export class ApiError extends Error {
  readonly code: string
  constructor(code: string, message: string) {
    super(message)
    this.code = code
  }
}

/** Promise form of Serverless.call; retries once after 2 s when Codeforces is busy. */
export async function call<T>(name: string, input: object = {}): Promise<T> {
  const once = () =>
    new Promise<T>((resolve, reject) => {
      if (!tg?.Serverless || !insideTelegram) {
        reject(new ApiError('NO_TELEGRAM', 'Open this app from Telegram'))
        return
      }
      tg.Serverless.call<T>(name, input, (err, result) => {
        if (err) {
          const code = err.parameters?.code ?? err.type ?? 'UNKNOWN'
          reject(new ApiError(String(code), err.message ?? String(code)))
        } else resolve(result)
      })
    })
  try {
    return await once()
  } catch (e) {
    if (e instanceof ApiError && e.code === 'CF_BUSY') {
      await new Promise((r) => setTimeout(r, 2200))
      return once()
    }
    throw e
  }
}

export const haptic = {
  tap: () => tg?.HapticFeedback?.selectionChanged(),
  impact: (s: 'light' | 'medium' | 'heavy' = 'light') => tg?.HapticFeedback?.impactOccurred(s),
  success: () => tg?.HapticFeedback?.notificationOccurred('success'),
  error: () => tg?.HapticFeedback?.notificationOccurred('error'),
}

export function openLink(url: string) {
  if (tg) tg.openLink(url)
  else window.open(url, '_blank', 'noopener')
}

/** A link that opens this Mini App on a given screen, e.g. startapp=profile_tourist. */
export function appLink(route: string) {
  return `https://t.me/${BOT}?startapp=${encodeURIComponent(route)}`
}

/** Opens Telegram's share sheet for a link plus text. */
export function shareLink(url: string, text: string) {
  const share = `https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text)}`
  if (tg) tg.openTelegramLink(share)
  else window.open(share, '_blank', 'noopener')
}

export function shareStory(text: string, route: string) {
  if (!can.story()) return false
  tg!.shareToStory!(`${location.origin}/story.png`, {
    text: text.slice(0, 200),
    widget_link: { url: appLink(route), name: 'cpstands' },
  })
  return true
}

/** Per-user storage that follows the user across devices; falls back to localStorage. */
export const storage = {
  async getMany(keys: string[]): Promise<Record<string, string | null>> {
    const local = () => {
      const out: Record<string, string | null> = {}
      for (const k of keys) {
        try {
          out[k] = localStorage.getItem(k)
        } catch {
          out[k] = null
        }
      }
      return out
    }
    if (!can.cloud()) return local()
    return new Promise((resolve) => {
      tg!.CloudStorage!.getItems(keys, (err, values) => {
        if (err || !values) resolve(local())
        else resolve(Object.fromEntries(keys.map((k) => [k, values[k] || null])))
      })
    })
  },
  set(key: string, value: string) {
    try {
      localStorage.setItem(key, value)
    } catch {
      /* private mode */
    }
    if (can.cloud()) tg!.CloudStorage!.setItem(key, value)
  },
}
