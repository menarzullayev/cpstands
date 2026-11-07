# Product Requirements Document

## Product scope

cpstands is a Telegram bot (`@cpstandsbot`) that gives contest communities live friends standings, reliable reminders and solve alerts for
Codeforces (and later kep.uz), in Uzbek, Russian and English. It targets production quality from the first public release
(release R1); there is no throwaway MVP. Scope is split into releases:

| Release | Features | Condition |
|---|---|---|
| **R1 (first public, production-grade)** | FEAT-001, FEAT-002, FEAT-003, FEAT-004, FEAT-005, FEAT-006, FEAT-011, FEAT-012 | all quality gates and launch criteria of stage 10 |
| R2 | FEAT-007, FEAT-008, FEAT-009 | R1 stable for one contest cycle |
| R3 | FEAT-010 (kep.uz) | written confirmation from the kep.uz owner |

Out of scope for all releases above: paid features, Telegram Stars, importing private friend lists with Codeforces API keys, moderation
tools for groups, other platforms (AtCoder, CodeChef, LeetCode), a Mini App dashboard.

## Target users

Primary: **S1 community member in groups**. Control surface: **S2 group admin**. Later: **S3 private follower** (R2, FEAT-008) and
**S4 kep.uz participant** (R3, FEAT-010). Personas and evidence: stage 02 and stage 03.

## Features

| ID | Feature | Solves | Release |
|---|---|---|---|
| FEAT-001 | Group live standings: one message per contest per chat, edited in place, listing the chat's watch list | PROB-001, PROB-004 | R1 |
| FEAT-002 | Contest reminders (24 h, 1 h, 10 min before start, configurable), with the start time shown in each reader's own time zone | PROB-002, PROB-004 | R1 |
| FEAT-003 | Solve, upsolve and system-test alerts for watched handles, grouped, with contest and problem context | PROB-002 | R1 |
| FEAT-004 | Watch-list management by public handle: add, remove, list, bulk input, validation, per-chat limits; no API keys | PROB-003 | R1 |
| FEAT-005 | Localization: uz, ru, en per chat; time zone per chat; localized dates and numbers | PROB-004 | R1 |
| FEAT-006 | Upcoming contests list with local start times and registration links | PROB-002 | R1 |
| FEAT-007 | Post-contest summary with rating changes and notable events | PROB-002 | R2 |
| FEAT-008 | Private mode: personal watch list, one thread per contest using threaded mode | PROB-003 | R2 |
| FEAT-009 | Guest mode and ephemeral answers, e.g. `/rank` visible only to the asker | PROB-001 | R2 |
| FEAT-010 | kep.uz as a second contest source | PROB-005 | R3 |
| FEAT-011 | Privacy and data control: policy link, `/privacy`, `/delete` for a chat or a user | PROB-003 | R1 |
| FEAT-012 | Operations surface: health, status, owner alerts, kill switches, rate-limit visibility | PROB-001, PROB-002 | R1 |

## User stories

- As a community member, I see one live standings message for the running contest in my group (FEAT-001).
- As a community member, I get a reminder before each contest in my own time zone and language (FEAT-002, FEAT-005).
- As a community member, I am told when a watched friend solves a problem, with contest and problem named (FEAT-003).
- As a group admin, I add the bot, pick a language and time zone, and paste handles in one message (FEAT-004, FEAT-005).
- As a group admin, I can turn alerts or standings off and delete the group's data (FEAT-011).
- As an operator, I am alerted when data fetches, reminders or edits fail (FEAT-012).

## Functional requirements

