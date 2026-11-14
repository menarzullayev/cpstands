import { useState } from 'react'
import { Plus, X } from 'lucide-react'
import { useCall } from '@/lib/api'
import { ratingColor, type Comparison } from '@/lib/cf'
import { useRouter } from '@/lib/router'
import { useSettings } from '@/lib/settings'
import { haptic } from '@/lib/tg'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Avatar, Empty, ErrorState, Handle, Loading, Panel, Rise } from '@/components/kit'
import { RatingChart } from '@/components/charts'
import { ShareBar } from '@/components/ShareBar'

const MAX = 6
// Line colours distinct from each other and readable on both themes.
const PALETTE = ['#22d3ee', '#a78bfa', '#4ade80', '#fbbf24', '#f472b6', '#fb923c']

export default function Compare({ initial }: { initial: string[] }) {
  const { t, me, fmt } = useSettings()
  const { push } = useRouter()
  const [handles, setHandles] = useState<string[]>(() => {
    const start = initial.length === 1 && me && me.toLowerCase() !== initial[0].toLowerCase() ? [me, ...initial] : initial
    return start.slice(0, MAX)
  })
  const [draft, setDraft] = useState('')
  const [all, setAll] = useState(false)
  const { data, error, loading, reload } = useCall<Comparison>('compare', handles.length ? { handles } : null, 600_000)
  const colorOf = (h: string) => PALETTE[Math.max(0, handles.findIndex((x) => x.toLowerCase() === h.toLowerCase())) % PALETTE.length]

  const add = () => {
    const next = [...handles]
    for (const p of draft.split(/[\s,;]+/).map((x) => x.trim()).filter(Boolean)) {
      if (next.length < MAX && !next.some((h) => h.toLowerCase() === p.toLowerCase())) next.push(p)
    }
    haptic.tap()
    setHandles(next)
    setDraft('')
  }

  // Wins: in how many common contests each handle had the best place.
  const wins: Record<string, number> = {}
  for (const row of data?.common ?? []) {
    const best = Math.min(...Object.values(row.ranks))
    for (const [h, r] of Object.entries(row.ranks)) if (r === best) wins[h] = (wins[h] ?? 0) + 1
  }

  return (
    <>
      <Rise i={0}>
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            add()
          }}
        >
          <Input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={handles.length >= MAX ? t('cmp.max') : t('cmp.placeholder')}
            disabled={handles.length >= MAX}
            className="h-10 font-mono"
            autoCapitalize="off"
            spellCheck={false}
          />
          <Button type="submit" className="h-10" disabled={!draft.trim() || handles.length >= MAX}>
            <Plus />
          </Button>
        </form>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {handles.map((h) => (
            <button
              key={h}
              onClick={() => setHandles(handles.filter((x) => x !== h))}
              className="flex items-center gap-1.5 rounded-full border bg-card px-2.5 py-1 font-mono text-xs"
              style={{ borderColor: colorOf(h) }}
            >
              <span className="size-2 rounded-full" style={{ background: colorOf(h) }} />
              {h}
              <X className="size-3 text-muted-foreground" />
            </button>
          ))}
        </div>
      </Rise>
      {handles.length < 2 && <Empty>{t('cmp.empty')}</Empty>}
      {handles.length > 0 &&
        (error ? (
          <ErrorState code={error} onRetry={reload} />
        ) : loading || !data ? (
          <Loading lines={6} />
        ) : (
          <>
            <Rise i={1}>
              <Panel glow extra={<ShareBar route={{ name: 'compare', handles }} text={t('share.compare', data.series.map((s) => `${s.handle} ${s.rating ?? '—'}`).join(' · '))} />}>
                <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
                  {data.series.map((s) => (
                    <button
                      key={s.handle}
                      onClick={() => push({ name: 'profile', handle: s.handle })}
                      className="flex items-center gap-2 rounded-xl border bg-muted/40 p-2 text-left"
                      style={{ borderLeft: `3px solid ${colorOf(s.handle)}` }}
                    >
                      <Avatar src={s.avatar} handle={s.handle} rating={s.rating} size={30} />
                      <div className="min-w-0">
                        <Handle handle={s.handle} rating={s.rating} className="block truncate text-sm" />
                        <div className="font-mono text-[11px] text-muted-foreground">
                          {s.rating ?? '—'} / <span style={{ color: ratingColor(s.maxRating) }}>{s.maxRating ?? '—'}</span>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
                <RatingChart lines={data.series.map((s) => ({ handle: s.handle, color: colorOf(s.handle), points: s.points }))} />
              </Panel>
            </Rise>
            {data.series.length >= 2 && (
              <Rise i={2}>
                <Panel title={t('cmp.h2h')}>
                  <div className="mb-3 flex flex-wrap gap-3 font-mono text-xs">
                    {data.series.map((s) => (
                      <span key={s.handle}>
                        <span style={{ color: colorOf(s.handle) }}>{s.handle}</span> <b>{wins[s.handle] ?? 0}</b>{' '}
                        <span className="text-muted-foreground">{t('cmp.wins')}</span>
                      </span>
                    ))}
                  </div>
                  {data.common.length === 0 ? (
                    <p className="text-sm text-muted-foreground">{t('cmp.noCommon')}</p>
                  ) : (
                    <table className="w-full table-fixed text-sm">
                      <thead>
                        <tr className="border-b font-mono text-[11px]">
                          <th className="w-[44%] py-2 text-left font-normal text-muted-foreground">{t('cmp.contest')}</th>
                          {data.series.map((s) => (
                            <th key={s.handle} className="truncate py-2 text-center" style={{ color: colorOf(s.handle) }}>
                              {s.handle}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {data.common.slice(0, all ? undefined : 10).map((row) => {
                          const best = Math.min(...Object.values(row.ranks))
                          return (
                            <tr key={row.contestId} className="border-b last:border-0">
                              <td className="py-2 pr-2">
                                <div className="line-clamp-2 text-xs leading-snug">{row.contest}</div>
                                <div className="font-mono text-[10px] text-muted-foreground">{fmt.date(row.time, false)}</div>
                              </td>
                              {data.series.map((s) => {
                                const r = row.ranks[s.handle]
                                return (
                                  <td key={s.handle} className={cn('py-2 text-center font-mono text-xs', r === best && 'font-bold text-success')}>
                                    {r ?? '—'}
                                  </td>
                                )
                              })}
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  )}
                  {data.common.length > 10 && (
                    <Button variant="ghost" size="sm" className="mt-1 w-full text-primary" onClick={() => setAll((v) => !v)}>
                      {all ? t('less') : t('more')}
                    </Button>
                  )}
                </Panel>
              </Rise>
            )}
          </>
        ))}
    </>
  )
}
