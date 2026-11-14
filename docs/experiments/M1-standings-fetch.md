# Experiment M1: the standings data path

Date: 2026-11-08. Code: `scripts/experiment_standings.py`, `scripts/record_fixtures.py`, `src/cpstands/sources/`.
Questions: can the data path meet NFR-001 (fetch cadence), NFR-002 (7 MB parse in under 3 s and 256 MB) and REQ-N01 (p95 data age at most 60 s)?

## Method

1. **Live measurement** with the production client (one request per two seconds, gzip, identifying User-Agent) against three finished contests of different size and `contest.list`.
2. **Parse benchmark** on synthetic bodies shaped like real ones (rows cycled from an anonymized fixture), each size in a fresh process, body read from disk, peak working set from the operating system.
3. **Cache probe**: repeated requests and an expiry-aligned polling loop on one contest, reading `Cache-Control`, `Expires` and `X-Proxy-Cache`.
4. **Cadence model**: a simulation of the age of the displayed data for several polling strategies under the observed cache behavior (6 hours simulated, 20 000 random observation instants, 3 s processing delay).

## Results

### Payload size and fetch time (live, 2026-11-08)

| Request | Rows | Wire (gzip) | Decoded | Ratio | Fetch | Parse |
|---|---|---|---|---|---|---|
| `contest.list` | 2168 contests | 39.7 KB | 413 KB | 10x | 0.67 s | n/a |
| standings, small round | 670 | 33 KB | 0.52 MB | 16x | 0.27 s | 13 ms |
| standings, large Div. 2 | 8 974 | 357 KB | 6.25 MB | 18x | 1.25 s | 146 ms |
| standings, large Educational | 9 743 | 305 KB | 7.20 MB | 24x | 1.13 s | 169 ms |

The earlier "6 to 7 MB per fetch" figure (EVID-003) is the **decoded** size; the bytes on the wire are 17 to 24 times smaller because the API answers with gzip.

### Parse benchmark (synthetic bodies, separate process per cell)

| Rows | Watched | Decoded MB | Median ms | Parser adds MB (RSS) |
|---|---|---|---|---|
| 670 | 20 to 200 | 0.57 | 14 to 15 | 0.0 |
| 3 000 | 20 to 2000 | 2.54 | 57 to 71 | 0.3 to 6.0 |
| 9 743 | 20 to 2000 | 8.26 | 183 to 194 | 1.5 to 7.1 |
| 20 000 | 20 to 2000 | 16.97 | 371 to 388 | 2.9 to 8.8 |

NFR-002 is met with a very large margin: 9 743 rows parse in about 0.19 s (limit 3 s) and add 2 to 7 MB (limit 256 MB). The C backend of `ijson` reads the largest observed body in under 0.2 s.

### Platform cache behavior

- `contest.standings` responses carry `Cache-Control: public, max-age=60`, an `Expires` header, and `X-Proxy-Cache: HIT` or `EXPIRED`. There is no `ETag`, `Last-Modified` or `Age`; a conditional request is ignored.
- Probe of one contest: three requests within 8 s were all `HIT` with the same `Expires`.
- Expiry-aligned loop (request 1 s after `Expires`): cycle 0 `HIT` (earlier request), cycle 1 `EXPIRED` with a new `Expires` 60.0 s ahead, cycle 2 `EXPIRED` again. The proxy refreshes on the first request after expiry and the cache then lives for 60 s.
- `contest.list` is served with `no-cache` headers (always fresh) and costs about 40 KB.

### Cadence model (age of the data a user sees, seconds)

| Demand model | Strategy | Requests per minute | p50 | p95 | p99 |
|---|---|---|---|---|---|
| shared (other clients keep the cache fresh) | fixed 15 s | 4.0 | 40.6 | 67.6 | 69.9 |
| shared | fixed 20 s (current NFR-001 default) | 3.0 | 41.1 | 68.4 | 70.7 |
| shared | fixed 30 s | 2.0 | 58.3 | 85.1 | 87.5 |
| shared | fixed 60 s | 1.0 | 91.1 | 117.8 | 120.0 |
| shared | **expiry-aligned** | **1.0** | **33.2** | **60.6** | **62.9** |
| only our requests refresh the cache | fixed 20 s | 3.0 | 32.9 | 60.0 | 62.3 |
| only our requests refresh the cache | fixed 60 s | 1.0 | 32.7 | 60.0 | 62.4 |
| only our requests refresh the cache | **expiry-aligned** | **1.0** | **33.5** | **60.4** | **62.9** |

## Conclusions

1. **Faster polling does not help.** Inside the 60 s cache window every request returns the same body. Expiry-aligned polling gives the best result in both demand models with one request per minute, while the fixed 20 s default costs three times more and is worse when other clients share the cache (p95 about 68 s).
2. **The achievable floor for p95 data age is about 60 to 63 s** (60 s cache plus a few seconds of processing). The target in REQ-N01 and METRIC-001 (p95 at most 60 s) cannot be promised with any margin. A target of p95 at most 75 s is realistic.
3. **Bandwidth and parsing are not a problem.** About 0.3 MB per fetch on the wire, about 0.2 s to parse, negligible memory.
4. **Alert latency** (REQ-N03, p95 at most 120 s) is achievable: the same one-minute cache bounds the delay to about 60 s plus batching.
5. The data path therefore fits ADR-004 (shared full-standings fetch, local filtering) and the home-PC hosting decision: one request per active contest per minute.

## Limits of this experiment

- Only **finished** contests were available (no round was running). Whether a running contest uses the same 60 s cache, and whether other clients keep it warm, is **not verified**. The next live round (Codeforces Round Div. 4 on 2026-11-12, 19:35 Tashkent time) is the chance to run `scripts/experiment_standings.py expiry --contest <id>` during CODING and compare.
- The cadence model assumes a 60 s cache and a 3 s processing delay; real Telegram edit latency is not included.
- Parse timings use synthetic bodies; the real largest bodies parsed in about the same time in the live run.

## Recommended amendments (need the owner's approval)

| Document | Change |
|---|---|
| NFR-001 (stage 08) | Replace "one fetch every 20 s, adaptive between 15 s and 120 s" with "fetch shortly after the cache expiry reported by `Expires` (margin 1 s), fallback 60 s, never faster than the 2 s request spacing" |
| REQ-N01 and METRIC-001 (stages 01 and 04) | Replace "p95 data age at most 60 s" with "p95 at most 75 s", because the source cache alone is 60 s |
| ADR-004 consequences (stage 07) | Bandwidth is about 0.3 MB per fetch on the wire; no conditional requests exist; polling is expiry-aligned |
| Evidence register (stage 03) | Add EVID-019, EVID-020 and EVID-021 |
