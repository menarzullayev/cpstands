# Vision

## Mission

Give every competitive programmer and every programming community a **reliable, live view of the contests that matter to
them**, inside the chat where they already talk, without setup friction and in their own language.

## Vision

In three years cpstands is the default Telegram companion for contests: a group admin adds the bot once, and from then on
the group sees one live standings message per round, gets reminders that always arrive, and celebrates every solve, for
Codeforces and local platforms such as kep.uz, in Uzbek, Russian and English. It is open source, transparent about the data
it keeps, and boring to operate.

## Long-term goals

Problems this product exists to solve (details and evidence in stage 02):

- PROB-001: Live friends standings in existing tools are slow or missing exactly during contests.
- PROB-002: Alerts stop silently (upsolving, reminders), so users stop trusting the tool.
- PROB-003: Setup is cumbersome and unsafe (Codeforces API key and secret typed into a chat, 20 pages of per-friend settings).
- PROB-004: Output is English-only and rendered as ASCII tables that break on phones.
- PROB-005: Local platforms such as kep.uz are not covered at all.

Measurable strategic targets (to be validated and refined in stage 02 and 04):

- METRIC-001: Live standings freshness: p95 age of the data in the edited standings message at most 60 seconds during a contest.
- METRIC-002: Reminder reliability: at least 99.5 percent of reminders delivered within 60 seconds of their scheduled time.
- METRIC-003: Solve alert latency: p95 at most 120 seconds from the submission verdict to the Telegram message.
- METRIC-004: Availability inside contest windows is measured and published every month. Amended 2026-11-08 by owner decision: while the bot runs on a single home machine there is no formal target (best effort); a target of at least 99.9 percent per month applies once a dedicated always-on host is used.
- METRIC-005: Adoption: 50 active chats within 3 months of launch and 500 within 12 months (planning target, not a measured fact).
- METRIC-006: Privacy: zero personal-data incidents; deletion of a chat's data completed within 24 hours of request.

## Product principles

1. **Reliability over features.** A smaller feature set that always works beats a large one that sometimes does not.
2. **One message per contest.** Standings are one message edited in place; chats are never flooded.
3. **Silence is a bug.** If the bot cannot deliver something it says so, and the operator is alerted.
4. **Privacy by design.** Public handles only; no secrets typed into chats; data kept minimal and deletable.
5. **Local-first language.** Uzbek, Russian and English are equal citizens, including time zones and date formats.
6. **Open and observable.** Open source, documented decisions, public status of known limitations, metrics from day one.
7. **Respect upstream platforms.** Obey rate limits, cache aggressively, prefer official APIs, and get written permission for local platforms.

## Strategic assumptions

- Telegram groups remain the main place where contest communities talk.
- Codeforces keeps a public read API; its restrictions may tighten again, so the design must degrade gracefully.
- The owner of kep.uz will confirm cooperation in writing before that source goes live (currently a verbal agreement).
- Demand outside Uzbekistan resembles the observed community demand (not yet measured).
- Hosting and Telegram costs stay low at early scale.

## Evidence

Registered as formal evidence records (stage 03 holds the register). Summary: the incumbent bot is unmaintained and
its standings design is broken by a Codeforces API change; its live-standings command failed in most requests during contests;
a 99-member community uses it regularly; Bot API 10.3 offers capabilities it does not use; kep.uz exposes public data.

## Open questions

- Which platforms after Codeforces and kep.uz (AtCoder, CodeChef, LeetCode, clist.by)?
- Should the bot ever offer paid features? If so, what are the consequences of Telegram Star fees and payment rules?
- What is the long-term governance: single maintainer, or a small team and an organization account?
- Is a Mini App dashboard part of the 12-month vision or later?

## Decisions / approvals

Strategic direction (mission, vision, scope: private chats and groups, global audience, uz/ru/en, Codeforces first and kep.uz
after written confirmation) was approved on 2026-11-08 by Saidakbar Narzullayev (project owner). The METRIC-001 to METRIC-006
targets were accepted as planning targets, to be refined with evidence in stages 02 and 04.
Formal records are stored under `.project-alpha/decisions/` and `.project-alpha/approvals/` (approvals APR-002; earlier: APR-001).
