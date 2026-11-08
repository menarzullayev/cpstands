# Technical Specification

Scope: release R1. Decisions are recorded as ADR-001 to ADR-014 (stage 07). Domain terms DOM-001 to DOM-020 come from stage 05.
Targets are defined here as NFR-001 to NFR-012 and trace to the stage 04 requirements.

## API contract

### Telegram commands (menus from the bot profile)

| Command | Scope | Who | Behavior | Requirements |
|---|---|---|---|---|
| `/start` | private, group | anyone (group: admin completes setup) | Starts onboarding: language, time zone, then optional first handles | REQ-014, REQ-011 |
| `/standings` | private, group | any member | Shows or refreshes the contest's standings message for this chat; creates it if absent | REQ-001, REQ-002, REQ-003 |
| `/upcoming` | private, group | any member | Next contests with `date_time` entities and links | REQ-016, REQ-005 |
| `/friends` (private) and `/track` (group admins) | private, group admins | admin of the chat | Watch-list management: add, remove, list, bulk input | REQ-011, REQ-012, REQ-021 |
| `/rank` | group | any member | Ephemeral answer with the asker's rank (R2; reserved name) | FEAT-009 |
| `/settings` | private, group admins | admin of the chat | Language, time zone, reminder offsets, tone, alerts on or off | REQ-014, REQ-009 |
| `/privacy` | all | anyone | What is stored, policy link | REQ-017 |
| `/delete` | all | chat admin (chat data) or user (own data) | Confirmation step, then deletion | REQ-018 |
| `/help` | all | anyone | Short help in the chat language | REQ-015 |
| `/status`, `/pause`, `/resume`, `/stats` | private | owner only (Telegram id from configuration) | Health, source and chat pause controls, counters | REQ-019, REQ-020 |

Rules: commands with an `@cpstandsbot` suffix are accepted in groups; unknown commands get a localized hint; all user-visible text comes from Fluent catalogs (ADR-010).

### Callback data (inline buttons)

Callback data is at most 64 bytes: `<area>:<action>[:<arg>]`, for example `set:lang:uz`, `wl:rm:<handle_id>`, `rem:toggle:24h`. Unknown or expired data
is answered with a localized "button expired" notice and never raises. Admin-only actions re-check the caller's role on every press.

### Operational HTTP endpoints (bound to localhost)

| Endpoint | Purpose |
|---|---|
| `GET /healthz` | Liveness: process and event loop respond |
| `GET /readyz` | Readiness: database reachable, migrations at head, scheduler leader known |
| `GET /metrics` | Prometheus text format (NFR-009) |

No endpoint is exposed to the internet on the home PC (long polling, ADR-006). Webhook mode on a dedicated host adds `POST /tg/<secret_path>` verified by the secret-token header.

## Database schema

PostgreSQL 16, managed by Alembic (ADR-011). All timestamps are `timestamptz` in UTC; identifiers are `bigint` Telegram ids or `bigserial` surrogate keys.
Core DDL (abridged to the constraints that carry the domain invariants):

