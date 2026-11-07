# Development Plan

Scope: release R1 (production-grade), built by one maintainer with AI assistance. Estimates are ideal working days; they are planning figures, not commitments.
Inputs: PRD (REQ identifiers), architecture decisions (ADR identifiers), technical specification (NFR identifiers).

## Milestones

| Milestone | Outcome (exit criterion) | Est. days |
|---|---|---|
| M0 Foundations | Repository skeleton, CI green, container image, database baseline with migrations, config and logging, documentation checks in CI | 3 |
| M1 Contest data | Codeforces client with rate governor, contest list and standings ingestion with streaming parser, recorded fixtures, contract tests, experiment harness | 6 |
| M2 Tracking and settings | Onboarding, language and time zone, Fluent catalogs (uz, ru, en) with completeness test, watch-list management, admin authorization | 5 |
| M3 Standings | Snapshot diff, standings renderer, `/standings`, dirty-flag coalescing, edit-in-place delivery, staleness notice | 6 |
| M4 Reminders | Reminder planner and claimer, `date_time` entities, `/upcoming`, reschedule and cancel handling | 4 |
| M5 Alerts | Event detection, transactional outbox, batching, tone catalogs, system-test alerts, optional upsolve fallback | 6 |
| M6 Privacy and operations | `/privacy`, `/delete`, retention jobs, owner commands, metrics, health, in-app alerts | 5 |
| M7 Hardening | Replay and load experiment, soak test, failure injection, security review, runbooks | 6 |
| M8 Beta and launch | Closed beta on the home PC through at least two real contest rounds, fixes, README and status wording, launch review against stage 10 criteria | 5 |

Total about 46 ideal days. At a part-time pace this is roughly 12 to 16 calendar weeks; the first working vertical slice (M0 to M3) is expected after about 20 ideal days.

## Epics

| Epic | Milestones | Goal |
|---|---|---|
| EPIC-A Platform | M0 | Engineering base and delivery pipeline |
| EPIC-B Data | M1 | Reliable, rate-respecting contest data |
| EPIC-C Chat experience | M2, M3, M4 | Setup, standings, reminders in three languages |
| EPIC-D Alerts | M5 | Solve and system-test alerts with grouping |
| EPIC-E Trust | M6 | Privacy, observability, operator control |
| EPIC-F Readiness | M7, M8 | Proof under load and failure, beta, launch |

## Stories

| Story | Epic | As a... I want... | Requirements |
|---|---|---|---|
| S-A1 | A | maintainer: a reproducible build and quality gates | REQ-N10, REQ-N09 |
| S-B1 | B | operator: data fetched within upstream limits | REQ-N07, REQ-N01 |
| S-B2 | B | developer: replayable recorded contests | REQ-N10 |
| S-C1 | C | admin: onboarding with language and time zone | REQ-014, REQ-015 |
| S-C2 | C | admin: manage the watch list safely | REQ-011, REQ-012, REQ-013, REQ-021 |
| S-C3 | C | member: one live standings message | REQ-001, REQ-002, REQ-003, REQ-022 |
| S-C4 | C | member: reminders and an upcoming list | REQ-004, REQ-005, REQ-006, REQ-016 |
| S-D1 | D | member: alerts when friends solve | REQ-007, REQ-008, REQ-009, REQ-010 |
| S-E1 | E | user: control over my data | REQ-017, REQ-018, REQ-N06 |
| S-E2 | E | operator: see and fix problems fast | REQ-019, REQ-020, REQ-N08 |
| S-F1 | F | owner: evidence that targets hold | REQ-N01, REQ-N02, REQ-N03, REQ-N05 |

## Tasks

M0: `uv` project and lockfile; `pyproject.toml` tooling (ruff, mypy strict, pytest); GitHub Actions (lint, type, test with PostgreSQL, pip-audit, image build); Dockerfile (non-root) and Compose file;
settings via pydantic-settings; JSON logging with redaction; Alembic baseline matching the specification schema; CI step running the documentation validator; repository `CONTRIBUTING` and `SECURITY` notes.
M1: `SourcePort` interface; HTTP client with 2 s spacing, jitter, timeout, backoff and circuit breaker; `contest.list` ingestion and phase mapping; streaming standings parser keeping watched handles;
fixture recorder and three recorded contests (small, medium, largest); contract tests; experiment harness that replays fetch cadence and payload sizes.
M2: onboarding state machine; Fluent catalogs and the completeness test; time-zone selection by confirmed IANA name; watch-list service with `user.info` validation, bulk parsing and limits; admin check cache and `chat_member` handling.
M3: snapshot store and diff; standings renderer with 3800-character cap; `standings_messages` lifecycle; dirty-flag coalescing worker with edit budgets; `/standings`; staleness notice; orphaned-message recovery.
M4: reminder planner on chat join and contest changes; claimer with `FOR UPDATE SKIP LOCKED`; `date_time` entity rendering; `/upcoming`; cancel and move on contest changes; restart tests for no double sends.
M5: event detector with deterministic keys; outbox into `deliveries`; per-chat batching window; tone catalogs (playful default, neutral switch) with a content guard; system-test events; optional `user.status` upsolve fallback.
M6: `/privacy` and `/delete` flows with confirmation; retention jobs (30 days); owner-only `/status`, `/pause`, `/resume`, `/stats`; metrics endpoint; `/healthz` and `/readyz`; alert rules from NFR-010; alert deduplication.
M7: replay of recorded contests at accelerated speed; load test with 500 chats and 20 000 handles; soak test of at least 24 hours; failure injection (Codeforces outage, Telegram 429, database restart, process kill); dependency and image scan; threat review; runbooks.
M8: closed beta with a small circle over at least two rounds; README with status, best-effort wording and known limits; launch review against the production launch criteria in stage 10; tag `v1.0.0`.

