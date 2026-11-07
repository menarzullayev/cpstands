import asyncio

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputRichMessage

from cpstands.config import get_settings

MD = """# Round 1234

| # | Handle | Solved | Penalty |
|---|--------|:------:|--------:|
| 1 | tourist | 6 | 312 |
| 2 | Petr | 5 | 401 |

> Last update 19:52 Asia/Tashkent
"""


async def main() -> None:
    bot = Bot(get_settings().telegram_bot_token.get_secret_value())
    try:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Refresh", callback_data="x:y", style="primary")]
            ]
        )
        m = await bot.send_rich_message(1808327630, InputRichMessage(markdown=MD), reply_markup=kb)
        print("rich OK", m.message_id)
    except Exception as exc:
        print("rich FAIL", type(exc).__name__, str(exc)[:300])
    await bot.session.close()


asyncio.run(main())