```sql
CREATE TABLE chats (
  chat_id        bigint PRIMARY KEY,
  chat_type      text NOT NULL CHECK (chat_type IN ('private','group','supergroup')),
  language       text CHECK (language IN ('uz','ru','en')),
  time_zone      text,
  tone           text NOT NULL DEFAULT 'playful' CHECK (tone IN ('playful','neutral')),
  alerts_enabled boolean NOT NULL DEFAULT true,
  reminder_offsets integer[] NOT NULL DEFAULT '{1440,60,10}',
  status         text NOT NULL DEFAULT 'onboarding' CHECK (status IN ('onboarding','active','paused','removed','deleted')),
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE watched_handles (
  chat_id        bigint NOT NULL REFERENCES chats ON DELETE CASCADE,
  platform       text NOT NULL,
  handle_key     text NOT NULL,            -- lower-case canonical key
  handle_display text NOT NULL,
  added_at       timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (chat_id, platform, handle_key)      -- no duplicates (domain invariant 2)
);

CREATE TABLE contests (
  platform text NOT NULL, external_id bigint NOT NULL,
  name text NOT NULL, phase text NOT NULL, starts_at timestamptz, duration_s integer,
  problems jsonb NOT NULL DEFAULT '[]', source_version bigint NOT NULL DEFAULT 0,
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (platform, external_id)
);

CREATE TABLE participant_results (
  platform text NOT NULL, contest_id bigint NOT NULL, handle_key text NOT NULL,
  rank integer, points numeric, penalty integer, problem_results jsonb NOT NULL, official boolean NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (platform, contest_id, handle_key)
);

CREATE TABLE solve_events (
  event_key text PRIMARY KEY,               -- deterministic: platform|contest|handle|problem|kind|verdict_time (invariant 5)
  platform text NOT NULL, contest_id bigint NOT NULL, handle_key text NOT NULL, problem text NOT NULL,
  kind text NOT NULL CHECK (kind IN ('solve','upsolve','systest_fail','systest_pass')),
  occurred_at timestamptz NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE reminders (
  chat_id bigint NOT NULL REFERENCES chats ON DELETE CASCADE,
  platform text NOT NULL, contest_id bigint NOT NULL, offset_min integer NOT NULL,
  due_at timestamptz NOT NULL, state text NOT NULL DEFAULT 'scheduled' CHECK (state IN ('scheduled','sent','cancelled','skipped')),
  sent_at timestamptz, attempts integer NOT NULL DEFAULT 0,
  PRIMARY KEY (chat_id, platform, contest_id, offset_min)   -- at most one per offset (invariant 4)
);

CREATE TABLE standings_messages (
  chat_id bigint NOT NULL REFERENCES chats ON DELETE CASCADE,
  platform text NOT NULL, contest_id bigint NOT NULL,
  message_id bigint, state text NOT NULL DEFAULT 'active' CHECK (state IN ('active','frozen','orphaned')),
  last_hash text, last_edit_at timestamptz, dirty boolean NOT NULL DEFAULT false,
  PRIMARY KEY (chat_id, platform, contest_id)                -- one message per chat and contest (invariant 3)
);

CREATE TABLE deliveries (
  id bigserial PRIMARY KEY, chat_id bigint NOT NULL REFERENCES chats ON DELETE CASCADE,
  kind text NOT NULL CHECK (kind IN ('alert','reminder','standings')),
  event_key text, payload jsonb NOT NULL, state text NOT NULL DEFAULT 'pending'
    CHECK (state IN ('pending','batched','sent','failed')),
  not_before timestamptz NOT NULL DEFAULT now(), attempts integer NOT NULL DEFAULT 0, last_error text,
  UNIQUE (chat_id, event_key)                                -- announced at most once per chat (invariant 6)
);
CREATE INDEX deliveries_due ON deliveries (not_before) WHERE state IN ('pending','batched');

CREATE TABLE source_health (
  source text PRIMARY KEY, last_success_at timestamptz, consecutive_errors integer NOT NULL DEFAULT 0,
  paused boolean NOT NULL DEFAULT false, note text
);
CREATE TABLE deletion_requests (
  id bigserial PRIMARY KEY, subject_type text NOT NULL, subject_id bigint NOT NULL,
  requested_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz
);
CREATE TABLE runtime_state (key text PRIMARY KEY, value jsonb NOT NULL);   -- Telegram update offset, leader info
```

Retention: `participant_results`, `solve_events` and `contests` older than 30 days are purged by a daily job; chats in state `removed` become `deleted`
and their rows are removed after 30 days; `deletion_requests` keep only the subject id and timestamps. No message text, usernames or phone numbers are stored (REQ-N06).
Indexes support the claim queries (due reminders, due deliveries, dirty standings) so claims stay in the low milliseconds.

## Events

Internal domain events are rows and are idempotent (ADR-003). Event kinds: `solve`, `upsolve`, `systest_fail`, `systest_pass`; contest changes: `contest_scheduled`,
`contest_rescheduled`, `contest_cancelled`, `contest_phase_changed`; operational: `source_stale`, `source_recovered`, `reminder_missed`, `delivery_failed`.
Each has a deterministic key. The notifier consumes events through `deliveries`; operator alerts consume the operational ones.

## Authentication / authorization

- Identity: Telegram user and chat ids from updates; no passwords, no tokens from users (REQ-013). The one exception is the opt-in `/import` flow: an API key and secret in a private chat, deleted at once, used for one call, never stored or logged.
- Roles: **member** (read-only commands), **chat admin** (Telegram administrators and the creator; watch list and settings), **owner** (configured Telegram id; operator commands in private chat).
- Admin check: `getChatMember` result cached for 5 minutes per `(chat, user)` and refreshed from `chat_member` updates; every admin-only callback re-checks (REQ-021).
- Rate limits: per user 20 commands per minute and per chat 60 per minute; excess gets one localized notice then silence for the window.
- Webhook mode: secret-token header compared in constant time.

## Security

