"""Counting what the senders do, for the metrics endpoint and the operator alert rules."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import Bot
from aiogram.client.session.middlewares.base import BaseRequestMiddleware, NextRequestMiddlewareType
from aiogram.methods import TelegramMethod
from aiogram.methods.base import TelegramType

from cpstands import metrics
from cpstands.services.ops import OpsState


def record_send(kind: str, ops: OpsState | None, *, error: str | None = None) -> None:
    """Record one delivery attempt: ``error`` is the class of the failure, ``None`` on success."""
    ok = error is None
    metrics.SENDS.inc(kind=kind, outcome="ok" if ok else "error")
    if not ok:
        metrics.SEND_ERRORS.inc(1.0, kind=kind, **{"class": error or "unknown"})
    if ops is not None:
        ops.record_send(ok=ok)


class TelegramMetrics(BaseRequestMiddleware):
    """Counts Bot API calls by method name (no chat ids, no content)."""

    async def __call__(
        self,
        make_request: NextRequestMiddlewareType[TelegramType],
        bot: Bot,
        method: TelegramMethod[TelegramType],
    ) -> Any:
        metrics.TELEGRAM_REQUESTS.inc(method=type(method).__name__)
        return await make_request(bot, method)


type Refresh = Callable[[], Awaitable[None]]
