// List, add or remove the caller's friends. Added handles are checked against Codeforces.
import { EndpointError } from 'sdk';
import { cached, callCf, checkHandle, now } from '../lib/cf.js';
import { addHandles, callerId, listHandles, MAX_FRIENDS, removeHandles } from '../lib/friends.js';

const BATCH = 100; // user.info accepts many handles; keep URLs short

async function infos(handles) {
  const out = [];
  for (let i = 0; i < handles.length; i += BATCH) {
    const part = handles.slice(i, i + BATCH);
    const key = `users:${part.map((h) => h.toLowerCase()).sort().join(';')}`;
    const users = await cached(key, 900, () => callCf('user.info', { handles: part.join(';') }));
    out.push(...users);
  }
  return out;
}

function card(u) {
  return {
    handle: u.handle,
    rating: u.rating ?? null,
    maxRating: u.maxRating ?? null,
    rank: u.rank ?? null,
    avatar: u.titlePhoto ?? null,
    lastOnline: u.lastOnlineTimeSeconds ?? null,
  };
}

export default async function (input, ctx) {
  const userId = callerId(ctx);
  const action = input?.action ?? 'list';
  const raw = Array.isArray(input?.handles) ? input.handles : [];
  let result = {};

  if (action === 'add') {
    const handles = [...new Set(raw.map(checkHandle))];
    if (!handles.length) throw new EndpointError('No handles', { code: 'BAD_COUNT' });
    // Validates every handle at once; an unknown one makes Codeforces answer "not found".
    const found = await callCf('user.info', { handles: handles.join(';') });
    result = await addHandles(userId, found.map((u) => u.handle), now());
  } else if (action === 'remove') {
    result = { removed: await removeHandles(userId, raw.map(checkHandle)) };
  } else if (action !== 'list') {
    throw new EndpointError('Unknown action', { code: 'BAD_ACTION' });
  }

  const handles = await listHandles(userId);
  const users = handles.length ? await infos(handles) : [];
  const byKey = new Map(users.map((u) => [u.handle.toLowerCase(), u]));
  const list = handles.map((h) => card(byKey.get(h.toLowerCase()) ?? { handle: h }));
  list.sort((a, b) => (b.rating ?? -1) - (a.rating ?? -1));
  return { ...result, max: MAX_FRIENDS, friends: list };
}
