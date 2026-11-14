// Public service status: the bot's heartbeat and counters from its database, Codeforces and
// the Mini App's own backend (both answer through the contests endpoint).
import { useEffect, useState, type ReactNode } from 'react'
import { Activity, Bot, CloudCog, Server } from 'lucide-react'
import { useCall } from '@/lib/api'
import type { ContestList } from '@/lib/cf'
import { dbReady, rpc } from '@/lib/db'
import { useSettings } from '@/lib/settings'
import { cn } from '@/lib/utils'
import { Loading, Panel, Rise, Stat, useNow } from '@/components/kit'

interface StatusAnswer {
  now: number
  heartbeat: { at: number; commit: string; version: string; startedAt: number } | null
  chats: number
  handles: number
  remindersSent24h: number
  liveContests: number
  nextContest: { name: string; startsAt: number } | null
}

const STALE_S = 180 // three missed beats

function Light({ ok, label, detail, icon }: { ok: boolean | null; label: string; detail?: string; icon: ReactNode }) {
  return (
    <div className="flex items-center gap-3 py-3">
      <span className="grid size-9 place-items-center rounded-xl bg-muted text-muted-foreground [&_svg]:size-4">{icon}</span>
      <div className="min-w-0 flex-1">
        <div className="text-sm font-medium">{label}</div>
        {detail && <div className="truncate font-mono text-[11px] text-muted-foreground">{detail}</div>}
      </div>
      <span
        className={cn(
          'size-3 rounded-full',
          ok === null ? 'bg-muted-foreground/40' : ok ? 'bg-success shadow-[0_0_10px_var(--success)]' : 'bg-destructive shadow-[0_0_10px_var(--destructive)]',
        )}
      />
    </div>
  )
}

export function Status() {
  const { t, fmt } = useSettings()
  const now = useNow(10_000)
  const [status, setStatus] = useState<StatusAnswer | null>(null)
  const [dbError, setDbError] = useState(false)
  const contests = useCall<ContestList>('contests', {}, 60_000)

  useEffect(() => {
    if (!dbReady) return
    const load = () =>
      rpc<StatusAnswer>('app_status', {}, false)
        .then((s) => {
          setStatus(s)
          setDbError(false)
        })
        .catch(() => setDbError(true))
    load()
    const id = setInterval(load, 30_000)
    return () => clearInterval(id)
  }, [])

  const hb = status?.heartbeat ?? null
  const alive = hb ? now - hb.at < STALE_S : dbReady ? (dbError ? false : null) : null
  const cfOk = contests.data ? true : contests.error ? false : null
  return (
    <>
      <Rise i={0}>
        <Panel glow title={t('st.page')}>
          <div className="divide-y">
            <Light
              ok={alive}
              icon={<Bot />}
              label={`${t('st.bot')}: ${alive === null ? t('st.unknown') : alive ? t('st.alive') : t('st.down')}`}
              detail={hb ? `${t('st.lastBeat', fmt.ago(hb.at))} · ${t('st.version', hb.version, hb.commit.slice(0, 7))}` : undefined}
            />
            <Light ok={cfOk} icon={<Activity />} label={`${t('st.cf')}: ${cfOk === false ? t('st.cfBad') : t('st.cfOk')}`} />
            <Light ok={contests.error ? false : contests.data ? true : null} icon={<CloudCog />} label={t('st.app')} detail="app9170246912.tgcloud.ai" />
            {dbReady && <Light ok={dbError ? false : status ? true : null} icon={<Server />} label="Supabase" />}
          </div>
          {hb && <div className="mt-2 text-right font-mono text-[11px] text-muted-foreground">{t('st.uptime', fmt.span(now - hb.startedAt))}</div>}
        </Panel>
      </Rise>
      {dbReady && (
        <Rise i={1}>
          {status ? (
            <div className="grid grid-cols-2 gap-2">
              <Stat label={t('st.chats')} value={status.chats} />
              <Stat label={t('st.handles')} value={status.handles} />
              <Stat label={t('st.sent')} value={status.remindersSent24h} />
              <Stat label={t('st.live')} value={status.liveContests} color={status.liveContests ? 'var(--success)' : undefined} />
            </div>
          ) : (
            !dbError && <Loading lines={2} />
          )}
        </Rise>
      )}
      {status?.nextContest && (
        <Rise i={2}>
          <Panel title={t('st.next')}>
            <div className="font-medium">{status.nextContest.name}</div>
            <div className="font-mono text-xs text-muted-foreground">
              {fmt.weekday(status.nextContest.startsAt)} · {t('contests.in', fmt.span(status.nextContest.startsAt - now))}
            </div>
          </Panel>
        </Rise>
      )}
    </>
  )
}
