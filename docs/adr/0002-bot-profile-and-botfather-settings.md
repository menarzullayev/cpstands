# ADR 0002: Bot profile and BotFather settings

- Status: accepted (2026-11-08)
- Source of truth for API-managed fields: `config/bot_profile.json`, applied by `scripts/apply_bot_profile.py`
  (idempotent; Telegram rate-limits `setMyName` to roughly one change per 24 h).

## Decisions

| # | Topic | Decision |
|---|---|---|
| 1 | Name | Brand + description, localized: `cpstands · Contest standings` / ru / uz |
| 2 | Short description | Value proposition in uz/ru/en (Codeforces + kep.uz) |
| 3 | Description | Feature list + "Press Start" in uz/ru/en |
| 4 | Commands | Scoped by chat type (private, group, group admins) and localized; `/rank` is ephemeral in groups |
| 5 | Avatar | Podium (`assets/avatar.svg`, rendered to `assets/avatar.jpg`), also used for the channel |
| 6 | BotFather defaults | Keep: privacy mode ON, inline OFF until an inline handler exists, secretary mode OFF, no group admin rights |
| 7 | Privacy policy | `PRIVACY.md` (draft, pre-alpha); linked in BotFather on 2026-11-08 |
| 8 | Description picture | Banner "Brand + podium" 640x360 (`assets/description_banner.svg` + `.jpg`), uploaded through BotFather 2026-11-08 |

## Settings only in the @BotFather Mini App (done 2026-11-08, verified with `getMe`)

| Setting | Value | `getMe` field |
|---|---|---|
| Threaded Mode (topics in private chats, streaming replies) | ON | `has_topics_enabled=true` |
| Users may create new threads | ON (default, revisit if per-contest topics get messy) | `allows_users_to_create_topics=true` |
| Guest Chat Mode (`@cpstandsbot` mentions in chats it has not joined) | ON | `supports_guest_queries=true` |
| Bot management, guard, secretary, bot-to-bot | OFF | unchanged |

Note: Threaded Mode is documented as "subject to an additional fee for Telegram Star purchases"; we sell nothing,
so no cost is expected. Re-check the Mini App text before ever adding paid features.

## Open

Main Mini App, menu button (currently the default command list).
