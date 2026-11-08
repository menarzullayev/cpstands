import { useEffect, useState } from 'react'
import { profileUrl, ratingColor, submissionUrl, VERDICT_SHORT, type Profile as P } from '../cf'
import { fmtDate, fmtNumber, t } from '../i18n'
import { haptic, storage, tg } from '../tg'
import { useCall } from '../useCall'
import { Bars, Card, ErrorBox, Skeleton, Stat } from '../components/ui'
import { Heatmap } from '../components/Heatmap'
import { RatingChart } from '../components/RatingChart'
import type { RatingPoint } from '../cf'

const KEY = 'profile.handle'

function HandleForm({ initial, onSubmit }: { initial: string; onSubmit: (h: string) => void }) {
  const [value, setValue] = useState(initial)
  return (
    <form
      className="search"
      onSubmit={(e) => {
        e.preventDefault()
        const h = value.trim()
        if (h) {
          haptic()
          onSubmit(h)
        }
      }}
    >
      <input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={t('profile.placeholder')}
        autoCapitalize="off"
        autoCorrect="off"
        spellCheck={false}
        enterKeyHint="search"
      />
      <button className="btn" type="submit">
        {t('profile.search')}
      </button>
    </form>
  )
}

function useRatingHistory(handle: string | null) {
  // The profile endpoint keeps only aggregates; the chart reuses the compare endpoint.
  return useCall<{ series: { points: RatingPoint[] }[] }>('compare', handle ? { handles: [handle] } : null)
}

function ProfileView({ data }: { data: P }) {
  const u = data.user
  const s = data.stats
  const history = useRatingHistory(u.handle)
  const color = ratingColor(u.rating)
  const yearSubs = s.heatmap.reduce((a, d) => a + d.count, 0)
  const open = (url: string) => (tg ? tg.openLink(url) : window.open(url, '_blank', 'noopener'))
  return (
    <>
      <Card>
        <div className="profile-head">
          {u.avatar && <img className="avatar" src={u.avatar} alt="" referrerPolicy="no-referrer" />}
          <div>
            <button className="handle" style={{ color }} onClick={() => open(profileUrl(u.handle))}>
              {u.handle}
            </button>
            <div className="rank" style={{ color }}>
              {u.rank ?? t('unrated')}
            </div>
            <div className="muted small">{[u.organization, u.country].filter(Boolean).join(' · ')}</div>
          </div>
        </div>
        <div className="stats">
          <Stat label={t('profile.rating')} value={u.rating ?? '—'} color={color} />
          <Stat label={t('profile.max')} value={u.maxRating ?? '—'} color={ratingColor(u.maxRating)} />
          <Stat label={t('profile.solved')} value={fmtNumber(s.solved)} />
          <Stat label={t('profile.contests')} value={data.contests} />
          <Stat label={t('profile.best')} value={data.best ? `#${data.best.rank}` : '—'} />
          <Stat label={t('profile.streak')} value={s.streak} />
        </div>
      </Card>
      {data.contests > 0 && (
        <Card title={t('profile.history')}>
          {history.data ? (
            <RatingChart lines={[{ handle: u.handle, color: 'var(--accent)', points: history.data.series[0]?.points ?? [] }]} />
          ) : history.error ? (
            <ErrorBox code={history.error} onRetry={history.reload} />
          ) : (
            <Skeleton lines={4} />
          )}
        </Card>
      )}
      <Card title={t('profile.activity')} extra={<span className="muted small">{t('profile.submissionsYear', fmtNumber(yearSubs))}</span>}>
        <Heatmap days={s.heatmap} />
      </Card>
      {s.tags.length > 0 && (
        <Card title={t('profile.tags')}>
          <Bars items={s.tags} />
        </Card>
      )}
      {s.ratings.length > 0 && (
        <Card title={t('profile.difficulty')}>
          <div className="columns">
            {(() => {
              const max = Math.max(...s.ratings.map((r) => r.count))
              return s.ratings.map((r) => (
                <div key={r.rating} className="column" title={`${r.rating}: ${r.count}`}>
                  <span className="column-count">{r.count}</span>
                  <span className="column-bar" style={{ height: `${(r.count / max) * 100}%`, background: ratingColor(r.rating) }} />
                  <span className="column-label">{r.rating}</span>
                </div>
              ))
            })()}
          </div>
        </Card>
      )}
      <div className="grid2">
        <Card title={t('profile.verdicts')}>
          <Bars items={s.verdicts.map((v) => ({ name: VERDICT_SHORT[v.name] ?? v.name, count: v.count }))} />
        </Card>
        <Card title={t('profile.languages')}>
          <Bars items={s.languages} />
        </Card>
      </div>
      <Card title={t('profile.recent')}>
        <ul className="subs">
          {s.recent.map((r) => (
            <li key={r.id}>
              <button
                className="sub"
                onClick={() => r.contestId && open(submissionUrl(r.contestId, r.id))}
                disabled={!r.contestId}
              >
                <span className={`verdict ${r.verdict === 'OK' ? 'ok' : 'bad'}`}>{VERDICT_SHORT[r.verdict] ?? r.verdict}</span>
                <span className="sub-name">
                  {r.contestId}
                  {r.index}. {r.name}
                </span>
                {r.rating && (
                  <span className="sub-rating" style={{ color: ratingColor(r.rating) }}>
                    {r.rating}
                  </span>
                )}
                <span className="muted small">{fmtDate(r.time)}</span>
              </button>
            </li>
          ))}
        </ul>
      </Card>
    </>
  )
}

export function Profile() {
  const [handle, setHandle] = useState<string | null>(null)
  const [ready, setReady] = useState(false)
  useEffect(() => {
    storage.get(KEY).then((h) => {
      setHandle(h)
      setReady(true)
    })
  }, [])
  const { data, error, loading, reload } = useCall<P>('profile', handle ? { handle } : null)
  const submit = (h: string) => {
    setHandle(h)
    storage.set(KEY, h)
  }
  return (
    <>
      <HandleForm key={handle ?? ''} initial={handle ?? ''} onSubmit={submit} />
      {!ready ? null : !handle ? (
        <p className="empty">{t('profile.empty')}</p>
      ) : error ? (
        <ErrorBox code={error} onRetry={reload} />
      ) : loading || !data ? (
        <Card>
          <Skeleton lines={5} />
        </Card>
      ) : (
        <ProfileView data={data} />
      )}
    </>
  )
}
