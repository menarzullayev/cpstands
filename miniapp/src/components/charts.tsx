// Recharts-based charts. Imported only by lazy pages, so Home never loads Recharts.
import { useEffect, useMemo, useRef } from 'react'
import { Area, AreaChart, Bar, BarChart, Brush, CartesianGrid, Cell, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { RANKS, ratingColor, type RatingPoint } from '@/lib/cf'
import { useSettings } from '@/lib/settings'

export interface Line {
  handle: string
  color: string
  points: RatingPoint[]
}

function bands(min: number, max: number) {
  return RANKS.map((r, i) => ({ from: r.from, to: RANKS[i + 1]?.from ?? 5000, color: r.color })).filter(
    (b) => b.to > min && b.from < max,
  )
}

function TooltipBox({ active, payload }: { active?: boolean; payload?: { payload: Record<string, unknown> }[] }) {
  const { fmt } = useSettings()
  if (!active || !payload?.length) return null
  const p = payload[0].payload as { time: number; [k: string]: unknown }
  const rows = Object.entries(p).filter(([k]) => k.startsWith('r:'))
  const info = p.info as { contest: string; rank: number; delta: number } | undefined
  return (
    <div className="max-w-60 rounded-xl border bg-popover/95 px-3 py-2 text-xs shadow-xl backdrop-blur">
      <div className="mb-1 font-mono text-muted-foreground">{fmt.date(p.time, false)}</div>
      {rows.map(([k, v]) => (
        <div key={k} className="flex justify-between gap-3 font-mono">
          <span style={{ color: ratingColor(v as number) }}>{k.slice(2)}</span>
          <b>{v as number}</b>
        </div>
      ))}
      {info && (
        <div className="mt-1 text-muted-foreground">
          <span className={info.delta >= 0 ? 'text-success' : 'text-destructive'}>
            {info.delta >= 0 ? '+' : ''}
            {info.delta}
          </span>{' '}
          · #{info.rank}
          <div className="truncate">{info.contest}</div>
        </div>
      )}
    </div>
  )
}

/** Rating history over Codeforces rank bands; one line per handle, with a brush to zoom. */
export function RatingChart({ lines }: { lines: Line[] }) {
  const { effects } = useSettings()
  const data = useMemo(() => {
    // Merge all points on one time axis; each handle carries its last known rating forward.
    const times = [...new Set(lines.flatMap((l) => l.points.map((p) => p.time)))].sort((a, b) => a - b)
    const last: Record<string, number | undefined> = {}
    const idx: Record<string, number> = {}
    return times.map((time) => {
      const row: Record<string, unknown> = { time }
      for (const l of lines) {
        idx[l.handle] ??= 0
        while (idx[l.handle] < l.points.length && l.points[idx[l.handle]].time <= time) {
          const p = l.points[idx[l.handle]]
          last[l.handle] = p.rating
          if (p.time === time && lines.length === 1) row.info = { contest: p.contest, rank: p.rank, delta: p.rating - p.old }
          idx[l.handle]++
        }
        if (last[l.handle] !== undefined) row[`r:${l.handle}`] = last[l.handle]
      }
      return row
    })
  }, [lines])
  if (!data.length) return null
  const all = lines.flatMap((l) => l.points.map((p) => p.rating))
  const min = Math.max(0, Math.floor((Math.min(...all) - 100) / 100) * 100)
  const max = Math.ceil((Math.max(...all) + 100) / 100) * 100
  const single = lines.length === 1
  const Chart = single ? AreaChart : LineChart
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer>
        <Chart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
          <defs>
            <linearGradient id="area" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="var(--primary)" stopOpacity={0.35} />
              <stop offset="1" stopColor="var(--primary)" stopOpacity={0} />
            </linearGradient>
          </defs>
          {bands(min, max).map((b) => (
            <ReferenceArea key={b.from} y1={Math.max(b.from, min)} y2={Math.min(b.to, max)} fill={b.color} fillOpacity={0.09} stroke="none" ifOverflow="hidden" />
          ))}
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 6" vertical={false} />
          <XAxis
            dataKey="time"
            type="number"
            domain={['dataMin', 'dataMax']}
            tickFormatter={(v: number) => String(new Date(v * 1000).getFullYear())}
            tick={{ fill: 'var(--muted-foreground)', fontSize: 10, fontFamily: 'var(--font-mono)' }}
            tickLine={false}
            axisLine={false}
            minTickGap={24}
          />
          <YAxis
            domain={[min, max]}
            tick={{ fill: 'var(--muted-foreground)', fontSize: 10, fontFamily: 'var(--font-mono)' }}
            tickLine={false}
            axisLine={false}
            width={44}
          />
          <Tooltip content={<TooltipBox />} cursor={{ stroke: 'var(--primary)', strokeOpacity: 0.4 }} />
          {lines.map((l) =>
            single ? (
              <Area
                key={l.handle}
                dataKey={`r:${l.handle}`}
                type="monotone"
                stroke="var(--primary)"
                strokeWidth={2}
                fill="url(#area)"
                dot={false}
                activeDot={{ r: 4, fill: 'var(--primary)', stroke: 'var(--background)', strokeWidth: 2 }}
                isAnimationActive={effects}
                animationDuration={900}
                connectNulls
              />
            ) : (
              <Line
                key={l.handle}
                dataKey={`r:${l.handle}`}
                type="monotone"
                stroke={l.color}
                strokeWidth={2}
                dot={false}
                isAnimationActive={effects}
                animationDuration={900}
                connectNulls
              />
            ),
          )}
          {data.length > 30 && (
            <Brush dataKey="time" height={18} stroke="var(--primary)" fill="var(--muted)" travellerWidth={8} tickFormatter={() => ''} />
          )}
        </Chart>
      </ResponsiveContainer>
    </div>
  )
}

