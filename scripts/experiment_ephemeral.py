import asyncio

from aiogram import Bot
from aiogram.types import EphemeralMessageParameters

from cpstands.config import get_settings

GROUP = -1004360454680
OWNER = 1808327630


async def main() -> None:
    bot = Bot(get_settings().telegram_bot_token.get_secret_value())
    try:
        m = await bot.send_message(
            GROUP,
            "ephemeral test: only you should see this",
            ephemeral_message_parameters=EphemeralMessageParameters(receiver_user_id=OWNER),
        )
        print("ephemeral OK", m.message_id, m.receiver_user, m.ephemeral_message_id)
    except Exception as exc:
        print("ephemeral FAIL", type(exc).__name__, str(exc)[:300])
    await bot.session.close()


asyncio.run(main())
