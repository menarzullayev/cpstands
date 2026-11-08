"""Dispatcher assembly and the long-polling runner."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Protocol

import structlog
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import ErrorEvent

from cpstands import __version__, metrics
from cpstands.bot.alerts import AlertNotifier, AlertWatcher
from cpstands.bot.appcmd import create_app_router
from cpstands.bot.deps import Deps, PlatformKit
from cpstands.bot.donate import create_donate_router
from cpstands.bot.handlers import create_router
from cpstands.bot.import_friends import create_import_router
from cpstands.bot.live import LiveUpdater
from cpstands.bot.monitor import OperatorAlerts
from cpstands.bot.owner import create_owner_router
from cpstands.bot.privacy import create_privacy_router
from cpstands.bot.ratelimit import RateLimiter, RateLimitMiddleware
from cpstands.bot.rating_card import create_rating_router
from cpstands.bot.reminders import ReminderSender
from cpstands.bot.scheduler import Scheduler
from cpstands.bot.settings import create_settings_router
from cpstands.bot.silence import SilenceMiddleware
from cpstands.bot.summary import SummaryWorker, create_summary_router
from cpstands.bot.telemetry import TelegramMetrics
from cpstands.bot.upsolve import UpsolveWatcher
from cpstands.config import Settings
from cpstands.db import repos
from cpstands.db.engine import create_engine, create_session_factory
from cpstands.http_server import ReadinessChecker, start_server
from cpstands.http_server import build_app as build_http_app
from cpstands.i18n import I18n
from cpstands.services import applink
from cpstands.services.admin import AdminChecker
from cpstands.services.alerts import AlertService
from cpstands.services.announce import register_channel
from cpstands.services.contests import ContestService
from cpstands.services.heartbeat import Heartbeat, store_api_secret
from cpstands.services.ops import ObservedSource, OpsState, load_source_state, refresh_gauges
from cpstands.services.ratings import RatingService
from cpstands.services.retention import RetentionService
from cpstands.services.standings import StandingsService
from cpstands.services.summary import SummaryService
from cpstands.services.upsolve import UpsolveService
from cpstands.services.watchlist import WatchlistService
from cpstands.sources.codeforces.client import ClientConfig, CodeforcesClient
from cpstands.sources.codeforces.source import CodeforcesSource
from cpstands.sources.kep import KepClient, KepClientConfig, KepSource

PLATFORM = "codeforces"
KEP_REFRESH_AGE_S = 5.0  # the Refresh button re-reads a kep.uz table this soon
ALLOWED_UPDATES = [
    "message",
    "callback_query",
    "my_chat_member",
    "chat_member",
    "pre_checkout_query",
]

log = structlog.get_logger(__name__)


class _Worker(Protocol):
    async def run(self) -> None: ...


def build_dispatcher(
    deps: Deps, limiter: RateLimiter | None = None, *, silent_chats: tuple[int, ...] = ()
) -> Dispatcher:
    dispatcher = Dispatcher(deps=deps)
    if silent_chats:
        silence = SilenceMiddleware(silent_chats)
        for observer in (
            dispatcher.message,
            dispatcher.callback_query,
            dispatcher.my_chat_member,
            dispatcher.chat_member,
        ):
            observer.outer_middleware(silence)
    middleware = RateLimitMiddleware(limiter or RateLimiter())
    dispatcher.message.outer_middleware(middleware)
    dispatcher.callback_query.outer_middleware(middleware)
    dispatcher.include_router(create_app_router())
    dispatcher.include_router(create_donate_router())  # before /start: catches /start donate
    dispatcher.include_router(create_router())
    dispatcher.include_router(create_settings_router())
    dispatcher.include_router(create_rating_router())
    dispatcher.include_router(create_summary_router())
    dispatcher.include_router(create_import_router())
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
        # aiogram 3.31 types status as a plain string ("creator"); older releases used an enum.
        status = member.status
        return str(getattr(status, "value", status))

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
    applink.configure(settings.telegram_bot_token.get_secret_value())
    sessions = create_session_factory(engine)
    ops = OpsState()
    metrics.BUILD_INFO.set(1, commit=settings.git_sha, version=__version__)
    await load_source_state(sessions, ops)
    source = ObservedSource(CodeforcesSource(client), ops)
    contests = ContestService(sessions, source)
    standings = StandingsService(source)
    kep_client: KepClient | None = None
    extra: dict[str, PlatformKit] = {}
    extra_sources = {}
    if settings.kep_enabled:
        kep_client = KepClient(
            KepClientConfig(
                base_url=settings.kep_api_base,
                min_interval_s=settings.kep_min_request_interval_seconds,
            )
        )
        kep = ObservedSource(KepSource(kep_client), ops)
        kep_standings = StandingsService(kep, min_refresh_age_s=KEP_REFRESH_AGE_S)
        extra[kep.platform] = PlatformKit(
            standings=kep_standings,
            contests=ContestService(sessions, kep),
            ratings=RatingService(kep),
            summaries=SummaryService(kep, kep_standings),
        )
        extra_sources[kep.platform] = kep
    deps = Deps(
        i18n=I18n(custom_emoji=settings.custom_emoji),
        sessions=sessions,
        watchlist=WatchlistService(sessions, source, extra=extra_sources),
        admin=make_admin_checker(bot),
        standings=standings,
        contests=contests,
        ops=ops,
        ratings=RatingService(source),
        summaries=SummaryService(source, standings),
        owner_id=settings.telegram_owner_id,
        icons=settings.button_icons,
        extra=extra,
    )
    dispatcher = build_dispatcher(deps, silent_chats=tuple(settings.silent_chats))
    await store_api_secret(sessions, settings.telegram_bot_token.get_secret_value())
    heartbeat = Heartbeat(
        sessions,
        commit=settings.git_sha,
        version=__version__,
        ping_url=(
            settings.healthchecks_ping_url.get_secret_value()
            if settings.healthchecks_ping_url
            else None
        ),
    )
    if settings.announce_channel and settings.announce_offsets:
        await register_channel(
            bot,
            sessions,
            settings.announce_channel,
            offsets=settings.announce_offsets,
            language=settings.announce_language,
            time_zone=settings.default_timezone,
        )
    updater = LiveUpdater(bot, sessions, deps.standings, deps.i18n, icons=deps.icons)
    sender = ReminderSender(bot, sessions, deps.i18n, icons=deps.icons, ops=ops)
    scheduler = Scheduler(sessions, contests, sender, retention=RetentionService(sessions), ops=ops)
    watcher = AlertWatcher(sessions, deps.standings, AlertService(sessions))
    notifier = AlertNotifier(bot, sessions, deps.i18n, ops=ops, icons=deps.icons)
    summarizer = SummaryWorker(sessions, deps.summaries, ops=ops)
    upsolver = UpsolveWatcher(sessions, source, UpsolveService(sessions), ops=ops)
    monitor = OperatorAlerts(
        bot, sessions, ops, deps.standings, deps.i18n, settings.telegram_owner_id
    )
    background: list[asyncio.Task[None]] = []
    for name, kit in extra.items():
        workers: list[_Worker] = [
            LiveUpdater(bot, sessions, kit.standings, deps.i18n, icons=deps.icons),
            Scheduler(
                sessions,
                kit.contests,
                ReminderSender(bot, sessions, deps.i18n, icons=deps.icons, ops=ops, platform=name),
                ops=ops,
            ),
            AlertWatcher(sessions, kit.standings, AlertService(sessions, platform=name)),
            SummaryWorker(sessions, kit.summaries, ops=ops),
            UpsolveWatcher(
                sessions, extra_sources[name], UpsolveService(sessions, platform=name), ops=ops
            ),
        ]
        background += [
            asyncio.create_task(w.run(), name=f"{name}-{type(w).__name__}") for w in workers
        ]
    tasks = [
        *background,
        asyncio.create_task(updater.run(), name="live-standings"),
        asyncio.create_task(scheduler.run(), name="scheduler"),
        asyncio.create_task(watcher.run(), name="alert-watcher"),
        asyncio.create_task(notifier.run(), name="alert-notifier"),
        asyncio.create_task(summarizer.run(), name="summaries"),
        asyncio.create_task(upsolver.run(), name="upsolve"),
        asyncio.create_task(monitor.run(), name="operator-alerts"),
        asyncio.create_task(heartbeat.run(), name="heartbeat"),
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
        if kep_client is not None:
            await kep_client.aclose()
        await engine.dispose()
