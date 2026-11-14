import { useState, type ReactNode } from 'react'
import { Activity, Bot, ChevronRight, Languages, MonitorSmartphone, Palette, Pencil, Sparkles, Star } from 'lucide-react'
import { LANGS } from '@/lib/i18n'
import { useRouter } from '@/lib/router'
import { useSettings, type Theme } from '@/lib/settings'
import { BOT, can, haptic, startParam, tg } from '@/lib/tg'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { Logo, Panel, Rise } from '@/components/kit'
import { BotSettings } from '@/components/BotSettings'
import { dbReady } from '@/lib/db'

function Segmented<V extends string>({ value, options, onChange }: { value: V; options: { value: V; label: string }[]; onChange: (v: V) => void }) {
  return (
    <div className="grid rounded-xl border bg-muted/50 p-1" style={{ gridTemplateColumns: `repeat(${options.length}, 1fr)` }}>
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => {
            haptic.tap()
            onChange(o.value)
          }}
          className={cn(
            'rounded-lg px-2 py-1.5 text-xs font-medium transition-colors',
            value === o.value ? 'bg-primary text-primary-foreground shadow-[0_0_14px_rgb(34_211_238/0.35)]' : 'text-muted-foreground',
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

function Row({ icon, title, hint, children }: { icon: ReactNode; title: string; hint?: string; children?: ReactNode }) {
  return (
    <div className="space-y-2.5 py-3">
      <div className="flex items-center gap-3">
        <div className="grid size-8 shrink-0 place-items-center rounded-lg bg-primary/12 text-primary [&_svg]:size-4">{icon}</div>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium">{title}</div>
          {hint && <div className="text-xs text-muted-foreground">{hint}</div>}
        </div>
      </div>
      {children}
    </div>
  )
}

export function Me() {
  const { t, me, lang, theme, effects, set } = useSettings()
  const { push } = useRouter()
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(me ?? '')

  return (
    <>
      <Rise i={0}>
        <Panel title={t('me.handle')} glow>
          {editing || !me ? (
            <form
              className="flex gap-2"
              onSubmit={(e) => {
                e.preventDefault()
                set({ me: draft.trim() || '' })
                setEditing(false)
              }}
            >
              <Input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder={t('onb.placeholder')} className="font-mono" autoCapitalize="off" spellCheck={false} />
              <Button type="submit">{t('onb.go')}</Button>
            </form>
          ) : (
            <div className="flex items-center gap-2">
              <button className="flex flex-1 items-center gap-2 text-left" onClick={() => push({ name: 'profile', handle: me })}>
                <span className="font-mono text-xl font-bold text-primary text-glow">{me}</span>
                <ChevronRight className="size-4 text-muted-foreground" />
              </button>
              <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
                <Pencil /> {t('me.change')}
              </Button>
            </div>
          )}
        </Panel>
      </Rise>
      <Rise i={1}>
        <Panel title={t('me.settings')}>
          <div className="divide-y">
            <Row icon={<Languages />} title={t('me.language')}>
              <Segmented value={lang} options={LANGS.map((l) => ({ value: l.code, label: l.label }))} onChange={(v) => set({ lang: v })} />
            </Row>
            <Row icon={<Palette />} title={t('me.theme')}>
              <Segmented<Theme>
                value={theme}
                options={[
                  { value: 'dark', label: t('me.theme.dark') },
                  { value: 'light', label: t('me.theme.light') },
                  { value: 'auto', label: t('me.theme.auto') },
                ]}
                onChange={(v) => set({ theme: v })}
              />
            </Row>
            <div className="flex items-center gap-3 py-3">
              <div className="grid size-8 shrink-0 place-items-center rounded-lg bg-primary/12 text-primary [&_svg]:size-4">
                <Sparkles />
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium">{t('me.effects')}</div>
                <div className="text-xs text-muted-foreground">{t('me.effectsHint')}</div>
              </div>
              <Switch checked={effects} onCheckedChange={(v) => set({ effects: v })} aria-label={t('me.effects')} />
            </div>
            {can.homeScreen() && (
              <button className="flex w-full items-center gap-3 py-3 text-left" onClick={() => tg?.addToHomeScreen?.()}>
                <div className="grid size-8 shrink-0 place-items-center rounded-lg bg-primary/12 text-primary [&_svg]:size-4">
                  <MonitorSmartphone />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium">{t('me.home')}</div>
                  <div className="text-xs text-muted-foreground">{t('me.homeHint')}</div>
                </div>
                <ChevronRight className="size-4 text-muted-foreground" />
              </button>
            )}
            <button className="flex w-full items-center gap-3 py-3 text-left" onClick={() => tg?.openTelegramLink(`https://t.me/${BOT}?start=donate`)}>
              <div className="grid size-8 shrink-0 place-items-center rounded-lg bg-warning/15 text-warning [&_svg]:size-4">
                <Star />
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium">{t('me.donate')}</div>
                <div className="text-xs text-muted-foreground">{t('me.donateHint')}</div>
              </div>
              <ChevronRight className="size-4 text-muted-foreground" />
            </button>
            <button className="flex w-full items-center gap-3 py-3 text-left" onClick={() => tg?.openTelegramLink(`https://t.me/${BOT}`)}>
              <div className="grid size-8 shrink-0 place-items-center rounded-lg bg-primary/12 text-primary [&_svg]:size-4">
                <Bot />
              </div>
              <div className="min-w-0 flex-1 text-sm font-medium">{t('me.bot')}</div>
              <ChevronRight className="size-4 text-muted-foreground" />
            </button>
          </div>
        </Panel>
      </Rise>
      {dbReady && (
        <Rise i={2}>
          <BotSettings />
        </Rise>
      )}
      <Rise i={3}>
        <button className="flex w-full items-center gap-3 rounded-2xl border bg-card/90 p-4 text-left" onClick={() => push({ name: 'status' })}>
          <div className="grid size-8 shrink-0 place-items-center rounded-lg bg-success/15 text-success [&_svg]:size-4">
            <Activity />
          </div>
          <div className="min-w-0 flex-1 text-sm font-medium">{t('st.open')}</div>
          <ChevronRight className="size-4 text-muted-foreground" />
        </button>
      </Rise>
      <Rise i={4}>
        <div className="flex flex-col items-center gap-1 py-4 text-xs text-muted-foreground">
          <Logo className="opacity-70" />
          <span>{t('me.about')}</span>
          <span className="font-mono text-[10px] opacity-60">
            {tg?.platform ?? 'web'} · v{tg?.version ?? '-'}
            {startParam ? ` · start=${startParam}` : ''}
          </span>
        </div>
      </Rise>
    </>
  )
}
