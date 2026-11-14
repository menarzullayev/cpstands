// Weekly or monthly leaderboard of the caller's friends (and their own handle): rating gained
// and problems solved in the period. Like `activity`, it refreshes only a few handles per call.
import { db, EndpointError } from 'sdk';
import { eq } from 'sdk/db';
import { cached, callCf, checkHandle, now } from '../lib/cf.js';
import { callerId, handlesFor } from '../lib/friends.js';
import { cfCache } from '../schema.js';

const FRESH_PER_CALL = 2;
const PERIODS = { week: 7 * 86400, month: 30 * 86400 };

async function isCached(key) {
  const row = await db.select({ e: cfCache.expiresAt }).from(cfCache).where(eq(cfCache.key, key)).get();
  return Boolean(row && row.e >= now());
}

function ratingKey(h) {
  return `rating:${h.toLowerCase()}`;
}
function solvedKey(h) {
  return `solved30:${h.toLowerCase()}`;
}

async function ratings(handle) {
  return cached(ratingKey(handle), 1800, async () =>
    (await callCf('user.rating', { handle })).map((r) => ({
      contestId: r.contestId,
      contest: r.contestName,
      time: r.ratingUpdateTimeSeconds,
      rank: r.rank,
      old: r.oldRating,
      rating: r.newRating,
    })),
  );
}

/** Times of first accepted submissions per problem in the last 30 days (newest 500 submissions). */
async function solves(handle) {
  return cached(solvedKey(handle), 1800, async () => {
    const subs = await callCf('user.status', { handle, from: '1', count: '500' });
    const since = now() - PERIODS.month;
    const first = new Map();
    for (const s of subs) {
      if (s.verdict !== 'OK' || s.creationTimeSeconds < since) continue;
      const k = `${s.problem.contestId}/${s.problem.index}`;
      const t = first.get(k);
      if (t === undefined || s.creationTimeSeconds < t) first.set(k, s.creationTimeSeconds);
    }
    return [...first.values()];
  });
}

export default async function (input, ctx) {
  const userId = callerId(ctx);
  const period = input?.period === 'month' ? 'month' : 'week';
  const since = now() - PERIODS[period];
  const me = typeof input?.me === 'string' && input.me ? checkHandle(input.me) : null;
  const handles = [...new Map([...(me ? [me] : []), ...(await handlesFor(userId, input, checkHandle))].map((h) => [h.toLowerCase(), h])).values()];
  if (!handles.length) throw new EndpointError('No friends yet', { code: 'NO_FRIENDS' });

  const rows = [];
  let fresh = 0;
  let pending = 0;
  for (const handle of handles) {
    const warm = (await isCached(ratingKey(handle))) && (await isCached(solvedKey(handle)));
    if (!warm && fresh >= FRESH_PER_CALL) {
      pending++;
      continue;
    }
    if (!warm) fresh++;
    try {
      const history = await ratings(handle);
      const times = await solves(handle);
      const inPeriod = history.filter((r) => r.time >= since);
      const current = history.length ? history[history.length - 1].rating : null;
      rows.push({
        handle,
        rating: current,
        delta: inPeriod.reduce((s, r) => s + (r.rating - r.old), 0),
        contests: inPeriod.length,
        best: inPeriod.length ? Math.min(...inPeriod.map((r) => r.rank)) : null,
        solved: times.filter((t) => t >= since).length,
      });
    } catch (e) {
      const code = e instanceof EndpointError ? e.parameters?.code : null;
      if (code === 'CF_BUSY' || code === 'CF_DOWN') {
        pending++;
        fresh = FRESH_PER_CALL;
        continue;
      }
      if (code === 'NOT_FOUND') continue;
      throw e;
    }
  }
  rows.sort((a, b) => b.solved - a.solved || b.delta - a.delta);
  return { period, rows, pending, me };
}
