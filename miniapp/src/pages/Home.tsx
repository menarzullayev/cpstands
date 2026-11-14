import { useEffect, useState } from 'react'
import { Activity as ActivityIcon, ArrowDownRight, ArrowUpRight, ListTodo, Radio, UserPlus, Zap } from 'lucide-react'
import { useCall } from '@/lib/api'
import { useFriendHandles } from '@/lib/friends'
import { cfUrl, nextRank, ratingColor, type Activity, type ActivityEvent, type Comparison, type ContestList } from '@/lib/cf'
import { useRouter } from '@/lib/router'
import { useSettings } from '@/lib/settings'
import { openLink } from '@/lib/tg'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Countdown, CountUp, Empty, ErrorState, Handle, Loading, Panel, Rise, Sparkline } from '@/components/kit'

function NextContest() {
  const { t, fmt } = useSettings()
  const { push } = useRouter()
  const { data, error, loading, reload } = useCall<ContestList>('contests', {}, 300_000)
  if (error) return <ErrorState code={error} onRetry={reload} />
  if (loading || !data) return <Loading lines={3} />
  const live = data.live[0]
  const next = data.upcoming[0]
  const c = live ?? next
  if (!c || !c.start) return <Panel title={t('home.next')}>{t('home.noContest')}</Panel>
  const end = c.start + c.duration
  return (
    <Panel glow title={live ? t('home.live') : t('home.next')} extra={live && <Badge className="animate-pulse bg-success/20 text-success"><Radio /> LIVE</Badge>}>
      <button className="block w-full text-left" onClick={() => (live ? push({ name: 'standings', contestId: c.id }) : openLink(cfUrl.contest(c.id)))}>
        <div className="text-lg font-semibold leading-snug">{c.name}</div>
        <div className="mt-1 font-mono text-xs text-muted-foreground">
          {fmt.weekday(c.start)} · {fmt.span(c.duration)} · {c.type}
        </div>
        <div className="mt-4 text-[11px] uppercase tracking-[0.14em] text-muted-foreground">{live ? t('home.endsIn') : t('home.startsIn')}</div>
        <Countdown to={live ? end : c.start} className="mt-1" />
      </button>
    </Panel>
  )
}

function MyRating() {
  const { t, me } = useSettings()
  const { push, go } = useRouter()
  const { data, error, loading, reload } = useCall<Comparison>('compare', me ? { handles: [me] } : null, 600_000)
  if (!me)
    return (
      <Panel title={t('home.myRating')}>
        <Button variant="outline" className="w-full" onClick={() => go('me')}>
          {t('home.setHandle')}
        </Button>
      </Panel>
    )
  if (error) return <ErrorState code={error} onRetry={reload} />
  if (loading || !data) return <Loading lines={3} />
  const s = data.series[0]
  if (!s) return null
  const last = s.points[s.points.length - 1]
  const rating = s.rating ?? 0
  const next = s.rating != null ? nextRank(s.rating) : null
  const prevFrom = [0, 1200, 1400, 1600, 1900, 2100, 2300, 2400, 2600, 3000].filter((x) => x <= rating).pop() ?? 0
  const progress = next ? ((rating - prevFrom) / (next.from - prevFrom)) * 100 : 100
  const delta = last ? last.rating - last.old : 0
  return (
    <Panel
      title={t('home.myRating')}
      extra={
        <Button size="xs" variant="outline" onClick={() => push({ name: 'upsolve', handle: s.handle })}>
          <ListTodo /> {t('up.title')}
        </Button>
      }
    >
      <button className="block w-full text-left" onClick={() => push({ name: 'profile', handle: s.handle })}>
        <div className="flex items-end justify-between gap-3">
          <div>
            <Handle handle={s.handle} rating={s.rating} className="text-sm" />
            <div className="font-mono text-4xl font-bold" style={{ color: ratingColor(s.rating) }}>
              {s.rating == null ? '—' : <CountUp value={s.rating} group={false} />}
            </div>
            <div className="text-xs capitalize text-muted-foreground">{s.rank ?? t('unrated')}</div>
          </div>
          <div className="flex flex-col items-end gap-1">
            <Sparkline values={s.points.slice(-20).map((p) => p.rating)} />
            {last && (
              <span className={`flex items-center font-mono text-sm font-semibold ${delta >= 0 ? 'text-success' : 'text-destructive'}`}>
                {delta >= 0 ? <ArrowUpRight className="size-4" /> : <ArrowDownRight className="size-4" />}
                {delta >= 0 ? '+' : ''}
                {delta}
              </span>
            )}
          </div>
        </div>
        {s.rating != null && (
          <div className="mt-4 space-y-1.5">
            <Progress value={progress} className="h-1.5" />
            <div className="flex justify-between text-[11px] text-muted-foreground">
              <span>{last ? `${t('home.lastChange')}: #${last.rank}` : ''}</span>
              <span>{next ? t('home.toNext', next.from - rating, next.name) : t('home.top')}</span>
            </div>
          </div>
        )}
      </button>
    </Panel>
  )
}

