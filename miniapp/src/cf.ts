// Codeforces rank colours and the shapes our endpoints return.

export interface Contest {
  id: number
  name: string
  type: string
  phase: string
  start: number | null
  duration: number
}

export interface ContestList {
  live: Contest[]
  upcoming: Contest[]
  finished: Contest[]
}

export interface RatingPoint {
  contestId: number
  contest: string
  time: number
  rank: number
  old: number
  rating: number
}

export interface Profile {
  user: {
    handle: string
    rating: number | null
    maxRating: number | null
    rank: string | null
    maxRank: string | null
    avatar: string | null
    country: string | null
    organization: string | null
    contribution: number
    friendOfCount: number
    registered: number | null
  }
  contests: number
  best: { contestId: number; contestName: string; rank: number } | null
  stats: {
    solved: number
    attempted: number
    submissions: number
    verdicts: { name: string; count: number }[]
    languages: { name: string; count: number }[]
    tags: { name: string; count: number }[]
    ratings: { rating: number; count: number }[]
    heatmap: { day: number; count: number }[]
    streak: number
    recent: {
      id: number
      contestId: number | null
      index: string
      name: string
      rating: number | null
      verdict: string
      time: number
    }[]
  }
}

export interface Series {
  handle: string
  rating: number | null
  maxRating: number | null
  rank: string | null
  avatar: string | null
  points: RatingPoint[]
}

export interface Comparison {
  series: Series[]
  common: { contestId: number; contest: string; time: number; ranks: Record<string, number> }[]
}

/** Rating bands as on Codeforces; the colour is a CSS variable so dark mode can brighten it. */
export const BANDS: { from: number; to: number; color: string }[] = [
  { from: 0, to: 1200, color: 'var(--r-newbie)' },
  { from: 1200, to: 1400, color: 'var(--r-pupil)' },
  { from: 1400, to: 1600, color: 'var(--r-specialist)' },
  { from: 1600, to: 1900, color: 'var(--r-expert)' },
  { from: 1900, to: 2100, color: 'var(--r-cm)' },
  { from: 2100, to: 2400, color: 'var(--r-master)' },
  { from: 2400, to: 3000, color: 'var(--r-gm)' },
  { from: 3000, to: 5000, color: 'var(--r-lgm)' },
]

export function ratingColor(rating: number | null | undefined): string {
  if (rating == null) return 'var(--hint)'
  return (BANDS.find((b) => rating < b.to) ?? BANDS[BANDS.length - 1]).color
}

export const contestUrl = (id: number) => `https://codeforces.com/contest/${id}`
export const profileUrl = (handle: string) => `https://codeforces.com/profile/${handle}`
export const submissionUrl = (contestId: number, id: number) =>
  `https://codeforces.com/contest/${contestId}/submission/${id}`

export const VERDICT_SHORT: Record<string, string> = {
  OK: 'AC',
  WRONG_ANSWER: 'WA',
  TIME_LIMIT_EXCEEDED: 'TLE',
  MEMORY_LIMIT_EXCEEDED: 'MLE',
  RUNTIME_ERROR: 'RE',
  COMPILATION_ERROR: 'CE',
  IDLENESS_LIMIT_EXCEEDED: 'ILE',
  CHALLENGED: 'HACKED',
  SKIPPED: 'SKIP',
  PARTIAL: 'PART',
  TESTING: '…',
}
