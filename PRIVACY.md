# Privacy

cpstands (the Telegram bot @cpstandsbot) stores the minimum it needs to work.

## What is stored

| Data | Why | How long |
|---|---|---|
| Telegram chat id, chat type | to know where to send messages | until the chat is deleted or removed the bot (then 30 days) |
| language, time zone, tone, reminder and alert switches | your settings | same |
| public Codeforces and kep.uz handles the chat follows | to follow them | same |
| contest results of those handles (problems, times) | to detect solves | 30 days |
| ids of the bot's own live-standings messages | to edit them in place | 30 days after the contest |
| queued and sent reminders and alerts (no message text) | to send each one once | 30 days |

## What is not stored

- the text of any message sent to the bot or to a chat it is in
- names, usernames or phone numbers of Telegram users
- full names, avatars or countries of kep.uz users: the kep.uz tables include them, the bot reads only the public username
- Codeforces passwords or tokens (the bot never asks for them)
- Codeforces API keys and secrets: the only exception is the optional `/import` command, see below

Logs are structured, contain no message text and keep Telegram ids hashed.

## Importing friends with an API key (optional)

`/import` (private chat only) can copy the friends list of your Codeforces account. For that you
send an API key and its secret in one message. The bot deletes that message first, uses the key
for a single signed `user.friends` request, and drops it: the key and secret are held in memory for
the duration of that request, never written to the database, never logged and never repeated back.
If Telegram refuses to delete the message, the bot tells you so; delete it yourself. Afterwards,
remove the key at https://codeforces.com/settings/api. Telegram itself and Codeforces see the key
as they see any message or request; use a key you can revoke. The command is entirely optional:
handles can always be added by name with `/track`.

## Deleting your data

Send `/delete` in the chat (group admins only in groups). After a confirmation, everything
stored about that chat is erased at once. Messages the bot already sent stay in the chat;
delete them yourself. If the bot is removed from a chat, its data is purged after 30 days.

## Contact

Open an issue at https://github.com/menarzullayev/cpstands or write to the maintainer, @menarzullayev.
