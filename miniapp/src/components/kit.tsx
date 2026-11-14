// Brand building blocks shared by every page.
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { animate, motion, useInView, useMotionValue, useTransform } from 'motion/react'
import { AlertTriangle, RotateCw } from 'lucide-react'
import { cn } from '@/lib/utils'
import { ratingColor } from '@/lib/cf'
import { errorKey } from '@/lib/i18n'
import { useSettings } from '@/lib/settings'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

export function Logo({ className }: { className?: string }) {
  return (
    <div className={cn('flex items-center gap-2 font-mono text-[15px] font-bold tracking-tight', className)}>
      <svg viewBox="0 0 24 24" className="size-6" aria-hidden>
        <defs>
          <linearGradient id="lg" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="var(--primary)" />
            <stop offset="1" stopColor="var(--violet)" />
          </linearGradient>
        </defs>
        <rect x="2" y="13" width="5" height="9" rx="1.2" fill="url(#lg)" opacity=".55" />
        <rect x="9.5" y="8" width="5" height="14" rx="1.2" fill="url(#lg)" opacity=".8" />
        <rect x="17" y="3" width="5" height="19" rx="1.2" fill="url(#lg)" />
      </svg>
      <span>
        cp<span className="text-primary">stands</span>
      </span>
    </div>
  )
}

/** Section card with an optional mono caption, in the terminal style of the brand. */
export function Panel({
  title,
  extra,
  children,
  className,
  glow,
}: {
  title?: ReactNode
  extra?: ReactNode
  children: ReactNode
  className?: string
  glow?: boolean
}) {
  return (
    <section className={cn('rounded-2xl border bg-card/90 p-4 backdrop-blur-sm', glow && 'gradient-border glow', className)}>
      {(title || extra) && (
        <header className="mb-3 flex items-center justify-between gap-2">
          {title && (
            <h2 className="font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
              <span className="text-primary">{'// '}</span>
              {title}
            </h2>
          )}
          {extra}
        </header>
      )}
      {children}
    </section>
  )
}

export function Handle({ handle, rating, className }: { handle: string; rating: number | null | undefined; className?: string }) {
  const lgm = rating != null && rating >= 3000
  return (
    <span className={cn('font-mono font-semibold', className)} style={rating == null ? undefined : { color: ratingColor(rating) }}>
      {lgm ? (
        <>
          <span className="text-foreground">{handle.charAt(0)}</span>
          {handle.slice(1)}
        </>
      ) : (
        handle
      )}
    </span>
  )
}

export function Avatar({ src, handle, rating, size = 44 }: { src?: string | null; handle: string; rating?: number | null; size?: number }) {
  const [failed, setFailed] = useState(false)
  const color = ratingColor(rating)
  const style = { width: size, height: size, borderColor: color }
  if (!src || failed || src.includes('no-title')) {
    return (
      <div
        className="grid shrink-0 place-items-center rounded-full border-2 bg-muted font-mono font-bold"
        style={{ ...style, color, fontSize: size * 0.42 }}
        aria-hidden
      >
        {handle.charAt(0).toUpperCase()}
      </div>
    )
  }
  return (
    <img
      src={src}
      alt=""
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
      className="shrink-0 rounded-full border-2 bg-muted object-cover"
      style={style}
    />
  )
}

/** A number that counts up when it scrolls into view (instant when effects are off). */
export function CountUp({ value, className, group = true }: { value: number; className?: string; group?: boolean }) {
  const { effects, fmt } = useSettings()
  const ref = useRef<HTMLSpanElement>(null)
  const inView = useInView(ref, { once: true })
  const mv = useMotionValue(effects ? 0 : value)
  // Ratings are written without digit grouping, as on Codeforces.
  const text = useTransform(mv, (v) => (group ? fmt.number(Math.round(v)) : String(Math.round(v))))
  useEffect(() => {
    if (!effects) {
      mv.set(value)
      return
    }
    if (!inView) return
    const controls = animate(mv, value, { duration: 0.9, ease: [0.16, 1, 0.3, 1] })
    return () => controls.stop()
  }, [value, inView, effects, mv])
  return (
    <motion.span ref={ref} className={cn('tabular-nums', className)}>
      {text}
    </motion.span>
  )
}

export function useNow(stepMs = 1000) {
  const [now, setNow] = useState(() => Date.now() / 1000)
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now() / 1000), stepMs)
    return () => clearInterval(id)
  }, [stepMs])
  return now
}

