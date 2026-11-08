// The bot's own database, reached through Supabase's REST API with the public anon key.
// Every app_* function verifies the Telegram init data itself (migration 0005), so the key
// grants nothing on its own. Until the project is configured the app keeps its own lists.
import { ApiError, tg } from './tg'

const URL = import.meta.env.VITE_SUPABASE_URL as string | undefined
const KEY = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined

export const dbReady = Boolean(URL && KEY)

export async function rpc<T>(fn: string, args: Record<string, unknown> = {}, signed = true): Promise<T> {
  if (!dbReady) throw new ApiError('NO_DB', 'database not configured')
  const body = signed ? { init_data: tg?.initData ?? '', ...args } : args
  let res: Response
  try {
    res = await fetch(`${URL}/rest/v1/rpc/${fn}`, {
      method: 'POST',
      headers: { apikey: KEY!, Authorization: `Bearer ${KEY}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch {
    throw new ApiError('DB_DOWN', 'database unreachable')
  }
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { message?: string; code?: string }
    const message = err.message ?? ''
    const code =
      err.code === '28000' ? 'UNAUTHORIZED' : /bad handle/.test(message) ? 'BAD_HANDLE' : err.code === '22023' ? 'BAD_INPUT' : 'DB_DOWN'
    throw new ApiError(code, message)
  }
  return (await res.json()) as T
}
