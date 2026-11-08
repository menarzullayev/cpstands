"""Live standings in a channel post's comments.

A target names a contest and a message in a channel's discussion group (the automatic forward
of the channel post). When the contest starts, the bot replies to that message once with the
standings table; the reply shows under the post as a comment, and the live updater keeps
editing it until the contest ends. Configured with ``LIVE_COMMENTS``, for example
``kep:504@-1001305284030:140896``.

The table carries only link buttons: the group may be a silent chat whose button taps are
dropped, and a link needs no answer from the bot.
"""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InputRichMessage, ReplyParameters
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cpstands import platforms
from cpstands.bot import standings_view
from cpstands.bot.deps import PlatformKit
from cpstands.bot.live import MAX_LIVE_PER_CHAT
from cpstands.db import repos
from cpstands.domain.contest import FullStandings
from cpstands.i18n import I18n
from cpstands.sources.base import SourceError

log = structlog.get_logger(__name__)

TICK_S = 30.0
MAX_SEND_ATTEMPTS = 5
DEFAULT_LANGUAGE = "uz"
DEFAULT_ZONE = "Asia/Tashkent"
_TARGET_RE = re.compile(r"^(?:([a-z]+):)?(\d{1,7})@(-?\d{5,20}):(\d{1,12})$")


@dataclass(frozen=True, slots=True)
class CommentTarget:
    platform: str
    contest_id: int
    chat_id: int
    reply_to: int


def parse_targets(items: Iterable[str]) -> list[CommentTarget]:
    """``kep:504@-1001305284030:140896`` -> a target; a bare id means Codeforces."""
    found: list[CommentTarget] = []
    for item in items:
        match = _TARGET_RE.match(item.strip())
        if match is None:
            raise ValueError(
                f"LIVE_COMMENTS entry is not <platform>:<contest>@<chat>:<message>: {item!r}"
            )
        name = match.group(1) or platforms.CODEFORCES
        if name not in platforms.PLATFORMS:
            raise ValueError(f"unknown platform in LIVE_COMMENTS: {name!r}")
        found.append(
            CommentTarget(name, int(match.group(2)), int(match.group(3)), int(match.group(4)))
        )
    return found


class CommentPoster:
    def __init__(
        self,
        bot: Bot,
        sessions: async_sessionmaker[AsyncSession],
        kits: Mapping[str, PlatformKit],
        i18n: I18n,
        targets: Iterable[CommentTarget],
        *,
        icons: bool = True,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._bot = bot
        self._sessions = sessions
        self._kits = kits
        self._i18n = i18n
        self._pending = list(targets)
        self._icons = icons
        self._now = now
        self._sleep = sleep
        self._clock = clock
        self._attempts: dict[CommentTarget, int] = {}

    @property
    def pending(self) -> tuple[CommentTarget, ...]:
        return tuple(self._pending)

    async def run(self) -> None:
        while self._pending:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.error("comment_tick_failed", exc_info=True)
            await self._sleep(TICK_S)

    async def tick(self) -> int:
        """Post every target whose contest is running; returns how many were posted."""
        posted = 0
        for target in list(self._pending):
            outcome = await self._try(target)
            if outcome != "wait":
                self._pending.remove(target)
            if outcome == "posted":
                posted += 1
        return posted

    async def _try(self, target: CommentTarget) -> str:
        """``posted``, ``done`` (nothing more to do) or ``wait`` (try again later)."""
        kit = self._kits.get(target.platform)
        if kit is None:
            log.warning("comment_platform_off", platform=target.platform)
            return "done"
        now = self._now()
        async with self._sessions() as session:
            contest = await repos.get_contest(session, target.platform, target.contest_id)
            messages = await repos.live_messages(session, target.platform, target.contest_id)
        if any(m.chat_id == target.chat_id for m in messages):
            return "done"  # already posted (a restart while the contest runs)
        if contest is None or contest.starts_at is None or now < contest.starts_at:
            return "wait"
        if now > contest.starts_at + timedelta(seconds=contest.duration_s or 0):
            log.info("comment_contest_over", contest_id=target.contest_id)
            return "done"
        try:
            standings = await kit.standings.get(target.contest_id, refresh=True)
        except SourceError:
            return "wait"  # the table may not be open yet in the first seconds
        if not standings.contest.phase.is_active:
            return "wait"
        return await self._post(target, standings)

    async def _post(self, target: CommentTarget, standings: FullStandings) -> str:
        async with self._sessions() as session, session.begin():
            chat = await repos.get_chat(session, target.chat_id)
            if chat is None:
                chat = await repos.upsert_chat(session, target.chat_id, "supergroup")
            if chat.language is None:
                await repos.set_language(session, target.chat_id, DEFAULT_LANGUAGE)
            if chat.time_zone is None:
                await repos.set_time_zone(session, target.chat_id, DEFAULT_ZONE)
        say = self._i18n.bound(chat.language or DEFAULT_LANGUAGE, chat.tone)
        html = standings_view.render(standings, 0, 0, say, time_zone=chat.time_zone or DEFAULT_ZONE)
        try:
            sent = await self._bot.send_rich_message(
                target.chat_id,
                InputRichMessage(html=html),
                reply_parameters=ReplyParameters(message_id=target.reply_to),
                reply_markup=standings_view.link_keyboard(standings, say, icons=self._icons),
            )
        except TelegramAPIError as exc:
            tries = self._attempts.get(target, 0) + 1
            self._attempts[target] = tries
            log.warning("comment_send_failed", tries=tries, reason=str(exc)[:160])
            return "done" if tries >= MAX_SEND_ATTEMPTS else "wait"
        async with self._sessions() as session, session.begin():
            await repos.register_live_message(
                session,
                target.chat_id,
                target.platform,
                target.contest_id,
                sent.message_id,
                max_live=MAX_LIVE_PER_CHAT,
            )
        log.info("comment_posted", platform=target.platform, contest_id=target.contest_id)
        return "posted"
