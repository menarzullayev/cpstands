import { useState } from 'react'
import { RotateCw, Share2, UserPlus } from 'lucide-react'
import { useCall } from '@/lib/api'
import { useFriendHandles } from '@/lib/friends'
import { cfUrl, LIVE_PHASES, type StandingsAnswer } from '@/lib/cf'
import { routeParam, useRouter } from '@/lib/router'
import { useSettings } from '@/lib/settings'
import { appLink, openLink, shareLink } from '@/lib/tg'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Empty, ErrorState, Handle, Loading, Panel, Rise } from '@/components/kit'

function Cell({ c, icpc }: { c: StandingsAnswer['rows'][number]['cells'][number]; icpc: boolean }) {
  const solved = c.points > 0
  if (!solved && c.rejected === 0) return <td className="px-1 py-2 text-center text-muted-foreground/40">·</td>
  const minutes = c.time != null ? Math.floor(c.time / 60) : null
  return (
    <td className={cn('px-1 py-2 text-center font-mono text-[11px] leading-tight', solved ? 'bg-success/10 text-success' : 'bg-destructive/10 text-destructive')}>
      <div className="font-semibold">{solved ? (icpc ? `+${c.rejected || ''}` : Math.round(c.points)) : `-${c.rejected}`}</div>
      {solved && minutes != null && (
        <div className="text-[9px] opacity-70">
          {Math.floor(minutes / 60)}:{String(minutes % 60).padStart(2, '0')}
        </div>
      )}
    </td>
  )
}

/** A group passes its own handles (and no personal handle); otherwise the user's friends. */
export function Standings({ contestId: fixed, group }: { contestId?: number; group?: string[] }) {
  const { t, me, fmt } = useSettings()
  const { go } = useRouter()
  const [picked, setPicked] = useState<number | undefined>(fixed)
  const friends = useFriendHandles()
  const handles = group ?? friends
  const input = handles === null ? null : { me: group ? undefined : me || undefined, contestId: picked, handles }
  const { data, error, loading, reload, refreshing } = useCall<StandingsAnswer>('standings', input, 60_000)

  if (error === 'NO_FRIENDS')
    return (
      <Empty icon={<UserPlus />} action={<Button onClick={() => go('friends')}>{t('fr.add')}</Button>}>
        {t('st.noFriends')}
      </Empty>
    )
  if (error) return <ErrorState code={error} onRetry={reload} />
  if (loading || !data || input === null) return <Loading lines={8} />

  const c = data.contest
  const icpc = c?.type === 'ICPC'
  const live = c ? LIVE_PHASES.has(c.phase) : false
  const myKey = me?.toLowerCase()
  return (
    <>
      <Rise i={0}>
        <div className="-mx-3 flex gap-2 overflow-x-auto px-3 pb-1 [scrollbar-width:none]">
          {data.recent.map((r) => (
            <button
              key={r.id}
              onClick={() => setPicked(r.id)}
              className={cn(
                'shrink-0 rounded-full border px-3 py-1.5 text-xs whitespace-nowrap transition-colors',
                c?.id === r.id ? 'border-primary bg-primary/15 text-primary' : 'text-muted-foreground',
              )}
            >
              {LIVE_PHASES.has(r.phase) && <span className="mr-1 inline-block size-1.5 animate-pulse rounded-full bg-success align-middle" />}
              {r.name.replace(/^Codeforces Round /, 'CF ').replace(/Educational Codeforces Round /, 'Edu ')}
            </button>
          ))}
        </div>
      </Rise>
      <Rise i={1}>
        <Panel
          glow={live}
          title={c ? c.name : t('st.title')}
          extra={
            <div className="flex gap-1">
              {live && <Badge className="animate-pulse bg-success/15 text-success">LIVE</Badge>}
              <Button size="icon-sm" variant="ghost" aria-label={t('st.refresh')} onClick={reload}>
                <RotateCw className={cn(refreshing && 'animate-spin')} />
              </Button>
              {c && (
                <Button
                  size="icon-sm"
                  variant="ghost"
                  aria-label={t('share')}
                  onClick={() => shareLink(appLink(routeParam({ name: 'standings', contestId: c.id })), c.name)}
                >
                  <Share2 />
                </Button>
              )}
            </div>
          }
        >
          {c && <div className="-mt-1 mb-3 font-mono text-[11px] text-muted-foreground">{c.start ? fmt.date(c.start) : ''} · {c.type}</div>}
          {data.rows.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t('st.nobody')}</p>
          ) : (
            <div className="-mx-4 overflow-x-auto">
              <table className="w-full min-w-max border-collapse text-sm">
                <thead>
                  <tr className="border-b font-mono text-[11px] text-muted-foreground">
                    <th className="sticky left-0 z-10 bg-card px-2 py-2 text-left">{t('st.rank')}</th>
                    <th className="sticky left-9 z-10 bg-card px-2 py-2 text-left">{t('st.who')}</th>
                    <th className="px-2 py-2 text-right">{t('st.score')}</th>
                    {data.problems.map((p) => (
                      <th key={p.index} className="min-w-9 px-1 py-2 text-center">
                        <button onClick={() => c && openLink(cfUrl.problem(c.id, p.index))} title={p.name}>
                          {p.index}
                        </button>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map((r, i) => {
                    const mine = r.handle.toLowerCase() === myKey
                    return (
                      <tr key={`${r.handle}-${r.type}`} className={cn('border-b last:border-0', mine && 'bg-primary/10')}>
                        <td className={cn('sticky left-0 z-10 px-2 py-2 font-mono text-xs', mine ? 'bg-[color-mix(in_srgb,var(--primary)_10%,var(--card))]' : 'bg-card')}>
                          {i === 0 ? <span className="text-warning">★</span> : null}
                          {r.type === 'CONTESTANT' ? r.rank : '*'}
                        </td>
                        <td className={cn('sticky left-9 z-10 max-w-36 truncate px-2 py-2', mine ? 'bg-[color-mix(in_srgb,var(--primary)_10%,var(--card))]' : 'bg-card')}>
                          <Handle handle={r.handle} rating={null} className="text-foreground" />
                          {r.type !== 'CONTESTANT' && <div className="text-[10px] text-muted-foreground">{t('st.unofficial')}</div>}
                        </td>
                        <td className="px-2 py-2 text-right font-mono text-xs font-semibold">
                          {icpc ? r.points : Math.round(r.points)}
                          {icpc && <div className="text-[10px] font-normal text-muted-foreground">{r.penalty}</div>}
                        </td>
                        {r.cells.map((cell, k) => (
                          <Cell key={k} c={cell} icpc={icpc} />
                        ))}
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      </Rise>
    </>
  )
}
