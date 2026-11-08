import { useState } from 'react'
import { Check, ExternalLink, GitCompareArrows, ListTodo, MapPin, UserPlus } from 'lucide-react'
import { call, forget, useCall } from '@/lib/api'
import { cfUrl, ratingColor, VERDICT_SHORT, type Comparison, type FriendsAnswer, type Profile as P } from '@/lib/cf'
import { useRouter } from '@/lib/router'
import { useSettings } from '@/lib/settings'
import { haptic, openLink } from '@/lib/tg'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Avatar, Bars, CountUp, ErrorState, Handle, Loading, Panel, Rise, Stat } from '@/components/kit'
import { DifficultyChart, Heatmap, RatingChart, WeeklyArea } from '@/components/charts'
import { ShareBar } from '@/components/ShareBar'

function FollowButton({ handle }: { handle: string }) {
  const { t, me } = useSettings()
  const friends = useCall<FriendsAnswer>('friends', { action: 'list' }, 300_000)
  const [busy, setBusy] = useState(false)
  if (me && me.toLowerCase() === handle.toLowerCase()) return null
  const following = friends.data?.friends.some((f) => f.handle.toLowerCase() === handle.toLowerCase())
  return (
    <Button
      size="sm"
      variant={following ? 'secondary' : 'default'}
      disabled={busy || !friends.data}
      onClick={async () => {
        setBusy(true)
        try {
          const res = await call<FriendsAnswer>('friends', { action: following ? 'remove' : 'add', handles: [handle] })
          friends.set(res)
          forget('activity')
          forget('standings')
          haptic.success()
        } catch {
          haptic.error()
        } finally {
          setBusy(false)
        }
      }}
    >
      {following ? <Check /> : <UserPlus />} {following ? t('pr.following') : t('pr.follow')}
    </Button>
  )
}