| ID | Requirement | Feature |
|---|---|---|
| REQ-001 | For each running contest and each chat with a non-empty watch list, the bot keeps exactly one standings message and edits it in place. | FEAT-001 |
| REQ-002 | Standings show rank, handle, per-problem result and penalty marks for watched handles only, in a layout that fits a phone screen in uz, ru and en. | FEAT-001 |
| REQ-003 | While a contest is in its testing phase the standings message is labelled as provisional and updated when final results are published. | FEAT-001 |
| REQ-004 | Reminders are scheduled per contest and per chat at the enabled offsets and are sent at most once per offset. | FEAT-002 |
| REQ-005 | Reminder text uses Telegram `date_time` entities so each reader sees the start in their own zone. | FEAT-002 |
| REQ-006 | A reminder for a rescheduled or cancelled contest is corrected or withdrawn. | FEAT-002 |
| REQ-007 | When a watched handle gets a new accepted problem, an alert is sent once, naming contest, problem, and time. | FEAT-003 |
| REQ-008 | Alerts arriving close together are grouped into one message per chat. | FEAT-003 |
| REQ-009 | System-test failures of a watched handle produce an alert in a playful tone by default; texts must not insult the named person, and each chat can switch to a neutral tone in settings. | FEAT-003 |
| REQ-010 | Upsolved problems are reported separately from in-contest solves, when the data source permits it. | FEAT-003 |
| REQ-011 | Admins add and remove handles by public handle, singly or in bulk; invalid handles are reported individually without rejecting valid ones. | FEAT-004 |
| REQ-012 | A chat's watch list is limited (default 100 handles) with a clear message at the limit. | FEAT-004 |
| REQ-013 | The bot never asks for Codeforces API keys, secrets, passwords or tokens. | FEAT-004 |
| REQ-014 | Each chat has a language (uz, ru, en) and a time zone; defaults come from the chat's first admin setup, never from guesses without confirmation. | FEAT-005 |
| REQ-015 | All user-facing texts exist in uz, ru and en with the same meaning; a missing translation fails the build. | FEAT-005 |
| REQ-016 | `/upcoming` lists the next contests with local start times and links. | FEAT-006 |
| REQ-017 | `/privacy` shows what is stored and links to the privacy policy. | FEAT-011 |
| REQ-018 | `/delete` removes a chat's stored data (admin) or a user's data (user) and confirms completion within the target time. | FEAT-011 |
| REQ-019 | The operator can see health, queue depth, source freshness and failure counts, and can pause a source or a chat. | FEAT-012 |
| REQ-020 | The operator is alerted on missed reminders, stale data, failing sends and source errors. | FEAT-012 |
| REQ-021 | Only chat admins can change watch lists and settings in groups; any member can read standings. | FEAT-001, FEAT-004 |
| REQ-022 | If a data source is down or restricted, standings show the age of the data and a notice instead of failing silently. | FEAT-001 |

## Non-functional requirements

Non-functional requirements use REQ identifiers prefixed N; measurable targets reuse the stage 01 strategic targets.

| ID | Requirement | Target |
|---|---|---|
| REQ-N01 | Standings freshness during a contest | p95 data age at most 60 s (METRIC-001) |
| REQ-N02 | Reminder reliability | at least 99.5 percent within 60 s of schedule (METRIC-002) |
| REQ-N03 | Solve alert latency | p95 at most 120 s from verdict to message (METRIC-003) |
| REQ-N04 | Availability inside contest windows | measured and published monthly; no formal target on the interim home host (best effort); at least 99.9 percent per month on a dedicated always-on host (METRIC-004, amended 2026-11-08) |
| REQ-N05 | Scalability | 500 active chats and 20 000 watched handles without redesign (METRIC-005 growth) |
| REQ-N06 | Privacy | data minimization, deletion within 24 h of request, no secrets collected (METRIC-006) |
| REQ-N07 | Upstream respect | stay within documented Codeforces and Telegram limits; never exceed one Codeforces request per 2 s per instance |
| REQ-N08 | Observability | structured logs without message content, metrics, traces, dashboards, and alert rules for every REQ-N0x target |
| REQ-N09 | Security | secrets only in environment or secret store; dependency scanning; least privilege; no secrets in logs |
| REQ-N10 | Maintainability | automated tests for every requirement, CI gates, reproducible builds, documented runbooks |