/** Big DD:HH:MM:SS countdown in the mono face. */
export function Countdown({ to, className }: { to: number; className?: string }) {
  const { t } = useSettings()
  const now = useNow(1000)
  const s = Math.max(0, Math.floor(to - now))
  const parts = [
    { n: Math.floor(s / 86400), unit: t('unit.d') },
    { n: Math.floor((s % 86400) / 3600), unit: t('unit.h') },
    { n: Math.floor((s % 3600) / 60), unit: t('unit.m') },
    { n: s % 60, unit: t('unit.s') },
  ]
  const shown = parts[0].n > 0 ? parts : parts.slice(1)
  return (
    <div className={cn('flex items-start gap-1 font-mono tabular-nums', className)} aria-live="off">
      {shown.map((p, i) => (
        <div key={i} className="flex items-start">
          {i > 0 && <span className="px-0.5 text-4xl font-bold leading-none text-primary/50">:</span>}
          <div className="flex flex-col items-center">
            <span className="animate-pulse-glow text-4xl font-bold leading-none text-primary">{String(p.n).padStart(2, '0')}</span>
            <span className="mt-1.5 text-[10px] uppercase tracking-[0.12em] text-muted-foreground">{p.unit}</span>
          </div>
        </div>
      ))}
    </div>
  )
}

export function Loading({ lines = 4, className }: { lines?: number; className?: string }) {
  return (
    <div className={cn('space-y-3 rounded-2xl border bg-card p-4', className)} aria-busy="true">
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} className="h-4" style={{ width: `${92 - i * 11}%` }} />
      ))}
    </div>
  )
}

export function ErrorState({ code, onRetry }: { code: string; onRetry?: () => void }) {
  const { t } = useSettings()
  return (
    <div role="alert" className="flex items-center gap-3 rounded-2xl border border-destructive/40 bg-destructive/10 p-4">
      <AlertTriangle className="size-5 shrink-0 text-destructive" />
      <p className="flex-1 text-sm">{t(errorKey(code))}</p>
      {onRetry && code !== 'NO_TELEGRAM' && (
        <Button size="sm" variant="outline" onClick={onRetry}>
          <RotateCw /> {t('retry')}
        </Button>
      )}
    </div>
  )
}

export function Empty({ icon, children, action }: { icon?: ReactNode; children: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed p-8 text-center text-sm text-muted-foreground">
      {icon && <div className="text-primary/70 [&_svg]:size-8">{icon}</div>}
      <div>{children}</div>
      {action}
    </div>
  )
}

/** Fade-and-rise entrance for list items, staggered by index; plain when effects are off. */
export function Rise({ i = 0, children, className }: { i?: number; children: ReactNode; className?: string }) {
  const { effects } = useSettings()
  if (!effects) return <div className={className}>{children}</div>
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: Math.min(i, 12) * 0.035, ease: [0.16, 1, 0.3, 1] }}
    >
      {children}
    </motion.div>
  )
}

export function Stat({ label, value, color, mono = true }: { label: string; value: ReactNode; color?: string; mono?: boolean }) {
  return (
    <div className="rounded-xl border bg-muted/50 px-2 py-2.5 text-center">
      <div className={cn('text-lg font-bold leading-tight', mono && 'font-mono')} style={color ? { color } : undefined}>
        {value}
      </div>
      <div className="mt-0.5 text-[11px] text-muted-foreground">{label}</div>
    </div>
  )
}

export function Bars({ items, color }: { items: { name: string; count: number }[]; color?: string }) {
  const max = Math.max(1, ...items.map((i) => i.count))
  return (
    <ul className="space-y-2">
      {items.map((i, k) => (
        <li key={i.name} className="grid grid-cols-[minmax(84px,36%)_1fr_auto] items-center gap-2 text-[13px]">
          <span className="truncate">{i.name}</span>
          <span className="h-2 overflow-hidden rounded-full bg-muted">
            <motion.span
              className="block h-full rounded-full"
              style={{ background: color ?? 'linear-gradient(90deg, var(--primary), var(--violet))' }}
              initial={{ width: 0 }}
              animate={{ width: `${(i.count / max) * 100}%` }}
              transition={{ duration: 0.7, delay: k * 0.03, ease: [0.16, 1, 0.3, 1] }}
            />
          </span>
          <span className="min-w-[2.5em] text-right font-mono text-xs text-muted-foreground tabular-nums">{i.count}</span>
        </li>
      ))}
    </ul>
  )
}

/** Tiny rating sparkline without a chart library (used on Home, where Recharts is not loaded). */
export function Sparkline({ values, className }: { values: number[]; className?: string }) {
  if (values.length < 2) return null
  const w = 120
  const h = 36
  const min = Math.min(...values)
  const max = Math.max(...values)
  const pts = values.map((v, i) => `${(i / (values.length - 1)) * w},${h - 3 - ((v - min) / Math.max(1, max - min)) * (h - 6)}`)
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className={cn('h-9 w-28', className)} aria-hidden>
      <defs>
        <linearGradient id="spark" x1="0" x2="1">
          <stop offset="0" stopColor="var(--violet)" />
          <stop offset="1" stopColor="var(--primary)" />
        </linearGradient>
      </defs>
      <polyline points={pts.join(' ')} fill="none" stroke="url(#spark)" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  )
}
