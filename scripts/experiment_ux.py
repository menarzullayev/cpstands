"""Experiment M2-UX: which modern Telegram features really work for this bot (run by hand)."""

import asyncio
import json
import sys

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, MessageEntity

from cpstands.config import get_settings

OWNER = 1808327630
WANT = "🏆🎉✅⚠️⏰🌍🗣👥📊⚙️🔔❌👋🤖🚀🔥⭐📅👑🌐🕐🧭➕➖📋💬ℹ️🎯🥇🥈🥉🇺🇿🇷🇺🇬🇧⚡🔁🔒"


async def main(step: str) -> None:
    bot = Bot(get_settings().telegram_bot_token.get_secret_value())
    sticker_set = await bot.get_sticker_set("RestrictedEmoji")
    by_emoji: dict[str, str] = {}
    for s in sticker_set.stickers:
        if s.emoji and s.custom_emoji_id and s.emoji not in by_emoji:
            by_emoji[s.emoji] = s.custom_emoji_id
    if step == "coverage":
        have = {e: by_emoji.get(e) for e in dict.fromkeys(WANT) if e.strip()}
        print(json.dumps(have, ensure_ascii=True))
    if step == "emoji":
        text = "🏆 cpstands: custom emoji 🎉 ✅ ⏰"
        entities = []
        for i, ch in enumerate(text):
            if ch in by_emoji:
                entities.append(
                    MessageEntity(
                        type="custom_emoji",
                        offset=len(text[:i].encode("utf-16-le")) // 2,
                        length=len(ch.encode("utf-16-le")) // 2,
                        custom_emoji_id=by_emoji[ch],
                    )
                )
        m = await bot.send_message(OWNER, text, entities=entities)
        print("sent", m.message_id, len(entities))
    if step == "buttons":
        for label, kwargs in {
            "style only": {"style": "success"},
            "style+icon": {"style": "primary", "icon_custom_emoji_id": by_emoji["🏆"]},
        }.items():
            try:
                kb = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(text=label, callback_data="x:y", **kwargs),
                            InlineKeyboardButton(
                                text="danger", callback_data="x:z", style="danger"
                            ),
                        ]
                    ]
                )
                m = await bot.send_message(OWNER, f"buttons: {label}", reply_markup=kb)
                print(label, "OK", m.message_id)
            except Exception as exc:
                print(label, "FAIL", exc)
    if step == "effect":
        try:
            m = await bot.send_message(
                OWNER, "effect test", message_effect_id="5046509860389126442"
            )
            print("effect OK", m.message_id)
        except Exception as exc:
            print("effect FAIL", exc)
    await bot.session.close()


asyncio.run(main(sys.argv[1]))
