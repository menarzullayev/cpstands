# Privacy Policy

**cpstands** (`@cpstandsbot`, `t.me/cpstands`) · Last updated: 2026-11-08

> Status: **pre-alpha.** The bot does not process any user data yet. This document describes how it will behave
> once it launches, so you can review it in advance. It will be updated before the first public release.

## Who is responsible

The bot is operated by Saidakbar Narzullayev. Contact: open an issue at
<https://github.com/menarzullayev/cpstands/issues> or message the channel admin via `t.me/cpstands`.

## What the bot stores

| Data | Why |
|---|---|
| Telegram user ID, chat ID and chat type | to reply to you and to keep your settings |
| Interface language and time zone | to show texts and contest times correctly |
| Notification preferences (reminders, alerts) | to send only what you asked for |
| Codeforces / kep.uz handles that you or your group choose to track | to build standings and alerts |
| IDs of the bot's own messages in a chat | to edit live standings in place instead of sending new messages |

The bot reads public contest data (ratings, standings, submission results) from the Codeforces and kep.uz APIs
for the handles above. It does not copy private data from those sites.

## What the bot does not collect

- Phone numbers, location, contacts, or profile photos.
- Codeforces API keys or secrets. The bot never asks for them.
- The content of group conversations. Telegram privacy mode stays on, so the bot only receives commands,
  replies to its own messages, and mentions.

## How long data is kept

- Until you delete it with `/delete` (planned) or remove the bot from a chat.
- Data of chats where the bot was removed is deleted within 30 days.
- Server logs contain no message text and are kept for at most 30 days.
- The maintainer takes backups only by hand and rarely; any such backup is stored protected and deleted within 30 days, and is never restored for a chat that asked for deletion.

## Sharing

Your data is never sold. It is not shared with third parties, except the services needed to run the bot:
Telegram (message delivery) and the contest sites above (queried by public handle). The bot runs on the maintainer's own computer; no third-party
hosting provider receives your data, and no analytics or advertising service is used.

## Your rights

You can ask what is stored about you, ask for correction, or ask for deletion at any time using the contact above.

## Changes

Material changes will be announced in `t.me/cpstands` and recorded in this file's git history.
