# Architecture Decision Records

Index of decisions for release R1. Each record follows the template: decision ID, status, context, options, selection, rationale, consequences, evidence,
reversibility and approval. Statuses: ACCEPTED (approved), PROPOSED (pending approval). High-impact or irreversible decisions require the owner's approval;
routine reversible decisions are agent-approved and listed for transparency.

| ADR | Title | Status | Approval |
|---|---|---|---|
| ADR-001 | Python 3.13 and aiogram 3.31 | ACCEPTED | owner (DEC-006) |
| ADR-002 | Modular monolith, one image, role flag | ACCEPTED | owner (DEC-006) |
| ADR-003 | PostgreSQL as store and queue, no Redis | ACCEPTED | owner (DEC-006) |
| ADR-004 | Shared full-standings fetch with local filtering | ACCEPTED | owner (DEC-006) |
| ADR-005 | Edit in place with latest-state-wins coalescing | ACCEPTED | owner (DEC-006) |
| ADR-006 | Long polling on the home PC, webhook on a dedicated host | ACCEPTED | owner (DEC-006) |
| ADR-007 | Hosting phases: home PC first, best-effort availability | ACCEPTED | owner (DEC-007) |
| ADR-008 | Telegram Serverless not used as the backend | ACCEPTED | owner (DEC-006) |
| ADR-009 | Observability: logs, metrics, in-app owner alerts; no external heartbeat | ACCEPTED | owner (DEC-008) |
| ADR-010 | Localization with Fluent catalogs and a completeness test | ACCEPTED | agent (routine, reversible) |
| ADR-011 | SQLAlchemy 2 async with Alembic migrations | ACCEPTED | agent (routine, reversible) |
| ADR-012 | Tooling and CI: uv, ruff, mypy, pytest, pip-audit, GitHub Actions | ACCEPTED | agent (routine, reversible) |
| ADR-013 | Configuration and secrets handling | ACCEPTED | agent (routine, reversible) |
| ADR-014 | Backups: manual by the owner, no automated off-site copy | ACCEPTED | owner (DEC-008) |

---

## ADR-001 Python 3.13 and aiogram 3.31

- **Decision ID:** ADR-001 (linked decision record DEC-006)
- **Status:** ACCEPTED
- **Context / problem:** Choose the language and Telegram library for a long-lived async bot that must use the newest Bot API features (REQ-005, REQ-N08, REQ-N10).
- **Options considered:** Python with aiogram; Python with python-telegram-bot; TypeScript with grammY; Go with telego; Java TelegramBots.
- **Selected solution:** Python 3.13 with aiogram 3.31 and httpx.
- **Rationale:** aiogram supports Bot API 10.3 since 2026-08-25, one day after the API; python-telegram-bot 22.8 is older; grammY support for 10.3 is unconfirmed; Go and Java are viable but fit the maintainer less.
- **Consequences:** Python runtime performance is sufficient for the load (Telegram budgets, not CPU, are the limit); we depend on aiogram's release pace; typing is enforced with mypy.
- **Evidence:** EVID-014 (library support) and EVID-008 (new Bot API features)
- **Reversibility:** Medium: the domain core is framework-free, so only the `bot` adapter would be replaced.
- **Approval:** owner, 2026-11-08.

## ADR-002 Modular monolith, one image, role flag

- **Decision ID:** ADR-002 (DEC-006)
- **Status:** ACCEPTED
- **Context / problem:** One maintainer must run bot, ingest, scheduler and notifier with minimal operational surface (REQ-N04, REQ-N10).
- **Options considered:** microservices; one process with all roles; one image with a role flag running selected roles per process.
- **Selected solution:** One codebase and image; a `ROLES` setting selects which async tasks run; default runs all.
- **Rationale:** Fewest moving parts now; the role flag allows splitting without a rewrite (REQ-N05 path).
- **Consequences:** Module boundaries must be enforced by tests (import rules) to keep the split possible; shared database is the integration point.
- **Evidence:** domain boundaries (DOM-018, DOM-019, DOM-020).
- **Reversibility:** High.
- **Approval:** owner, 2026-11-08.

## ADR-003 PostgreSQL as store and queue, no Redis

