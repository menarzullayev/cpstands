# Market Research

## Market definition

Tools that let competitive programmers and their communities follow online contests: schedules and reminders, live standings,
solve and verdict alerts, and rating tracking. The addressable niche is contest communities that already live in Telegram groups;
the wider market (Discord communities, web calendars) is reachable later. Sizing is not measured: the only hard datapoint is a single
99-member community with regular bot use (EVID-007). Codeforces is the main platform; kep.uz is the local platform for Uzbekistan.

This research addresses PROB-001, PROB-002, PROB-003, PROB-004 and PROB-005 from stage 02.

## Competitors

| Competitor | What it does | Strengths | Weaknesses (relevant to our problems) |
|---|---|---|---|
| `@codeforces_live_bot` (incumbent) | Reminders, friends standings, solve and system-test alerts, rating tables on Telegram | Feature breadth, years of use, open source (EVID-001) | Live standings unreliable (PROB-001, EVID-004), alerts dead or silent (PROB-002, EVID-005), secret-based setup and paged settings (PROB-003), English only and ASCII tables (PROB-004), unmaintained (EVID-001) |
| TLE Discord bot | Contest and rating features on Discord | Active community, MIT license (EVID-013) | Not on Telegram; different audience |
| ContestMate | Telegram contest bot, serverless | Active, Telegram native (EVID-013) | Reminder and calendar focus; no live friends standings found |
| clist.by based tools | Multi-platform contest calendar and aggregation | Many platforms | API key and rate limit 10 requests per minute (EVID-013); calendar rather than live standings |
| Codeforces website | Friends standings, official data | Accurate | Not in Telegram; manual refresh |

## Substitutes

Screenshots and manual posts in groups, browser tabs with the friends standings page, calendar subscriptions, and platform email or
push notifications. These are zero-cost, which makes reliability and convenience the only reasons to switch.

## SWOT

| | Helpful | Harmful |
|---|---|---|
| Internal | Strong local access (kep.uz, community), modern Telegram capabilities (EVID-008), clean-slate engineering, open source | Single maintainer, no operations history yet, pre-alpha |
| External | Incumbent is failing (EVID-001, EVID-004, EVID-005), underserved uz/ru audience (PROB-004, PROB-005), growing Bot API (EVID-008) | Codeforces API restrictions (EVID-002, EVID-003, EVID-012), Telegram rate limits (EVID-009), kep.uz terms unwritten (EVID-010, EVID-011), platform rule changes |

## Positioning

For contest communities on Telegram, cpstands is the live standings and reminder bot that **always shows one fresh, readable standings
message per contest, in your language**, built in the open, unlike the incumbent whose live standings and alerts fail silently (PROB-001, PROB-002).
Differentiators: reliability as a stated, measured goal; localization (uz, ru, en); group-first design; no secrets in chats (PROB-003); local
platform support (PROB-005).

## Pricing

Direction: **free and open source** at launch, no paid tier, no Telegram Stars features. Operating cost is expected to be small at early
scale (to be verified in stage 06 and 10). Sustainability options for later: voluntary sponsorship, hosted instances for organizations.
Telegram documents an extra fee tied to Star purchases for threaded bots; a free product is unaffected (EVID-008).

## Demand signals

- A 99-member community uses the incumbent regularly, with repeated `/upcoming` and `/current_standings` calls and about 56 bot standings posts in 2026 (EVID-007).
- Users manually relay bot output into the group and complain about slowness, which indicates unmet reliability needs (EVID-004, EVID-007).
- The incumbent's last commit is a rescue patch, showing that users depend on a tool that the author barely maintains (EVID-001).
- Not measured: demand outside Uzbekistan, kep.uz audience size, willingness to switch bots.

## Regulatory / market risks

