// A kep.uz user: rating, title, place and the rating history.
import { ExternalLink, Trophy } from 'lucide-react'
import { useCall } from '@/lib/api'
import { kepUrl, type KepProfileAnswer } from '@/lib/kep'
import { useRouter } from '@/lib/router'
import { useSettings } from '@/lib/settings'
import { openLink } from '@/lib/tg'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { CountUp, ErrorState, Loading, Panel, Rise, Stat } from '@/components/kit'
import { RatingChart } from '@/components/charts'

export default function KepProfile({ handle }: { handle: string }) {
  const { t } = useSettings()
  const { push } = useRouter()
  const { data, error, loading, reload } = useCall<KepProfileAnswer>('kep', { op: 'profile', handle }, 600_000)
  if (error) return <ErrorState code={error} onRetry={reload} />
  if (loading || !data) return <Loading lines={8} />
  const points = data.history.map((h) => ({
    contestId: h.contestId,
    contest: h.name,
    time: Math.floor(Date.parse(`${h.date}T00:00:00Z`) / 1000),
    rank: h.rank,
    old: h.rating - h.delta,
    rating: h.rating,
  }))
  const recent = [...data.history].reverse().slice(0, 10)
  return (
    <>
      <Rise i={0}>
        <Panel glow>
          <div className="flex items-start gap-3">
            <div className="min-w-0 flex-1">
              <div className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted-foreground">kep.uz</div>
              <div className="truncate text-xl font-semibold">{data.handle}</div>
              <div className="text-sm text-muted-foreground">{data.title ?? t('unrated')}</div>
            </div>
            <Button size="sm" variant="outline" onClick={() => openLink(kepUrl.profile(data.handle))}>
              <ExternalLink /> kep.uz
            </Button>
          </div>
          <div className="mt-4 grid grid-cols-3 gap-2">
            <Stat label={t('kep.rating')} value={data.rating != null ? <CountUp value={data.rating} /> : '—'} />
            <Stat label={t('kep.max')} value={data.maxRating ?? '—'} />
            <Stat label={t('kep.place')} value={data.place ? `#${data.place}` : '—'} />
          </div>
          <p className="mt-3 text-xs text-muted-foreground">{t('kep.contests', data.contests)}</p>
        </Panel>
      </Rise>
      {points.length > 1 && (
        <Rise i={1}>
          <Panel title={t('kep.history')}>
            <RatingChart lines={[{ handle: data.handle, color: 'var(--primary)', points }]} />
          </Panel>
        </Rise>
      )}
      {recent.length > 0 && (
        <Rise i={2}>
          <Panel title={t('kep.recent')}>
            <ul className="divide-y">
              {recent.map((h) => (
                <li key={h.contestId}>
                  <button
                    className="flex w-full items-center gap-3 py-2.5 text-left"
                    onClick={() => push({ name: 'kstandings', contestId: h.contestId })}
                  >
                    <Trophy className="size-4 shrink-0 text-muted-foreground" />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium">{h.name}</span>
                      <span className="font-mono text-[11px] text-muted-foreground">
                        {h.date} · #{h.rank}
                      </span>
                    </span>
                    <span className={cn('font-mono text-sm font-semibold', h.delta >= 0 ? 'text-success' : 'text-destructive')}>
                      {h.delta >= 0 ? `+${h.delta}` : h.delta}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </Panel>
        </Rise>
      )}
    </>
  )
}
