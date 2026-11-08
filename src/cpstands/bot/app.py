"""Dispatcher assembly and the long-polling runner."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import structlog
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import ErrorEvent

from cpstands import __version__, metrics
from cpstands.bot.alerts import AlertNotifier, AlertWatcher
from cpstands.bot.deps import Deps
from cpstands.bot.handlers import create_router
from cpstands.bot.live import LiveUpdater
from cpstands.bot.monitor import OperatorAlerts
from cpstands.bot.owner import create_owner_router
from cpstands.bot.privacy import create_privacy_router
from cpstands.bot.ratelimit import RateLimiter, RateLimitMiddleware
from cpstands.bot.rating_card import create_rating_router
from cpstands.bot.reminders import ReminderSender
from cpstands.bot.scheduler import Scheduler
from cpstands.bot.settings import create_settings_router
from cpstands.bot.telemetry import TelegramMetrics
from cpstands.config import Settings
from cpstands.db import repos
from cpstands.db.engine import create_engine, create_session_factory
from cpstands.http_server import ReadinessChecker, start_server
from cpstands.http_server import build_app as build_http_app
from cpstands.i18n import I18n
from cpstands.services.admin import AdminChecker
from cpstands.services.alerts import AlertService
from cpstands.services.contests import ContestService
from cpstands.services.ops import ObservedSource, OpsState, load_source_state, refresh_gauges
from cpstands.services.ratings import RatingService
from cpstands.services.retention import RetentionService
from cpstands.services.standings import StandingsService
from cpstands.services.watchlist import WatchlistService
from cpstands.sources.codeforces.client import ClientConfig, CodeforcesClient
from cpstands.sources.codeforces.source import CodeforcesSource

PLATFORM = "codeforces"
ALLOWED_UPDATES = ["message", "callback_query", "my_chat_member", "chat_member"]

log = structlog.get_logger(__name__)


def build_dispatcher(deps: Deps, limiter: RateLimiter | None = None) -> Dispatcher:
    dispatcher = Dispatcher(deps=deps)
    middleware = RateLimitMiddleware(limiter or RateLimiter())
    dispatcher.message.outer_middleware(middleware)
    dispatcher.callback_query.outer_middleware(middleware)
    dispatcher.include_router(create_router())
    dispatcher.include_router(create_settings_router())
    dispatcher.include_router(create_rating_router())
    dispatcher.include_router(create_privacy_router())
    dispatcher.include_router(create_owner_router())

    @dispatcher.errors()
    async def on_error(event: ErrorEvent) -> bool:
        log.error("update_failed", exc_info=event.exception)
        update = event.update
        text = deps.i18n.t(None, "error-generic")
        try:
            if update.message is not None:
                await update.message.answer(text)
            elif update.callback_query is not None:
                await update.callback_query.answer(text, show_alert=True)
        except Exception:
            log.warning("error_reply_failed", exc_info=True)
        return True

    return dispatcher


def make_admin_checker(bot: Bot) -> AdminChecker:
    async def fetch_status(chat_id: int, user_id: int) -> str:
        member = await bot.get_chat_member(chat_id, user_id)
        return str(member.status.value)

    return AdminChecker(fetch_status)


def _expected_head() -> str | None:
    """The newest migration revision in the code, or ``None`` when it cannot be read."""
    try:
        from alembic.script import ScriptDirectory

        from cpstands.__main__ import alembic_config

        return ScriptDirectory.from_config(alembic_config()).get_current_head()
    except Exception:
        log.warning("migration_head_unknown", exc_info=True)
        return None


async def run_bot(settings: Settings) -> None:
    """Long polling until cancelled; closes every resource on exit."""
    if settings.telegram_bot_token is None:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set")
    engine = create_engine(settings.database_url.get_secret_value())
    client = CodeforcesClient(
        ClientConfig(
            base_url=settings.cf_api_base, min_interval_s=settings.cf_min_request_interval_seconds
        )
    )
    bot = Bot(
        settings.telegram_bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    bot.session.middleware(TelegramMetrics())
    sessions = create_session_factory(engine)
    ops = OpsState()
    metrics.BUILD_INFO.set(1, commit=settings.git_sha, version=__version__)
    await load_source_state(sessions, ops)
    source = ObservedSource(CodeforcesSource(client), ops)
    contests = ContestService(sessions, source)
    deps = Deps(
        i18n=I18n(custom_emoji=settings.custom_emoji),
        sessions=sessions,
        watchlist=WatchlistService(sessions, source),
        admin=make_admin_checker(bot),
        standings=StandingsService(source),
        contests=contests,
        ops=ops,
        ratings=RatingService(source),
        owner_id=settings.telegram_owner_id,
        icons=settings.button_icons,
    )
    dispatcher = build_dispatcher(deps)
    updater = LiveUpdater(bot, sessions, deps.standings, deps.i18n, icons=deps.icons)
    sender = ReminderSender(bot, sessions, deps.i18n, icons=deps.icons, ops=ops)
    scheduler = Scheduler(sessions, contests, sender, retention=RetentionService(sessions), ops=ops)
    watcher = AlertWatcher(sessions, deps.standings, AlertService(sessions))
    notifier = AlertNotifier(bot, sessions, deps.i18n, ops=ops)
    monitor = OperatorAlerts(
        bot, sessions, ops, deps.standings, deps.i18n, settings.telegram_owner_id
    )
    tasks = [
        asyncio.create_task(updater.run(), name="live-standings"),
        asyncio.create_task(scheduler.run(), name="scheduler"),
        asyncio.create_task(watcher.run(), name="alert-watcher"),
        asyncio.create_task(notifier.run(), name="alert-notifier"),
        asyncio.create_task(monitor.run(), name="operator-alerts"),
    ]
    runner = None
    if settings.http_port:
        readiness = ReadinessChecker(sessions, ops, _expected_head(), commit=settings.git_sha)

        async def refresh() -> None:
            async with sessions() as session:
                ages = {
                    cid: age
                    for cid in await repos.live_contest_ids(session, PLATFORM)
                    if (age := deps.standings.age_s(cid)) is not None
                }
                await refresh_gauges(session, ops, now=datetime.now(UTC), ages=ages)

        runner = await start_server(
            build_http_app(readiness, refresh), settings.http_host, settings.http_port
        )
        log.info("http_started", host=settings.http_host, port=settings.http_port)
    try:
        me = await bot.get_me()
        log.info("bot_started", username=me.username)
        await dispatcher.start_polling(bot, allowed_updates=ALLOWED_UPDATES)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if runner is not None:
            await runner.cleanup()
        await bot.session.close()
        await client.aclose()
        await engine.dispose()
