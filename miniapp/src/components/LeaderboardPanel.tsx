import { useEffect, useState } from 'react'
import { Crown, Medal } from 'lucide-react'
import { useCall } from '@/lib/api'
import type { Leaderboard } from '@/lib/cf'
import { useRouter } from '@/lib/router'
import { useSettings } from '@/lib/settings'
import { cn } from '@/lib/utils'
import { ErrorState, Handle, Loading, Panel, Rise } from '@/components/kit'

const PLACE = ['text-warning', 'text-[#cbd5e1]', 'text-[#d97706]']

/** Friends ranked by problems solved, then rating gained, in the last week or month. */
export function LeaderboardPanel() {
  const { t, me } = useSettings()
  const { push } = useRouter()
  const [period, setPeriod] = useState<'week' | 'month'>('week')
  const { data, error, loading, reload } = useCall<Leaderboard>('leaderboard', { period, me: me || undefined }, 300_000)
  useEffect(() => {
    if (!data?.pending) return
    const id = setTimeout(reload, 3000)
    return () => clearTimeout(id)
  }, [data, reload])
  const myKey = me?.toLowerCase()
  return (
    <Panel
      glow
      title={t('fr.board')}
      extra={
        <div className="flex rounded-lg border bg-muted/50 p-0.5">
          {(['week', 'month'] as const).map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={cn('rounded-md px-2.5 py-1 text-xs font-medium', period === p ? 'bg-primary text-primary-foreground' : 'text-muted-foreground')}
            >
              {t(p === 'week' ? 'lb.week' : 'lb.month')}
            </button>
          ))}
        </div>
      }
    >
      {error ? (
        <ErrorState code={error} onRetry={reload} />
      ) : loading || !data ? (
        <Loading lines={5} className="border-0 p-0" />
      ) : (
        <>
          <ol className="space-y-1.5">
            {data.rows.map((r, i) => (
              <Rise key={r.handle} i={i}>
                <li>
                  <button
                    onClick={() => push({ name: 'profile', handle: r.handle })}
                    className={cn(
                      'flex w-full items-center gap-3 rounded-xl border px-3 py-2.5 text-left',
                      r.handle.toLowerCase() === myKey ? 'border-primary/60 bg-primary/10' : 'bg-muted/30',
                    )}
                  >
                    <span className={cn('grid w-7 shrink-0 place-items-center font-mono text-sm font-bold', PLACE[i] ?? 'text-muted-foreground')}>
                      {i === 0 ? <Crown className="size-5" /> : i < 3 ? <Medal className="size-5" /> : i + 1}
                    </span>
                    <span className="min-w-0 flex-1">
                      <Handle handle={r.handle} rating={r.rating} className="block truncate" />
                      <span className="text-[11px] text-muted-foreground">
                        {t('lb.contests')}: {r.contests}
                        {r.best ? ` · ${t('lb.best', r.best)}` : ''}
                      </span>
                    </span>
                    <span className="text-right">
                      <span className="block font-mono text-lg font-bold leading-none">{r.solved}</span>
                      <span className="text-[10px] text-muted-foreground">{t('lb.solved')}</span>
                    </span>
                    <span
                      className={cn(
                        'w-12 text-right font-mono text-xs font-semibold',
                        r.delta > 0 ? 'text-success' : r.delta < 0 ? 'text-destructive' : 'text-muted-foreground',
                      )}
                    >
                      {r.delta > 0 ? '+' : r.delta === 0 ? '±' : ''}
                      {r.delta}
                    </span>
                  </button>
                </li>
              </Rise>
            ))}
          </ol>
          {data.pending > 0 && <p className="mt-2 text-center font-mono text-[11px] text-muted-foreground">{t('home.pending', data.pending)}</p>}
        </>
      )}
    </Panel>
  )
}
