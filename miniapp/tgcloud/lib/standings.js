// Full Codeforces standings are only served without filters (anonymous GET, no `handles`), and a
// big round is many megabytes. This reader streams the answer, keeps only the rows of the wanted
// handles, and stops as soon as all of them were seen.
import { fetch, EndpointError } from 'sdk';

const URL_BASE = 'https://codeforces.com/api/contest.standings?contestId=';
const ROW = '{"party":';

function cutRow(text) {
  // A row runs up to the next row start; only the separating comma has to go.
  return text.trim().replace(/,$/, '');
}

export async function streamStandings(contestId, handles) {
  const wanted = new Set(handles.map((h) => h.toLowerCase()));
  let res;
  try {
    res = await fetch(URL_BASE + encodeURIComponent(String(contestId)));
  } catch {
    throw new EndpointError('Codeforces is not reachable', { code: 'CF_DOWN' });
  }
  if (res.status === 429 || res.status === 503) throw new EndpointError('Codeforces is busy', { code: 'CF_BUSY' });
  if (!res.ok && res.status !== 400) throw new EndpointError('Codeforces is not available', { code: 'CF_DOWN' });

  const decoder = new TextDecoder();
  let buf = '';
  let head = null; // the text before "rows"
  const rows = [];
  const seen = new Set();
  let bytes = 0;
  for await (const chunk of res.body) {
    bytes += chunk.length;
    buf += decoder.decode(chunk, { stream: true });
    if (head === null) {
      const at = buf.indexOf('"rows":[');
      if (at < 0) {
        if (buf.length > 2_000_000) break; // not a standings answer
        continue;
      }
      head = buf.slice(0, at);
      buf = buf.slice(at + 8);
    }
    // Process every complete row: from one row start to the next.
    let start = buf.indexOf(ROW);
    while (start >= 0) {
      const next = buf.indexOf(ROW, start + ROW.length);
      if (next < 0) break;
      const text = buf.slice(start, next);
      const lower = text.toLowerCase();
      for (const h of wanted) {
        if (lower.includes(`"handle":"${h}"`)) {
          rows.push(JSON.parse(cutRow(text)));
          for (const m of rows[rows.length - 1].party.members) seen.add(m.handle.toLowerCase());
          break;
        }
      }
      start = next;
    }
    buf = start >= 0 ? buf.slice(start) : buf.slice(-ROW.length);
    if (seen.size >= wanted.size) break;
  }
  // The last row of the answer has no successor; check it too.
  if (head !== null && seen.size < wanted.size) {
    const start = buf.indexOf(ROW);
    if (start >= 0) {
      const end = buf.lastIndexOf(']');
      const text = buf.slice(start, end > start ? end : undefined);
      const lower = text.toLowerCase();
      if ([...wanted].some((h) => lower.includes(`"handle":"${h}"`))) {
        try {
          rows.push(JSON.parse(cutRow(text)));
        } catch {
          /* a truncated tail: ignore */
        }
      }
    }
  }
  if (head === null) {
    let comment = '';
    try {
      comment = JSON.parse(buf).comment ?? '';
    } catch {
      /* not JSON */
    }
    throw new EndpointError('Codeforces refused the request', { code: 'CF_ERROR', comment });
  }
  // head looks like {"status":"OK","result":{"contest":{...},"problems":[...],
  const problems = JSON.parse(head.slice(head.indexOf('"problems":') + 11).replace(/,\s*$/, ''));
  return { problems, rows, bytes };
}
