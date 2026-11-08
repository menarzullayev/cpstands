// Thin, typed wrapper over the official telegram-web-app.js (loaded in index.html).

type Callback<T> = (err: ServerlessError | null, result: T) => void

export interface ServerlessError {
  type: string // 'ENDPOINT_ERROR', 'UNAUTHORIZED', ...
  message?: string
  parameters?: { code?: string; [key: string]: unknown }
}

interface WebApp {
  initData: string
  initDataUnsafe: { user?: { id: number; first_name: string; language_code?: string } }
  colorScheme: 'light' | 'dark'
  ready(): void
  expand(): void
  onEvent(event: string, cb: () => void): void
  openLink(url: string): void
  HapticFeedback?: { selectionChanged(): void; impactOccurred(style: string): void }
  BackButton?: { show(): void; hide(): void; onClick(cb: () => void): void; offClick(cb: () => void): void }
  CloudStorage?: {
    getItem(key: string, cb: (err: unknown, value?: string) => void): void
    setItem(key: string, value: string, cb?: (err: unknown) => void): void
  }
  Serverless?: {
    call<T>(name: string, input: object, cb: Callback<T>): void
  }
  isVersionAtLeast?(version: string): boolean
}

declare global {
  interface Window {
    Telegram?: { WebApp?: WebApp }
  }
}

export const tg: WebApp | undefined = window.Telegram?.WebApp

/** True when the page runs inside Telegram with signed init data. */
export const insideTelegram = Boolean(tg && tg.initData)

export class ApiError extends Error {
  readonly code: string
  constructor(code: string, message: string) {
    super(message)
    this.code = code
  }
}

/** Promise form of Telegram.WebApp.Serverless.call; retries once when Codeforces is busy. */
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
        } else {
          resolve(result)
        }
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

export function haptic(): void {
  tg?.HapticFeedback?.selectionChanged()
}

/** Per-user storage that follows the user across devices; falls back to localStorage. */
export const storage = {
  get(key: string): Promise<string | null> {
    return new Promise((resolve) => {
      const local = () => {
        try {
          resolve(localStorage.getItem(key))
        } catch {
          resolve(null)
        }
      }
      if (tg?.CloudStorage && insideTelegram && tg.isVersionAtLeast?.('6.9')) {
        tg.CloudStorage.getItem(key, (err, value) => (err ? local() : resolve(value || null)))
      } else {
        local()
      }
    })
  },
  set(key: string, value: string): void {
    try {
      localStorage.setItem(key, value)
    } catch {
      /* private mode */
    }
    if (tg?.CloudStorage && insideTelegram && tg.isVersionAtLeast?.('6.9')) {
      tg.CloudStorage.setItem(key, value)
    }
  },
}