- **Decision ID:** ADR-003 (DEC-006)
- **Status:** ACCEPTED
- **Context / problem:** Need durable state, job queues, leader election and idempotency (REQ-004, REQ-007, REQ-N02).
- **Options considered:** PostgreSQL only; PostgreSQL plus Redis; SQLite; managed queue.
- **Selected solution:** PostgreSQL 16; jobs and deliveries as rows claimed with `FOR UPDATE SKIP LOCKED`; advisory locks for leader election; transactional outbox.
- **Rationale:** One stateful component to run, back up and monitor on a single home machine; transactional guarantees between events and deliveries; load is small.
- **Consequences:** Queue throughput is bounded by the database (ample for R1); polling latency of the claimer is tuned (sub-second); a later switch to a broker needs an adapter.
- **Evidence:** EVID-009 (message rates), REQ-N05 planning figures.
- **Reversibility:** Medium.
- **Approval:** owner, 2026-11-08.

## ADR-004 Shared full-standings fetch with local filtering

- **Decision ID:** ADR-004 (DEC-006)
- **Status:** ACCEPTED
- **Context / problem:** Codeforces forbids handle filters on standings for non-admin callers, and full responses are 0.5 to 7 MB (REQ-N01, REQ-N07).
- **Options considered:** per-handle `user.status` polling; one shared full-standings fetch per contest; scraping HTML pages; authenticated requests.
- **Selected solution:** One shared anonymous fetch per active contest with an adaptive interval, a streaming parser keeping only watched handles, and per-handle `user.status` only as a limited fallback for upsolves.
- **Rationale:** Per-handle polling cannot meet freshness within one request per two seconds; scraping is fragile; authenticated requests are rejected for the same parameters.
- **Consequences:** Bandwidth cost per active contest; need caching and backoff; the interval must be tuned by experiment before the freshness target is promised.
- **Evidence:** EVID-002, EVID-003 and EVID-012 (API restriction, payload size, rate limit)
- **Reversibility:** High (adapter behind `SourcePort`).
- **Approval:** owner, 2026-11-08.

## ADR-005 Edit in place with latest-state-wins coalescing

- **Decision ID:** ADR-005 (DEC-006)
- **Status:** ACCEPTED
- **Context / problem:** Standings must stay one readable message while respecting Telegram limits (REQ-001, REQ-N01).
- **Options considered:** a new message per update; edit in place without coalescing; edit in place with coalescing per `(chat, contest)`.
- **Selected solution:** Mark `(chat, contest)` dirty; a delivery worker renders the latest state and edits once per allowed interval; older pending renders are discarded.
- **Rationale:** Matches the product principle and the per-chat and per-group budgets.
- **Consequences:** Intermediate states may be skipped by design; message-gone errors trigger one re-create.
- **Evidence:** EVID-009 (Telegram rate limits)
- **Reversibility:** High.
- **Approval:** owner, 2026-11-08.

## ADR-006 Long polling on the home PC, webhook on a dedicated host

- **Decision ID:** ADR-006 (DEC-006)
- **Status:** ACCEPTED
- **Context / problem:** A home machine has no public inbound endpoint; a dedicated host can expose a webhook (REQ-N04, REQ-N09).
- **Options considered:** long polling; webhook through a tunnel; webhook on a public host.
- **Selected solution:** Long polling by default; webhook mode (secret header, reverse proxy) available by configuration for a dedicated host.
- **Rationale:** No inbound exposure on the home PC; both modes use the same handlers.
- **Consequences:** Two intake paths to test; polling must handle restarts without losing updates (offset persisted).
- **Evidence:** Bot API documentation (getUpdates and setWebhook cannot be used together).
- **Reversibility:** High.
- **Approval:** owner, 2026-11-08.

## ADR-007 Hosting phases: home PC first, best-effort availability

- **Decision ID:** ADR-007 (linked decision record DEC-007)
- **Status:** ACCEPTED
- **Context / problem:** Choose where production runs and what availability to promise (REQ-N04).
- **Options considered:** home PC; VPS; managed PaaS; Telegram Serverless.
- **Selected solution:** The maintainer's home PC for the beta and the first public release; no formal availability target; availability is measured and published; a dedicated host later.
- **Rationale:** Owner decision; no extra cost now; an honest commitment matches the host's real reliability.
- **Consequences:** Outages from power, network or reboots are possible; mitigations: Docker restart policy, sleep disabled, auto-start, recommended UPS, external heartbeat, owner alerts (ADR-009), restore rehearsal (ADR-014); users are told in the README and status messages.
- **Evidence:** EVID-015 (Serverless unsuitable), PRD amendment of REQ-N04 (availability wording)
- **Reversibility:** High (documented migration to a dedicated host).
- **Approval:** owner, 2026-11-08.

## ADR-008 Telegram Serverless not used as the backend

