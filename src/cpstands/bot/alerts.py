"""Alerts: poll running contests, queue what is new, and deliver it in batches per chat."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

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

from cpstands import metrics, platforms
from cpstands.bot.common import html_link
from cpstands.bot.live import fetch_delay
from cpstands.bot.reminders import duration_text
from cpstands.bot.summary import render_summary
from cpstands.bot.telemetry import record_send
from cpstands.db import repos
from cpstands.i18n import I18n, Translator
from cpstands.services.alerts import PLATFORM, AlertService
from cpstands.services.ops import OpsState
from cpstands.services.standings import StandingsService
from cpstands.sources.base import PermanentSourceError, SourceError

log = structlog.get_logger(__name__)

SHARE_S = 20.0  # live standings and alerts reuse one fetch made within this many seconds
WATCH_TICK_S = 5.0
NOTIFY_TICK_S = 3.0
ERROR_BACKOFF_S = 60.0
MIN_GAP_S = 3.0  # between two alert messages to one chat
MAX_LINES_PER_MESSAGE = 12
MAX_ATTEMPTS = 3
CLAIM_LIMIT = 200


class AlertWatcher:
    """Fetches each running contest that someone waits for, on the platform's cache schedule."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        standings: StandingsService,
        alerts: AlertService,
        *,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._sessions = sessions
        self._standings = standings
        self._alerts = alerts
        self._clock = clock
        self._now = now
        self._sleep = sleep
        self._platform = standings.platform
        self._next_due: dict[int, float] = {}

    async def run(self) -> None:
        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.error("alert_watch_failed", exc_info=True)
            await self._sleep(WATCH_TICK_S)

    async def tick(self) -> None:
        async with self._sessions() as session:
            contests = await repos.active_contests_to_watch(session, self._platform)
        for gone in set(self._next_due) - set(contests):
            self._next_due.pop(gone, None)
        for contest_id in contests:
            if self._next_due.get(contest_id, 0.0) <= self._clock():
                await self._poll(contest_id)

    async def _poll(self, contest_id: int) -> None:
        try:
            standings = await self._standings.get_shared(contest_id, max_age_s=SHARE_S)
        except PermanentSourceError:
            log.warning("alert_contest_gone", contest_id=contest_id)
            self._next_due[contest_id] = self._clock() + 600.0
            return
        except SourceError:
            self._next_due[contest_id] = self._clock() + ERROR_BACKOFF_S
            log.warning("alert_fetch_failed", contest_id=contest_id)
            return
        await self._alerts.process(standings)
        contest = standings.contest
        if contest.phase.is_active:
            self._next_due[contest_id] = self._clock() + fetch_delay(standings, self._now())
            return
        # The last poll (with the final system-test results) has been processed: stop watching.
        async with self._sessions() as session, session.begin():
            await repos.upsert_contest(
                session,
                self._platform,
                contest_id,
                contest.name,
                contest.phase.value,
                contest.starts_at,
                contest.duration_s,
            )
        self._next_due.pop(contest_id, None)


_link = html_link


def render_alerts(
    i18n: I18n, chat: repos.ChatRecord, alerts: list[repos.ClaimedAlert]
) -> list[str]:
    """Turn queued alerts into messages.

    Each contest is a block: a header and one line per alert. A block longer than
    ``MAX_LINES_PER_MESSAGE`` is cut into several messages that each repeat the header; small
    blocks of different contests share a message.
    """
    say = i18n.bound(chat.language, chat.tone)
    by_contest: dict[tuple[str, int], list[repos.ClaimedAlert]] = defaultdict(list)
    for alert in alerts:
        platform = str(alert.payload.get("platform", PLATFORM))
        by_contest[(platform, int(str(alert.payload["contest_id"])))].append(alert)
    blocks: list[tuple[str, list[str]]] = []
    for (platform, contest_id), group in by_contest.items():
        site = platforms.get(platform)
        name = str(group[0].payload["contest_name"])
        header = say("alert-contest", contest=_link(site.contest_url(contest_id), name))
        lines = [_alert_line(say, site, contest_id, alert.payload) for alert in group]
        for start in range(0, len(lines), MAX_LINES_PER_MESSAGE):
            blocks.append((header, lines[start : start + MAX_LINES_PER_MESSAGE]))
    messages: list[str] = []
    current: list[str] = []
    used = 0
    for header, lines in blocks:
        if current and used + len(lines) + 1 > MAX_LINES_PER_MESSAGE:
            messages.append("\n\n".join(current))
            current, used = [], 0
        current.append("\n".join([header, *lines]))
        used += len(lines) + 1
    if current:
        messages.append("\n\n".join(current))
    return messages


def _alert_line(
    say: Translator, site: platforms.Platform, contest_id: int, p: dict[str, object]
) -> str:
    problem = _link(site.problem_url(contest_id, str(p["problem"])), str(p["problem"]))
    handle = _link(site.profile_url(str(p["handle"])), site.shown(str(p["handle"])))
    time_s = p.get("time_s")
    title = str(p.get("problem_name") or "")
    when = duration_text(time_s) if isinstance(time_s, int) else "-"
    variant = int(str(p.get("v", 0)))
    if p["kind"] == "upsolve":
        return say("alert-upsolve", handle=handle, problem=problem, title=title, v=variant)
    if p["kind"] == "systest_fail":
        return say(
            "alert-systest-fail", handle=handle, problem=problem, title=title, time=when, v=variant
        )
    return say("alert-solve", handle=handle, problem=problem, title=title, time=when, v=variant)


