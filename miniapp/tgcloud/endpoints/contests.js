// Contest calendar: running and upcoming Codeforces rounds, plus the latest finished ones.
import { cached, callCf } from '../lib/cf.js';

const RECENT = 12;

function slim(c) {
  return {
    id: c.id,
    name: c.name,
    type: c.type,
    phase: c.phase,
    start: c.startTimeSeconds ?? null,
    duration: c.durationSeconds,
  };
}

export default async function () {
  return cached('contests', 600, async () => {
    const all = await callCf('contest.list', { gym: 'false' });
    const live = all.filter((c) => c.phase === 'CODING' || c.phase === 'PENDING_SYSTEM_TEST' || c.phase === 'SYSTEM_TEST');
    const upcoming = all
      .filter((c) => c.phase === 'BEFORE')
      .sort((a, b) => (a.startTimeSeconds ?? 0) - (b.startTimeSeconds ?? 0));
    const finished = all.filter((c) => c.phase === 'FINISHED').slice(0, RECENT);
    return {
      live: live.map(slim),
      upcoming: upcoming.map(slim),
      finished: finished.map(slim),
    };
  });
}