- Secrets only in the environment (`.env`, git-ignored); the log filter redacts the bot token and any URL token; tooling never prints secrets (ADR-013, REQ-N09).
- Input handling: handles are matched against `^[A-Za-z0-9_.-]{1,24}$` before any request; bulk input is capped at 100 items per message; Markdown or HTML parse mode escapes every user-provided value.
- Least privilege: database roles for migration, application and read-only; container runs as non-root with a read-only root filesystem where possible.
- Dependency hygiene: locked versions via uv, `pip-audit` and image scan in CI, Renovate or Dependabot updates reviewed weekly (ADR-012).
- Data protection: only public identifiers and settings are stored; manual dumps follow the 30-day rule (ADR-014); deletion is immediate in the live database (REQ-018).
- Abuse and flooding: bounded watch lists, bounded payloads, source parsers with size and time limits, and a global kill switch.

## Performance targets

| ID | Target | Requirement |
|---|---|---|
| NFR-001 | During CODING and SYSTEM_TEST, one standings fetch per active contest shortly after the source cache expires (`Expires` header plus a 1 s margin, fallback 60 s, never waiting longer than 120 s), never faster than one Codeforces request per 2 s per instance (amended 2026-11-08 after experiment M1) | REQ-N01, REQ-N07 |
| NFR-002 | Parsing a 7 MB standings body keeps peak memory under 256 MB using streaming and finishes within 3 s | REQ-N01, REQ-N05 |
| NFR-003 | A rendered standings message is at most 3800 characters; longer lists are truncated with a localized "and N more" line | REQ-002 |
| NFR-004 | Edit budget: at most one edit per `(chat, contest)` per 3 s; at most 20 messages per minute per group; at most 25 messages per second overall (configurable, verified against Telegram limits) | REQ-N01, REQ-N03 |
| NFR-005 | Delivery claim latency under 1 s; alert latency from a new verdict in a fetched standings to the Telegram request under 15 s | REQ-N03 |
| NFR-006 | Database: p95 query under 50 ms, pool of 10 connections, claim queries use indexes | REQ-N02, REQ-N05 |
| NFR-007 | Total process memory under 512 MB at 500 chats and 20 000 watched handles | REQ-N05 |
| NFR-008 | Restart recovery under 30 s: state restored from the database, no duplicate sends | REQ-N02 |
| NFR-009 | Metrics exposed: fetch duration, standings age, queue depth, delivery latency, send errors by class, reminders due and sent, source errors, process uptime | REQ-N08 |
| NFR-010 | Alert thresholds to the owner: standings older than 180 s during a contest; a reminder not sent within 60 s of due time; send failure rate above 5 percent over 5 minutes; three consecutive source errors | REQ-019, REQ-020, REQ-N08 |
| NFR-011 | Logs are structured JSON without message text, kept at most 30 days; log level configurable | REQ-N06, REQ-N08 |
| NFR-012 | Quality: strict typing, at least 85 percent line coverage on the domain and notification modules, and contract tests against recorded Codeforces fixtures | REQ-N10 |

Targets NFR-002, NFR-004 and NFR-005 are validated by experiments before the freshness promise in REQ-N01 is published. Experiment M1 (docs/experiments/M1-standings-fetch.md) validated NFR-002 (9743 rows in about 0.19 s adding 2 to 7 MB) and changed NFR-001; the cache behavior during a running contest is confirmed in the first live round.

## Integrations

### Codeforces public API

| Method | Use | Notes |
|---|---|---|
| `contest.list?gym=false` | Contest schedule and phases | Refreshed every 10 minutes and before reminder planning; fields used: id, name, phase, startTimeSeconds, durationSeconds |
| `contest.standings?contestId=<id>` | Standings for active contests | Bare parameter only (ADR-004); streaming parse; keep rows whose handle is watched; fields: rank, points, penalty, problemResults, party.participantType |
| `user.info?handles=a;b;c` | Handle validation and canonical spelling | Batches of up to 200; unknown handle errors are mapped to per-handle results |
| `user.status?handle=<h>&from=1&count=<n>` | Limited fallback for upsolves (R1 optional) | At most a small rotating set; never exceeds the shared request budget |

All calls go through one rate-governed client: minimum spacing 2 s, jitter, timeouts of 15 s, retry with exponential backoff and a circuit breaker per method, `User-Agent` identifying the project and its repository.

### Telegram Bot API

aiogram 3.31 (ADR-001). Features used in R1: message edits, `date_time` entities (REQ-005), inline keyboards, `answerCallbackQuery`, `chat_member` and `my_chat_member` updates. Reserved for R2: guest mode, ephemeral replies, topics.
Parse mode: HTML with escaping. Flood control: respect `retry_after`; token buckets implement the edit budget in NFR-004 (see targets)

