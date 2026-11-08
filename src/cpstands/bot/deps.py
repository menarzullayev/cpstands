"""Everything a handler needs, passed through the dispatcher's workflow data."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cpstands.bot.import_gate import ImportGate
from cpstands.bot.whisper import Whisper
from cpstands.i18n import I18n
from cpstands.services.admin import AdminChecker
from cpstands.services.contests import ContestService
from cpstands.services.ops import OpsState
from cpstands.services.ratings import RatingService
from cpstands.services.standings import StandingsService
from cpstands.services.summary import SummaryService
from cpstands.services.watchlist import WatchlistService
from cpstands.sources.codeforces.friends import fetch_friends


@dataclass(slots=True)
class Deps:
    i18n: I18n
    sessions: async_sessionmaker[AsyncSession]
    watchlist: WatchlistService
    admin: AdminChecker
    standings: StandingsService
    contests: ContestService
    ops: OpsState
    ratings: RatingService
    summaries: SummaryService
    owner_id: int | None = None
    icons: bool = False
    whisper: Whisper = field(default_factory=Whisper)
    imports: ImportGate = field(default_factory=ImportGate)
    # One-shot call with the owner's own API key; replaceable so tests never touch the network.
    fetch_friends: Callable[[str, str], Awaitable[tuple[str, ...]]] = fetch_friends