export default function Profile({ handle }: { handle: string }) {
  const { t, fmt } = useSettings()
  const { push } = useRouter()
  const { data, error, loading, reload } = useCall<P>('profile', { handle }, 600_000)
  const history = useCall<Comparison>('compare', { handles: [handle] }, 600_000)
  if (error) return <ErrorState code={error} onRetry={reload} />
  if (loading || !data) return <Loading lines={8} />
  const u = data.user
  const s = data.stats
  const color = ratingColor(u.rating)
  const yearSubs = s.heatmap.reduce((a, d) => a + d.count, 0)
  const acRate = s.submissions ? Math.round(((s.verdicts.find((v) => v.name === 'OK')?.count ?? 0) / s.submissions) * 100) : 0
  return (
    <>
      <Rise i={0}>
        <Panel glow className="relative overflow-hidden">
          <div className="pointer-events-none absolute -top-16 -right-16 size-48 rounded-full blur-3xl" style={{ background: color, opacity: 0.18 }} />
          <div className="relative flex items-center gap-4">
            <Avatar src={u.avatar} handle={u.handle} rating={u.rating} size={72} />
            <div className="min-w-0 flex-1">
              <Handle handle={u.handle} rating={u.rating} className="text-2xl" />
              <div className="text-sm font-medium capitalize" style={{ color }}>
                {u.rank ?? t('unrated')}
              </div>
              {(u.organization || u.country) && (
                <div className="mt-0.5 flex items-center gap-1 truncate text-xs text-muted-foreground">
                  <MapPin className="size-3" /> {[u.organization, u.country].filter(Boolean).join(' · ')}
                </div>
              )}
            </div>
          </div>
          <div className="relative mt-4 flex flex-wrap gap-2">
            <FollowButton handle={u.handle} />
            <Button size="sm" variant="outline" onClick={() => push({ name: 'compare', handles: [u.handle] })}>
              <GitCompareArrows /> {t('pr.compare')}
            </Button>
            <Button size="sm" variant="outline" onClick={() => push({ name: 'upsolve', handle: u.handle })}>
              <ListTodo /> {t('up.title')}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => openLink(cfUrl.profile(u.handle))}>
              <ExternalLink /> CF
            </Button>
          </div>
          <div className="relative mt-4 grid grid-cols-3 gap-2">
            <Stat label={t('pr.rating')} value={u.rating == null ? '—' : <CountUp value={u.rating} group={false} />} color={color} />
            <Stat label={t('pr.max')} value={u.maxRating ?? '—'} color={ratingColor(u.maxRating)} />
            <Stat label={t('pr.solved')} value={<CountUp value={s.solved} />} />
            <Stat label={t('pr.contests')} value={data.contests} />
            <Stat label={t('pr.best')} value={data.best ? `#${data.best.rank}` : '—'} />
            <Stat label={t('pr.streak')} value={s.streak} color={s.streak > 0 ? 'var(--warning)' : undefined} />
          </div>
          <div className="relative mt-4">
            <ShareBar route={{ name: 'profile', handle: u.handle }} text={t('share.profile', u.handle, String(u.rating ?? t('unrated')))} />
          </div>
        </Panel>
      </Rise>
      {data.contests > 0 && (
        <Rise i={1}>
          <Panel title={t('pr.history')}>
            {history.data ? <RatingChart lines={[{ handle: u.handle, color: 'var(--primary)', points: history.data.series[0]?.points ?? [] }]} /> : <Loading lines={4} className="border-0 p-0" />}
          </Panel>
        </Rise>
      )}
      <Rise i={2}>
        <Panel title={t('pr.activity')} extra={<span className="font-mono text-[11px] text-muted-foreground">{t('pr.subsYear', fmt.number(yearSubs))}</span>}>
          <WeeklyArea days={s.heatmap} />
          <div className="mt-2">
            <Heatmap days={s.heatmap} />
          </div>
        </Panel>
      </Rise>
      {s.ratings.length > 0 && (
        <Rise i={3}>
          <Panel title={t('pr.difficulty')}>
            <DifficultyChart items={s.ratings} />
          </Panel>
        </Rise>
      )}
      {s.tags.length > 0 && (
        <Rise i={4}>
          <Panel title={t('pr.tags')}>
            <Bars items={s.tags} />
          </Panel>
        </Rise>
      )}
      <Rise i={5} className="grid gap-3 sm:grid-cols-2">
        <Panel title={t('pr.verdicts')} extra={<Badge variant="outline" className="font-mono">AC {acRate}%</Badge>}>
          <Bars items={s.verdicts.map((v) => ({ name: VERDICT_SHORT[v.name] ?? v.name, count: v.count }))} />
        </Panel>
        <Panel title={t('pr.languages')}>
          <Bars items={s.languages} color="var(--violet)" />
        </Panel>
      </Rise>
      <Rise i={6}>
        <Panel title={t('pr.recent')}>
          <ul className="divide-y">
            {s.recent.map((r) => (
              <li key={r.id}>
                <button
                  className="flex w-full items-center gap-3 py-2.5 text-left disabled:cursor-default"
                  disabled={!r.contestId}
                  onClick={() => r.contestId && openLink(cfUrl.submission(r.contestId, r.id))}
                >
                  <span
                    className={cn(
                      'w-12 shrink-0 rounded-md py-0.5 text-center font-mono text-[11px] font-bold',
                      r.verdict === 'OK' ? 'bg-success/15 text-success' : 'bg-destructive/15 text-destructive',
                    )}
                  >
                    {VERDICT_SHORT[r.verdict] ?? r.verdict}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-sm">
                    <span className="font-mono text-muted-foreground">
                      {r.contestId}
                      {r.index}
                    </span>{' '}
                    {r.name}
                  </span>
                  {r.rating && (
                    <span className="font-mono text-xs font-semibold" style={{ color: ratingColor(r.rating) }}>
                      {r.rating}
                    </span>
                  )}
                  <span className="w-14 shrink-0 text-right text-[11px] text-muted-foreground">{fmt.ago(r.time)}</span>
                </button>
              </li>
            ))}
          </ul>
        </Panel>
      </Rise>
    </>
  )
}
