# Idea Selection

## Candidate ideas

| # | Idea | Short description |
|---|---|---|
| 1 | **cpstands** (new bot) | A new multi-source contest tracker for Telegram: live friends standings in one edited message, reliable reminders, solve alerts, groups and private chats, uz/ru/en. Codeforces first, kep.uz next. |
| 2 | Fork and repair the incumbent bot | Take over `TobxD/codeforces_live_bot` (Apache-2.0), patch the Codeforces API change, keep its architecture. |
| 3 | kep.uz-only notifier | A small bot that only follows kep.uz contests. |
| 4 | Web dashboard without Telegram | A website with live standings and calendars; no bot. |
| 5 | Contest reminder bot only | Calendar and reminders for Codeforces, no standings, no alerts. |

## Evaluation criteria

Problem severity, differentiation, technical feasibility, distribution, founder advantage, regulatory and privacy risk, and
quality of available evidence. Scores run from 1 (weak) to 5 (strong); the sum is a decision aid, not a verdict.

## Evidence

All figures are measured on 2026-11-08 and are registered as formal evidence records (see stage 03 for the register).

- The incumbent bot has 224 commits, 206 of them in 2019-2020, and its last commit (2026-05-10) is an emergency fix for a
  Codeforces API change.
- Codeforces now rejects every extra parameter on `contest.standings` for non-admin callers, so filtering friends on the
  server is impossible; a full response is 0.5-7 MB.
- In the maintainer's own chat with the incumbent bot (aggregate counts), 11 of 15 live-standings requests got no reply within
  60 seconds, and upsolving notifications stopped after 2026-04.
- A 99-member Uzbek competitive-programming community uses the incumbent bot regularly, so demand exists.
- Telegram Bot API 10.3 provides tools the incumbent does not use: `date_time` entities, rich messages with tables,
  ephemeral messages, message drafts and guest mode.
- kep.uz exposes unauthenticated JSON endpoints and its owner has verbally agreed to cooperation.

## Candidate comparison

| Criterion | 1 cpstands | 2 Fork incumbent | 3 kep.uz only | 4 Web only | 5 Reminders only |
|---|---|---|---|---|---|
| Problem severity | 5 | 4 | 3 | 3 | 2 |
| Differentiation | 4 | 1 | 3 | 2 | 1 |
| Feasibility | 4 | 3 | 5 | 3 | 5 |
| Distribution (Telegram communities) | 5 | 4 | 3 | 1 | 4 |
| Founder advantage (kep.uz access, Telegram tooling) | 5 | 2 | 5 | 2 | 3 |
| Regulatory / privacy risk (higher is safer) | 4 | 3 | 4 | 4 | 5 |
| Evidence quality | 4 | 4 | 3 | 2 | 3 |
| **Total (max 35)** | **31** | 21 | 26 | 17 | 23 |

## Leading candidate

**Idea 1, cpstands.** It addresses the measured failures of the incumbent (live standings unreliable, upsolving alerts dead,
unmaintained code, English only), uses the strongest founder advantages, and contains ideas 3 and 5 as later slices.

## Risks

- Codeforces can change its public API again; the design must tolerate extra restrictions and large payloads.
- kep.uz terms are not written down; the integration depends on a personal agreement until it is formalized.
- Telegram rate limits cap how fast many live standings can be edited.
- Running a public service requires privacy compliance and operational discipline from day one.
- A single maintainer is a continuity risk.

## Assumptions

- The kep.uz owner's verbal agreement will be confirmed in writing before production use of that source.
- Friends-standings demand outside Uzbekistan is comparable to the observed community demand (not measured).
- Hosting and Telegram costs stay small at early scale.

## Rejected / parked ideas

- Idea 2 (fork) rejected: inherits the single-process threaded design, plaintext secrets and polling, and the broken standings
  design; the repair effort is close to a rewrite and gives no differentiation.
- Idea 3 (kep.uz only) parked: becomes the second source module of idea 1.
- Idea 4 (web only) rejected: users act inside Telegram groups; a web dashboard may return later as a Mini App.
- Idea 5 (reminders only) parked: becomes the first release slice of idea 1.

## Recommendation

Select idea 1 and enter stage 01 Vision with these constraints: production-grade engineering from the first release,
public repository, no personal data in public documents, Codeforces first and kep.uz after written confirmation.

## Human decision

Approved on 2026-11-08 by Saidakbar Narzullayev (project owner) in the working session: idea 1, cpstands, enters stage 01 Vision.
The formal decision and approval records are stored under `.project-alpha/decisions/` and `.project-alpha/approvals/` (approval APR-001).
