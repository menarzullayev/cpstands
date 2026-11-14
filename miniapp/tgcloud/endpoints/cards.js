// Rating cards for a list of handles (the friend list kept in the bot's database).
import { EndpointError } from 'sdk';
import { cached, callCf, checkHandle } from '../lib/cf.js';

const BATCH = 100;
const MAX = 200;

export default async function (input) {
  const handles = Array.isArray(input?.handles) ? input.handles.map(checkHandle) : [];
  if (handles.length > MAX) throw new EndpointError('Too many handles', { code: 'BAD_COUNT' });
  const out = [];
  for (let i = 0; i < handles.length; i += BATCH) {
    const part = handles.slice(i, i + BATCH);
    const key = `users:${part.map((h) => h.toLowerCase()).sort().join(';')}`;
    const users = await cached(key, 900, () => callCf('user.info', { handles: part.join(';') }));
    out.push(...users);
  }
  const byKey = new Map(out.map((u) => [u.handle.toLowerCase(), u]));
  const cards = handles.map((h) => {
    const u = byKey.get(h.toLowerCase()) ?? { handle: h };
    return {
      handle: u.handle,
      rating: u.rating ?? null,
      maxRating: u.maxRating ?? null,
      rank: u.rank ?? null,
      avatar: u.titlePhoto ?? null,
      lastOnline: u.lastOnlineTimeSeconds ?? null,
    };
  });
  cards.sort((a, b) => (b.rating ?? -1) - (a.rating ?? -1));
  return { cards };
}
