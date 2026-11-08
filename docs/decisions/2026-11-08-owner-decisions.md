# Owner decisions, 2026-11-08

Answers to the open questions collected from `docs/*/OUTPUT.md`. Each row closes the question it
names; the stage documents keep their history.

| # | Question (source) | Decision |
|---|---|---|
| 1 | Backups and retention window (05, REQ-018) | No backups for now; risk accepted. Revisit with the database move (row 9). |
| 2 | Next platform after Codeforces (01) | kep.uz. Check its API and terms of use before design. |
| 3 | Alerting when the bot itself is down (06) | Healthchecks.io: the bot pings every minute, and Healthchecks notifies the owner when pings stop. |
| 4 | Watch-list limit per chat (04) | Raise from 100 to 200 handles. |
| 5 | Reminders on `t.me/cpstands` (04) | Yes, automatic: posts 24 h and 1 h before each Codeforces contest. The bot must be a channel admin. |
| 6 | Mini App in the 12-month vision (01) | Start now, with production-grade design. |
| 7 | Paid features (01) | Optional Telegram Stars donations only; nothing is gated. |
| 8 | Real handles in test fixtures (09) | Keep them: public profiles and public results. |
| 9 | Hosting for the Mini App (06) | Telegram Serverless hosts the front end (`app<id>.tgcloud.ai`) and JS endpoints. No Serverless update handlers: `tgcloud webhook sync` must never run, because the Python bot keeps long polling. |
| 10 | Database | Move PostgreSQL to Supabase free (500 MB). The Python bot connects with asyncpg; Mini App endpoints use the Supabase REST API over `fetch`. |
| 11 | Mini App front end | React + Vite + TypeScript. |
| 12 | Mini App v1 scope | Live standings, rating charts, settings panel, contest calendar, profile and statistics, friend comparison, upsolve list, group leaderboard. |
| 13 | Group leaderboard history | Weekly and monthly, inside the existing 30-day retention. |
| 14 | Status page (10) | A separate status page. Assumed to be a Mini App route; not yet confirmed. |

Already closed by the code: secret scanning (`gitleaks` in CI), the `user.status` fallback (upsolve
alerts), friends versus watch lists (friends/all view).

## Capacity check for Supabase free (measured)

Bytes per row, including indexes. Measured by inserting 10 000 synthetic rows inside a rolled-back
transaction:

| Table | Bytes per row |
|---|---|
| `participant_results` | 531 |
| `deliveries` | 500 |
| `solve_events` | 222 |

Contest data and deliveries are kept 30 days (`RETENTION_DAYS`), so size depends on active chats,
not on age.

Assumptions:
- 14 Codeforces contests a month;
- 40% participation per handle;
- 4 solves per participation;
- 20 handles per chat;
- each handle followed by 1.5 chats on average;
- 20% bloat;
- 8 MB for an empty database.

| Active chats | Size |
|---|---|
| 100 | ~50 MB |
| 500 | ~225 MB |
| 1 000 | ~440 MB |
| ~1 100 | 500 MB limit |

Mini App caches, such as rating history and profile statistics, live in the Serverless SQLite
store, not in PostgreSQL.

## Still open

- Exact adaptive polling interval (15–120 s): decided after the live contest on 2026-11-12.
- kep.uz terms of use.
- Serverless limits and pricing: the official page does not state them.
- Where the Supabase key is stored safely for the endpoints: the official page does not say how
  secrets work.
- Account creation: the owner creates the Supabase account and turns on Serverless in BotFather.

## Done: the move to Supabase (2026-11-08)

- **Project:** `cpstands` (ref `upztrvigdloqzxcgdkwi`), organization `cpstands`, Free plan,
  Central EU (Frankfurt).
  - "Automatically expose new tables" is off.
  - Automatic RLS is on.
- **Bot connection:** session pooler (IPv4), `aws-1-eu-central-1.pooler.supabase.com:5432`, with
  `ssl=require`. The URL lives only in `.env` as `CPSTANDS_DATABASE_URL`. The local Docker
  database stays as a fallback: remove that line and the bot uses it again.
- **Data:** copied with `pg_dump --data-only` in one transaction. Row counts matched in all
  eight tables.
- **API audit:** the anon role has no table grants, RLS is on everywhere, the `private` schema is
  closed, and only the six `app_*` functions are executable.
  - Reading a table over REST returns 401.
  - A forged signature returns 403.
  - Real Telegram init data from the Mini App works for settings and friends; checked live.
- **Mini App config:** `miniapp/.env.production` holds the URL and the publishable key (public by
  design). `.gitleaks.toml` allows only `sb_publishable_` keys, and a negative test shows other
  secrets are still caught.
- **Settings left as they are:**
  - There are no network restrictions.
  - There are no backups (row 1).
- **Enforce SSL turned on (2026-11-08, owner approval):**
  - The database restart caused one moment of "database not available" errors in the bot's
    loops (06:32:42 UTC); the bot recovered without a restart.
  - Measured: an SSL connection works, and a non-SSL one is refused with `ESSLREQUIRED`.

## Follow-up decisions (2026-11-08, later)

| Topic | Decision and state |
|---|---|
| Backups (row 1 revised) | One every 30 days, plus manual runs. The scheduled task is `cpstands\monthly-db-backup`. Dumps leave out the bot token, and a restore into a throwaway container is checked. See `docs/runbooks/database-backup.md`. |
| Local production database | Deleted after a final token-free dump (`~/backups/cpstands/localdb-final-*.dump`). The compose `db` service is now `profiles: ["dev"]`, used for tests only. Production needs `CPSTANDS_DATABASE_URL`, with no fallback. |
| Secret files | Moved from the Desktop to `~/.secrets/cpstands/`. The folder ACL allows only the owner and SYSTEM. |
| Next feature | Group mode in the Mini App. |

