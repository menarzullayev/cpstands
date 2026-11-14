import { useState } from 'react'
import { motion } from 'motion/react'
import { ArrowRight, Loader2 } from 'lucide-react'
import { call } from '@/lib/api'
import { errorKey } from '@/lib/i18n'
import { useSettings } from '@/lib/settings'
import { ApiError, haptic, tgUser } from '@/lib/tg'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Logo } from '@/components/kit'
import type { Comparison } from '@/lib/cf'

export function Onboarding() {
  const { t, set } = useSettings()
  const [value, setValue] = useState(tgUser?.username ?? '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async () => {
    const handle = value.trim()
    if (!handle) return
    setBusy(true)
    setError(null)
    try {
      // compare with one handle validates it and warms the cache for the Home rating card.
      const res = await call<Comparison>('compare', { handles: [handle] })
      haptic.success()
      set({ me: res.series[0]?.handle ?? handle })
    } catch (e) {
      haptic.error()
      setError(e instanceof ApiError ? e.code : 'generic')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="bg-grid relative flex min-h-screen flex-col justify-center overflow-hidden px-6">
      <div className="pointer-events-none absolute -top-40 left-1/2 size-[480px] -translate-x-1/2 rounded-full bg-primary/15 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-40 -right-20 size-[360px] rounded-full bg-violet/15 blur-3xl" />
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        className="relative mx-auto w-full max-w-sm space-y-8"
      >
        <Logo className="text-2xl [&_svg]:size-9" />
        <div className="space-y-3">
          <h1 className="text-3xl font-bold leading-tight">{t('onb.title')}</h1>
          <p className="text-muted-foreground">{t('onb.lead')}</p>
        </div>
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault()
            void submit()
          }}
        >
          <label className="block font-mono text-xs uppercase tracking-[0.14em] text-primary" htmlFor="handle">
            {'> '}
            {t('onb.ask')}
          </label>
          <Input
            id="handle"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={t('onb.placeholder')}
            autoCapitalize="off"
            autoCorrect="off"
            spellCheck={false}
            className="h-12 font-mono text-base"
            aria-invalid={Boolean(error)}
          />
          {error && <p className="text-sm text-destructive">{t(errorKey(error))}</p>}
          <Button type="submit" size="lg" className="glow h-12 w-full text-base font-semibold" disabled={busy || !value.trim()}>
            {busy ? (
              <>
                <Loader2 className="animate-spin" /> {t('onb.checking')}
              </>
            ) : (
              <>
                {t('onb.go')} <ArrowRight />
              </>
            )}
          </Button>
          <Button type="button" variant="ghost" className="w-full text-muted-foreground" onClick={() => set({ me: '' })}>
            {t('onb.skip')}
          </Button>
        </form>
      </motion.div>
    </div>
  )
}
