import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, call } from './tg'

export interface CallState<T> {
  data: T | null
  error: string | null // an error code
  loading: boolean
  reload: () => void
}

/** Calls an endpoint whenever `input` changes (compared as JSON); `null` input skips the call. */
export function useCall<T>(name: string, input: object | null): CallState<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(input !== null)
  const [nonce, setNonce] = useState(0)
  const key = input === null ? null : JSON.stringify(input)
  const latest = useRef(0)

  useEffect(() => {
    if (key === null) {
      setData(null)
      setError(null)
      setLoading(false)
      return
    }
    const id = ++latest.current
    setLoading(true)
    setError(null)
    call<T>(name, JSON.parse(key))
      .then((result) => {
        if (id === latest.current) setData(result)
      })
      .catch((e: unknown) => {
        if (id !== latest.current) return
        setData(null)
        setError(e instanceof ApiError ? e.code : 'generic')
      })
      .finally(() => {
        if (id === latest.current) setLoading(false)
      })
  }, [name, key, nonce])

  const reload = useCallback(() => setNonce((n) => n + 1), [])
  return { data, error, loading, reload }
}
