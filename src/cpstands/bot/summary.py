"""Post-contest summaries: the message, the worker that queues it, and ``/summary``."""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import structlog
from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import InlineKeyboardMarkup, LinkPreviewOptions, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cpstands.bot import keyboards
from cpstands.bot.common import ensure_chat, html_link, say
from cpstands.bot.deps import Deps
from cpstands.db import repos
from cpstands.domain.contest import handle_key
from cpstands.i18n import I18n, Markup
from cpstands.services.ops import OpsState
from cpstands.services.summary import FriendResult, Summary, SummaryService
from cpstands.sources.base import PermanentSourceError, SourceError

PLATFORM = "codeforces"
log = structlog.get_logger(__name__)

TICK_S = 300.0
RETRY_S = 600.0
WINDOW = timedelta(hours=12)  # a contest that ended longer ago is not announced any more
RATING_WAIT = timedelta(hours=4)  # how long to wait for the rating changes before going without
MAX_LINES = 15
MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}
_ID_RE = re.compile(r"^\d{1,7}$")


def event_key(contest_id: int) -> str:
    return f"summary|{PLATFORM}|{contest_id}"


def _results(payload: dict[str, object]) -> list[FriendResult]:
    raw = payload.get("results")
    found: list[FriendResult] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        old, new = item.get("old"), item.get("new")
        found.append(
            FriendResult(
                handle=str(item.get("handle", "")),
                rank=int(item.get("rank", 0)),
                solved=int(item.get("solved", 0)),
                old_rating=old if isinstance(old, int) else None,
                new_rating=new if isinstance(new, int) else None,
            )
        )
    return found


def render_summary(
    i18n: I18n, chat: repos.ChatRecord, payload: dict[str, object], *, icons: bool = False
) -> tuple[str, InlineKeyboardMarkup]:
    """The text and buttons of one summary; works from a stored outbox payload."""
    tr = i18n.bound(chat.language, chat.tone)
    contest_id = int(str(payload["contest_id"]))
    url = f"https://codeforces.com/contest/{contest_id}"
    results = _results(payload)
    lines = [
        tr(
            "summary-header",
            contest=html_link(url, str(payload["contest_name"])),
            count=int(str(payload.get("participants", 0))),
        ),
        "",
    ]
    for result in results[:MAX_LINES]:
        line = tr(
            "summary-line",
            medal=MEDALS.get(result.rank, "▫️"),
            handle=html_link(f"https://codeforces.com/profile/{result.handle}", result.handle),
            rank=str(result.rank),
            solved=result.solved,
        )
        if result.delta is not None:
            line += tr("summary-rating", delta=f"{result.delta:+d}", new=str(result.new_rating))
        lines.append(line)
    if len(results) > MAX_LINES:
        lines.append(tr("summary-more", count=len(results) - MAX_LINES))
    gainers = [r for r in results if r.delta is not None and r.delta > 0]
    if gainers:
        best = max(gainers, key=lambda r: r.delta or 0)
        lines += [
            "",
            tr(
                "summary-best",
                handle=html_link(f"https://codeforces.com/profile/{best.handle}", best.handle),
                delta=f"{best.delta:+d}",
            ),
        ]
    if not payload.get("rated"):
        lines += ["", tr("summary-unrated")]
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                keyboards.link(
                    tr("button-results"),
                    f"{url}/standings",
                    emoji="🏆",
                    style="primary",
                    icons=icons,
                )
            ]
        ]
    )
    return "\n".join(lines), markup