## Priorities

Must (R1): REQ-001 to REQ-022 except those tagged R2 or R3, and REQ-N01 to REQ-N10.
Should (R2): FEAT-007, FEAT-008, FEAT-009. Could (R3): FEAT-010.
Within R1, REQ-001, REQ-004, REQ-007, REQ-N01, REQ-N02 and REQ-N04 define the product's core promise and are tested first.

## Constraints

- Codeforces public API: bare `contestId` for standings, large payloads, about one request per two seconds (EVID-002, EVID-003, EVID-012).
- Telegram limits on edits and messages per chat and overall (EVID-009) and 4096 characters per message.
- kep.uz data only after written confirmation (EVID-010, EVID-011).
- One maintainer; AI-assisted development; public repository; low operating budget.

## Acceptance criteria

Each requirement is testable. Examples (the full set is derived in the technical specification):

- REQ-001: in a test chat with a running replayed contest, exactly one bot message exists for that contest after 10 updates, and its text changes.
- REQ-004: with a scheduled contest in 25 hours, one 24-hour reminder is sent within 60 seconds of T-24 h and none is repeated after a restart.
- REQ-007: replaying a contest log produces one alert per accepted problem per watched handle, in the right order.
- REQ-011: sending `a,b,bad!,c` adds three handles and reports one invalid, in one reply.
- REQ-015: removing any translation key in one language fails the language-completeness test.
- REQ-018: after `/delete`, no record keyed by that chat remains in the database or backups older than the retention window.
- REQ-N01: a load test with the largest observed standings payload keeps p95 data age under 60 s.
- REQ-N04: a game-day test with a forced source outage shows degraded notices and alerts, and recovery without manual repair.

## Requirement traceability

| Problem | Features | Requirements |
|---|---|---|
| PROB-001 | FEAT-001, FEAT-009, FEAT-012 | REQ-001, REQ-002, REQ-003, REQ-021, REQ-022, REQ-N01, REQ-N04, REQ-N05 |
| PROB-002 | FEAT-002, FEAT-003, FEAT-006, FEAT-007, FEAT-012 | REQ-004, REQ-005, REQ-006, REQ-007, REQ-008, REQ-009, REQ-010, REQ-016, REQ-019, REQ-020, REQ-N02, REQ-N03, REQ-N08 |
| PROB-003 | FEAT-004, FEAT-008, FEAT-011 | REQ-011, REQ-012, REQ-013, REQ-017, REQ-018, REQ-N06, REQ-N09 |
| PROB-004 | FEAT-001, FEAT-002, FEAT-005 | REQ-002, REQ-005, REQ-014, REQ-015 |
| PROB-005 | FEAT-010 | R3 requirements are written when the kep.uz confirmation exists; the source is isolated behind a flag |

REQ-N07 and REQ-N10 trace to all problems as enabling constraints.

## Evidence / assumptions

Evidence: EVID-001 to EVID-013 (stage 03). Assumptions: community demand generalizes (EVID-007), kep.uz cooperation will be written down
(EVID-011), Telegram limits still hold (EVID-009).

## Open questions

- Is the default 100-handle watch-list limit right for communities of 500 members?
- Which Codeforces data path meets REQ-N01 given the standings restrictions (decided by an ADR in stage 07)?
- Should reminders also be offered as a channel broadcast on `t.me/cpstands`?

## Decisions / approvals

Release scope (R1 group-first with reminders and alerts; R2 summaries, private mode, guest mode; R3 kep.uz), target users, exclusions (no paid
features, no API-key import) and the non-functional targets were approved on 2026-11-08 by Saidakbar Narzullayev. The owner chose a playful alert tone
by default (REQ-009), with a per-chat switch to a neutral tone and a content guard against insulting named people. Formal records are stored under
`.project-alpha/decisions/` and `.project-alpha/approvals/` (approval APR-005).
