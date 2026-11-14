// Rating histories of up to six handles, for one chart, plus head-to-head contest results.
import { EndpointError } from 'sdk';
import { cached, callCf, checkHandle } from '../lib/cf.js';

const MAX = 6;

async function history(handle) {
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

export default async function (input) {
  const list = Array.isArray(input?.handles) ? input.handles : [];
  const handles = [...new Set(list.map(checkHandle).map((h) => h.toLowerCase()))];
  if (handles.length === 0 || handles.length > MAX) {
    throw new EndpointError(`Give 1 to ${MAX} handles`, { code: 'BAD_COUNT' });
  }
  const users = await cached(`users:${handles.join(';')}`, 900, () =>
    callCf('user.info', { handles: handles.join(';') }),
  );
  const series = [];
  for (const user of users) {
    series.push({
      handle: user.handle,
      rating: user.rating ?? null,
      maxRating: user.maxRating ?? null,
      rank: user.rank ?? null,
      avatar: user.titlePhoto ?? null,
      points: await history(user.handle),
    });
  }
  // Contests that at least two of the handles took part in, newest first.
  const byContest = new Map();
  for (const s of series) {
    for (const p of s.points) {
      const row = byContest.get(p.contestId) ?? { contestId: p.contestId, contest: p.contest, time: p.time, ranks: {} };
      row.ranks[s.handle] = p.rank;
      byContest.set(p.contestId, row);
    }
  }
  const common = [...byContest.values()]
    .filter((r) => Object.keys(r.ranks).length >= 2)
    .sort((a, b) => b.time - a.time)
    .slice(0, 20);
  return { series, common };
}
