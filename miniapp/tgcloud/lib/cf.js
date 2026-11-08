// Codeforces API access for the Mini App endpoints: one place for caching and errors.
import { db, fetch, EndpointError } from 'sdk';
import { eq, lt } from 'sdk/db';
import { cfCache } from '../schema.js';

const BASE = 'https://codeforces.com/api/';
const HANDLE_RE = /^[A-Za-z0-9_.-]{1,24}$/;

export function now() {
  return Math.floor(Date.now() / 1000);
}

export function checkHandle(value) {
  const handle = typeof value === 'string' ? value.trim() : '';
  if (!HANDLE_RE.test(handle)) {
    throw new EndpointError('Invalid handle', { code: 'BAD_HANDLE' });
  }
  return handle;
}

async function readCache(key) {
  const row = await db.select().from(cfCache).where(eq(cfCache.key, key)).get();
  if (!row || row.expiresAt < now()) return null;
  return JSON.parse(row.body);
}

async function writeCache(key, value, ttl) {
  const body = JSON.stringify(value);
  const expiresAt = now() + ttl;
  await db
    .insert(cfCache)
    .values({ key, body, expiresAt })
    .onConflictDoUpdate({ target: cfCache.key, set: { body, expiresAt } })
    .run();
  // Keep the table small: drop a few expired rows on every write.
  await db.delete(cfCache).where(lt(cfCache.expiresAt, now() - 3600)).run();
}

/**
 * Raw Codeforces call. Throws EndpointError with a code the front end can branch on.
 * The sandbox has no timers, so a rate-limit answer is not retried here: the client retries.
 */
export async function callCf(method, params = {}) {
  // The sandbox has no URLSearchParams.
  const query = Object.entries(params)
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
    .join('&');
  let res;
  try {
    res = await fetch(`${BASE}${method}${query ? `?${query}` : ''}`);
  } catch (e) {
    console.warn('cf unreachable', method, String(e));
    throw new EndpointError('Codeforces is not reachable', { code: 'CF_DOWN' });
  }
  if (res.status === 429 || res.status >= 500) {
    throw new EndpointError('Codeforces is busy', { code: 'CF_DOWN' });
  }
  let doc;
  try {
    doc = await res.json();
  } catch {
    throw new EndpointError('Codeforces is busy', { code: 'CF_DOWN' });
  }
  if (doc.status !== 'OK') {
    const comment = String(doc.comment || '');
    if (/limit/i.test(comment)) {
      throw new EndpointError('Codeforces is busy', { code: 'CF_BUSY' });
    }
    if (/not found/i.test(comment)) {
      throw new EndpointError('Handle not found', { code: 'NOT_FOUND', comment });
    }
    throw new EndpointError('Codeforces refused the request', { code: 'CF_ERROR', comment });
  }
  return doc.result;
}

/** Cached derived value: `build` runs only on a miss, and only its (small) result is stored. */
export async function cached(key, ttl, build) {
  const hit = await readCache(key);
  if (hit !== null) return hit;
  const value = await build();
  await writeCache(key, value, ttl);
  return value;
}
