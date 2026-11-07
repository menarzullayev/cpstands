# Privacy

cpstands (the Telegram bot @cpstandsbot) stores the minimum it needs to work.

## What is stored

| Data | Why | How long |
|---|---|---|
| Telegram chat id, chat type | to know where to send messages | until the chat is deleted or removed the bot (then 30 days) |
| language, time zone, tone, reminder and alert switches | your settings | same |
| public Codeforces handles the chat follows | to follow them | same |
| contest results of those handles (problems, times) | to detect solves | 30 days |
| ids of the bot's own live-standings messages | to edit them in place | 30 days after the contest |
| queued and sent reminders and alerts (no message text) | to send each one once | 30 days |

## What is not stored

- the text of any message sent to the bot or to a chat it is in
- names, usernames or phone numbers of Telegram users
- Codeforces passwords, API keys, secrets or tokens (the bot never asks for them)

Logs are structured, contain no message text and keep Telegram ids hashed.

## Deleting your data

Send `/delete` in the chat (group admins only in groups). After a confirmation, everything
stored about that chat is erased at once. Messages the bot already sent stay in the chat;
delete them yourself. If the bot is removed from a chat, its data is purged after 30 days.

## Contact

Open an issue at https://github.com/menarzullayev/cpstands or write to the maintainer, @menarzullayev.
