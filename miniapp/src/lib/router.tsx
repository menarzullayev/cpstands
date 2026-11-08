import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { can, haptic, startParam, tg } from './tg'

export type Tab = 'home' | 'contests' | 'standings' | 'friends' | 'me'
export type Inner =
  | { name: 'profile'; handle: string }
  | { name: 'compare'; handles: string[] }
  | { name: 'standings'; contestId: number }
  | { name: 'upsolve'; handle: string }
  | { name: 'status' }
  | { name: 'group'; param: string }
  | { name: 'kstandings'; contestId: number }
  | { name: 'kprofile'; handle: string }

interface Router {
  tab: Tab
  stack: Inner[]
  top: Inner | null
  go: (tab: Tab) => void
  push: (route: Inner) => void
  back: () => void
}

const Ctx = createContext<Router | null>(null)
const TABS: Tab[] = ['home', 'contests', 'standings', 'friends', 'me']
const HANDLE = /^[A-Za-z0-9_.-]{1,24}$/

/** startapp parameter → initial screen. Formats: profile_<h>, compare_<h>_<h>, standings_<id>, <tab>. */
export function parseStart(param: string): { tab: Tab; stack: Inner[] } {
  const [kind, ...rest] = param.split('_')
  // Handles may contain '_', so a profile takes everything after the first separator.
  if (kind === 'profile') {
    const handle = param.slice('profile_'.length)
    if (HANDLE.test(handle)) return { tab: 'home', stack: [{ name: 'profile', handle }] }
  }
  // kep.uz: kprofile_<handle> and standings_kep<id>.
  if (kind === 'kprofile') {
    const handle = param.slice('kprofile_'.length)
    if (HANDLE.test(handle)) return { tab: 'contests', stack: [{ name: 'kprofile', handle }] }
  }
  if (kind === 'standings' && /^kep\d{1,7}$/.test(rest[0] ?? '')) {
    return { tab: 'contests', stack: [{ name: 'kstandings', contestId: Number(rest[0].slice(3)) }] }
  }
  if (param === 'status') return { tab: 'me', stack: [{ name: 'status' }] }
  // A signed group link from the bot: g<id>_<signature>[_s<contest>]; the database checks it.
  if (/^g\d{1,15}_[0-9a-f]{16}(_s\d{1,7})?$/.test(param)) return { tab: 'home', stack: [{ name: 'group', param }] }
  if (kind === 'upsolve') {
    const handle = param.slice('upsolve_'.length)
    if (HANDLE.test(handle)) return { tab: 'home', stack: [{ name: 'upsolve', handle }] }
  }
  if (kind === 'compare') {
    const handles = param.slice('compare_'.length).split('-').filter((h) => HANDLE.test(h)).slice(0, 6)
    if (handles.length) return { tab: 'friends', stack: [{ name: 'compare', handles }] }
  }
  if (kind === 'standings' && /^\d+$/.test(rest[0] ?? '')) {
    return { tab: 'standings', stack: [{ name: 'standings', contestId: Number(rest[0]) }] }
  }
  if ((TABS as string[]).includes(kind)) return { tab: kind as Tab, stack: [] }
  return { tab: 'home', stack: [] }
}

/** The inverse of parseStart, for share links. */
export function routeParam(route: Inner | Tab): string {
  if (typeof route === 'string') return route
  if (route.name === 'profile') return `profile_${route.handle}`
  if (route.name === 'compare') return `compare_${route.handles.join('-')}`
  if (route.name === 'upsolve') return `upsolve_${route.handle}`
  if (route.name === 'status') return 'status'
  if (route.name === 'group') return route.param
  if (route.name === 'kprofile') return `kprofile_${route.handle}`
  if (route.name === 'kstandings') return `standings_kep${route.contestId}`
  return `standings_${route.contestId}`
}

export function RouterProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState(() => parseStart(startParam))

  const go = useCallback((tab: Tab) => {
    setState((s) => {
      if (s.tab !== tab || s.stack.length) haptic.tap()
      return { tab, stack: [] }
    })
    window.scrollTo({ top: 0 })
  }, [])
  const push = useCallback((route: Inner) => {
    haptic.tap()
    setState((s) => ({ ...s, stack: [...s.stack, route] }))
    window.scrollTo({ top: 0 })
  }, [])
  const back = useCallback(() => {
    setState((s) => ({ ...s, stack: s.stack.slice(0, -1) }))
  }, [])

  // Telegram's own Back button mirrors the inner-page stack.
  useEffect(() => {
    if (!can.back()) return
    const bb = tg!.BackButton!
    if (state.stack.length) bb.show()
    else bb.hide()
    bb.onClick(back)
    return () => bb.offClick(back)
  }, [state.stack.length, back])

  const value = useMemo<Router>(
    () => ({ ...state, top: state.stack[state.stack.length - 1] ?? null, go, push, back }),
    [state, go, push, back],
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useRouter(): Router {
  const v = useContext(Ctx)
  if (!v) throw new Error('useRouter outside RouterProvider')
  return v
}
