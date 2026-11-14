// A group's own view, opened from the signed link the bot posts in the group (/app, reminders,
// summaries, standings). The database checks the link and returns the group's handles.
import { useEffect, useState } from 'react'
import { Info, Trophy, Users } from 'lucide-react'
import { useCall } from '@/lib/api'
import type { Friend } from '@/lib/cf'
import { rpc } from '@/lib/db'
import { useRouter } from '@/lib/router'
import { useSettings } from '@/lib/settings'
import { ApiError } from '@/lib/tg'
import { cn } from '@/lib/utils'
import { Avatar, Empty, ErrorState, Handle, Loading, Panel, Rise } from '@/components/kit'
import { LeaderboardPanel } from '@/components/LeaderboardPanel'
import { Standings } from '@/pages/Standings'

interface GroupAnswer {
  chatId: number
  title: string | null
  language: string | null
  timeZone: string
  contestId: number | null
  handles: string[]
}

type View = 'standings' | 'board' | 'list'

function Members({ handles }: { handles: string[] }) {
  const { t } = useSettings()
  const { push } = useRouter()
  const { data, error, loading, reload } = useCall<{ cards: Friend[] }>('cards', { handles }, 300_000)
  if (error) return <ErrorState code={error} onRetry={reload} />
  if (loading || !data) return <Loading lines={6} />
  return (
    <Panel title={t('gr.count', data.cards.length)}>
      <ul className="divide-y">
        {data.cards.map((f, i) => (
          <Rise key={f.handle} i={i}>
            <li>
              <button className="flex w-full items-center gap-3 py-2.5 text-left" onClick={() => push({ name: 'profile', handle: f.handle })}>
                <span className="w-6 text-right font-mono text-xs text-muted-foreground">{i + 1}</span>
                <Avatar src={f.avatar} handle={f.handle} rating={f.rating} size={36} />
                <span className="min-w-0 flex-1">
                  <Handle handle={f.handle} rating={f.rating} className="block truncate" />
                  <span className="text-xs capitalize text-muted-foreground">{f.rank ?? t('unrated')}</span>
                </span>
                <span className="font-mono text-sm font-semibold">{f.rating ?? '—'}</span>
              </button>
            </li>
          </Rise>
        ))}
      </ul>
    </Panel>
  )
}

export function GroupView() {
  const { t } = useSettings()
  const [group, setGroup] = useState<GroupAnswer | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [view, setView] = useState<View>('standings')

  useEffect(() => {
    rpc<GroupAnswer>('app_group')
      .then(setGroup)
      .catch((e: unknown) => setError(e instanceof ApiError ? e.code : 'generic'))
  }, [])

  if (error)
    return (
      <Empty icon={<Info />}>
        {error === 'GROUP_INACTIVE'
          ? t('gr.inactive')
          : error === 'UNAUTHORIZED' || error === 'BAD_INPUT'
            ? t('gr.bad')
            : t('error.generic')}
      </Empty>
    )
  if (!group) return <Loading lines={6} />

  const tabs: { id: View; label: string; icon: typeof Trophy }[] = [
    { id: 'standings', label: t('gr.standings'), icon: Trophy },
    { id: 'board', label: t('gr.board'), icon: Trophy },
    { id: 'list', label: t('gr.list'), icon: Users },
  ]
  return (
    <>
      <Rise i={0}>
        <Panel glow>
          <div className="flex items-center gap-3">
            <div className="grid size-11 shrink-0 place-items-center rounded-xl bg-primary/15 text-primary">
              <Users className="size-5" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted-foreground">{t('gr.title')}</div>
              <div className="truncate text-lg font-semibold">{group.title ?? `#${Math.abs(group.chatId)}`}</div>
            </div>
            <span className="font-mono text-xs text-muted-foreground">{t('gr.count', group.handles.length)}</span>
          </div>
          <p className="mt-3 text-xs text-muted-foreground">{t('gr.readonly')}</p>
        </Panel>
      </Rise>
      {group.handles.length === 0 ? (
        <Empty icon={<Users />}>{t('gr.empty')}</Empty>
      ) : (
        <>
          <div className="grid grid-cols-3 rounded-xl border bg-muted/50 p-1">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setView(tab.id)}
                className={cn('rounded-lg py-1.5 text-sm font-medium', view === tab.id ? 'bg-primary text-primary-foreground' : 'text-muted-foreground')}
              >
                {tab.label}
              </button>
            ))}
          </div>
          {view === 'standings' && <Standings contestId={group.contestId ?? undefined} group={group.handles} />}
          {view === 'board' && <LeaderboardPanel group={group.handles} />}
          {view === 'list' && <Members handles={group.handles} />}
        </>
      )}
    </>
  )
}
