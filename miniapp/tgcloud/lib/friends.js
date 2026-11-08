// The caller's friend list. The caller is always the verified Telegram user.
import { db, EndpointError } from 'sdk';
import { and, asc, eq, inArray } from 'sdk/db';
import { friends } from '../schema.js';

export const MAX_FRIENDS = 200;

export function callerId(ctx) {
  const id = ctx?.initData?.user?.id;
  if (typeof id !== 'number') throw new EndpointError('Open the app from Telegram', { code: 'UNAUTHORIZED' });
  return id;
}

export async function listHandles(userId) {
  const rows = await db
    .select({ handle: friends.handle })
    .from(friends)
    .where(eq(friends.userId, userId))
    .orderBy(asc(friends.addedAt), asc(friends.id))
    .all();
  return rows.map((r) => r.handle);
}

export async function addHandles(userId, handles, now) {
  const have = await listHandles(userId);
  const room = MAX_FRIENDS - have.length;
  const known = new Set(have.map((h) => h.toLowerCase()));
  const fresh = handles.filter((h) => !known.has(h.toLowerCase()));
  const added = fresh.slice(0, Math.max(0, room));
  if (added.length) {
    await db
      .insert(friends)
      .values(added.map((handle) => ({ userId, handle, handleKey: handle.toLowerCase(), addedAt: now })))
      .onConflictDoNothing()
      .run();
  }
  return { added, already: handles.length - fresh.length, overLimit: fresh.length - added.length };
}

export async function removeHandles(userId, handles) {
  const keys = handles.map((h) => h.toLowerCase());
  if (!keys.length) return 0;
  const res = await db
    .delete(friends)
    .where(and(eq(friends.userId, userId), inArray(friends.handleKey, keys)))
    .run();
  return res.rowsAffected ?? 0;
}
