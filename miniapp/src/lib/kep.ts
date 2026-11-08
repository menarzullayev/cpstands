// kep.uz answers of the `kep` endpoint and the site's links.
import type { Contest } from './cf'

export interface KepContest extends Contest {
  rated: boolean
  contestants: number
}

export interface KepContestList {
  live: KepContest[]
  upcoming: KepContest[]
  finished: KepContest[]
}

export interface KepCell {
  points: number
  rejected: number
  time: number | null
}

export interface KepRow {
  handle: string
  rank: number
  points: number
  penalty: number
  virtual: boolean
  delta: number | null
  rating: number | null
  cells: KepCell[]
}

export interface KepStandingsAnswer {
  contest: KepContest
  problems: { index: string; name: string }[]
  rows: KepRow[]
  total?: number
}

export interface KepProfileAnswer {
  handle: string
  rating: number | null
  maxRating: number | null
  title: string | null
  place: number | null
  contests: number
  history: { contestId: number; name: string; date: string; rank: number; delta: number; rating: number }[]
}

const SITE = 'https://kep.uz'

export const kepUrl = {
  contest: (id: number) => `${SITE}/competitions/contests/contest/${id}`,
  standings: (id: number) => `${SITE}/competitions/contests/contest/${id}/standings`,
  problem: (id: number, symbol: string) => `${SITE}/competitions/contests/contest/${id}/problem/${symbol}`,
  profile: (handle: string) => `${SITE}/users/${handle}`,
}
