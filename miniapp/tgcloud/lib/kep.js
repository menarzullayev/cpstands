// kep.uz API access for the Mini App: one place for errors. Answers are cached by the caller.
// Privacy: contestant rows carry full names, avatars and countries; nothing here keeps them.
import { fetch, EndpointError } from 'sdk';

const BASE = 'https://kep.uz/api/';
const HANDLE_RE = /^[A-Za-z0-9_.-]{1,24}$/;

export function checkKepHandle(value) {
  const handle = typeof value === 'string' ? value.trim() : '';
  if (!HANDLE_RE.test(handle)) throw new EndpointError('Invalid handle', { code: 'BAD_HANDLE' });
  return handle;
}

export function checkContestId(value) {
  const id = Number(value);
  if (!Number.isInteger(id) || id <= 0 || id > 9_999_999) {
    throw new EndpointError('Invalid contest', { code: 'BAD_INPUT' });
  }
  return id;
}

/** GET a kep.uz path; 404 -> NOT_FOUND, 401/403 -> NOT_STARTED (tables are closed before the start). */
export async function callKep(path) {
  let res;
  try {
    res = await fetch(`${BASE}${path}`, { headers: { Accept: 'application/json' } });
  } catch (e) {
    console.warn('kep unreachable', path, String(e));
    throw new EndpointError('kep.uz is not reachable', { code: 'KEP_DOWN' });
  }
  if (res.status === 404) throw new EndpointError('Not found', { code: 'NOT_FOUND' });
  if (res.status === 401 || res.status === 403) {
    throw new EndpointError('Not open yet', { code: 'NOT_STARTED' });
  }
  if (res.status === 429) throw new EndpointError('kep.uz is busy', { code: 'KEP_BUSY' });
  if (res.status >= 400) throw new EndpointError('kep.uz is not available', { code: 'KEP_DOWN' });
  try {
    return await res.json();
  } catch {
    throw new EndpointError('kep.uz sent no JSON', { code: 'KEP_DOWN' });
  }
}

const PHASE = { '-1': 'BEFORE', 0: 'CODING', 1: 'FINISHED' };

function seconds(iso) {
  const t = Date.parse(iso);
  return Number.isFinite(t) ? Math.floor(t / 1000) : null;
}

export function slimContest(c) {
  const start = seconds(c.startTime);
  const end = seconds(c.finishTime);
  return {
    id: c.id,
    name: String(c.title ?? ''),
    type: String(c.type ?? '').startsWith('ACM') ? 'ICPC' : String(c.type ?? ''),
    phase: PHASE[String(c.status)] ?? 'FINISHED',
    start,
    duration: start !== null && end !== null ? end - start : 0,
    rated: Boolean(c.isRated),
    contestants: Number(c.contestantsCount ?? 0),
  };
}

/** "HH:MM" from the start -> seconds. */
function contestTime(value) {
  if (typeof value !== 'string') return null;
  const [h, m, s] = value.split(':').map(Number);
  if (!Number.isFinite(h) || !Number.isFinite(m)) return null;
  return h * 3600 + m * 60 + (Number.isFinite(s) ? s : 0);
}

/** One contestant row with only public facts, cells in problem order. */
export function slimRow(row, order) {
  const bySymbol = new Map((row.problemsInfo ?? []).map((p) => [String(p.problemSymbol), p]));
  return {
    handle: String(row.username ?? ''),
    rank: Number(row.rank ?? 0),
    points: Number(row.points ?? 0),
    penalty: Number(row.penalties ?? 0),
    virtual: Boolean(row.isVirtual),
    delta: typeof row.delta === 'number' ? row.delta : null,
    rating: typeof row.newRating === 'number' ? row.newRating : null,
    cells: order.map((symbol) => {
      const p = bySymbol.get(symbol);
      if (!p) return { points: 0, rejected: 0, time: null };
      return {
        points: Number(p.points ?? 0),
        rejected: Number(p.attemptsCount ?? 0),
        time: Number(p.points ?? 0) > 0 ? contestTime(p.contestTime) : null,
      };
    }),
  };
}
