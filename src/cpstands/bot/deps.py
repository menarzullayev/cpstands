"""Everything a handler needs, passed through the dispatcher's workflow data."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cpstands.bot.whisper import Whisper
from cpstands.i18n import I18n
from cpstands.services.admin import AdminChecker
from cpstands.services.contests import ContestService
from cpstands.services.ops import OpsState
from cpstands.services.standings import StandingsService
from cpstands.services.watchlist import WatchlistService


@dataclass(slots=True)
class Deps:
    i18n: I18n
    sessions: async_sessionmaker[AsyncSession]
    watchlist: WatchlistService
    admin: AdminChecker
    standings: StandingsService
    contests: ContestService
    ops: OpsState
    owner_id: int | None = None
    icons: bool = False
    whisper: Whisper = field(default_factory=Whisper)
