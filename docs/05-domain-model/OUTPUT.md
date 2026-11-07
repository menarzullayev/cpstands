# Domain Model

Scope: release R1 (REQ-001 to REQ-022 and REQ-N01 to REQ-N10). R2 and R3 concepts are marked as extensions.

## Entities

| ID | Entity | Identity | Purpose |
|---|---|---|---|
| DOM-001 | Chat | Telegram chat id | A private chat, group or supergroup served by the bot; owns language, time zone, tone, status and settings. |
| DOM-002 | WatchList | Chat id (one per chat) | The set of platform handles whose results the chat follows. |
| DOM-003 | Contest | (platform, external contest id) | A contest on a source platform with phase, schedule and problems. |
| DOM-004 | ParticipantResult | (contest, handle) | A watched handle's rank, points, penalty and per-problem results in a contest. |
| DOM-005 | SolveEvent | (contest, handle, problem, kind, verdict time) | An immutable fact that something notable happened to a handle. |
| DOM-006 | Reminder | (chat, contest, offset) | A scheduled message announcing a contest start. |
| DOM-007 | StandingsMessage | (chat, contest) | The single Telegram message that shows a chat's standings for a contest. |
| DOM-008 | AlertDelivery | (chat, event) | The record that an event was, or must be, announced to a chat; supports grouping. |
| DOM-009 | SourceHealth | source id | Freshness, error counters and pause state of a data source. |
| DOM-010 | DeletionRequest | request id | A subject's request to delete stored data and its completion state. |

## Value objects

| ID | Value object | Rules |
|---|---|---|
| DOM-011 | PlatformHandle | Pair (platform, handle). Compared case-insensitively; stored with its canonical spelling; the platform decides validity. |
| DOM-012 | ProblemResult | Status (not tried, rejected, accepted, provisional, failed after tests), attempts before acceptance, time from start. |
| DOM-013 | ChatLanguage | One of uz, ru, en. |
| DOM-014 | TimeZone | A valid IANA zone name, confirmed by an admin. |
| DOM-015 | ReminderOffset | One of 24 hours, 1 hour, 10 minutes before start (the enabled set is per chat). |
| DOM-016 | ContestPhase | BEFORE, CODING, PENDING_SYSTEM_TEST, SYSTEM_TEST, FINISHED, CANCELLED. |
| DOM-017 | Tone | PLAYFUL (default) or NEUTRAL. |

## Aggregates

| ID | Aggregate | Root | Members | Transaction boundary |
|---|---|---|---|---|
| DOM-018 | ChatAggregate | Chat | WatchList, settings, enabled reminder offsets | All changes to one chat's settings and watch list commit together. |
| DOM-019 | ContestAggregate | Contest | problems, ParticipantResult snapshot for watched handles | One source refresh of one contest commits as one version. |
| DOM-020 | DeliveryAggregate | AlertDelivery or Reminder or StandingsMessage | its own state | One delivery attempt updates one record; sends are idempotent. |

## Relationships

- A Chat has exactly one WatchList; a WatchList has zero to many PlatformHandle values (limit 100 by default).
- A Contest has many ParticipantResult rows, but only for handles that some active chat watches.
- A ParticipantResult produces zero to many SolveEvent facts when its state changes.
- A SolveEvent leads to one AlertDelivery per chat whose WatchList contains the handle and whose alerts are enabled.
- A Chat has at most one StandingsMessage per Contest and up to three Reminder records per Contest.
- A SourceHealth record exists per source and gates reads of its contests.

## Invariants

1. A Chat has exactly one language and one time zone once set up; setup is incomplete until both are confirmed.
2. A WatchList never contains duplicate PlatformHandle values and never exceeds the chat's limit.
3. A (chat, contest) pair has at most one StandingsMessage; a send that would create a second one is turned into an edit or rejected.
4. A (chat, contest, offset) triple has at most one sent Reminder; restarts and retries never send it twice.
5. A SolveEvent is immutable and has a deterministic key, so processing the same source data twice creates no new event.
6. An accepted problem is announced at most once per chat; a later system-test failure creates a distinct event that corrects it.
7. No record stores a secret, token or message text of members; stored identifiers are limited to Telegram ids, public handles and settings.
8. A DeletionRequest, once completed, leaves no record keyed to the subject outside the documented backup retention window.

## Business rules

