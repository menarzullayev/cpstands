// kep.uz in the Mini App: { op: 'contests' } | { op: 'standings', contestId, handles? }
// | { op: 'profile', handle }. Public facts only; no full names, avatars or countries.
import { EndpointError } from 'sdk';
import { cached } from '../lib/cf.js';
import { callKep, checkContestId, checkKepHandle, slimContest, slimRow } from '../lib/kep.js';

async function contests() {
  return cached('kep:contests', 300, async () => {
    const pages = await Promise.all([1, 2].map((p) => callKep(`contests/?page=${p}`)));
    const all = pages.flatMap((p) => (Array.isArray(p?.data) ? p.data : [])).map(slimContest);
    const byStart = (a, b) => (a.start ?? 0) - (b.start ?? 0);
    return {
      live: all.filter((c) => c.phase === 'CODING'),
      upcoming: all.filter((c) => c.phase === 'BEFORE').sort(byStart),
      finished: all.filter((c) => c.phase === 'FINISHED').slice(0, 12),
    };
  });
}

async function standings(input) {
  const id = checkContestId(input?.contestId);
  const contest = await cached(`kep:contest:${id}`, 60, async () => slimContest(await callKep(`contests/${id}/`)));
  if (contest.phase === 'BEFORE') return { contest, problems: [], rows: [] };
  // A running table is re-read every 30 s, as in the bot.
  const ttl = contest.phase === 'CODING' ? 30 : 900;
  const table = await cached(`kep:table:${id}`, ttl, async () => {
    const [problems, rows] = await Promise.all([
      callKep(`contests/${id}/problems/`),
      callKep(`contests/${id}/contestants/`),
    ]);
    const list = (Array.isArray(problems) ? problems : []).map((p) => ({
      index: String(p.symbol),
      name: String(p.problem?.title ?? ''),
    }));
    const order = list.map((p) => p.index);
    return { problems: list, rows: (Array.isArray(rows) ? rows : []).map((r) => slimRow(r, order)) };
  });
  const wanted = Array.isArray(input?.handles)
    ? new Set(input.handles.filter((h) => typeof h === 'string').slice(0, 200).map((h) => h.toLowerCase()))
    : null;
  const rows = wanted && wanted.size ? table.rows.filter((r) => wanted.has(r.handle.toLowerCase())) : table.rows;
  return { contest, problems: table.problems, rows: rows.slice(0, 500), total: table.rows.length };
}

async function profile(input) {
  const handle = checkKepHandle(input?.handle);
  const key = handle.toLowerCase();
  return cached(`kep:profile:${key}`, 600, async () => {
    const [rating, changes] = await Promise.all([
      callKep(`contests-rating/${encodeURIComponent(handle)}/`),
      callKep(`contests-rating/${encodeURIComponent(handle)}/rating-changes/`).catch(() => []),
    ]);
    const played = Number(rating?.contestantsCount ?? 0);
    return {
      handle: String(rating?.username ?? handle),
      // kep.uz shows 1200 for users with no rated contest: that is not a real rating.
      rating: played > 0 ? Number(rating?.rating ?? 0) : null,
      maxRating: played > 0 ? Number(rating?.maxRating ?? 0) : null,
      title: played > 0 ? String(rating?.ratingTitle ?? '') : null,
      place: played > 0 ? Number(rating?.ratingPlace ?? 0) : null,
      contests: played,
      history: (Array.isArray(changes) ? changes : []).map((c) => ({
        contestId: Number(c.contestId),
        name: String(c.contestTitle ?? ''),
        date: String(c.contestStartDate ?? ''),
        rank: Number(c.rank ?? 0),
        delta: Number(c.delta ?? 0),
        rating: Number(c.newRating ?? 0),
      })),
    };
  });
}

export default async function (input) {
  switch (input?.op) {
    case 'contests':
      return contests();
    case 'standings':
      return standings(input);
    case 'profile':
      return profile(input);
    default:
      throw new EndpointError('Unknown operation', { code: 'BAD_INPUT' });
  }
}
