import { useState } from 'react'
import { CheckCircle2, Circle, PartyPopper, RotateCcw } from 'lucide-react'
import { useCall } from '@/lib/api'
import { cfUrl, ratingColor, type UpsolveAnswer } from '@/lib/cf'
import { useSettings } from '@/lib/settings'
import { openLink } from '@/lib/tg'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Empty, ErrorState, Handle, Loading, Panel, Rise, Stat } from '@/components/kit'
import { ShareBar } from '@/components/ShareBar'

const STATUS = {
  todo: { icon: Circle, cls: 'border-warning/50 text-warning bg-warning/10' },
  upsolved: { icon: RotateCcw, cls: 'border-primary/50 text-primary bg-primary/10' },
  solved: { icon: CheckCircle2, cls: 'border-success/40 text-success bg-success/10' },
} as const

export function Upsolve({ handle }: { handle: string }) {
  const { t, fmt } = useSettings()
  const { data, error, loading, reload } = useCall<UpsolveAnswer>('upsolve', { handle }, 600_000)
  const [onlyTodo, setOnlyTodo] = useState(true)
  if (error) return <ErrorState code={error} onRetry={reload} />
  if (loading || !data) return <Loading lines={8} />
  const contests = onlyTodo ? data.contests.filter((c) => c.problems.some((p) => p.status === 'todo')) : data.contests
  return (
    <>
      <Rise i={0}>
        <Panel glow title={t('up.title')} extra={<ShareBar route={{ name: 'upsolve', handle }} text={`${handle}: ${t('up.title')}`} />}>
          <div className="mb-3 flex items-center gap-2">
            <Handle handle={handle} rating={null} className="text-lg" />
          </div>
          <p className="mb-3 text-xs text-muted-foreground">{t('up.hint')}</p>
          <div className="grid grid-cols-2 gap-2">
            <Stat label={t('up.todo')} value={data.todo} color="var(--warning)" />
            <Stat label={t('up.done')} value={data.upsolved} color="var(--primary)" />
          </div>
          <div className="mt-3 flex gap-2">
            <Button size="sm" variant={onlyTodo ? 'default' : 'outline'} onClick={() => setOnlyTodo(true)}>
              {t('up.todo')}
            </Button>
            <Button size="sm" variant={onlyTodo ? 'outline' : 'default'} onClick={() => setOnlyTodo(false)}>
              {t('up.all')}
            </Button>
          </div>
        </Panel>
      </Rise>
      {contests.length === 0 ? (
        <Empty icon={<PartyPopper />}>{t('up.empty')}</Empty>
      ) : (
        contests.map((c, i) => (
          <Rise key={c.contestId} i={i + 1}>
            <Panel
              title={c.name}
              extra={
                <span className="font-mono text-[11px] text-muted-foreground">
                  {fmt.date(c.time, false)}
                  {c.virtual && ` · ${t('up.virtual')}`}
                </span>
              }
            >
              <ul className="space-y-2">
                {c.problems.map((p) => {
                  const S = STATUS[p.status]
                  return (
                    <li key={p.index}>
                      <button
                        onClick={() => openLink(cfUrl.problem(c.contestId, p.index))}
                        className={cn('flex w-full items-center gap-3 rounded-xl border px-3 py-2 text-left', S.cls)}
                      >
                        <S.icon className="size-4 shrink-0" />
                        <span className="w-8 shrink-0 font-mono font-bold">{p.index}</span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm text-foreground">{p.name}</span>
                          {p.tags.length > 0 && <span className="block truncate text-[11px] text-muted-foreground">{p.tags.join(' · ')}</span>}
                        </span>
                        {p.rating && (
                          <Badge variant="outline" className="shrink-0 font-mono" style={{ color: ratingColor(p.rating) }}>
                            {p.rating}
                          </Badge>
                        )}
                      </button>
                    </li>
                  )
                })}
              </ul>
            </Panel>
          </Rise>
        ))
      )}
    </>
  )
}
