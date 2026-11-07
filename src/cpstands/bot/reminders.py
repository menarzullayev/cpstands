"""Reminder messages: rendering with ``tg-time`` and the sender that obeys Telegram's limits."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import structlog
from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
)
from aiogram.types import InlineKeyboardMarkup, LinkPreviewOptions
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cpstands.bot import keyboards
from cpstands.db import repos
from cpstands.i18n import I18n, Markup
from cpstands.services import timezone as tzs
from cpstands.services.contests import PLATFORM

log = structlog.get_logger(__name__)

MAX_ATTEMPTS = 3
CONTEST_URL = "https://codeforces.com/contest/{id}"
REGISTER_URL = "https://codeforces.com/contestRegistration/{id}"


def tg_time(moment: datetime, zone: str | None) -> Markup:
    """The start time as two ``tg-time`` entities: exact (in the reader's zone) and relative.

    Telegram shows each reader the time in their own zone; the text inside is the fallback.
    """
    zone_name = zone if zone and tzs.is_valid_zone(zone) else "UTC"
    fallback = moment.astimezone(ZoneInfo(zone_name)).strftime("%d.%m %H:%M")
    unix = int(moment.timestamp())
    return Markup(
        f'<tg-time unix="{unix}" format="wDt">{fallback}</tg-time>'
        f' · <tg-time unix="{unix}" format="r">{fallback}</tg-time>'
    )


def duration_text(seconds: int | None) -> str:
    if not seconds:
        return "-"
    hours, minutes = divmod(seconds // 60, 60)
    return f"{hours}:{minutes:02d}"


def render_reminder(
    i18n: I18n,
    chat: repos.ChatRecord,
    contest: repos.ContestRow,
    offset_min: int,
) -> tuple[str, InlineKeyboardMarkup | None]:
    """Text and buttons of one reminder, "moved" notice or "cancelled" notice."""
    say = i18n.bound(chat.language, chat.tone)
    name = contest.name
    if offset_min == repos.NOTICE_CANCELLED:
        return say("reminder-cancelled", name=name), None
    start = tg_time(contest.starts_at, chat.time_zone) if contest.starts_at else Markup("-")
    if offset_min == repos.NOTICE_MOVED:
        text = say("reminder-moved", name=name, start=start)
    else:
        left = {1440: "day", 60: "hour"}.get(offset_min, "minutes")
        text = say("reminder", name=name, start=start, left=left, minutes=offset_min)
    return text, reminder_keyboard(say, contest.contest_id)


def reminder_keyboard(say: object, contest_id: int, *, icons: bool = True) -> InlineKeyboardMarkup:
    from cpstands.i18n import Translator

    assert isinstance(say, Translator)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                keyboards.link(
                    say("button-register"),
                    REGISTER_URL.format(id=contest_id),
                    emoji="🚀",
                    style="primary",
                    icons=icons,
                ),
                keyboards.link(
                    say("button-contest"),
                    CONTEST_URL.format(id=contest_id),
                    emoji="🏆",
                    icons=icons,
                ),
            ]
        ]
    )


class ReminderSender:
    def __init__(
        self,
        bot: Bot,
        sessions: async_sessionmaker[AsyncSession],
        i18n: I18n,
        *,
        icons: bool = True,
    ) -> None:
        self._bot = bot
        self._sessions = sessions
        self._i18n = i18n
        self._icons = icons

    async def send(self, claimed: repos.ClaimedReminder) -> bool:
        """Deliver one claimed reminder; returns whether Telegram accepted it."""
        async with self._sessions() as session:
            chat = await repos.get_chat(session, claimed.chat_id)
            contest = await repos.get_contest(session, PLATFORM, claimed.contest_id)
        if chat is None or contest is None or chat.status != "active":
            return False
        text, markup = render_reminder(self._i18n, chat, contest, claimed.offset_min)
        if markup is not None and not self._icons:
            markup = reminder_keyboard(
                self._i18n.bound(chat.language, chat.tone), claimed.contest_id, icons=False
            )
        try:
            await self._bot.send_message(
                claimed.chat_id,
                text,
                reply_markup=markup,
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
        except TelegramRetryAfter as exc:
            log.warning("reminder_throttled", chat_id=claimed.chat_id, retry_after=exc.retry_after)
            await self._release(claimed)
            return False
        except TelegramForbiddenError:
            async with self._sessions() as session, session.begin():
                await repos.set_status(session, claimed.chat_id, "removed")
            return False
        except TelegramNetworkError:
            await self._release(claimed)
            return False
        except TelegramBadRequest as exc:
            log.warning("reminder_rejected", chat_id=claimed.chat_id, reason=str(exc)[:120])
            return False
        except TelegramAPIError:
            log.warning("reminder_failed", chat_id=claimed.chat_id, exc_info=True)
            await self._release(claimed)
            return False
        return True

    async def _release(self, claimed: repos.ClaimedReminder) -> None:
        """A send that surely did not happen goes back to the queue, a few times at most."""
        if claimed.attempts >= MAX_ATTEMPTS:
            return
        async with self._sessions() as session, session.begin():
            await repos.release_reminder(session, PLATFORM, claimed)


def now_utc() -> datetime:
    return datetime.now(UTC)