| Risk | Impact | Mitigation |
|---|---|---|
| Codeforces tightens public API again (EVID-002, EVID-003) | Live data path breaks | Adaptive polling, caching, graceful degradation, monitoring, fallback sources |
| Codeforces terms of use for automated access are not yet reviewed | Possible restrictions | Review terms before launch; respect the documented rate limit (EVID-012) |
| kep.uz without written terms (EVID-010, EVID-011) | Source may disappear or be disputed | Written confirmation before enabling; module is optional |
| Telegram rate limits (EVID-009) | Slower edits for large groups | Queueing, batching, edit coalescing, per-chat budgets |
| Privacy law (personal identifiers: Telegram IDs, handles) | Compliance and trust | Minimal data, public privacy policy, deletion path, no secrets collected |
| Single-maintainer continuity | Project stalls | Open source, documentation framework, runbooks, automation |

## Evidence register

| ID | Claim (short) | Type | Confidence | Source |
|---|---|---|---|---|
| EVID-001 | Incumbent bot history: 224 commits, 206 in 2019-2020, last fix 2026-05-10 | FACT | high | GitHub repository |
| EVID-002 | Codeforces standings reject extra parameters for non-admin callers | FACT | high | measured API error |
| EVID-003 | Full standings payload is 0.5 MB to 7 MB | FACT | high | measured API responses |
| EVID-004 | 11 of 15 live-standings requests unanswered within 60 s in the maintainer's chat | FACT | high | private chat export, aggregate |
| EVID-005 | Upsolving alerts stopped after 2026-04 | FACT | high | private chat export, aggregate |
| EVID-006 | Solve-alert latency about 1 min median, 11 min p90, 93 min p99 | INFERENCE | medium | estimated from timestamps |
| EVID-007 | A 99-member community uses the incumbent regularly | FACT | high | community history, aggregate |
| EVID-008 | Bot API 10.3 capabilities (date_time, rich messages, ephemeral, drafts, guest mode) | FACT | high | Telegram changelog |
| EVID-009 | Telegram rate limits: about 1 message per second per chat, 20 per minute per group, 30 per second overall | FACT | medium | Telegram FAQ via research agent |
| EVID-010 | kep.uz exposes unauthenticated JSON endpoints without published documentation | FACT | medium | measured by research agent |
| EVID-011 | kep.uz owner verbally approved cooperation | ASSUMPTION | low | owner statement relayed |
| EVID-012 | Codeforces API: about 1 request per 2 s; signed requests use SHA-512 | FACT | medium | API help via web archive |
| EVID-013 | Alternatives: TLE (Discord), ContestMate (Telegram), clist.by (10 requests per minute) | FACT | medium | public repositories and docs |
| EVID-014 | Library support for Bot API 10.3: aiogram 3.31.0, telego 1.12.0, TelegramBots 10.3.0 yes; python-telegram-bot 22.8 older; telegraf stale since 2024 (added 2026-11-08 during stage 06) | FACT | high | GitHub releases |
| EVID-015 | Telegram Serverless: JavaScript V8 handlers triggered by updates and Mini App calls; SQLite without foreign keys; 30 MB outbound response cap; no documented scheduler, limits or pricing (added 2026-11-08 during stage 06) | FACT | high | Telegram Serverless documentation |
| EVID-016 | Healthchecks.io Hobbyist plan: 0 USD per month, 20 jobs; free Business plan for open-source projects (added 2026-11-08 during stage 07) | FACT | high | vendor pricing page |
| EVID-017 | Cloudflare R2 free tier 10 GB-month with free egress; Backblaze B2 first 10 GB free (added 2026-11-08 during stage 07) | FACT | high | vendor pricing pages |

## Assumptions

- Demand seen in one community generalizes to similar communities worldwide (not measured).
- Users switch bots if reliability and language support are clearly better.
- The free, open-source model is sustainable at early scale.

## Open questions

- Terms of use of Codeforces for automated access and of kep.uz for data reuse.
- Real distribution: how many Telegram contest communities exist per language, and how do they discover bots?
- Whether the Telegram rate-limit figures in EVID-009 still hold for Bot API 10.3 and per-bot limits (verify before load design).

## Decisions / approvals

Positioning as the reliable, localized, group-first live standings bot and pricing as free and open source at launch (no paid features, no
Telegram Stars) were approved on 2026-11-08 by Saidakbar Narzullayev. Formal records are stored under `.project-alpha/decisions/` and
`.project-alpha/approvals/` (approval APR-004).
