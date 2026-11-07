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

## Not available through the chat menu of @BotFather

Topics in private chats, guest mode, bot-to-bot messaging, and managing other bots are configured in the
@BotFather Mini App (graphical). They are tracked as manual steps for the bot owner.

## Open

Main Mini App, menu button (currently the default command list).