- **Decision ID:** ADR-008 (DEC-006)
- **Status:** ACCEPTED
- **Context / problem:** BotFather offers Serverless hosting; could it run the product (REQ-004, REQ-007)?
- **Options considered:** Serverless as the whole backend; a hybrid with a worker; no Serverless.
- **Selected solution:** Not used for R1; revisit for a Mini App backend.
- **Rationale:** The documentation shows handlers triggered only by Telegram updates and Mini App calls, JavaScript only, no scheduler, no stated CPU or duration limits, no pricing; scheduled polling and reminders cannot run there, and a hybrid would split state and the update stream.
- **Consequences:** We operate our own host; we may reconsider if Telegram adds timers.
- **Evidence:** EVID-015 (Serverless documentation review)
- **Reversibility:** High.
- **Approval:** owner, 2026-11-08.

## ADR-009 Observability: logs, metrics, in-app owner alerts; no external heartbeat

- **Decision ID:** ADR-009 (linked decision record DEC-008)
- **Status:** ACCEPTED
- **Context / problem:** Make silence a bug (REQ-019, REQ-020, REQ-N08): detect missed reminders, stale data and failed sends; decide whether to detect total host failure with an external service.
- **Options considered:** (a) structured logs, a metrics endpoint, owner alerts by Telegram direct message, plus an external heartbeat service such as Healthchecks.io (free tier verified in EVID-016); (b) the same with UptimeRobot; (c) in-app observability only, with the owner watching the machine.
- **Selected solution:** (c). Structured JSON logs without message content; a Prometheus-format metrics endpoint for a local dashboard; in-app alerts delivered to the owner by Telegram direct message for logic failures (stale data, missed reminders, failing sends, source errors); an owner-only status command. No external vendor is used.
- **Rationale:** The owner uses the host machine daily and checks it personally; the project is a hobby with low stakes; avoiding a vendor keeps the system simple and free of external dependencies.
- **Consequences:** Total host or network failure produces no automatic alert; the owner accepts this. If the project later adopts a dedicated host or a formal availability target, an external heartbeat (EVID-016) becomes the first addition. The published availability is derived from the bot's own records, which cannot observe full-host outages, so published figures must say so.
- **Evidence:** EVID-016 (alternative considered, not adopted) and REQ-N08 (observability requirement)
- **Reversibility:** High.
- **Approval:** owner, 2026-11-08.

## ADR-010 Localization with Fluent catalogs and a completeness test

- **Decision ID:** ADR-010
- **Status:** ACCEPTED (agent-approved: routine, reversible)
- **Context / problem:** uz, ru and en must stay equivalent, including plurals and dates (REQ-014, REQ-015).
- **Options considered:** gettext; Fluent (`.ftl`); a custom YAML catalog.
- **Selected solution:** Fluent catalogs, one file set per language, with a CI test that fails when a message ID is missing in any language or arguments differ.
- **Rationale:** Fluent handles Russian plural forms and message arguments well and is supported by aiogram integrations; the test enforces REQ-015 (language completeness)
- **Consequences:** Translators edit `.ftl` files; dates use `date_time` entities instead of formatted strings where possible (REQ-005).
- **Evidence:** EVID-008 (`date_time` entity).
- **Reversibility:** High.
- **Approval:** agent.

## ADR-011 SQLAlchemy 2 async with Alembic migrations

- **Decision ID:** ADR-011
- **Status:** ACCEPTED (agent-approved: routine, reversible)
- **Context / problem:** Persist the domain model with safe schema evolution (REQ-018, REQ-N10).
- **Options considered:** raw SQL with a driver; SQLAlchemy 2 with Alembic; another ORM.
- **Selected solution:** SQLAlchemy 2 (async, asyncpg) for access and Alembic for versioned migrations run as an explicit step; queue queries use explicit SQL where needed.
- **Rationale:** Mature migration tooling, typing, testability with real PostgreSQL in tests.
- **Consequences:** ORM discipline needed for queue claims; migrations are reviewed like code.
- **Evidence:** none required.
- **Reversibility:** Medium.
- **Approval:** agent.

## ADR-012 Tooling and CI: uv, ruff, mypy, pytest, pip-audit, GitHub Actions

