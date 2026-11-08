// Friends' activity: recent accepted solutions and rating changes, newest first.
//
// Codeforces allows about one call per two seconds and the sandbox has no timers, so one
// request refreshes at most FRESH_PER_CALL handles; the rest come from cache or wait for the
// next request (the answer says how many are still pending).
import { EndpointError } from 'sdk';
import { cached, callCf, checkHandle, now } from '../lib/cf.js';
import { callerId, handlesFor } from '../lib/friends.js';
import { db } from 'sdk';
import { eq } from 'sdk/db';
import { cfCache } from '../schema.js';

const FRESH_PER_CALL = 2; // two calls per handle: about four Codeforces calls per request
const WINDOW = 14 * 86400; // two weeks
const LIMIT = 60;

async function isCached(key) {
  const row = await db.select({ e: cfCache.expiresAt }).from(cfCache).where(eq(cfCache.key, key)).get();
  return Boolean(row && row.e >= now());
}

async function recentSolves(handle) {
  return cached(`recent:${handle.toLowerCase()}`, 900, async () => {
    const subs = await callCf('user.status', { handle, from: '1', count: '30' });
    const seen = new Set();
    return subs
      .filter((s) => s.verdict === 'OK')
      .filter((s) => {
        const k = `${s.problem.contestId}/${s.problem.index}`;
        if (seen.has(k)) return false;
        seen.add(k);
        return true;
      })
      .map((s) => ({
        kind: 'solve',
        handle,
        time: s.creationTimeSeconds,
        contestId: s.problem.contestId ?? null,
        index: s.problem.index,
        name: s.problem.name,
        rating: s.problem.rating ?? null,
        live: s.author?.participantType === 'CONTESTANT',
        submissionId: s.id,
      }));
  });
}

async function ratingChanges(handle) {
  return cached(`rating:${handle.toLowerCase()}`, 1800, async () => {
    const rows = await callCf('user.rating', { handle });
    return rows.map((r) => ({
      contestId: r.contestId,
      contest: r.contestName,
      time: r.ratingUpdateTimeSeconds,
      rank: r.rank,
      old: r.oldRating,
      rating: r.newRating,
    }));
  });
}

export default async function (input, ctx) {
  const userId = callerId(ctx);
  const extra = typeof input?.me === 'string' && input.me ? [checkHandle(input.me)] : [];
  const handles = [...new Map([...extra, ...(await handlesFor(userId, input, checkHandle))].map((h) => [h.toLowerCase(), h])).values()];
  const since = now() - WINDOW;
  const events = [];
  let fresh = 0;
  let pending = 0;
  for (const handle of handles) {
    const warm =
      (await isCached(`recent:${handle.toLowerCase()}`)) && (await isCached(`rating:${handle.toLowerCase()}`));
    if (!warm && fresh >= FRESH_PER_CALL) {
      pending++;
      continue;
    }
    if (!warm) fresh++;
    try {
      for (const e of await recentSolves(handle)) if (e.time >= since) events.push(e);
      for (const r of await ratingChanges(handle)) {
        if (r.time >= since) events.push({ kind: 'rating', handle, ...r });
      }
    } catch (e) {
      const code = e instanceof EndpointError ? e.parameters?.code : null;
      if (code === 'CF_BUSY' || code === 'CF_DOWN') {
        // Codeforces pushed back: stop refreshing in this request, keep what is cached.
        pending++;
        fresh = FRESH_PER_CALL;
        continue;
      }
      if (e instanceof EndpointError && e.parameters?.code === 'NOT_FOUND') continue;
      throw e;
    }
  }
  events.sort((a, b) => b.time - a.time);
  return { events: events.slice(0, LIMIT), pending, handles: handles.length };
}
