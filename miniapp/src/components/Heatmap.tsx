import { useEffect, useRef } from 'react'
import { fmtDate } from '../i18n'

const CELL = 11
const GAP = 2

/** GitHub-style activity grid of the last 53 weeks; `days` are unix days with counts. */
export function Heatmap({ days }: { days: { day: number; count: number }[] }) {
  // On narrow screens the grid scrolls; start at the most recent weeks.
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (box.current) box.current.scrollLeft = box.current.scrollWidth
  }, [days])
  const counts = new Map(days.map((d) => [d.day, d.count]))
  const today = Math.floor(Date.now() / 86400000)
  // Start on the Monday 52 weeks before the current week (unix day 0 was a Thursday).
  const weekday = (d: number) => (d + 3) % 7 // Monday = 0
  const start = today - weekday(today) - 52 * 7
  const max = Math.max(1, ...days.map((d) => d.count))
  const level = (c: number) => (c === 0 ? 0 : Math.min(4, 1 + Math.floor((c / max) * 4)))
  const cells = []
  for (let d = start; d <= today; d++) {
    const c = counts.get(d) ?? 0
    const col = Math.floor((d - start) / 7)
    const row = weekday(d)
    cells.push(
      <rect key={d} x={col * (CELL + GAP)} y={row * (CELL + GAP)} width={CELL} height={CELL} rx={2} className={`heat l${level(c)}`}>
        <title>
          {fmtDate(d * 86400, false)}: {c}
        </title>
      </rect>,
    )
  }
  const width = 53 * (CELL + GAP)
  return (
    <div className="heatmap" ref={box}>
      <svg viewBox={`0 0 ${width} ${7 * (CELL + GAP)}`} preserveAspectRatio="xMaxYMin meet">
        {cells}
      </svg>
    </div>
  )
}