- **Decision ID:** ADR-012
- **Status:** ACCEPTED (agent-approved: routine, reversible)
- **Context / problem:** One maintainer needs fast, strict, automated quality gates (REQ-N09, REQ-N10).
- **Options considered:** pip with requirements; Poetry; uv; different linters.
- **Selected solution:** uv for environments and a lockfile; ruff for lint and format; mypy in strict mode; pytest with a real PostgreSQL service in CI; pip-audit for vulnerabilities; GitHub Actions for build, test, image build; releases by tags.
- **Rationale:** Speed, reproducibility, one config in `pyproject.toml`.
- **Consequences:** CI must pass before merge; the repository's documentation checks (`project-alpha validate`) run in CI as well.
- **Evidence:** none required.
- **Reversibility:** High.
- **Approval:** agent.

## ADR-013 Configuration and secrets handling

- **Decision ID:** ADR-013
- **Status:** ACCEPTED (agent-approved: routine, reversible)
- **Context / problem:** Keep secrets out of the repository and logs (REQ-013, REQ-N09).
- **Options considered:** environment variables with a git-ignored `.env`; a secret manager; encrypted files in the repository.
- **Selected solution:** `pydantic-settings` reads environment variables; `.env` is git-ignored with a committed `.env.example`; secrets are redacted from logs; the token is never printed by tooling (already practiced in this project).
- **Rationale:** Simple and sufficient on a single host; compatible with Docker and future secret stores.
- **Consequences:** Rotation is manual (documented in the runbook); backups of `.env` must be stored separately and encrypted.
- **Evidence:** none required.
- **Reversibility:** High.
- **Approval:** agent.

## ADR-014 Backups: manual by the owner, no automated off-site copy

- **Decision ID:** ADR-014 (linked decision record DEC-008)
- **Status:** ACCEPTED
- **Context / problem:** The home PC can fail; decide how much protection the data needs, and keep deletion requests honest (REQ-018, REQ-N06).
- **Options considered:** (a) nightly encrypted dump to object storage such as Cloudflare R2 (free tier in EVID-017); (b) the same to Backblaze B2; (c) no automated backups, manual dumps by the owner when wanted.
- **Selected solution:** (c). A documented one-command dump script is provided; the owner runs it occasionally and stores the file himself. There is no scheduled backup and no off-site copy.
- **Rationale:** The stored data (chat settings, public handles, delivery state) is easy to recreate and the owner accepts losing it; no vendor, key or cost to manage.
- **Consequences:** After a disk failure the bot restarts empty and chats must be set up again; this is acceptable to the owner. Privacy obligation: any manual dump is personal data of chats, so it must be kept encrypted or in a protected place, deleted within 30 days of creation, and must not be restored after a chat's deletion request (the runbook states this). The privacy policy's 30-day statement stays true only if that rule is followed.
- **Evidence:** EVID-017 (alternatives considered, not adopted).
- **Reversibility:** High.
- **Approval:** owner, 2026-11-08.

---

## Traceability to requirements

| Requirement | Decisions |
|---|---|
| REQ-001, REQ-N01 | ADR-004, ADR-005 |
| REQ-004, REQ-N02 | ADR-003, ADR-006 |
| REQ-005, REQ-014, REQ-015 | ADR-010 |
| REQ-007, REQ-N03 | ADR-003, ADR-004, ADR-005 |
| REQ-013, REQ-N06, REQ-N09 | ADR-013, ADR-014 |
| REQ-018 | ADR-011, ADR-014 (manual dumps subject to the 30-day rule) |
| REQ-019, REQ-020, REQ-N08 | ADR-009 |
| REQ-N04, REQ-N05 | ADR-002, ADR-007, ADR-008 |
| REQ-N07 | ADR-004 |
| REQ-N10 | ADR-001, ADR-011, ADR-012 |

## Evidence

EVID-008, EVID-009, EVID-012, EVID-014, EVID-015 and the measured API behavior in EVID-002 and EVID-003 (see stage 03 register)

## Reversibility summary

Every decision above is reversible at moderate cost before launch. The costliest to reverse are ADR-001 (language) and ADR-003 (queue in the database). ADR-009 and ADR-014 are accepted risks: a full-host outage is not alerted and data may be lost.

## Approval

ADR-001 to ADR-008 carry the owner's approval from the architecture gate (DEC-006, DEC-007). At this gate the owner approved the whole set on 2026-11-08 and decided ADR-009 (no external heartbeat, owner watches the machine) and ADR-014 (no automated backups, manual dumps when wanted) as recorded in DEC-008. ADR-010 to ADR-013 are routine and reversible, agent-approved and confirmed by the owner. Formal records are stored under `.project-alpha/decisions/` and `.project-alpha/approvals/` (approval APR-008).
