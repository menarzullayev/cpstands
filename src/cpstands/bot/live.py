"""Live standings: while a contest runs, its standings messages are edited in place.

One fetch per active contest serves every chat (ADR-004). The fetch is scheduled for just after
the platform's cache expires, each message is re-rendered at the page its reader chose, and an
edit is sent only when the table changed (or the shown time is getting stale).
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import structlog
from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from aiogram.types import InputRichMessage
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cpstands import metrics
from cpstands.bot import standings_view
from cpstands.bot.telemetry import record_send
from cpstands.db import repos
from cpstands.domain.contest import FullStandings
from cpstands.i18n import I18n
from cpstands.services.standings import StandingsService
from cpstands.sources.base import PermanentSourceError, SourceError

log = structlog.get_logger(__name__)

TICK_S = 2.0
MIN_EDIT_GAP_S = 3.0  # per chat; Telegram allows about 20 messages a minute in a group
STALE_TIME_S = 300.0  # re-edit an unchanged table at least this often so the clock stays fresh
MIN_FETCH_DELAY_S = 2.0
MAX_FETCH_DELAY_S = 120.0
ERROR_BACKOFF_START_S = 30.0
ERROR_BACKOFF_MAX_S = 300.0
MAX_LIVE_PER_CHAT = 3
SHARE_S = 20.0  # a copy fetched this recently is shared with the alert watcher

_STATUS_RE = re.compile(r"<p>.*?</p>", re.DOTALL)


def table_digest(html: str) -> str:
    """Hash of a page without its status line, so a new timestamp alone is not a change."""
    return hashlib.sha1(_STATUS_RE.sub("", html, count=1).encode()).hexdigest()  # noqa: S324


def fetch_delay(standings: FullStandings, now: datetime) -> float:
    """Seconds until the next fetch: just after the cache expires, one minute when unknown."""
    if standings.expires_at is None:
        return 60.0
    wait = (standings.expires_at - now).total_seconds() + 1.0
    return min(max(wait, MIN_FETCH_DELAY_S), MAX_FETCH_DELAY_S)


class LiveUpdater:
    def __init__(
        self,
        bot: Bot,
        sessions: async_sessionmaker[AsyncSession],
        standings: StandingsService,
        i18n: I18n,
        *,
        icons: bool = True,
        link_only: frozenset[int] = frozenset(),
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._bot = bot
        self._sessions = sessions
        self._standings = standings
        self._i18n = i18n
        self._icons = icons
        # Chats whose tables carry link buttons only (their button taps are never answered).
        self._link_only = link_only
        self._clock = clock
        self._now = now
        self._sleep = sleep
        self._platform = standings.platform
        self._next_due: dict[int, float] = {}
        self._failures: dict[int, int] = {}
        self._last_edit: dict[int, float] = {}
        self._edited_at: dict[tuple[int, int, int], float] = {}

    async def run(self) -> None:
        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.error("live_tick_failed", exc_info=True)
            await self._sleep(TICK_S)

    async def tick(self) -> None:
        """One pass: update every live contest whose next fetch is due."""
        async with self._sessions() as session:
            contests = await repos.live_contest_ids(session, self._platform)
        for gone in set(self._next_due) - set(contests):
            self._next_due.pop(gone, None)
            self._failures.pop(gone, None)
        for contest_id in contests:
            if self._next_due.get(contest_id, 0.0) <= self._clock():
                await self._update_contest(contest_id)

    async def _update_contest(self, contest_id: int) -> None:
        try:
            standings = await self._standings.get_shared(contest_id, max_age_s=SHARE_S)
        except PermanentSourceError:
            log.warning("live_contest_gone", contest_id=contest_id)
            await self._freeze_all(contest_id)
            return
        except SourceError:
            failures = self._failures.get(contest_id, 0) + 1
            self._failures[contest_id] = failures
            backoff = min(ERROR_BACKOFF_START_S * 2 ** (failures - 1), ERROR_BACKOFF_MAX_S)
            self._next_due[contest_id] = self._clock() + backoff
            log.warning("live_fetch_failed", contest_id=contest_id, failures=failures)
            return
        self._failures.pop(contest_id, None)
        active = standings.contest.phase.is_active
        self._next_due[contest_id] = self._clock() + fetch_delay(standings, self._now())
        async with self._sessions() as session:
            messages = await repos.live_messages(session, self._platform, contest_id)
        for message in messages:
            await self._edit(message, standings, final=not active)
        if not active:
            self._next_due.pop(contest_id, None)

    async def _freeze_all(self, contest_id: int) -> None:
        async with self._sessions() as session, session.begin():
            for message in await repos.live_messages(session, self._platform, contest_id):
                await repos.mark_live_message(session, self._platform, message, state="orphaned")

    async def _edit(
        self, message: repos.LiveMessage, standings: FullStandings, *, final: bool
    ) -> None:
        async with self._sessions() as session:
            chat = await repos.get_chat(session, message.chat_id)
        if chat is None or chat.status in {"removed", "deleted"}:
            await self._mark(message, state="orphaned")
            return
        say = self._i18n.bound(chat.language, chat.tone)
        async with self._sessions() as session:
            friends = frozenset(await repos.scoreboard_keys(session, chat.chat_id, self._platform))
        ctx = standings_view.ViewContext(
            standings_view.resolve_view(message.view, friends), friends, chat.table_cols
        )
        html = standings_view.render(
            standings, message.row_page, message.col_page, say, time_zone=chat.time_zone, ctx=ctx
        )
        digest = table_digest(html)
        key = (message.chat_id, message.contest_id, message.message_id)
        edited_at = self._edited_at.get(key)
        age = self._clock() - edited_at if edited_at is not None else float("inf")
        if not final and digest == message.last_hash and age < STALE_TIME_S:
            return
        await self._respect_chat_gap(message.chat_id)
        if message.chat_id in self._link_only:
            markup = standings_view.link_keyboard(standings, say, icons=self._icons)
        else:
            markup = standings_view.keyboard(
                standings,
                message.row_page,
                message.col_page,
                say,
                icons=self._icons,
                ctx=ctx,
                chat_id=message.chat_id,
            )
        try:
            await self._bot.edit_message_text(
                chat_id=message.chat_id,
                message_id=message.message_id,
                rich_message=InputRichMessage(html=html),
                reply_markup=markup,
            )
        except TelegramRetryAfter as exc:
            self._next_due[message.contest_id] = self._clock() + float(exc.retry_after) + 1.0
            log.warning("live_edit_throttled", chat_id=message.chat_id, retry_after=exc.retry_after)
            return
        except TelegramForbiddenError:
            await self._mark(message, state="orphaned")
            return
        except TelegramBadRequest as exc:
            text = str(exc).lower()
            if "not modified" in text:
                self._edited_at[key] = self._clock()
                await self._mark(message, last_hash=digest, edited=True)
            elif "not found" in text or "can't be edited" in text or "invalid" in text:
                await self._mark(message, state="orphaned")
            else:
                log.warning("live_edit_rejected", chat_id=message.chat_id, reason=text[:120])
            return
        self._last_edit[message.chat_id] = self._clock()
        self._edited_at[key] = self._clock()
        metrics.LIVE_EDITS.inc()
        record_send("live", None)
        await self._mark(message, last_hash=digest, edited=True, state="frozen" if final else None)

    async def _respect_chat_gap(self, chat_id: int) -> None:
        last = self._last_edit.get(chat_id)
        if last is not None:
            wait = MIN_EDIT_GAP_S - (self._clock() - last)
            if wait > 0:
                await self._sleep(wait)

    async def _mark(
        self,
        message: repos.LiveMessage,
        *,
        state: str | None = None,
        last_hash: str | None = None,
        edited: bool = False,
    ) -> None:
        async with self._sessions() as session, session.begin():
            await repos.mark_live_message(
                session, self._platform, message, state=state, last_hash=last_hash, edited=edited
            )
