import { useMemo, useRef, useState } from 'react'
import { BANDS, type RatingPoint } from '../cf'
import { fmtDate } from '../i18n'

export interface Line {
  handle: string
  color: string
  points: RatingPoint[]
}

const W = 640
const H = 260
const PAD = { l: 40, r: 10, t: 10, b: 24 }

/** Rating history of one or more handles over the Codeforces rank bands. */
export function RatingChart({ lines }: { lines: Line[] }) {
  const [hover, setHover] = useState<{ x: number; y: number; line: Line; p: RatingPoint } | null>(null)
  const svgRef = useRef<SVGSVGElement>(null)

  const scale = useMemo(() => {
    const all = lines.flatMap((l) => l.points)
    if (all.length === 0) return null
    const t0 = Math.min(...all.map((p) => p.time))
    const t1 = Math.max(...all.map((p) => p.time))
    const r0 = Math.max(0, Math.floor((Math.min(...all.map((p) => p.rating)) - 100) / 100) * 100)
    const r1 = Math.ceil((Math.max(...all.map((p) => p.rating)) + 100) / 100) * 100
    const x = (t: number) => PAD.l + ((t - t0) / Math.max(1, t1 - t0)) * (W - PAD.l - PAD.r)
    const y = (r: number) => PAD.t + (1 - (r - r0) / Math.max(1, r1 - r0)) * (H - PAD.t - PAD.b)
    const step = r1 - r0 > 1600 ? 400 : r1 - r0 > 800 ? 200 : 100
    const ticks: number[] = []
    for (let r = Math.ceil(r0 / step) * step; r <= r1; r += step) ticks.push(r)
    const years: number[] = []
    for (let yv = new Date(t0 * 1000).getUTCFullYear() + 1; yv <= new Date(t1 * 1000).getUTCFullYear(); yv++) {
      years.push(yv)
    }
    return { x, y, r0, r1, ticks, years }
  }, [lines])

  if (!scale) return null

  const onMove = (e: React.PointerEvent<SVGSVGElement>) => {
    const svg = svgRef.current
    if (!svg) return
    const box = svg.getBoundingClientRect()
    const mx = ((e.clientX - box.left) / box.width) * W
    const my = ((e.clientY - box.top) / box.height) * H
    let best: typeof hover = null
    let bestD = Infinity
    for (const line of lines) {
      for (const p of line.points) {
        const dx = scale.x(p.time) - mx
        const dy = scale.y(p.rating) - my
        const d = dx * dx + dy * dy * 0.25
        if (d < bestD) {
          bestD = d
          best = { x: scale.x(p.time), y: scale.y(p.rating), line, p }
        }
      }
    }
    setHover(best)
  }

  return (
    <div className="chart">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        onPointerMove={onMove}
        onPointerLeave={() => setHover(null)}
      >
        {BANDS.filter((b) => b.to > scale.r0 && b.from < scale.r1).map((b) => {
          const top = scale.y(Math.min(b.to, scale.r1))
          const bottom = scale.y(Math.max(b.from, scale.r0))
          return (
            <rect key={b.from} x={PAD.l} y={top} width={W - PAD.l - PAD.r} height={bottom - top} fill={b.color} opacity={0.13} />
          )
        })}
        {scale.ticks.map((r) => (
          <g key={r}>
            <line x1={PAD.l} x2={W - PAD.r} y1={scale.y(r)} y2={scale.y(r)} className="grid" />
            <text x={PAD.l - 6} y={scale.y(r) + 4} className="axis" textAnchor="end">
              {r}
            </text>
          </g>
        ))}
        {scale.years.map((yv) => {
          const x = scale.x(Date.UTC(yv, 0, 1) / 1000)
          return (
            <text key={yv} x={x} y={H - 6} className="axis" textAnchor="middle">
              {yv}
            </text>
          )
        })}
        {lines.map((line) => (
          <polyline
            key={line.handle}
            points={line.points.map((p) => `${scale.x(p.time)},${scale.y(p.rating)}`).join(' ')}
            fill="none"
            stroke={line.color}
            strokeWidth={2}
            strokeLinejoin="round"
          />
        ))}
        {lines.length === 1 &&
          lines[0].points.map((p) => (
            <circle key={p.contestId} cx={scale.x(p.time)} cy={scale.y(p.rating)} r={2.2} fill={lines[0].color} />
          ))}
        {hover && <circle cx={hover.x} cy={hover.y} r={5} fill={hover.line.color} stroke="var(--bg)" strokeWidth={2} />}
      </svg>
      {hover && (
        <div className="tooltip" style={{ left: `${(hover.x / W) * 100}%` }}>
          <b style={{ color: hover.line.color }}>{hover.line.handle}</b> {hover.p.rating}{' '}
          <span className={hover.p.rating >= hover.p.old ? 'up' : 'down'}>
            ({hover.p.rating >= hover.p.old ? '+' : ''}
            {hover.p.rating - hover.p.old})
          </span>
          <div className="muted">
            #{hover.p.rank} · {hover.p.contest}
          </div>
          <div className="muted">{fmtDate(hover.p.time, false)}</div>
        </div>
      )}
    </div>
  )
}
