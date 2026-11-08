// Upsolve list: problems a handle tried during a contest but did not solve there, per contest,
// marked "upsolved" once a later accepted submission exists. Newest contests first.
import { cached, callCf, checkHandle } from '../lib/cf.js';

const CONTESTS = 15;
const IN_CONTEST = new Set(['CONTESTANT', 'OUT_OF_COMPETITION', 'VIRTUAL']);

async function contestNames() {
  return cached('contest.names', 3600, async () => {
    const all = await callCf('contest.list', { gym: 'false' });
    return Object.fromEntries(all.slice(0, 2000).map((c) => [c.id, c.name]));
  });
}

export function upsolveList(submissions, names) {
  const contests = new Map(); // contestId -> { time, problems: Map(index -> problem) }
  const solvedEver = new Set();
  for (const s of submissions) {
    const key = `${s.problem.contestId}/${s.problem.index}`;
    if (s.verdict === 'OK') solvedEver.add(key);
  }
  for (const s of submissions) {
    const type = s.author?.participantType;
    if (!IN_CONTEST.has(type) || !s.problem.contestId) continue;
    const c = contests.get(s.problem.contestId) ?? { time: 0, virtual: type === 'VIRTUAL', problems: new Map() };
    c.time = Math.max(c.time, s.creationTimeSeconds);
    const p = c.problems.get(s.problem.index) ?? {
      index: s.problem.index,
      name: s.problem.name,
      rating: s.problem.rating ?? null,
      tags: s.problem.tags ?? [],
      solvedInContest: false,
      tries: 0,
    };
    p.tries++;
    if (s.verdict === 'OK') p.solvedInContest = true;
    c.problems.set(s.problem.index, p);
    contests.set(s.problem.contestId, c);
  }
  return [...contests.entries()]
    .sort((a, b) => b[1].time - a[1].time)
    .slice(0, CONTESTS)
    .map(([id, c]) => {
      const problems = [...c.problems.values()]
        .sort((a, b) => a.index.localeCompare(b.index, 'en', { numeric: true }))
        .map((p) => ({
          index: p.index,
          name: p.name,
          rating: p.rating,
          tags: p.tags.slice(0, 3),
          status: p.solvedInContest ? 'solved' : solvedEver.has(`${id}/${p.index}`) ? 'upsolved' : 'todo',
        }));
      return { contestId: id, name: names[id] ?? `Contest ${id}`, time: c.time, virtual: c.virtual, problems };
    })
    .filter((c) => c.problems.some((p) => p.status !== 'solved'));
}

export default async function (input) {
  const handle = checkHandle(input?.handle);
  return cached(`upsolve:${handle.toLowerCase()}`, 900, async () => {
    const submissions = await callCf('user.status', { handle });
    const names = await contestNames();
    const contests = upsolveList(submissions, names);
    const todo = contests.reduce((n, c) => n + c.problems.filter((p) => p.status === 'todo').length, 0);
    const upsolved = contests.reduce((n, c) => n + c.problems.filter((p) => p.status === 'upsolved').length, 0);
    return { handle, todo, upsolved, contests };
  });
}
