// Standings of one contest, filtered to the caller's friends (and their own handle).
// Without a contest id: the running contest if there is one, else the latest finished one
// in which at least one friend took part.
import { EndpointError } from 'sdk';
import { cached, callCf, checkHandle } from '../lib/cf.js';
import { streamStandings } from '../lib/standings.js';
import { callerId, listHandles } from '../lib/friends.js';

const LIVE = new Set(['CODING', 'PENDING_SYSTEM_TEST', 'SYSTEM_TEST']);

async function contestList() {
  return cached('contest.list', 300, async () =>
    (await callCf('contest.list', { gym: 'false' })).slice(0, 300).map((c) => ({
      id: c.id,
      name: c.name,
      type: c.type,
      phase: c.phase,
      start: c.startTimeSeconds ?? null,
      duration: c.durationSeconds,
    })),
  );
}

async function table(contest, handles) {
  const ttl = LIVE.has(contest.phase) ? 60 : 900;
  const key = `standings:${contest.id}:${handles.map((h) => h.toLowerCase()).sort().join(';')}`;
  return cached(key, ttl, async () => {
    const res = await streamStandings(contest.id, handles);
    return {
      problems: res.problems.map((p) => ({ index: p.index, name: p.name, rating: p.rating ?? null, points: p.points ?? null })),
      rows: res.rows.map((r) => ({
        handle: r.party.members.map((m) => m.handle).join(', '),
        type: r.party.participantType,
        rank: r.rank,
        points: r.points,
        penalty: r.penalty,
        hacks: (r.successfulHackCount ?? 0) - (r.unsuccessfulHackCount ?? 0),
        cells: r.problemResults.map((c) => ({
          points: c.points,
          rejected: c.rejectedAttemptCount,
          time: c.bestSubmissionTimeSeconds ?? null,
        })),
      })),
    };
  });
}

export default async function (input, ctx) {
  const userId = callerId(ctx);
  const me = typeof input?.me === 'string' && input.me ? checkHandle(input.me) : null;
  const handles = [...new Map([...(me ? [me] : []), ...(await listHandles(userId))].map((h) => [h.toLowerCase(), h])).values()];
  if (!handles.length) throw new EndpointError('No friends yet', { code: 'NO_FRIENDS' });

  const contests = await contestList();
  let candidates;
  if (input?.contestId) {
    const c = contests.find((x) => x.id === Number(input.contestId));
    if (!c) throw new EndpointError('Unknown contest', { code: 'NOT_FOUND' });
    candidates = [c];
  } else {
    const live = contests.filter((c) => LIVE.has(c.phase));
    const finished = contests.filter((c) => c.phase === 'FINISHED').slice(0, 4);
    candidates = [...live, ...finished];
  }
  // The first candidate with at least one friend in it; at most 3 lookups per request.
  let chosen = null;
  for (const c of candidates.slice(0, 3)) {
    const t = await table(c, handles);
    if (t.rows.length || input?.contestId) {
      chosen = { contest: c, ...t };
      break;
    }
  }
  const recent = contests
    .filter((c) => c.phase !== 'BEFORE')
    .slice(0, 12)
    .map((c) => ({ id: c.id, name: c.name, phase: c.phase }));
  return { ...(chosen ?? { contest: null, problems: [], rows: [] }), recent, me };
}
