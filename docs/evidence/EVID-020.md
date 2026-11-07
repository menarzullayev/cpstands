# Evidence Record

- Evidence ID: EVID-020
- CLAIM: Codeforces serves contest.standings from a proxy cache for about 60 s (Cache-Control max-age=60, Expires header, X-Proxy-Cache HIT or EXPIRED, no ETag); a request just after Expires returns a fresh generation with a new Expires 60 s ahead. Verified on finished contests only.
- SOURCE: docs/experiments/M1-standings-fetch.md (live measurement, 2026-11-08)
- DATE: 2026-11-08
- CONFIDENCE: MEDIUM
- TYPE: FACT
- RISK: MEDIUM
- Stage: 03-market-research
