import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, call } from './tg'

// Answers stay in memory for the session so switching tabs is instant; a stale answer is shown
// at once and refreshed in the background (stale-while-revalidate).
const memory = new Map<string, { at: number; value: unknown }>()

export interface CallState<T> {
  data: T | null
  error: string | null
  loading: boolean // true only when there is nothing to show yet
  refreshing: boolean
  reload: () => void
  set: (value: T) => void
}

export function useCall<T>(name: string, input: object | null, freshMs = 60_000): CallState<T> {
  const key = input === null ? null : `${name}:${JSON.stringify(input)}`
  const cachedNow = key ? (memory.get(key)?.value as T | undefined) ?? null : null
  const [data, setData] = useState<T | null>(cachedNow)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [nonce, setNonce] = useState(0)
  const latest = useRef(0)

  useEffect(() => {
    if (key === null) return
    const hit = memory.get(key)
    // Keys change when the input changes: show what we have for the new key right away.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setData((hit?.value as T | undefined) ?? null)
    setError(null)
    if (hit && Date.now() - hit.at < freshMs && nonce === 0) return
    const id = ++latest.current
    setBusy(true)
    call<T>(name, JSON.parse(key.slice(name.length + 1)))
      .then((value) => {
        memory.set(key, { at: Date.now(), value })
        if (id === latest.current) setData(value)
      })
      .catch((e: unknown) => {
        if (id === latest.current) setError(e instanceof ApiError ? e.code : 'generic')
      })
      .finally(() => {
        if (id === latest.current) setBusy(false)
      })
  }, [name, key, nonce, freshMs])

  const reload = useCallback(() => setNonce((n) => n + 1), [])
  const set = useCallback(
    (value: T) => {
      if (key) memory.set(key, { at: Date.now(), value })
      setData(value)
    },
    [key],
  )
  return {
    data: key === null ? null : data,
    error: key === null ? null : error,
    loading: key !== null && busy && data === null,
    refreshing: busy && data !== null,
    reload,
    set,
  }
}

/** Drops cached answers of one endpoint, e.g. after the friend list changed. */
export function forget(name: string) {
  for (const k of memory.keys()) if (k.startsWith(`${name}:`)) memory.delete(k)
}

export { call }
