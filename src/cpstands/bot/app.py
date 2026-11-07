"""Dispatcher assembly and the long-polling runner."""

from __future__ import annotations

import structlog
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.types import ErrorEvent

from cpstands.bot.deps import Deps
from cpstands.bot.handlers import create_router
from cpstands.bot.ratelimit import RateLimiter, RateLimitMiddleware
from cpstands.config import Settings
from cpstands.db.engine import create_engine, create_session_factory
from cpstands.i18n import I18n
from cpstands.services.admin import AdminChecker
from cpstands.services.watchlist import WatchlistService
from cpstands.sources.codeforces.client import ClientConfig, CodeforcesClient
from cpstands.sources.codeforces.source import CodeforcesSource

ALLOWED_UPDATES = ["message", "callback_query", "my_chat_member", "chat_member"]

log = structlog.get_logger(__name__)


def build_dispatcher(deps: Deps, limiter: RateLimiter | None = None) -> Dispatcher:
    dispatcher = Dispatcher(deps=deps)
    middleware = RateLimitMiddleware(limiter or RateLimiter())
    dispatcher.message.outer_middleware(middleware)
    dispatcher.callback_query.outer_middleware(middleware)
    dispatcher.include_router(create_router())

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
    bot = Bot(settings.telegram_bot_token.get_secret_value(), default=DefaultBotProperties())
    sessions = create_session_factory(engine)
    deps = Deps(
        i18n=I18n(),
        sessions=sessions,
        watchlist=WatchlistService(sessions, CodeforcesSource(client)),
        admin=make_admin_checker(bot),
        owner_id=settings.telegram_owner_id,
    )
    dispatcher = build_dispatcher(deps)
    try:
        me = await bot.get_me()
        log.info("bot_started", username=me.username)
        await dispatcher.start_polling(bot, allowed_updates=ALLOWED_UPDATES)
    finally:
        await bot.session.close()
        await client.aclose()
        await engine.dispose()
