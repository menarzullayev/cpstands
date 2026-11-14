// One friend list for the whole app. With the database configured it is the bot's own list for
// the user's private chat (the same one /track edits); otherwise the Mini App's own list.
import { useCallback, useEffect, useState } from 'react'
import { call, forget, useCall } from './api'
import type { Friend, FriendsAnswer } from './cf'
import { dbReady, rpc } from './db'
import { ApiError } from './tg'

interface DbFriends {
  max: number
  friends: string[]
  added?: string[]
  already?: number
  overLimit?: number
}

let shared: string[] | null = null // the handle list, shared by every screen in this session
const listeners = new Set<(h: string[]) => void>()
function publish(handles: string[]) {
  shared = handles
  listeners.forEach((l) => l(handles))
}

/** The friend handles to send to endpoints, or undefined to let them use their own list. */
export function useFriendHandles(): string[] | undefined | null {
  const [handles, setHandles] = useState<string[] | null>(shared)
  useEffect(() => {
    listeners.add(setHandles)
    if (dbReady && shared === null) {
      rpc<DbFriends>('app_friends')
        .then((r) => publish(r.friends))
        .catch(() => publish([]))
    }
    return () => {
      listeners.delete(setHandles)
    }
  }, [])
  if (!dbReady) return undefined
  return handles // null while loading
}

export interface FriendsState {
  friends: Friend[] | null
  max: number
  error: string | null
  busy: boolean
  reload: () => void
  change: (action: 'add' | 'remove', handles: string[]) => Promise<FriendsAnswer>
}

export function useFriends(): FriendsState {
  const handles = useFriendHandles()
  // Serverless list (no database) or cards for the database list.
  const own = useCall<FriendsAnswer>('friends', dbReady ? null : { action: 'list' }, 300_000)
  const cards = useCall<{ cards: Friend[] }>('cards', dbReady && handles ? { handles } : null, 300_000)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const change = useCallback(
    async (action: 'add' | 'remove', list: string[]): Promise<FriendsAnswer> => {
      setBusy(true)
      setError(null)
      try {
        forget('activity')
        forget('standings')
        forget('leaderboard')
        if (!dbReady) {
          const res = await call<FriendsAnswer>('friends', { action, handles: list })
          own.set(res)
          return res
        }
        let names = list
        if (action === 'add') {
          // Codeforces spells the handles; unknown ones are refused before anything is stored.
          const known = await call<{ cards: Friend[] }>('cards', { handles: list })
          names = known.cards.map((c) => c.handle)
        }
        const res = await rpc<DbFriends>(action === 'add' ? 'app_friends_add' : 'app_friends_remove', { handles: names })
        publish(res.friends)
        return { friends: [], max: res.max, added: res.added, already: res.already, overLimit: res.overLimit }
      } catch (e) {
        setError(e instanceof ApiError ? e.code : 'generic')
        throw e
      } finally {
        setBusy(false)
      }
    },
    [own],
  )

  if (!dbReady) {
    return { friends: own.data?.friends ?? null, max: own.data?.max ?? 200, error: own.error ?? error, busy, reload: own.reload, change }
  }
  const empty = handles !== null && handles !== undefined && handles.length === 0
  return {
    friends: empty ? [] : (cards.data?.cards ?? null),
    max: 200,
    error: cards.error ?? error,
    busy,
    reload: cards.reload,
    change,
  }
}
