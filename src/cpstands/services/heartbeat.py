"""Liveness for the Mini App status page, and the key its database API checks signatures with.

Migration 0005 lets the Mini App call database functions that verify Telegram init data with
the bot token. The bot stores its own token there at start-up (never logged), and writes a
heartbeat every minute so the public status page can tell whether the bot is alive.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable

import aiohttp
import httpx
import structlog
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

log = structlog.get_logger(__name__)

HEARTBEAT_KEY = "bot.heartbeat"
TICK_S = 60.0
PING_TIMEOUT_S = 10.0


async def store_api_secret(sessions: async_sessionmaker[AsyncSession], bot_token: str) -> bool:
    """Put the bot token where the Mini App API reads it; False when the schema is missing."""
    try:
        async with sessions() as session, session.begin():
            await session.execute(
                text(
                    "INSERT INTO private.app_secrets (name, value) VALUES ('bot_token', :v) "
                    "ON CONFLICT (name) DO UPDATE SET value = EXCLUDED.value"
                ),
                {"v": bot_token},
            )
    except SQLAlchemyError:
        log.warning("api_secret_not_stored")  # the token itself is never part of the log
        return False
    return True


async def beat(
    sessions: async_sessionmaker[AsyncSession],
    *,
    commit: str,
    version: str,
    started_at: float,
    now: float,
) -> None:
    value = {
        "at": int(now),
        "commit": commit[:12],
        "version": version,
        "startedAt": int(started_at),
    }
    async with sessions() as session, session.begin():
        await session.execute(
            text(
                "INSERT INTO runtime_state (key, value) VALUES (:k, CAST(:v AS jsonb)) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"
            ),
            {"k": HEARTBEAT_KEY, "v": json.dumps(value)},
        )


Pinger = Callable[[str], Awaitable[None]]


async def http_ping(url: str) -> None:
    # aiohttp, not httpx: httpx logs every request URL at INFO, and this URL is a secret.
    timeout = aiohttp.ClientTimeout(total=PING_TIMEOUT_S)
    async with aiohttp.ClientSession(timeout=timeout) as session, session.get(url) as response:
        await response.read()


class Heartbeat:
    """Writes the heartbeat row and, when configured, pings an external monitor.

    The monitor (Healthchecks.io) alerts the owner when pings stop: the bot, Docker or the
    PC is down. A database failure pings ``<url>/fail`` so that alert comes at once.
    """

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        commit: str,
        version: str,
        ping_url: str | None = None,
        pinger: Pinger = http_ping,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._sessions = sessions
        self._commit = commit
        self._version = version
        self._ping_url = ping_url.rstrip("/") if ping_url else None
        self._pinger = pinger
        self._clock = clock
        self._started = clock()

    async def tick(self) -> None:
        try:
            await beat(
                self._sessions,
                commit=self._commit,
                version=self._version,
                started_at=self._started,
                now=self._clock(),
            )
        except SQLAlchemyError:
            await self._ping("/fail")
            raise
        await self._ping("")

    async def _ping(self, suffix: str) -> None:
        if self._ping_url is None:
            return
        try:
            await self._pinger(self._ping_url + suffix)
        except (aiohttp.ClientError, httpx.HTTPError, OSError, TimeoutError):
            # The monitor being unreachable must never disturb the bot; it alerts on silence.
            log.warning("monitor_ping_failed")  # the URL is a secret and is not logged

    async def run(self) -> None:
        while True:
            try:
                await self.tick()
            except SQLAlchemyError:
                log.warning("heartbeat_failed", exc_info=True)
            await asyncio.sleep(TICK_S)
