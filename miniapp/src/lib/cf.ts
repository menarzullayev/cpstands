// Codeforces shapes returned by our endpoints, rank colours and rank thresholds.

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
export interface Friend {
  handle: string
  rating: number | null
  maxRating: number | null
  rank: string | null
  avatar: string | null
  lastOnline: number | null
}
export interface FriendsAnswer {
  friends: Friend[]
  max: number
  added?: string[]
  already?: number
  overLimit?: number
}
export type ActivityEvent =
  | {
      kind: 'solve'
      handle: string
      time: number
      contestId: number | null
      index: string
      name: string
      rating: number | null
      live: boolean
      submissionId: number
    }
  | ({ kind: 'rating'; handle: string } & RatingPoint)
export interface Activity {
  events: ActivityEvent[]
  pending: number
  handles: number
}
export interface StandingsAnswer {
  contest: Contest | null
  problems: { index: string; name: string; rating: number | null; points: number | null }[]
  rows: {
    handle: string
    type: string
    rank: number
    points: number
    penalty: number
    hacks: number
    cells: { points: number; rejected: number; time: number | null }[]
  }[]
  recent: { id: number; name: string; phase: string }[]
  me: string | null
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
    recent: { id: number; contestId: number | null; index: string; name: string; rating: number | null; verdict: string; time: number }[]
  }
}

export interface UpsolveAnswer {
  handle: string
  todo: number
  upsolved: number
  contests: {
    contestId: number
    name: string
    time: number
    virtual: boolean
    problems: { index: string; name: string; rating: number | null; tags: string[]; status: 'solved' | 'upsolved' | 'todo' }[]
  }[]
}
export interface Leaderboard {
  period: 'week' | 'month'
  rows: { handle: string; rating: number | null; delta: number; contests: number; best: number | null; solved: number }[]
  pending: number
  me: string | null
}

export const RANKS: { from: number; name: string; color: string }[] = [
  { from: 0, name: 'newbie', color: 'var(--r-newbie)' },
  { from: 1200, name: 'pupil', color: 'var(--r-pupil)' },
  { from: 1400, name: 'specialist', color: 'var(--r-specialist)' },
  { from: 1600, name: 'expert', color: 'var(--r-expert)' },
  { from: 1900, name: 'candidate master', color: 'var(--r-cm)' },
  { from: 2100, name: 'master', color: 'var(--r-master)' },
  { from: 2300, name: 'international master', color: 'var(--r-master)' },
  { from: 2400, name: 'grandmaster', color: 'var(--r-gm)' },
  { from: 2600, name: 'international grandmaster', color: 'var(--r-gm)' },
  { from: 3000, name: 'legendary grandmaster', color: 'var(--r-lgm)' },
]

export function ratingColor(rating: number | null | undefined): string {
  if (rating == null) return 'var(--muted-foreground)'
  let color = RANKS[0].color
  for (const r of RANKS) if (rating >= r.from) color = r.color
  return color
}

/** The next rank above `rating`, or null at the top. */
export function nextRank(rating: number) {
  return RANKS.find((r) => r.from > rating) ?? null
}

export const cfUrl = {
  contest: (id: number) => `https://codeforces.com/contest/${id}`,
  profile: (h: string) => `https://codeforces.com/profile/${h}`,
  problem: (c: number, i: string) => `https://codeforces.com/contest/${c}/problem/${i}`,
  submission: (c: number, id: number) => `https://codeforces.com/contest/${c}/submission/${id}`,
}

export const VERDICT_SHORT: Record<string, string> = {
  OK: 'AC',
  WRONG_ANSWER: 'WA',
  TIME_LIMIT_EXCEEDED: 'TLE',
  MEMORY_LIMIT_EXCEEDED: 'MLE',
  RUNTIME_ERROR: 'RE',
  COMPILATION_ERROR: 'CE',
  IDLENESS_LIMIT_EXCEEDED: 'ILE',
  CHALLENGED: 'HACK',
  SKIPPED: 'SKIP',
  PARTIAL: 'PART',
  TESTING: '…',
}

export const LIVE_PHASES = new Set(['CODING', 'PENDING_SYSTEM_TEST', 'SYSTEM_TEST'])