## Estimates

Estimates per milestone are in the milestone table; uncertainty is highest in M1 (upstream behavior), M3 (edit budgets) and M7 (experiments). Contingency of 20 percent is held outside the figures; the plan is re-estimated after M1 and after M3.

## Dependencies

- M1 depends on M0. M2 depends on M0 (settings, catalogs) and on `user.info` from M1. M3 depends on M1 and M2. M4 depends on M1 (contest list) and M2. M5 depends on M3 (snapshots) and M2. M6 depends on M2 to M5 for data to delete and observe. M7 depends on M3 to M6. M8 depends on M7.
- External: Codeforces public API availability; Telegram Bot API; the maintainer's home PC for beta; written kep.uz confirmation is not a dependency of R1.

## Critical path

M0, M1, M3, M5, M7, M8. M2, M4 and M6 are scheduled in sequence by a single maintainer but are off the critical path in terms of technical dependency; a slip in M1 or M3 slips the release.

## Risks

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| Codeforces changes or restricts the public API again | Data path breaks | Medium | Contract tests on fixtures, monitoring, graceful degradation, isolation behind `SourcePort` |
| Freshness target cannot be met within request spacing and payload size | REQ-N01 missed | Medium | Early experiment in M1 and M7; adaptive cadence; honest published figures |
| Telegram rate limits stricter than assumed | Slower edits | Medium | Configurable budgets, coalescing, verify limits early (EVID-009) |
| Single maintainer unavailable | Delays | Medium | Documentation framework, automation, small scope |
| Home PC downtime during contests | Missed alerts | High | Best-effort wording, restart policy, owner watches, no promise of availability |
| Scope creep from R2 and R3 ideas | Late R1 | Medium | R2 and R3 backlog is frozen until R1 launch |
| Privacy mistake with personal identifiers | Trust loss | Low | Data minimization tests, retention jobs, policy kept in sync |

## Release plan

1. Internal builds: every merge to `main` builds an image; tags `v0.x` mark milestones M3, M5, M6.
2. Closed beta (M8): home PC, long polling, a small circle of groups, at least two real contest rounds; success means no duplicated or missing reminders, standings freshness measured against the target, and no unhandled errors.
3. Launch review: the production launch criteria in stage 10 are checked and recorded; the owner approves the launch explicitly.
4. Public release `v1.0.0`: announcement in `t.me/cpstands`, README with best-effort availability and privacy statements.
5. After launch: one full contest cycle of stabilization before R2 work starts (private mode, summaries, guest mode).
Rollback: previous image tag is kept; database migrations are forward-only with tested down paths for the last release; manual dumps are taken before migrations.

## Traceability to requirements

| Milestone | Requirements | Decisions |
|---|---|---|
| M0 | REQ-N09, REQ-N10 | ADR-001, ADR-002, ADR-011, ADR-012, ADR-013 |
| M1 | REQ-N01, REQ-N07, REQ-N10 | ADR-004 |
| M2 | REQ-011, REQ-012, REQ-013, REQ-014, REQ-015, REQ-021 | ADR-010, ADR-013 |
| M3 | REQ-001, REQ-002, REQ-003, REQ-022, REQ-N01 | ADR-003, ADR-005 |
| M4 | REQ-004, REQ-005, REQ-006, REQ-016, REQ-N02 | ADR-003, ADR-006 |
| M5 | REQ-007, REQ-008, REQ-009, REQ-010, REQ-N03 | ADR-003, ADR-005 |
| M6 | REQ-017, REQ-018, REQ-019, REQ-020, REQ-N06, REQ-N08 | ADR-009, ADR-014 |
| M7 | REQ-N01, REQ-N02, REQ-N03, REQ-N04, REQ-N05 | ADR-002, ADR-007 |
| M8 | REQ-N04 | ADR-007, ADR-008 |

## Assumptions

- One maintainer works part-time with AI assistance; estimates already assume AI-assisted coding and review.
- The home PC is available during beta contest rounds.
- Real contest rounds occur at least twice a week (observed in the Codeforces schedule), so beta needs about one to two weeks.

## Open questions

- Calendar dates for the beta rounds depend on the contest schedule and on when M7 completes.
- Whether to open-source test fixtures with real handles or replace them with synthetic handles (privacy review in M1).

## Approvals

No scope, budget, staffing or external timeline commitment is made by this plan; dates are estimates. Approval is required only if the owner wants to commit to a public launch date; none is requested now.