function EventRow({ e }: { e: ActivityEvent }) {
  const { t, fmt } = useSettings()
  const { push } = useRouter()
  if (e.kind === 'rating') {
    const d = e.rating - e.old
    return (
      <button className="flex w-full items-center gap-3 py-2.5 text-left" onClick={() => push({ name: 'profile', handle: e.handle })}>
        <div className={`grid size-8 shrink-0 place-items-center rounded-lg ${d >= 0 ? 'bg-success/15 text-success' : 'bg-destructive/15 text-destructive'}`}>
          {d >= 0 ? <ArrowUpRight className="size-4" /> : <ArrowDownRight className="size-4" />}
        </div>
        <div className="min-w-0 flex-1 text-sm">
          <Handle handle={e.handle} rating={e.rating} /> <span className="font-mono">{e.old} → {e.rating}</span>
          <div className="truncate text-xs text-muted-foreground">#{e.rank} · {e.contest}</div>
        </div>
        <span className="shrink-0 text-[11px] text-muted-foreground">{fmt.ago(e.time)}</span>
      </button>
    )
  }
  return (
    <button
      className="flex w-full items-center gap-3 py-2.5 text-left"
      onClick={() => e.contestId && openLink(cfUrl.problem(e.contestId, e.index))}
    >
      <div className="grid size-8 shrink-0 place-items-center rounded-lg bg-primary/12 text-primary">
        {e.live ? <Zap className="size-4" /> : <ActivityIcon className="size-4" />}
      </div>
      <div className="min-w-0 flex-1 text-sm">
        <Handle handle={e.handle} rating={null} className="text-foreground" /> <span className="text-muted-foreground">{t('home.solved')}</span>{' '}
        <span className="font-mono">{e.contestId}{e.index}</span>
        {e.live && <span className="text-muted-foreground"> · {t('home.inContest')}</span>}
        <div className="truncate text-xs text-muted-foreground">{e.name}</div>
      </div>
      {e.rating && (
        <span className="shrink-0 font-mono text-xs font-semibold" style={{ color: ratingColor(e.rating) }}>
          {e.rating}
        </span>
      )}
      <span className="w-12 shrink-0 text-right text-[11px] text-muted-foreground">{fmt.ago(e.time)}</span>
    </button>
  )
}

function FriendsActivity() {
  const { t, me } = useSettings()
  const { go } = useRouter()
  const handles = useFriendHandles()
  const { data, error, loading, reload } = useCall<Activity>(
    'activity',
    handles === null ? null : { me: me || undefined, handles },
    120_000,
  )
  const [all, setAll] = useState(false)
  // The endpoint refreshes a few handles per call; ask again while some are still pending.
  useEffect(() => {
    if (!data?.pending) return
    const id = setTimeout(reload, 3000)
    return () => clearTimeout(id)
  }, [data, reload])
  if (error) return <ErrorState code={error} onRetry={reload} />
  if (loading || !data) return <Loading lines={5} />
  if (data.handles === 0 || (data.handles === 1 && me))
    return (
      <Panel title={t('home.activity')}>
        <Empty icon={<UserPlus />} action={<Button onClick={() => go('friends')}>{t('fr.add')}</Button>}>
          {t('home.addFriends')}
        </Empty>
      </Panel>
    )
  return (
    <Panel title={t('home.activity')} extra={data.pending > 0 && <span className="font-mono text-[11px] text-muted-foreground">{t('home.pending', data.pending)}</span>}>
      {data.events.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t('home.noActivity')}</p>
      ) : (
        <>
          <div className="divide-y">
            {data.events.slice(0, all ? 40 : 8).map((e, i) => (
              <Rise key={`${e.kind}-${e.handle}-${e.time}-${i}`} i={i}>
                <EventRow e={e} />
              </Rise>
            ))}
          </div>
          {data.events.length > 8 && (
            <Button variant="ghost" size="sm" className="mt-1 w-full text-primary" onClick={() => setAll((v) => !v)}>
              {all ? t('less') : t('more')}
            </Button>
          )}
        </>
      )}
    </Panel>
  )
}

export function Home() {
  return (
    <>
      <Rise i={0}>
        <NextContest />
      </Rise>
      <Rise i={1}>
        <MyRating />
      </Rise>
      <Rise i={2}>
        <FriendsActivity />
      </Rise>
    </>
  )
}
