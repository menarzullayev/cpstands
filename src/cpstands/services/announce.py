"""The project channel as a reminder-only chat (owner decision 2026-11-08).

At start-up the configured channel is registered as a chat that gets contest reminders at fixed
offsets and nothing else. It is skipped, with a warning, while the bot cannot post there.
"""

from __future__ import annotations

from collections.abc import Sequence

import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cpstands.db import repos

log = structlog.get_logger(__name__)


async def register_channel(
    bot: Bot,
    sessions: async_sessionmaker[AsyncSession],
    channel: str,
    *,
    offsets: Sequence[int],
    language: str,
    time_zone: str,
) -> int | None:
    """Register ``channel`` (e.g. ``@cpstands``); returns its chat id, or None when skipped."""
    try:
        chat = await bot.get_chat(channel)
        me = await bot.get_me()
        member = await bot.get_chat_member(chat.id, me.id)
    except TelegramAPIError as exc:
        log.warning("announce_channel_unreachable", channel=channel, reason=str(exc)[:120])
        return None
    if chat.type != "channel" or not getattr(member, "can_post_messages", False):
        log.warning("announce_channel_cannot_post", channel=channel, status=member.status)
        return None
    async with sessions() as session, session.begin():
        await repos.upsert_chat(session, chat.id, "channel")
        await repos.set_language(session, chat.id, language)
        await repos.set_time_zone(session, chat.id, time_zone)
        await repos.set_reminder_offsets(session, chat.id, offsets)
        await repos.set_alerts_enabled(session, chat.id, False)
        await repos.set_summary_enabled(session, chat.id, False)
        await repos.set_status(session, chat.id, "active")
    log.info("announce_channel_ready", chat_id=chat.id, offsets=list(offsets))
    return chat.id
