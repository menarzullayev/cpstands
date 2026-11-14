"""Health and metrics endpoints: ``/healthz``, ``/readyz`` and ``/metrics`` (spec stage 08)."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from aiohttp import web
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cpstands import metrics
from cpstands.services.ops import OpsState

HEARTBEAT_MAX_AGE_S = 120.0
STARTUP_GRACE_S = 60.0
READY_CACHE_S = 10.0
CONTENT_TYPE = "text/plain; version=0.0.4"


@dataclass(frozen=True, slots=True)
class Readiness:
    ready: bool
    checks: dict[str, str]


class ReadinessChecker:
    """Ready means: database reachable, migrations at head, the scheduler is beating."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        ops: OpsState,
        expected_head: str | None,
        *,
        commit: str = "dev",
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._sessions = sessions
        self._ops = ops
        self._head = expected_head
        self.commit = commit
        self._clock = clock
        self._cached: tuple[float, Readiness] | None = None

    async def check(self) -> Readiness:
        now = self._clock()
        if self._cached is not None and now - self._cached[0] < READY_CACHE_S:
            return self._cached[1]
        checks: dict[str, str] = {}
        try:
            async with self._sessions() as session:
                await session.execute(text("SELECT 1"))
                checks["database"] = "ok"
                if self._head is None:
                    checks["migrations"] = "unchecked"
                else:
                    row = (
                        await session.execute(text("SELECT version_num FROM alembic_version"))
                    ).first()
                    current = str(row[0]) if row else None
                    checks["migrations"] = "ok" if current == self._head else f"at {current}"
        except Exception as exc:
            checks["database"] = f"error: {type(exc).__name__}"
        beat = self._ops.seconds_since_beat("scheduler")
        if beat is not None and beat <= HEARTBEAT_MAX_AGE_S:
            checks["scheduler"] = "ok"
        elif beat is None and self._ops.uptime_s() <= STARTUP_GRACE_S:
            checks["scheduler"] = "starting"
        else:
            checks["scheduler"] = "stalled"
        ready = (
            checks.get("database") == "ok"
            and checks.get("migrations") in {"ok", "unchecked"}
            and checks["scheduler"] in {"ok", "starting"}
        )
        result = Readiness(ready, checks)
        self._cached = (now, result)
        return result


def build_app(
    readiness: ReadinessChecker, refresh_gauges: Callable[[], Awaitable[None]]
) -> web.Application:
    async def healthz(_: web.Request) -> web.Response:
        return web.Response(text="ok\n")

    async def readyz(_: web.Request) -> web.Response:
        result = await readiness.check()
        return web.json_response(
            {"ready": result.ready, "commit": readiness.commit, "checks": result.checks},
            status=200 if result.ready else 503,
        )

    async def metrics_endpoint(_: web.Request) -> web.Response:
        await refresh_gauges()
        return web.Response(
            body=metrics.REGISTRY.render().encode(), headers={"Content-Type": CONTENT_TYPE}
        )

    app = web.Application()
    app.router.add_get("/healthz", healthz)
    app.router.add_get("/readyz", readyz)
    app.router.add_get("/metrics", metrics_endpoint)
    return app


async def start_server(app: web.Application, host: str, port: int) -> web.AppRunner:
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, host, port).start()
    return runner
