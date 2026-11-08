import type { ReactNode } from 'react'
import { ExternalLink, Radio, Trophy } from 'lucide-react'
import { useCall } from '@/lib/api'
import { cfUrl, type Contest, type ContestList } from '@/lib/cf'
import { useRouter } from '@/lib/router'
import { useSettings } from '@/lib/settings'
import { openLink } from '@/lib/tg'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { ErrorState, Loading, Panel, Rise, useNow } from '@/components/kit'
import { cn } from '@/lib/utils'

function Row({ c, now }: { c: Contest; now: number }) {
  const { t, fmt } = useSettings()
  const { push } = useRouter()
  const start = c.start ?? 0
  const end = start + c.duration
  const live = c.phase === 'CODING'
  const before = c.phase === 'BEFORE'
  const soon = before && start - now < 86400
  return (
    <div className="flex items-center gap-3 py-3">
      <div
        className={cn(
          'grid w-12 shrink-0 place-items-center rounded-xl border py-1.5 font-mono',
          live ? 'border-success/50 text-success' : soon ? 'border-primary/50 text-primary' : 'text-muted-foreground',
        )}
      >
        <span className="text-lg font-bold leading-none">{new Date(start * 1000).getDate()}</span>
        <span className="text-[10px] uppercase">{fmt.month(start)}</span>
      </div>
      <button className="min-w-0 flex-1 text-left" onClick={() => openLink(cfUrl.contest(c.id))}>
        <div className="line-clamp-2 font-medium leading-snug">{c.name}</div>
        <div className="mt-0.5 font-mono text-[11px] text-muted-foreground">
          {fmt.time(start)} · {fmt.span(c.duration)} · {c.type}
        </div>
        {live && <Progress value={((now - start) / c.duration) * 100} className="mt-2 h-1" />}
      </button>
      {before ? (
        <Badge variant="outline" className={cn('shrink-0 font-mono', soon && 'border-primary/60 text-primary')}>
          {t('contests.in', fmt.span(start - now))}
        </Badge>
      ) : live ? (
        <Badge className="shrink-0 bg-success/15 font-mono text-success">{t('contests.left', fmt.span(end - now))}</Badge>
      ) : (
        <Button size="icon-sm" variant="ghost" aria-label={t('contests.standings')} onClick={() => push({ name: 'standings', contestId: c.id })}>
          <Trophy />
        </Button>
      )}
    </div>
  )
}

export function Contests() {
  const { t } = useSettings()
  const { data, error, loading, reload } = useCall<ContestList>('contests', {}, 300_000)
  const now = useNow(30_000)
  if (error) return <ErrorState code={error} onRetry={reload} />
  if (loading || !data) return <Loading lines={8} />
  const section = (title: string, list: Contest[], i: number, icon?: ReactNode) =>
    list.length > 0 && (
      <Rise i={i}>
        <Panel title={title} extra={icon} glow={i === 0 && data.live.length > 0}>
          <div className="divide-y">
            {list.map((c) => (
              <Row key={c.id} c={c} now={now} />
            ))}
          </div>
        </Panel>
      </Rise>
    )
  return (
    <>
      {section(t('contests.live'), data.live, 0, <Radio className="size-4 animate-pulse text-success" />)}
      {section(t('contests.upcoming'), data.upcoming, 1)}
      {section(t('contests.finished'), data.finished, 2, <ExternalLink className="size-3.5 text-muted-foreground" />)}
    </>
  )
}
