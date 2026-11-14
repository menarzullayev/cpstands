// A handle's profile with statistics derived from its whole submission history.
import { cached, callCf, checkHandle, now } from '../lib/cf.js';

const DAY = 86400;
const HEATMAP_DAYS = 371; // 53 weeks

function problemKey(p) {
  return `${p.contestId ?? p.problemsetName ?? ''}/${p.index}`;
}

export function summarize(submissions, nowS) {
  const solved = new Map(); // key -> problem
  const attempted = new Set();
  const verdicts = {};
  const languages = {};
  const daily = {};
  const from = nowS - HEATMAP_DAYS * DAY;
  for (const s of submissions) {
    const key = problemKey(s.problem);
    attempted.add(key);
    const v = s.verdict || 'TESTING';
    verdicts[v] = (verdicts[v] || 0) + 1;
    const lang = String(s.programmingLanguage || '').replace(/\s*\(.*\)$/, '');
    if (lang) languages[lang] = (languages[lang] || 0) + 1;
    if (s.creationTimeSeconds >= from) {
      const day = Math.floor(s.creationTimeSeconds / DAY);
      daily[day] = (daily[day] || 0) + 1;
    }
    if (v === 'OK' && !solved.has(key)) solved.set(key, s.problem);
  }
  const tags = {};
  const ratings = {};
  for (const p of solved.values()) {
    for (const tag of p.tags || []) tags[tag] = (tags[tag] || 0) + 1;
    if (p.rating) ratings[p.rating] = (ratings[p.rating] || 0) + 1;
  }
  const top = (obj, n) =>
    Object.entries(obj)
      .sort((a, b) => b[1] - a[1])
      .slice(0, n)
      .map(([name, count]) => ({ name, count }));
  // Current streak of days with at least one submission, counting back from today.
  let streak = 0;
  for (let d = Math.floor(nowS / DAY); daily[d]; d--) streak++;
  return {
    solved: solved.size,
    attempted: attempted.size,
    submissions: submissions.length,
    verdicts: top(verdicts, 8),
    languages: top(languages, 5),
    tags: top(tags, 12),
    ratings: Object.entries(ratings)
      .map(([rating, count]) => ({ rating: Number(rating), count }))
      .sort((a, b) => a.rating - b.rating),
    heatmap: Object.entries(daily).map(([day, count]) => ({ day: Number(day), count })),
    streak,
    recent: submissions.slice(0, 8).map((s) => ({
      id: s.id,
      contestId: s.contestId ?? null,
      index: s.problem.index,
      name: s.problem.name,
      rating: s.problem.rating ?? null,
      verdict: s.verdict || 'TESTING',
      time: s.creationTimeSeconds,
    })),
  };
}

export default async function (input) {
  const handle = checkHandle(input?.handle);
  return cached(`profile:${handle.toLowerCase()}`, 1800, async () => {
    const [user] = await callCf('user.info', { handles: handle });
    const history = await callCf('user.rating', { handle: user.handle });
    const submissions = await callCf('user.status', { handle: user.handle });
    return {
      user: {
        handle: user.handle,
        rating: user.rating ?? null,
        maxRating: user.maxRating ?? null,
        rank: user.rank ?? null,
        maxRank: user.maxRank ?? null,
        avatar: user.titlePhoto ?? null,
        country: user.country ?? null,
        organization: user.organization ?? null,
        contribution: user.contribution ?? 0,
        friendOfCount: user.friendOfCount ?? 0,
        registered: user.registrationTimeSeconds ?? null,
      },
      contests: history.length,
      best: history.reduce((best, h) => (best === null || h.rank < best.rank ? h : best), null),
      stats: summarize(submissions, now()),
    };
  });
}
