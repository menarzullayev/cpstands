// The bot's own chat settings (the same row /settings edits), through the database API.
import { useEffect, useState, type ReactNode } from 'react'
import { Bell, BellRing, Columns3, Globe2, ScrollText } from 'lucide-react'
import { rpc } from '@/lib/db'
import { useSettings } from '@/lib/settings'
import { ApiError, haptic } from '@/lib/tg'
import { cn } from '@/lib/utils'
import { Switch } from '@/components/ui/switch'
import { ErrorState, Loading, Panel } from '@/components/kit'

interface BotChat {
  status: string
  language: string | null
  timeZone: string
  tone: string
  reminders: number[]
  alerts: boolean
  notifyLevel: number
  tableCols: number
  summary: boolean
}

const OFFSETS: { min: number; label: string }[] = [
  { min: 4320, label: '3d' },
  { min: 1440, label: '24h' },
  { min: 120, label: '2h' },
  { min: 60, label: '1h' },
  { min: 10, label: '10m' },
]
const ZONES = ['Asia/Tashkent', 'Asia/Almaty', 'Asia/Bishkek', 'Asia/Dushanbe', 'Europe/Moscow', 'Europe/Istanbul', 'Europe/Berlin', 'Europe/London', 'America/New_York', 'Asia/Tokyo', 'UTC']

function Chip({ on, children, onClick }: { on: boolean; children: ReactNode; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'rounded-lg border px-2.5 py-1.5 font-mono text-xs font-semibold transition-colors',
        on ? 'border-primary bg-primary/15 text-primary' : 'text-muted-foreground',
      )}
    >
      {children}
    </button>
  )
}

function Row({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <div className="space-y-2 py-3">
      <div className="flex items-center gap-2 text-sm font-medium">
        <span className="text-primary [&_svg]:size-4">{icon}</span>
        {title}
      </div>
      {children}
    </div>
  )
}

export function BotSettings() {
  const { t } = useSettings()
  const [chat, setChat] = useState<BotChat | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  const load = () => {
    setError(null)
    rpc<BotChat>('app_settings')
      .then(setChat)
      .catch((e: unknown) => setError(e instanceof ApiError ? e.code : 'generic'))
  }
  useEffect(load, [])

  const save = async (patch: Partial<BotChat>) => {
    if (!chat) return
    haptic.tap()
    setChat({ ...chat, ...patch }) // optimistic
    try {
      setChat(await rpc<BotChat>('app_settings_update', { patch }))
      setSaved(true)
      setTimeout(() => setSaved(false), 1200)
    } catch (e) {
      haptic.error()
      setError(e instanceof ApiError ? e.code : 'generic')
      load()
    }
  }

  return (
    <Panel title={t('bs.title')} extra={saved && <span className="font-mono text-[11px] text-success">✓ {t('bs.saved')}</span>}>
      <p className="-mt-1 text-xs text-muted-foreground">{t('bs.hint')}</p>
      {error ? (
        <div className="mt-3">
          <ErrorState code={error} onRetry={load} />
        </div>
      ) : !chat ? (
        <Loading lines={4} className="mt-3 border-0 p-0" />
      ) : (
        <div className="divide-y">
          {chat.status !== 'active' && <p className="mt-3 rounded-lg bg-warning/10 p-2 text-xs text-warning">{t('bs.start')}</p>}
          <Row icon={<Bell />} title={t('bs.reminders')}>
            <div className="flex flex-wrap gap-1.5">
              {OFFSETS.map((o) => {
                const on = chat.reminders.includes(o.min)
                return (
                  <Chip
                    key={o.min}
                    on={on}
                    onClick={() => save({ reminders: on ? chat.reminders.filter((m) => m !== o.min) : [...chat.reminders, o.min] })}
                  >
                    {o.label}
                  </Chip>
                )
              })}
            </div>
          </Row>
          <Row icon={<BellRing />} title={t('bs.alerts')}>
            <div className="grid grid-cols-5 gap-1">
              {[0, 1, 2, 3, 4].map((level) => (
                <button
                  key={level}
                  onClick={() => save({ notifyLevel: level, alerts: level > 0 })}
                  className={cn(
                    'rounded-lg border px-1 py-1.5 text-[10.5px] leading-tight',
                    chat.notifyLevel === level && (level > 0 ? chat.alerts : true) ? 'border-primary bg-primary/15 text-primary' : 'text-muted-foreground',
                  )}
                >
                  {t(`bs.level.${level}` as 'bs.level.0')}
                </button>
              ))}
            </div>
          </Row>
          <Row icon={<Columns3 />} title={t('bs.cols')}>
            <div className="flex gap-1.5">
              {[8, 12, 16].map((n) => (
                <Chip key={n} on={chat.tableCols === n} onClick={() => save({ tableCols: n })}>
                  {n}
                </Chip>
              ))}
            </div>
          </Row>
          <Row icon={<Globe2 />} title={t('bs.zone')}>
            <select
              value={chat.timeZone}
              onChange={(e) => save({ timeZone: e.target.value })}
              className="h-9 w-full rounded-lg border bg-card px-2 font-mono text-sm"
            >
              {[...new Set([chat.timeZone, ...ZONES])].map((z) => (
                <option key={z} value={z}>
                  {z}
                </option>
              ))}
            </select>
          </Row>
          <div className="flex items-center gap-2 py-3 text-sm font-medium">
            <span className="text-primary [&_svg]:size-4">
              <ScrollText />
            </span>
            <span className="flex-1">{t('bs.summary')}</span>
            <Switch checked={chat.summary} onCheckedChange={(v) => save({ summary: v })} aria-label={t('bs.summary')} />
          </div>
        </div>
      )}
    </Panel>
  )
}
