import { useEffect, useState } from 'react'
import { contestUrl, type Contest, type ContestList } from '../cf'
import { fmtDate, fmtSpan, t } from '../i18n'
import { tg } from '../tg'
import { useCall } from '../useCall'
import { Card, ErrorBox, Skeleton } from '../components/ui'

function useNow(stepMs = 30000) {
  const [now, setNow] = useState(() => Date.now() / 1000)
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now() / 1000), stepMs)
    return () => clearInterval(id)
  }, [stepMs])
  return now
}

function open(id: number) {
  const url = contestUrl(id)
  if (tg) tg.openLink(url)
  else window.open(url, '_blank', 'noopener')
}

function Row({ c, now }: { c: Contest; now: number }) {
  const start = c.start ?? 0
  const end = start + c.duration
  let badge: string
  let cls = ''
  if (c.phase === 'BEFORE') {
    badge = t('contests.in', fmtSpan(start - now))
    cls = start - now < 3600 ? 'soon' : ''
  } else if (c.phase === 'CODING') {
    badge = t('contests.left', fmtSpan(end - now))
    cls = 'live'
  } else {
    badge = fmtDate(start, false)
  }
  const progress = c.phase === 'CODING' ? Math.min(1, Math.max(0, (now - start) / c.duration)) : null
  return (
    <button className="contest" onClick={() => open(c.id)}>
      <div className="contest-main">
        <div className="contest-name">{c.name}</div>
        <div className="contest-meta">
          {c.start ? fmtDate(c.start) : '—'} · {fmtSpan(c.duration)} · {c.type}
        </div>
        {progress !== null && (
          <div className="progress">
            <span style={{ width: `${progress * 100}%` }} />
          </div>
        )}
      </div>
      <span className={`pill ${cls}`}>{badge}</span>
    </button>
  )
}

export function Contests() {
  const { data, error, loading, reload } = useCall<ContestList>('contests', {})
  const now = useNow()
  if (error) return <ErrorBox code={error} onRetry={reload} />
  if (loading || !data) return <Card><Skeleton lines={6} /></Card>
  const section = (title: string, list: Contest[]) => (
    <Card title={title}>
      {list.length === 0 ? <p className="muted">{t('contests.none')}</p> : list.map((c) => <Row key={c.id} c={c} now={now} />)}
    </Card>
  )
  return (
    <>
      {data.live.length > 0 && section(t('contests.live'), data.live)}
      {section(t('contests.upcoming'), data.upcoming)}
      {section(t('contests.finished'), data.finished)}
    </>
  )
}