class AlertNotifier:
    """Delivers queued alerts: one message per chat per round, at most once per event."""

    def __init__(
        self,
        bot: Bot,
        sessions: async_sessionmaker[AsyncSession],
        i18n: I18n,
        *,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        ops: OpsState | None = None,
        icons: bool = False,
    ) -> None:
        self._ops = ops
        self._icons = icons
        self._bot = bot
        self._sessions = sessions
        self._i18n = i18n
        self._clock = clock
        self._now = now
        self._sleep = sleep
        self._last_sent: dict[int, float] = {}

    async def run(self) -> None:
        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.error("alert_notify_failed", exc_info=True)
            await self._sleep(NOTIFY_TICK_S)

    async def tick(self) -> int:
        """Deliver every due alert; returns the number of messages sent."""
        async with self._sessions() as session, session.begin():
            claimed = await repos.claim_due_alerts(session, now=self._now(), limit=CLAIM_LIMIT)
        by_chat: dict[int, list[repos.ClaimedAlert]] = defaultdict(list)
        summaries: dict[int, list[repos.ClaimedAlert]] = defaultdict(list)
        for alert in claimed:
            target = summaries if alert.payload.get("kind") == "summary" else by_chat
            target[alert.chat_id].append(alert)
        sent = 0
        for chat_id, alerts in by_chat.items():
            sent += await self._deliver(chat_id, alerts)
        for chat_id, alerts in summaries.items():
            sent += await self._deliver_summaries(chat_id, alerts)
        return sent

    async def _deliver(self, chat_id: int, alerts: list[repos.ClaimedAlert]) -> int:
        async with self._sessions() as session:
            chat = await repos.get_chat(session, chat_id)
        if chat is None or chat.status != "active" or not chat.alerts_enabled:
            await self._fail(alerts, "chat is not receiving alerts")
            return 0
        delivered = 0
        for text in render_alerts(self._i18n, chat, alerts):
            await self._respect_gap(chat_id)
            if not await self._send(chat_id, text, alerts):
                return delivered
            delivered += 1
        self._observe_latency(alerts)
        return delivered

    async def _deliver_summaries(self, chat_id: int, alerts: list[repos.ClaimedAlert]) -> int:
        async with self._sessions() as session:
            chat = await repos.get_chat(session, chat_id)
        if chat is None or chat.status != "active" or not chat.summary_enabled:
            await self._fail(alerts, "chat is not receiving summaries")
            return 0
        delivered = 0
        for index, alert in enumerate(alerts):
            text, markup = render_summary(self._i18n, chat, alert.payload, icons=self._icons)
            await self._respect_gap(chat_id)
            if not await self._send(chat_id, text, alerts[index:], markup):
                return delivered
            delivered += 1
        return delivered

    async def _send(
        self,
        chat_id: int,
        text: str,
        alerts: list[repos.ClaimedAlert],
        markup: InlineKeyboardMarkup | None = None,
    ) -> bool:
        """Send one message; on a failure put ``alerts`` back or fail them, and say so."""
        try:
            await self._bot.send_message(
                chat_id,
                text,
                reply_markup=markup,
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
        except TelegramRetryAfter as exc:
            record_send("alert", self._ops, error="flood")
            await self._release(alerts, float(exc.retry_after) + 1.0, "flood control")
            return False
        except TelegramForbiddenError:
            record_send("alert", self._ops, error="forbidden")
            async with self._sessions() as session, session.begin():
                await repos.set_status(session, chat_id, "removed")
            await self._fail(alerts, "bot was blocked")
            return False
        except TelegramNetworkError:
            record_send("alert", self._ops, error="network")
            await self._release(alerts, 10.0, "network")
            return False
        except TelegramBadRequest as exc:
            log.warning("alert_rejected", chat_id=chat_id, reason=str(exc)[:120])
            record_send("alert", self._ops, error="bad_request")
            await self._fail(alerts, str(exc))
            return False
        except TelegramAPIError:
            record_send("alert", self._ops, error="api")
            await self._release(alerts, 30.0, "api error")
            return False
        record_send("alert", self._ops)
        metrics.ALERTS_SENT.inc()
        self._last_sent[chat_id] = self._clock()
        return True

    def _observe_latency(self, alerts: list[repos.ClaimedAlert]) -> None:
        """Seconds from the verdict to the message (REQ-N03)."""
        now = self._now()
        for alert in alerts:
            try:
                occurred = datetime.fromisoformat(str(alert.payload["at"]))
            except (KeyError, ValueError):
                continue
            metrics.DELIVERY_LATENCY.observe(max((now - occurred).total_seconds(), 0.0))

    async def _respect_gap(self, chat_id: int) -> None:
        last = self._last_sent.get(chat_id)
        if last is not None:
            wait = MIN_GAP_S - (self._clock() - last)
            if wait > 0:
                await self._sleep(wait)

    async def _release(self, alerts: list[repos.ClaimedAlert], delay_s: float, why: str) -> None:
        """Put alerts back after a send that surely did not happen, a few times at most."""
        again = [a for a in alerts if a.attempts < MAX_ATTEMPTS]
        gave_up = [a for a in alerts if a.attempts >= MAX_ATTEMPTS]
        async with self._sessions() as session, session.begin():
            if again:
                await repos.release_alerts(
                    session, again, not_before=self._now() + timedelta(seconds=delay_s), error=why
                )
            if gave_up:
                await repos.fail_alerts(session, gave_up, error=why)

    async def _fail(self, alerts: list[repos.ClaimedAlert], why: str) -> None:
        async with self._sessions() as session, session.begin():
            await repos.fail_alerts(session, alerts, error=why)