### kep.uz (R3)

Behind `SourcePort`, disabled by configuration until written confirmation exists; no code path reaches kep.uz in R1.

## Error handling

| Source | Condition | Action |
|---|---|---|
| Telegram | 429 with `retry_after` | Pause that chat's bucket for the given time, requeue; alert owner if sustained |
| Telegram | 400 message is not modified | Treat as success, update hash |
| Telegram | 400 message to edit not found | Mark `orphaned`, create one replacement message |
| Telegram | 403 bot blocked, kicked, or chat not found | Set chat `removed`, stop its jobs |
| Telegram | 5xx or network error | Retry with backoff up to 5 attempts, then `failed` and a metric |
| Codeforces | Timeout, 5xx, rate limit | Backoff and circuit breaker; standings show data age (REQ-022) |
| Codeforces | FAILED with unknown handle | Report that handle to the admin; never remove other handles |
| Codeforces | Contest not found or not started | Ignore and recheck at the next list refresh |
| Application | Unhandled exception in a handler | Log with a correlation id, reply with a generic localized error, never leak internals |
| Database | Serialization or deadlock | Retry the transaction up to 3 times |

A contract: no code path fails silently; every failure increments a labelled counter and, above thresholds, alerts the owner (NFR-010).

## Observability requirements

- Logs: JSON with fields `ts`, `level`, `event`, `chat_id` (hashed in logs), `contest`, `source`, `correlation_id`, `duration_ms`; no message text.
- Metrics: the set in NFR-009 plus per-method request counters for sources and Telegram.
- Alerts: delivered by direct message to the owner (ADR-009); no external service. Rules in NFR-010; alerts are deduplicated and rate-limited to avoid floods.
- Status: owner-only `/status` summarizes version, uptime, last successful fetch per source, queue depth, and open alerts.

## Traceability to requirements / ADRs

| Requirement | Specification | Decisions |
|---|---|---|
| REQ-001, REQ-002, REQ-003, REQ-022 | `/standings`, standings tables and `deliveries` kind `standings`, NFR-003, NFR-004, error table | ADR-004, ADR-005 |
| REQ-004, REQ-005, REQ-006 | `reminders` table, `contest_*` events, `date_time` entities | ADR-003, ADR-010 |
| REQ-007, REQ-008, REQ-009, REQ-010 | `solve_events`, `deliveries` kind `alert`, tone setting, batching | ADR-003, ADR-005 |
| REQ-011, REQ-012, REQ-013, REQ-021 | `/track` or `/friends`, `watched_handles`, authorization and validation rules | ADR-013 |
| REQ-014, REQ-015, REQ-016 | `chats` settings, Fluent catalogs, `/upcoming`, `contest.list` | ADR-010 |
| REQ-017, REQ-018 | `/privacy`, `/delete`, `deletion_requests`, retention jobs | ADR-011, ADR-014 |
| REQ-019, REQ-020 | `/status`, `/pause`, `source_health`, NFR-010 | ADR-009 |
| REQ-N01, REQ-N03 | NFR-001, NFR-002, NFR-004, NFR-005 | ADR-004, ADR-005 |
| REQ-N02, REQ-N04 | NFR-006, NFR-008, durable jobs, restart behavior | ADR-003, ADR-007 |
| REQ-N05 | NFR-002, NFR-006, NFR-007 | ADR-002 |
| REQ-N06, REQ-N09 | Security section, retention rules, redaction | ADR-013, ADR-014 |
| REQ-N07 | rate-governed client, NFR-001 | ADR-004 |
| REQ-N08, REQ-N10 | NFR-009 to NFR-012, observability section | ADR-009, ADR-012 |

## Assumptions

- Codeforces `contest.standings` keeps returning full anonymous results in the same JSON shape and field names used above.
- Telegram's rate figures in EVID-009 are close to real limits; NFR-004 values are configuration defaults to be verified.
- 30 days is an acceptable retention window for contest data and manual dumps.
- A single instance and a single database satisfy R1 load.

## Open questions

- Exact adaptive interval policy between 15 s and 120 s (phase based, payload size based) after the experiment.
- Whether to store chat ids hashed in logs only or also in metrics labels (current: logs only, metrics aggregate).
- Whether `user.status` fallback is needed in R1 or can wait for R2.

## Approvals

The owner approved this specification on 2026-11-08 (Saidakbar Narzullayev), including the authorization model (member, chat admin, owner), the stored-data set and a
retention window of 30 days for contest results and removed-chat data. Formal records are stored under `.project-alpha/decisions/` and `.project-alpha/approvals/` (approval APR-009).
