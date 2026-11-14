# Evidence Record

- Evidence ID: EVID-022
- CLAIM: kep.uz has a public, unauthenticated JSON API that covers what the bot needs. The contest list, contest detail, user rating, rating history and per-user attempts are public. The contestants table and problem list return 401 before a contest starts. robots.txt allows every path for every agent. No terms of use are published.
- SOURCE: requests made by hand and by the adapter's research on 2026-11-08; field facts are pinned by the fixtures in `fixtures/kep/` and by `tests/test_kep_parser.py`
- DATE: 2026-11-08
- CONFIDENCE: MEDIUM. The API is undocumented and can change without notice. Running-contest access is not yet measured; see "Open".
- TYPE: FACT
- RISK: MEDIUM
- Stage: 03-market-research

## Endpoints used (base `https://kep.uz/api`)

| Endpoint | Shape | Notes |
|---|---|---|
| `contests/?page=N` | `{page, pageSize: 10, total, pagesCount, data}` | newest first; the bot reads 2 pages |
| `contests/{id}/` | one contest | `status`: -1 not started, 0 running, 1 finished (from the site's own JS) |
| `contests/{id}/problems/` | `[{problem: {...}, symbol}]` | 401 before the start |
| `contests/{id}/contestants/` | one unpaged list (about 100 KB for 65 rows) | 401 before the start; `problemsInfo` is unsorted |
| `contests-rating/{user}/` | rating, max, titles, place | 404 for an unknown user; case-insensitive |
| `contests-rating/{user}/rating-changes/` | per-contest delta, rank, new rating | dates only, no times |
| `attempts/?username=X&page=N` | 20 per page, newest first | used for upsolve alerts |

## Measured semantics

- For a solved problem, `penalties == minutes + 10 * attemptsCount`. So `attemptsCount` is the number of rejected tries before the accepted one (ACM10M rules).
- Row `points` and `penalties` are the sums over problems.
- Virtual participants share the table and its ranks; the bot marks them `VIRTUAL`.
- A user with no rated contest shows rating 1200; the bot treats that as unrated.

## Privacy

Contestant rows also carry `userFullName`, `avatar` and `country`. The parser reads only
`username`. `tests/test_kep_parser.py` proves no full name reaches a domain object: making the
parser read `userFullName` made both privacy tests fail.

## Load

The bot paces kep.uz at one request per 1.5 s, with backoff on 429 and 5xx. A running contest
costs 2 requests every 30 s: the contest detail and the contestants table.

## Open

- Whether `contestants/` is public while a contest runs. Measure it on KEP Contest #23 (id 504),
  2026-11-08 15:35 to 18:05 UTC.
- Terms of use: none are published. Content-Signal in robots.txt says `ai-train=no`, which the bot
  respects; it trains nothing.
