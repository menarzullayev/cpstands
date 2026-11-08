import { useEffect, useState } from 'react'
import { ratingColor, type Comparison } from '../cf'
import { fmtDate, t } from '../i18n'
import { haptic, storage } from '../tg'
import { useCall } from '../useCall'
import { Card, ErrorBox, Skeleton } from '../components/ui'
import { RatingChart } from '../components/RatingChart'

const KEY = 'compare.handles'
const MAX = 6
// Distinct line colours that read on light and dark themes.
const PALETTE = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899']

export function Compare() {
  const [handles, setHandles] = useState<string[]>([])
  const [draft, setDraft] = useState('')
  useEffect(() => {
    storage.get(KEY).then((v) => {
      try {
        const list = JSON.parse(v ?? '[]')
        if (Array.isArray(list)) setHandles(list.filter((h) => typeof h === 'string').slice(0, MAX))
      } catch {
        /* ignore a bad stored value */
      }
    })
  }, [])
  const save = (list: string[]) => {
    setHandles(list)
    storage.set(KEY, JSON.stringify(list))
  }
  const add = () => {
    const parts = draft.split(/[\s,;]+/).map((h) => h.trim()).filter(Boolean)
    const next = [...handles]
    for (const p of parts) {
      if (next.length < MAX && !next.some((h) => h.toLowerCase() === p.toLowerCase())) next.push(p)
    }
    haptic()
    save(next)
    setDraft('')
  }
  const { data, error, loading, reload } = useCall<Comparison>('compare', handles.length ? { handles } : null)
  const colorOf = (handle: string) => {
    const i = handles.findIndex((h) => h.toLowerCase() === handle.toLowerCase())
    return PALETTE[(i < 0 ? 0 : i) % PALETTE.length]
  }
  return (
    <>
      <form
        className="search"
        onSubmit={(e) => {
          e.preventDefault()
          add()
        }}
      >
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={handles.length >= MAX ? t('compare.max') : t('compare.placeholder')}
          disabled={handles.length >= MAX}
          autoCapitalize="off"
          autoCorrect="off"
          spellCheck={false}
        />
        <button className="btn" type="submit" disabled={!draft.trim() || handles.length >= MAX}>
          {t('compare.add')}
        </button>
      </form>
      {handles.length > 0 && (
        <div className="chips">
          {handles.map((h) => (
            <button key={h} className="chip" style={{ borderColor: colorOf(h) }} onClick={() => save(handles.filter((x) => x !== h))}>
              <span className="dot" style={{ background: colorOf(h) }} />
              {h} <span aria-hidden>×</span>
            </button>
          ))}
        </div>
      )}
      {handles.length < 2 && <p className="empty">{t('compare.empty')}</p>}
      {handles.length > 0 &&
        (error ? (
          <ErrorBox code={error} onRetry={reload} />
        ) : loading || !data ? (
          <Card>
            <Skeleton lines={5} />
          </Card>
        ) : (
          <>
            <Card>
              <div className="legend">
                {data.series.map((s) => (
                  <div key={s.handle} className="legend-item">
                    <span className="dot" style={{ background: colorOf(s.handle) }} />
                    <b style={{ color: ratingColor(s.rating) }}>{s.handle}</b>
                    <span className="muted small">
                      {s.rating ?? '—'} / {s.maxRating ?? '—'}
                    </span>
                  </div>
                ))}
              </div>
              <RatingChart lines={data.series.map((s) => ({ handle: s.handle, color: colorOf(s.handle), points: s.points }))} />
            </Card>
            {data.series.length >= 2 && (
              <Card title={t('compare.common')}>
                {data.common.length === 0 ? (
                  <p className="muted">{t('compare.noCommon')}</p>
                ) : (
                  <div className="table-wrap">
                    <table className="h2h">
                      <thead>
                        <tr>
                          <th />
                          {data.series.map((s) => (
                            <th key={s.handle} style={{ color: colorOf(s.handle) }}>
                              {s.handle}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {data.common.map((row) => {
                          const best = Math.min(...Object.values(row.ranks))
                          return (
                            <tr key={row.contestId}>
                              <td>
                                <div className="h2h-name">{row.contest}</div>
                                <div className="muted small">{fmtDate(row.time, false)}</div>
                              </td>
                              {data.series.map((s) => {
                                const r = row.ranks[s.handle]
                                return (
                                  <td key={s.handle} className={r === best ? 'win' : ''}>
                                    {r ?? '—'}
                                  </td>
                                )
                              })}
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </Card>
            )}
          </>
        ))}
    </>
  )
}
