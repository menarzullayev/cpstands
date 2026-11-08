import type { ReactNode } from 'react'
import { errorText, t } from '../i18n'

export function Card({ title, children, extra }: { title?: string; children: ReactNode; extra?: ReactNode }) {
  return (
    <section className="card">
      {(title || extra) && (
        <header className="card-head">
          {title && <h2>{title}</h2>}
          {extra}
        </header>
      )}
      {children}
    </section>
  )
}

export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="skeleton" aria-busy="true">
      {Array.from({ length: lines }, (_, i) => (
        <div key={i} className="bone" style={{ width: `${90 - i * 12}%` }} />
      ))}
    </div>
  )
}

export function ErrorBox({ code, onRetry }: { code: string; onRetry?: () => void }) {
  return (
    <div className="error-box" role="alert">
      <p>{errorText(code)}</p>
      {onRetry && code !== 'NO_TELEGRAM' && (
        <button className="btn ghost" onClick={onRetry}>
          {t('retry')}
        </button>
      )}
    </div>
  )
}

export function Stat({ label, value, color }: { label: string; value: ReactNode; color?: string }) {
  return (
    <div className="stat">
      <div className="stat-value" style={color ? { color } : undefined}>
        {value}
      </div>
      <div className="stat-label">{label}</div>
    </div>
  )
}

/** Horizontal bars; `max` defaults to the largest value. */
export function Bars({ items, color }: { items: { name: string; count: number }[]; color?: string }) {
  const max = Math.max(1, ...items.map((i) => i.count))
  return (
    <ul className="bars">
      {items.map((i) => (
        <li key={i.name}>
          <span className="bar-name">{i.name}</span>
          <span className="bar-track">
            <span className="bar-fill" style={{ width: `${(i.count / max) * 100}%`, background: color }} />
          </span>
          <span className="bar-count">{i.count}</span>
        </li>
      ))}
    </ul>
  )
}
