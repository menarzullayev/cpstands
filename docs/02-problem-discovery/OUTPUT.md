# Problem Discovery

## Target users

| Segment | Who | What they do today |
|---|---|---|
| **S1 Community member (primary, recommended)** | A participant of a contest community group on Telegram (school, university, city or country group, 50-500 members) | Joins rounds, then checks in the group how friends did; asks the existing bot for `/upcoming` and `/current_standings` |
| S2 Community admin | Moderator or organizer of such a group | Wants one standings post per round, no spam, simple setup for the whole group |
| S3 Private follower | A participant who tracks a personal friends list in a private chat | Uses the incumbent bot with a Codeforces API key to import friends |
| S4 Local-platform user | A kep.uz participant (Uzbekistan) | Has no Telegram tracking at all for local contests |

Primary segment is chosen in the decisions section below (it requires owner approval).

## Problems / pain points

| ID | Problem | Who feels it |
|---|---|---|
| PROB-001 | Live friends standings are slow or missing exactly during contests. In the maintainer's chat with the incumbent bot, 11 of 15 live-standings requests got no reply within 60 seconds. | S1, S2, S3 |
| PROB-002 | Alerts stop silently. Upsolving notifications ended after 2026-04; reminders enabled by default were never observed in 18 months of chat history. Users cannot tell a quiet contest from a broken bot. | S1, S3 |
| PROB-003 | Setup is cumbersome and unsafe: friends come from a Codeforces API key and secret typed into the chat, and per-friend settings span about 20 pages for 199 friends. | S3, S2 |
| PROB-004 | Output is English only and standings are ASCII tables that wrap badly on phones and truncate long handles. | S1, S2, S4 |
| PROB-005 | Local platforms are not covered: kep.uz contests have no Telegram tracking. | S4, S1 (Uzbekistan) |

## Jobs to be done / use cases

- When a round starts, I want to see how my friends and group are doing without leaving the chat, so that I can react in real time.
- When a round is about to start, I want a reminder in my own time zone, so that I do not miss it.
- When a friend solves a hard problem, I want to know soon and in context (contest, problem, time), so that I can cheer or learn.
- As an admin, I want to add the bot once and get one clean standings message per round, so that the group stays readable.
- As a user, I want to control my data and never type secrets into a chat, so that I trust the bot.
- As a kep.uz participant, I want the same experience for local contests, so that I use one tool for both.

## Current alternatives

- The incumbent bot `@codeforces_live_bot`: broad feature set, but unreliable live standings, dead upsolving alerts, English only, unmaintained code.
- Codeforces website and its friends standings page: accurate but requires leaving Telegram and refreshing manually.
- Group members posting screenshots and manual updates (observed daily in the community group).
- Other tools: a Discord bot (TLE), a serverless Telegram bot (ContestMate), calendar sites such as clist.by; none combines live friends standings in Telegram groups with local languages.

## Problem severity

| Problem | Severity | Frequency | Basis |
|---|---|---|---|
| PROB-001 | High | every contest | measured failure rate of the live command |
| PROB-002 | High | continuous | measured: upsolving alerts stopped, reminders never observed |
| PROB-003 | Medium | at setup | observed in the setup flow of the incumbent |
| PROB-004 | Medium | every standings view | observed output format; language gap is certain, phone impact is inferred |
| PROB-005 | Medium (High locally) | every kep.uz contest | absence of any tool; size of the local audience is not measured |

## Success metrics

Success is measured with the strategic targets from stage 01, applied per problem:

- PROB-001 is solved when METRIC-001 (standings freshness) and METRIC-004 (availability in contest windows) are met.
- PROB-002 is solved when METRIC-002 (reminder reliability) and METRIC-003 (alert latency) are met.
- PROB-003 is solved when no user must paste secrets and group setup takes under two minutes (to be specified as a requirement in stage 04).
- PROB-004 is solved when standings render legibly in uz, ru and en on phones (acceptance tests in stage 04).
- PROB-005 is solved when kep.uz contests are supported after written confirmation.
- The whole product is judged by METRIC-005 (adoption) and METRIC-006 (privacy).

## Evidence

All figures are registered as evidence records in stage 03. Observed: failure rates, notification counts and latency of the incumbent bot
(aggregate chat data), repository activity, Codeforces API restrictions, and community usage. Hypothesis only: demand outside
Uzbekistan, the size of the kep.uz audience, and phone-rendering impact.

## Assumptions

- The community pattern seen in one 99-member group repeats in other contest communities.
- Group admins prefer one edited message to repeated posts.
- Users accept a public-handle-only model (no import of private friend lists).
- The kep.uz owner confirms cooperation in writing.

## Open questions

- How large is the audience of English-speaking communities that would adopt the bot (to be sampled in stage 03)?
- Do users want friends lists (personal) or watch lists (per group) as the main concept?
- Which events matter most to groups: solves, system-test failures, rating changes, new contests?

## Decisions / approvals

The primary target segment is **S1 community member in groups**, with S2 admins as the control surface and S3 private following as a
later slice (the owner's earlier requirement to serve both private and community use is kept; S1 is first in priority).
Approved on 2026-11-08 by Saidakbar Narzullayev. Formal records are stored under `.project-alpha/decisions/` and `.project-alpha/approvals/` (approval APR-003).
