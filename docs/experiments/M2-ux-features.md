# Experiment M2-UX: modern Telegram features measured on the real bot

Date: 2026-11-08. Scripts: `scripts/experiment_ux.py`, `scripts/experiment_rich.py`,
`scripts/experiment_ephemeral.py`, `scripts/gen_emoji_ids.py`. Bot API 10.3 (changelog of 2026-08-24), aiogram 3.31.0.

| Feature | Result | Decision |
|---|---|---|
| Custom emoji in message text (`tg-emoji`, Bot API 9.4) | Delivered; the owner account has Telegram Premium (`is_premium=True`). 28 of the 40 palette emoji exist in the `RestrictedEmoji` set; the rest stay normal emoji. | Catalogs keep plain emoji; `I18n` rewrites them to custom emoji when `CUSTOM_EMOJI=true`. |
| Button color `style` (`primary`, `success`, `danger`) | Accepted by the API. | Used: the current language/zone is `primary`. |
| Button icon `icon_custom_emoji_id` | Accepted by the API and seen rendering as a button icon in Telegram Desktop 7.4 (docs mention Fragment usernames, but no error was raised). | On by default (`BUTTON_ICONS=true`); set `false` to put the emoji in the button text instead. |
| Message effect (`message_effect_id`) | Accepted in a private chat. | Party popper on setup completion, private playful chats only. |
| Rich Message with a markdown table (`sendRichMessage`, 10.1) | Rendered as a real bordered table in Telegram Desktop 7.4. Hard limits found: at most 20 table columns (`RICH_MESSAGE_TABLE_COLS_TOO_MANY` above that); 120 rows x 20 columns (20 KB) was accepted. HTML input (`InputRichMessage.html`) is accepted and escapes `&`, `<`, `|`, `*` correctly. | Used for `/standings`: 4 fixed columns + 16 problems per column page, 25 rows per page. |
| Ephemeral message (`ephemeral_message_parameters`, 10.2) | Fails with `BOT_NOT_ADMIN` when the bot is a plain member; works when the bot is an admin of a supergroup. | Helper replies in groups go through `Whisper`: ephemeral when allowed, normal message otherwise, no retry for 10 minutes after a refusal. |

Checked on screen in Telegram Desktop 7.4.1 via computer use: custom emoji, button colors, button icon, rich tables.
