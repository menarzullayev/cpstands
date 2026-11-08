import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { detectLang, formatters, translator, type Fmt, type Lang, type T } from './i18n'
import { storage, tg } from './tg'

export type Theme = 'dark' | 'light' | 'auto'

interface Settings {
  ready: boolean
  me: string | null // own Codeforces handle; '' = skipped onboarding, null = not asked yet
  lang: Lang
  theme: Theme
  effects: boolean
  set: (patch: Partial<Pick<Settings, 'me' | 'lang' | 'theme' | 'effects'>>) => void
  t: T
  fmt: Fmt
}

const KEYS = { me: 'me', lang: 'lang', theme: 'theme', effects: 'effects' } as const
const Ctx = createContext<Settings | null>(null)

const reducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false)
  const [me, setMe] = useState<string | null>(null)
  const [lang, setLang] = useState<Lang>(detectLang)
  const [theme, setTheme] = useState<Theme>('dark')
  const [effects, setEffects] = useState(() => !reducedMotion())

  useEffect(() => {
    storage.getMany(Object.values(KEYS)).then((v) => {
      if (v.me !== null) setMe(v.me)
      if (v.lang === 'uz' || v.lang === 'ru' || v.lang === 'en') setLang(v.lang)
      if (v.theme === 'dark' || v.theme === 'light' || v.theme === 'auto') setTheme(v.theme)
      if (v.effects === '0' || v.effects === '1') setEffects(v.effects === '1')
      setReady(true)
    })
  }, [])

  // Apply the theme and the effects switch to <html>.
  useEffect(() => {
    const apply = () => {
      const light = theme === 'light' || (theme === 'auto' && tg?.colorScheme === 'light')
      document.documentElement.classList.toggle('light', light)
      const bg = getComputedStyle(document.documentElement).getPropertyValue('--background').trim() || '#0a0e14'
      if (tg?.isVersionAtLeast?.('6.1')) {
        tg.setHeaderColor?.(bg)
        tg.setBackgroundColor?.(bg)
      }
      if (tg?.isVersionAtLeast?.('7.10')) tg.setBottomBarColor?.(bg)
    }
    apply()
    tg?.onEvent('themeChanged', apply)
    return () => tg?.offEvent('themeChanged', apply)
  }, [theme])
  useEffect(() => {
    document.documentElement.classList.toggle('no-fx', !effects)
  }, [effects])
  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])

  const set = useCallback<Settings['set']>((patch) => {
    if (patch.me !== undefined) {
      setMe(patch.me)
      storage.set(KEYS.me, patch.me ?? '')
    }
    if (patch.lang) {
      setLang(patch.lang)
      storage.set(KEYS.lang, patch.lang)
    }
    if (patch.theme) {
      setTheme(patch.theme)
      storage.set(KEYS.theme, patch.theme)
    }
    if (patch.effects !== undefined) {
      setEffects(patch.effects)
      storage.set(KEYS.effects, patch.effects ? '1' : '0')
    }
  }, [])

  const value = useMemo<Settings>(
    () => ({ ready, me, lang, theme, effects, set, t: translator(lang), fmt: formatters(lang) }),
    [ready, me, lang, theme, effects, set],
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useSettings(): Settings {
  const v = useContext(Ctx)
  if (!v) throw new Error('useSettings outside SettingsProvider')
  return v
}