class SummaryWorker:
    """Queues one summary per chat for each contest that has just finished."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        summaries: SummaryService,
        *,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        ops: OpsState | None = None,
    ) -> None:
        self._sessions = sessions
        self._summaries = summaries
        self._clock = clock
        self._now = now
        self._sleep = sleep
        self._ops = ops
        self._done: set[int] = set()
        self._retry_at: dict[int, float] = {}

    async def run(self) -> None:
        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.error("summary_tick_failed", exc_info=True)
            await self._sleep(TICK_S)

    async def tick(self) -> int:
        """One pass; returns how many summaries were queued."""
        if self._ops is not None:
            self._ops.beat("summary")
        now = self._now()
        async with self._sessions() as session:
            audience = await repos.summary_audience(session, PLATFORM)
            if not audience:
                return 0
            finished = await repos.finished_contests(
                session, PLATFORM, ended_after=now - WINDOW, now=now, limit=10
            )
        queued = 0
        for contest in finished:
            if contest.contest_id in self._done:
                continue
            if self._retry_at.get(contest.contest_id, 0.0) > self._clock():
                continue
            queued += await self._announce(contest, audience, now)
        return queued

    async def _announce(
        self, contest: repos.ContestRow, audience: dict[int, dict[str, str]], now: datetime
    ) -> int:
        everyone = {key: shown for friends in audience.values() for key, shown in friends.items()}
        try:
            summary = await self._summaries.summary(contest.contest_id, everyone)
        except SourceError:
            log.warning("summary_fetch_failed", contest_id=contest.contest_id, exc_info=True)
            self._retry_at[contest.contest_id] = self._clock() + RETRY_S
            return 0
        if not summary.results:
            self._done.add(contest.contest_id)  # none of the followed handles took part
            return 0
        ended = (contest.starts_at or now) + timedelta(seconds=contest.duration_s or 0)
        if not summary.rated and now < ended + RATING_WAIT:
            self._retry_at[contest.contest_id] = self._clock() + RETRY_S
            return 0
        queued = 0
        async with self._sessions() as session, session.begin():
            for chat_id, friends in audience.items():
                mine = tuple(r for r in summary.results if handle_key(r.handle) in friends)
                if not mine:
                    continue
                payload = replace(summary, results=mine).payload()
                if await repos.enqueue_alert(
                    session, chat_id, event_key(contest.contest_id), payload, not_before=now
                ):
                    queued += 1
        self._done.add(contest.contest_id)
        log.info("summary_queued", contest_id=contest.contest_id, chats=queued)
        return queued


async def _friends_of(deps: Deps, chat_id: int) -> dict[str, str]:
    async with deps.sessions() as session:
        friends = await repos.list_friends(session, chat_id, PLATFORM)
    return {f.key: f.display for f in friends if f.show_in_list}


async def on_summary(message: Message, command: CommandObject, deps: Deps) -> None:
    chat = await ensure_chat(deps, message.chat)
    if chat is None:
        return
    tr = say(deps, chat)
    arg = (command.args or "").strip()
    if arg and not _ID_RE.match(arg):
        await deps.whisper.reply(message, tr("summary-usage"))
        return
    friends = await _friends_of(deps, chat.chat_id)
    if not friends:
        await deps.whisper.reply(message, tr("summary-no-friends"))
        return
    if arg:
        candidates = [int(arg)]
    else:
        async with deps.sessions() as session:
            recent = await repos.latest_finished_contests(session, PLATFORM, limit=3)
        candidates = [c.contest_id for c in recent]
    for contest_id in candidates:
        try:
            summary: Summary = await deps.summaries.summary(contest_id, friends)
        except PermanentSourceError:
            continue
        except SourceError:
            log.warning("summary_command_failed", exc_info=True)
            await deps.whisper.reply(message, tr("summary-source-error"))
            return
        if summary.results:
            payload = summary.payload()
            text, markup = render_summary(deps.i18n, chat, payload, icons=deps.icons)
            await message.answer(
                text, reply_markup=markup, link_preview_options=LinkPreviewOptions(is_disabled=True)
            )
            return
    await deps.whisper.reply(message, tr("summary-none"))


def create_summary_router() -> Router:
    router = Router(name="summary")
    router.message.register(on_summary, Command("summary"))
    return router


__all__ = ["Markup", "SummaryWorker", "create_summary_router", "render_summary"]
