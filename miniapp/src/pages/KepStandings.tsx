// A kep.uz contest table: everyone, or only the handles the user follows on kep.uz.
import { useState } from 'react'
import { ExternalLink, RotateCw, Share2 } from 'lucide-react'
import { useCall } from '@/lib/api'
import { kepUrl, type KepCell, type KepStandingsAnswer } from '@/lib/kep'
import { routeParam, useRouter } from '@/lib/router'
import { useSettings } from '@/lib/settings'
import { appLink, openLink, shareLink } from '@/lib/tg'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Empty, ErrorState, Loading, Panel, Rise } from '@/components/kit'

const PAGE = 50

function Cell({ c, icpc }: { c: KepCell; icpc: boolean }) {
  const solved = c.points > 0
  if (!solved && c.rejected === 0) return <td className="px-1 py-2 text-center text-muted-foreground/40">·</td>
  const minutes = c.time != null ? Math.floor(c.time / 60) : null
  return (
    <td
      className={cn(
        'px-1 py-2 text-center font-mono text-[11px] leading-tight',
        solved ? 'bg-success/10 text-success' : 'bg-destructive/10 text-destructive',
      )}
    >
      <div className="font-semibold">{solved ? (icpc ? `+${c.rejected || ''}` : Math.round(c.points)) : `-${c.rejected}`}</div>
      {solved && minutes != null && (
        <div className="text-[9px] opacity-70">
          {Math.floor(minutes / 60)}:{String(minutes % 60).padStart(2, '0')}
        </div>
      )}
    </td>
  )
}

export function KepStandings({ contestId, handles }: { contestId: number; handles?: string[] }) {
  const { t, fmt } = useSettings()
  const { push } = useRouter()
  const [shown, setShown] = useState(PAGE)
  const input = { op: 'standings', contestId, handles }
  const { data, error, loading, reload, refreshing } = useCall<KepStandingsAnswer>('kep', input, 30_000)
  if (error === 'NOT_STARTED') return <Empty icon={<RotateCw />}>{t('kep.notStarted')}</Empty>
  if (error) return <ErrorState code={error} onRetry={reload} />
  if (loading || !data) return <Loading lines={8} />

  const c = data.contest
  const icpc = c.type === 'ICPC'
  const live = c.phase === 'CODING'
  const rows = data.rows.slice(0, shown)
  return (
    <>
      <Rise i={0}>
        <Panel glow={live}>
          <div className="flex items-start gap-3">
            <div className="min-w-0 flex-1">
              <div className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted-foreground">kep.uz</div>
              <div className="line-clamp-2 text-lg font-semibold leading-snug">{c.name}</div>
              <div className="mt-1 font-mono text-[11px] text-muted-foreground">
                {c.start ? `${fmt.time(c.start)} · ` : ''}
                {fmt.span(c.duration)} · {t('kep.rows', data.total ?? data.rows.length)}
              </div>
            </div>
            {live ? (
              <Badge className="shrink-0 bg-success/15 text-success">{t('contests.live')}</Badge>
            ) : (
              <Badge variant="outline" className="shrink-0">
                {c.phase === 'BEFORE' ? t('contests.upcoming') : t('contests.finished')}
              </Badge>
            )}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button size="sm" variant="outline" onClick={reload} disabled={refreshing}>
              <RotateCw className={cn(refreshing && 'animate-spin')} /> {t('st.refresh')}
            </Button>
            <Button size="sm" variant="outline" onClick={() => openLink(kepUrl.standings(c.id))}>
              <ExternalLink /> kep.uz
            </Button>
            <Button
              size="sm"
              variant="ghost"
              aria-label={t('share')}
              onClick={() => shareLink(appLink(routeParam({ name: 'kstandings', contestId: c.id })), c.name)}
            >
              <Share2 />
            </Button>
          </div>
        </Panel>
      </Rise>
      {c.phase === 'BEFORE' ? (
        <Empty>{t('kep.notStarted')}</Empty>
      ) : rows.length === 0 ? (
        <Empty>{handles ? t('st.nobody') : t('kep.empty')}</Empty>
      ) : (
        <Rise i={1}>
          <Panel>
            <div className="-mx-4 overflow-x-auto">
              <table className="w-full min-w-max border-collapse text-sm">
                <thead>
                  <tr className="text-left font-mono text-[11px] text-muted-foreground">
                    <th className="px-2 py-1.5">{t('st.rank')}</th>
                    <th className="px-2 py-1.5">{t('st.who')}</th>
                    <th className="px-2 py-1.5 text-right">{t('st.score')}</th>
                    {data.problems.map((p) => (
                      <th key={p.index} className="px-1 py-1.5 text-center" title={p.name}>
                        <button onClick={() => openLink(kepUrl.problem(c.id, p.index))}>{p.index}</button>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {rows.map((r) => (
                    <tr key={`${r.handle}-${r.virtual}`} className={cn(r.virtual && 'opacity-60')}>
                      <td className="px-2 py-2 font-mono text-xs">{r.rank}</td>
                      <td className="max-w-40 px-2 py-2">
                        <button
                          className="block truncate text-left font-medium"
                          onClick={() => push({ name: 'kprofile', handle: r.handle })}
                        >
                          {r.handle}
                        </button>
                        {r.virtual && <span className="text-[10px] text-muted-foreground">{t('kep.virtual')}</span>}
                      </td>
                      <td className="px-2 py-2 text-right font-mono text-xs">
                        <div className="font-semibold">{r.points}</div>
                        {icpc && <div className="text-[10px] text-muted-foreground">{r.penalty}</div>}
                      </td>
                      {r.cells.map((cell, i) => (
                        <Cell key={i} c={cell} icpc={icpc} />
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {data.rows.length > shown && (
              <Button variant="ghost" className="mt-2 w-full" onClick={() => setShown((n) => n + PAGE)}>
                {t('more')}
              </Button>
            )}
          </Panel>
        </Rise>
      )}
    </>
  )
}