export function DifficultyChart({ items }: { items: { rating: number; count: number }[] }) {
  const { effects } = useSettings()
  return (
    <div className="h-44 w-full">
      <ResponsiveContainer>
        <BarChart data={items} margin={{ top: 8, right: 4, bottom: 0, left: -24 }}>
          <XAxis dataKey="rating" tick={{ fill: 'var(--muted-foreground)', fontSize: 9, fontFamily: 'var(--font-mono)' }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
          <YAxis tick={{ fill: 'var(--muted-foreground)', fontSize: 9 }} tickLine={false} axisLine={false} />
          <Tooltip
            cursor={{ fill: 'var(--muted)' }}
            content={({ active, payload }) =>
              active && payload?.length ? (
                <div className="rounded-lg border bg-popover px-2 py-1 font-mono text-xs">
                  {payload[0].payload.rating}: <b>{payload[0].payload.count}</b>
                </div>
              ) : null
            }
          />
          <Bar dataKey="count" radius={[4, 4, 0, 0]} isAnimationActive={effects}>
            {items.map((i) => (
              <Cell key={i.rating} fill={ratingColor(i.rating)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

/** Weekly submissions of the last year as a soft area (a compact companion to the heatmap). */
export function WeeklyArea({ days }: { days: { day: number; count: number }[] }) {
  const weeks = useMemo(() => {
    const today = Math.floor(Date.now() / 86400000)
    const out = Array.from({ length: 53 }, (_, i) => ({ w: i, count: 0 }))
    for (const d of days) {
      const w = 52 - Math.floor((today - d.day) / 7)
      if (w >= 0 && w < 53) out[w].count += d.count
    }
    return out
  }, [days])
  return (
    <div className="h-16 w-full">
      <ResponsiveContainer>
        <AreaChart data={weeks} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="weekly" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="var(--violet)" stopOpacity={0.5} />
              <stop offset="1" stopColor="var(--violet)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <Area dataKey="count" type="monotone" stroke="var(--violet)" strokeWidth={1.5} fill="url(#weekly)" isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

/** Activity grid of the last 53 weeks; scrolls to the latest weeks on narrow screens. */
export function Heatmap({ days }: { days: { day: number; count: number }[] }) {
  const { fmt } = useSettings()
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (box.current) box.current.scrollLeft = box.current.scrollWidth
  }, [days])
  const cells = useMemo(() => {
    const counts = new Map(days.map((d) => [d.day, d.count]))
    const today = Math.floor(Date.now() / 86400000)
    const weekday = (d: number) => (d + 3) % 7 // Monday = 0; unix day 0 was a Thursday
    const start = today - weekday(today) - 52 * 7
    const max = Math.max(1, ...days.map((d) => d.count))
    const out = []
    for (let d = start; d <= today; d++) {
      const c = counts.get(d) ?? 0
      out.push({ d, c, col: Math.floor((d - start) / 7), row: weekday(d), level: c === 0 ? 0 : Math.min(4, 1 + Math.floor((c / max) * 4)) })
    }
    return out
  }, [days])
  const opacity = [0, 0.3, 0.5, 0.75, 1]
  return (
    <div ref={box} className="overflow-x-auto [scrollbar-width:thin]">
      <svg viewBox={`0 0 ${53 * 13} ${7 * 13}`} className="block w-full min-w-[600px]">
        {cells.map((x) => (
          <rect
            key={x.d}
            x={x.col * 13}
            y={x.row * 13}
            width={11}
            height={11}
            rx={2.5}
            fill={x.level === 0 ? 'var(--muted)' : 'var(--primary)'}
            fillOpacity={x.level === 0 ? 1 : opacity[x.level]}
          >
            <title>
              {fmt.date(x.d * 86400, false)}: {x.c}
            </title>
          </rect>
        ))}
      </svg>
    </div>
  )
}
