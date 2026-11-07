# Experiment M2-UX: modern Telegram features measured on the real bot

Date: 2026-11-08. Scripts: `scripts/experiment_ux.py`, `scripts/experiment_rich.py`,
`scripts/experiment_ephemeral.py`, `scripts/gen_emoji_ids.py`. Bot API 10.3 (changelog of 2026-08-24), aiogram 3.31.0.

| Feature | Result | Decision |
|---|---|---|
| Custom emoji in message text (`tg-emoji`, Bot API 9.4) | Delivered; the owner account has Telegram Premium (`is_premium=True`). 28 of the 40 palette emoji exist in the `RestrictedEmoji` set; the rest stay normal emoji. | Catalogs keep plain emoji; `I18n` rewrites them to custom emoji when `CUSTOM_EMOJI=true`. |
| Button color `style` (`primary`, `success`, `danger`) | Accepted by the API. | Used: the current language/zone is `primary`. |
| Button icon `icon_custom_emoji_id` | Accepted by the API, but the docs require extra Fragment usernames on the bot; the rendered result was not seen. | Off by default (`BUTTON_ICONS=false`): the emoji is part of the button text instead. |
| Message effect (`message_effect_id`) | Accepted in a private chat. | Party popper on setup completion, private playful chats only. |
| Rich Message with a markdown table (`sendRichMessage`, 10.1) | Accepted by the API; client rendering is to be judged by eye. | Not used yet; candidate for the standings table in M3. |
| Ephemeral message (`ephemeral_message_parameters`, 10.2) | Fails with `BOT_NOT_ADMIN` when the bot is a plain member; works when the bot is an admin of a supergroup. | Helper replies in groups go through `Whisper`: ephemeral when allowed, normal message otherwise, no retry for 10 minutes after a refusal. |

Not verifiable without a logged-in Telegram client: how icons, effects and rich tables look on screen.
