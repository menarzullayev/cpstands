import { useState } from 'react'
import { ChevronRight, GitCompareArrows, Loader2, Plus, Trash2, Users } from 'lucide-react'
import { call, forget, useCall } from '@/lib/api'
import type { FriendsAnswer } from '@/lib/cf'
import { errorKey } from '@/lib/i18n'
import { useRouter } from '@/lib/router'
import { useSettings } from '@/lib/settings'
import { ApiError, haptic } from '@/lib/tg'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Avatar, Empty, ErrorState, Handle, Loading, Panel, Rise } from '@/components/kit'
import { LeaderboardPanel } from '@/components/LeaderboardPanel'
import { cn } from '@/lib/utils'

export function Friends() {
  const { t, fmt } = useSettings()
  const { push } = useRouter()
  const list = useCall<FriendsAnswer>('friends', { action: 'list' }, 300_000)
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState<{ ok: boolean; text: string } | null>(null)
  const [editing, setEditing] = useState(false)
  const [view, setView] = useState<'list' | 'board'>('list')

  const change = async (action: 'add' | 'remove', handles: string[]) => {
    setBusy(true)
    setNote(null)
    try {
      const res = await call<FriendsAnswer>('friends', { action, handles })
      list.set(res)
      forget('activity')
      forget('standings')
      if (action === 'add') {
        haptic.success()
        const parts = [
          res.added?.length ? t('fr.added', res.added.join(', ')) : '',
          res.already ? t('fr.already', res.already) : '',
          res.overLimit ? t('fr.over', res.overLimit) : '',
        ].filter(Boolean)
        setNote({ ok: true, text: parts.join(' · ') })
        setDraft('')
      } else haptic.impact('medium')
    } catch (e) {
      haptic.error()
      setNote({ ok: false, text: t(errorKey(e instanceof ApiError ? e.code : 'generic')) })
    } finally {
      setBusy(false)
    }
  }

  const add = () => {
    const handles = draft.split(/[\s,;]+/).map((h) => h.trim()).filter(Boolean)
    if (handles.length) void change('add', handles)
  }

  const friends = list.data?.friends ?? []
  const switcher = (
    <div className="grid grid-cols-2 rounded-xl border bg-muted/50 p-1">
      {(['list', 'board'] as const).map((v) => (
        <button
          key={v}
          onClick={() => setView(v)}
          className={cn('rounded-lg py-1.5 text-sm font-medium', view === v ? 'bg-primary text-primary-foreground' : 'text-muted-foreground')}
        >
          {t(v === 'list' ? 'fr.list' : 'fr.board')}
        </button>
      ))}
    </div>
  )
  if (view === 'board')
    return (
      <>
        {switcher}
        <Rise i={0}>
          <LeaderboardPanel />
        </Rise>
      </>
    )
  return (
    <>
      {switcher}
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
            placeholder={t('fr.placeholder')}
            autoCapitalize="off"
            autoCorrect="off"
            spellCheck={false}
            className="h-10 font-mono"
          />
          <Button type="submit" className="h-10" disabled={busy || !draft.trim()}>
            {busy ? <Loader2 className="animate-spin" /> : <Plus />} {t('fr.add')}
          </Button>
        </form>
        {note && <p className={`mt-2 text-sm ${note.ok ? 'text-success' : 'text-destructive'}`}>{note.text}</p>}
      </Rise>
      {list.error ? (
        <ErrorState code={list.error} onRetry={list.reload} />
      ) : list.loading || !list.data ? (
        <Loading lines={6} />
      ) : friends.length === 0 ? (
        <Empty icon={<Users />}>{t('fr.empty')}</Empty>
      ) : (
        <Rise i={1}>
          <Panel
            title={`${t('fr.title')} · ${t('fr.count', friends.length, list.data.max)}`}
            extra={
              <div className="flex gap-1">
                {friends.length >= 2 && (
                  <Button size="sm" variant="ghost" onClick={() => push({ name: 'compare', handles: friends.slice(0, 6).map((f) => f.handle) })}>
                    <GitCompareArrows /> {t('fr.compare')}
                  </Button>
                )}
                <Button size="icon-sm" variant={editing ? 'secondary' : 'ghost'} aria-label={t('fr.remove')} onClick={() => setEditing((v) => !v)}>
                  <Trash2 />
                </Button>
              </div>
            }
          >
            <ul className="divide-y">
              {friends.map((f, i) => (
                <Rise key={f.handle} i={i}>
                  <li className="flex items-center gap-3 py-2.5">
                    <Avatar src={f.avatar} handle={f.handle} rating={f.rating} size={40} />
                    <button className="min-w-0 flex-1 text-left" onClick={() => push({ name: 'profile', handle: f.handle })}>
                      <Handle handle={f.handle} rating={f.rating} />
                      <div className="truncate text-xs text-muted-foreground">
                        <span className="capitalize">{f.rank ?? t('unrated')}</span>
                        {f.lastOnline ? ` · ${fmt.ago(f.lastOnline)}` : ''}
                      </div>
                    </button>
                    <span className="font-mono text-sm font-semibold tabular-nums">{f.rating ?? '—'}</span>
                    {editing ? (
                      <Button size="icon-sm" variant="destructive" aria-label={t('fr.remove')} disabled={busy} onClick={() => void change('remove', [f.handle])}>
                        <Trash2 />
                      </Button>
                    ) : (
                      <ChevronRight className="size-4 text-muted-foreground" />
                    )}
                  </li>
                </Rise>
              ))}
            </ul>
          </Panel>
        </Rise>
      )}
    </>
  )
}
