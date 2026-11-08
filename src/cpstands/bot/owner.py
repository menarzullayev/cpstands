"""Owner-only operator commands: ``/status``, ``/pause``, ``/resume``, ``/stats`` (REQ-019)."""

from __future__ import annotations

import html
from datetime import UTC, datetime

import structlog
from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from cpstands import __version__, platforms
from cpstands.bot.deps import Deps
from cpstands.db import repos
from cpstands.i18n import Markup, Translator
from cpstands.services import ops

log = structlog.get_logger(__name__)

PLATFORM = "codeforces"


def duration_words(seconds: float) -> str:
    """Compact "1d 2h 3m" form; seconds only below a minute."""
    total = int(seconds)
    days, rest = divmod(total, 86400)
    hours, rest = divmod(rest, 3600)
    minutes, secs = divmod(rest, 60)
    parts = [
        f"{days}d" if days else "",
        f"{hours}h" if hours else "",
        f"{minutes}m" if minutes else "",
    ]
    text = " ".join(p for p in parts if p)
    return text or f"{secs}s"


def _is_owner(message: Message, deps: Deps) -> bool:
    user = message.from_user
    return (
        deps.owner_id is not None
        and user is not None
        and user.id == deps.owner_id
        and message.chat.type == "private"
    )


async def _owner_say(deps: Deps, message: Message) -> Translator | None:
    """The translator of the owner's chat, or ``None`` after telling a stranger off."""
    async with deps.sessions() as session:
        record = await repos.get_chat(session, message.chat.id)
    say = deps.i18n.bound(record.language, record.tone) if record else deps.i18n.bound(None)
    if not _is_owner(message, deps):
        await message.answer(say("owner-only"))
        return None
    return say


def _source_lines(deps: Deps, now: datetime) -> str:
    lines = []
    for name, health in sorted(deps.ops.sources.items()):
        seen = (
            f"{duration_words((now - health.last_success).total_seconds())} ago"
            if health.last_success
            else "never"
        )
        flags = " · PAUSED" if health.paused else ""
        lines.append(
            f"<code>{html.escape(name)}</code>: ok {seen} · errors in a row "
            f"{health.consecutive_errors}{flags}"
        )
    return "\n".join(lines) or "-"


async def on_status(message: Message, deps: Deps) -> None:
    say = await _owner_say(deps, message)
    if say is None:
        return
    now = datetime.now(UTC)
    async with deps.sessions() as session:
        shot = await ops.snapshot(session, now=now)
    open_alerts = ", ".join(sorted(deps.ops.open_alerts)) or "-"
    chats = ", ".join(f"{k} {v}" for k, v in sorted(shot.chats.items())) or "-"
    await message.answer(
        say(
            "owner-status",
            version=__version__,
            uptime=duration_words(deps.ops.uptime_s()),
            sources=Markup(_source_lines(deps, now)),
            alerts=shot.pending_alerts,
            overdue=shot.overdue_reminders,
            scheduled=shot.scheduled_reminders,
            live=shot.live_messages,
            contests=shot.watched_contests,
            chats=chats,
            open=open_alerts,
        )
    )


async def on_stats(message: Message, deps: Deps) -> None:
    say = await _owner_say(deps, message)
    if say is None:
        return
    async with deps.sessions() as session:
        numbers = await ops.stats(session, now=datetime.now(UTC))
    by_type = ", ".join(f"{k} {v}" for k, v in sorted(numbers.chats_by_type.items())) or "-"
    await message.answer(
        say(
            "owner-stats",
            chats=by_type,
            handles=numbers.handles_total,
            events=numbers.events_24h,
            reminders=numbers.reminders_sent_24h,
            pending=numbers.alerts_pending,
            failed=numbers.alerts_failed_24h,
        )
    )


async def _switch(message: Message, command: CommandObject, deps: Deps, *, pause: bool) -> None:
    say = await _owner_say(deps, message)
    if say is None:
        return
    target = (command.args or "").strip()
    if target.lstrip("-").isdigit():
        await _switch_chat(message, deps, say, int(target), pause=pause)
        return
    name = target.lower().rstrip(":") or PLATFORM
    if name not in platforms.PLATFORMS:
        await message.answer(say("owner-pause-usage"))
        return
    health = deps.ops.source(name)
    health.paused = pause
    await ops.save_source_state(deps.sessions, name, health)
    log.info("source_pause_changed", source=name, paused=pause)
    if pause:
        await message.answer(say("owner-paused-source", source=name))
    else:
        await message.answer(say("owner-resumed-source", source=name))


async def _switch_chat(
    message: Message, deps: Deps, say: Translator, chat_id: int, *, pause: bool
) -> None:
    wanted_from, wanted_to = ("active", "paused") if pause else ("paused", "active")
    async with deps.sessions() as session, session.begin():
        record = await repos.get_chat(session, chat_id, for_update=True)
        if record is None or record.status != wanted_from:
            await message.answer(say("owner-chat-unknown", id=str(chat_id)))
            return
        await repos.set_status(session, chat_id, wanted_to)
    log.info("chat_pause_changed", paused=pause)
    if pause:
        await message.answer(say("owner-paused-chat", id=str(chat_id)))
    else:
        await message.answer(say("owner-resumed-chat", id=str(chat_id)))


async def on_pause(message: Message, command: CommandObject, deps: Deps) -> None:
    await _switch(message, command, deps, pause=True)


async def on_resume(message: Message, command: CommandObject, deps: Deps) -> None:
    await _switch(message, command, deps, pause=False)


def create_owner_router() -> Router:
    router = Router(name="owner")
    router.message.register(on_status, Command("status"))
    router.message.register(on_stats, Command("stats"))
    router.message.register(on_pause, Command("pause"))
    router.message.register(on_resume, Command("resume"))
    return router