- Only chat admins (Telegram role) change settings and the WatchList; members can read standings and use read-only commands (REQ-021).
- Invalid handles in bulk input are reported individually; valid ones are still added (REQ-011).
- Standings contain watched handles only, ordered by the source's rank (REQ-001, REQ-002).
- During SYSTEM_TEST the standings are provisional and marked as such (REQ-003).
- Rescheduled or cancelled contests update or withdraw pending reminders (REQ-006).
- Alerts that occur within a short window for one chat are grouped (REQ-008); grouping never delays a message beyond the latency target (REQ-N03).
- Upsolve events exist only when the source exposes unofficial results (REQ-010).
- When a source is stale, the standings show data age and a notice (REQ-022).
- Tone selects the text variant of alerts, never their content or timing (REQ-009).
- The bot never requests secrets (REQ-013) and honors deletion within the target time (REQ-018).

## Lifecycle rules

Contest phase (as reported by the source): BEFORE to CODING to PENDING_SYSTEM_TEST to SYSTEM_TEST to FINISHED; BEFORE or CODING to CANCELLED.
Backward moves other than reschedule within BEFORE are treated as source anomalies and logged.

Reminder: SCHEDULED to SENT; SCHEDULED to CANCELLED (contest cancelled) or SKIPPED (offset already past when the chat joined); no other transitions.

StandingsMessage: NONE to ACTIVE (first send) to FROZEN (contest FINISHED and final results rendered); ACTIVE to ORPHANED if Telegram reports the message gone, then re-created once.

AlertDelivery: PENDING to BATCHED to SENT; PENDING or BATCHED to FAILED after bounded retries; FAILED is visible to operators.

Chat: ONBOARDING to ACTIVE; ACTIVE to PAUSED (operator or admin); ACTIVE or PAUSED to REMOVED when the bot is removed; REMOVED to DELETED after the retention window.

## Domain boundaries

- **Contest Data** (DOM-003, DOM-004, DOM-009): fetches and normalizes contests from sources; knows nothing about Telegram.
- **Tracking** (DOM-001, DOM-002, DOM-011 to DOM-014, DOM-017): chat configuration and watch lists.
- **Notification** (DOM-005 to DOM-008, DOM-015, DOM-020): decides what to say to which chat and tracks delivery.
- **Privacy** (DOM-010): deletion and data inventory across the other contexts.
- Sources are pluggable behind a single contest-data contract so kep.uz (R3) can be added without touching Tracking or Notification.

## Traceability to requirements

| Requirement | Domain elements |
|---|---|
| REQ-001, REQ-002, REQ-003 | DOM-003, DOM-004, DOM-007, DOM-016, invariant 3 |
| REQ-004, REQ-005, REQ-006 | DOM-006, DOM-015, invariant 4, reminder lifecycle |
| REQ-007, REQ-008, REQ-009, REQ-010 | DOM-005, DOM-008, DOM-017, invariants 5 and 6 |
| REQ-011, REQ-012, REQ-013 | DOM-002, DOM-011, invariant 2, invariant 7 |
| REQ-014, REQ-015 | DOM-013, DOM-014, invariant 1 |
| REQ-016 | DOM-003 |
| REQ-017, REQ-018 | DOM-010, invariants 7 and 8 |
| REQ-019, REQ-020, REQ-022 | DOM-009, chat PAUSED state |
| REQ-021 | business rule on admin role |
| REQ-N01 to REQ-N05 | DOM-019 refresh version, DOM-020 idempotent sends |
| REQ-N06 | DOM-010, invariants 7 and 8 |
| REQ-N07 to REQ-N10 | Contest Data boundary (rate budget), observability of DOM-009 and DOM-020 |

## Assumptions

- Telegram exposes chat administrator roles reliably through the Bot API.
- Sources provide stable contest identifiers and per-problem results for watched handles.
- Handles can be renamed on a source; a rename is handled as removal of an unknown handle and re-adding by an admin in R1.

## Open questions

- How should handle renames be detected and migrated automatically (post-R1)?
- Should a user-level subscription (R2 private mode) be a separate aggregate or a Chat of type private?
- How long are backups retained (REQ-018 retention window)? To be set in the technical specification.

## Decisions / approvals

The domain boundaries above are reversible design choices made by the agent for R1; they carry no irreversible migration impact before launch. Formal
decisions on storage and technology are made in stage 07. The owner may challenge any boundary at the next gate.
