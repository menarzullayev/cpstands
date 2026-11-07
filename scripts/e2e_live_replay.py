"""Replay a finished contest as if it were running, to watch live standings in real Telegram.

Run it, then send ``/standings 1970`` to the bot. The table is edited in place every few seconds
as more solves are revealed, and the last frame turns the contest FINISHED.

    uv run python scripts/e2e_live_replay.py [--frames 10] [--period 6]
"""

import argparse
import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from cpstands.bot.alerts import AlertNotifier, AlertWatcher
from cpstands.bot.app import ALLOWED_UPDATES, build_dispatcher, make_admin_checker
from cpstands.bot.deps import Deps
from cpstands.bot.live import LiveUpdater
from cpstands.config import get_settings
from cpstands.db import repos
from cpstands.db.engine import create_engine, create_session_factory
from cpstands.domain.contest import ContestPhase, FullStandings, ProblemStatus, StandingRow
from cpstands.i18n import I18n
from cpstands.services.alerts import AlertService
from cpstands.services.contests import ContestService
from cpstands.services.standings import StandingsService
from cpstands.services.watchlist import WatchlistService
from cpstands.sources.codeforces.client import ClientConfig, CodeforcesClient
from cpstands.sources.codeforces.source import CodeforcesSource

CONTEST = 1970


def frame(full: FullStandings, upto_s: int, *, final: bool, t0: datetime) -> FullStandings:
    """The table as it would have looked ``upto_s`` seconds into the contest."""
    rows: list[StandingRow] = []
    for row in full.rows:
        problems = []
        solved = 0
        penalty = 0
        for result in row.problems:
            seen = result.status in {ProblemStatus.ACCEPTED, ProblemStatus.PROVISIONAL}
            if seen and result.time_s is not None and result.time_s <= upto_s:
                solved += 1
                penalty += result.time_s // 60 + 20 * result.rejected_attempts
                problems.append(result)
            else:
                problems.append(
                    replace(
                        result,
                        status=ProblemStatus.NOT_TRIED,
                        time_s=None,
                        points=0.0,
                        rejected_attempts=0,
                    )
                )
        rows.append(replace(row, points=float(solved), penalty=penalty, problems=tuple(problems)))
    rows.sort(key=lambda r: (-r.points, r.penalty))
    ranked = tuple(replace(r, rank=i + 1) for i, r in enumerate(rows))
    phase = ContestPhase.FINISHED if final else ContestPhase.CODING
    return replace(
        full,
        contest=replace(full.contest, phase=phase, starts_at=t0),
        rows=ranked,
        fetched_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(seconds=3),
    )


class ReplaySource(CodeforcesSource):
    def __init__(self, client: CodeforcesClient, frames: int, step_s: int) -> None:
        super().__init__(client)
        self._full: FullStandings | None = None
        self._frames = frames
        self._step_s = step_s
        self._n = 0
        self.t0 = datetime.now(UTC)

    async def fetch_full_standings(self, contest_id: int) -> FullStandings:
        if self._full is None:
            self._full = await super().fetch_full_standings(contest_id)
        self._n += 1
        final = self._n > self._frames
        print(f"frame {self._n}/{self._frames}{' (final)' if final else ''}", flush=True)
        return frame(self._full, self._n * self._step_s, final=final, t0=self.t0)


async def main(frames: int, period: int) -> None:
    settings = get_settings()
    step_s = 18000 // frames
    engine = create_engine(settings.database_url.get_secret_value())
    client = CodeforcesClient(ClientConfig(min_interval_s=2.0))
    source = ReplaySource(client, frames, step_s)
    bot = Bot(
        settings.telegram_bot_token.get_secret_value(),  # type: ignore[union-attr]
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    sessions = create_session_factory(engine)
    i18n = I18n(custom_emoji=settings.custom_emoji)
    deps = Deps(
        i18n=i18n,
        sessions=sessions,
        watchlist=WatchlistService(sessions, source),
        admin=make_admin_checker(bot),
        standings=StandingsService(source),
        contests=ContestService(sessions, source),
        icons=settings.button_icons,
    )
    updater = LiveUpdater(bot, sessions, deps.standings, i18n, icons=settings.button_icons)
    async with sessions() as session, session.begin():
        await repos.upsert_contest(
            session, "codeforces", CONTEST, "Helvetic Coding Contest 2024 (replay)", "CODING",
            source.t0, 18000,
        )  # fmt: skip
    watcher = AlertWatcher(sessions, deps.standings, AlertService(sessions))
    notifier = AlertNotifier(bot, sessions, i18n)
    tasks = [
        asyncio.create_task(updater.run()),
        asyncio.create_task(watcher.run()),
        asyncio.create_task(notifier.run()),
    ]
    print(
        f"ready: send /standings {CONTEST} to the bot (frame step {step_s // 60} min)", flush=True
    )
    try:
        await build_dispatcher(deps).start_polling(bot, allowed_updates=ALLOWED_UPDATES)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await bot.session.close()
        await client.aclose()
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=int, default=10)
    parser.add_argument("--period", type=int, default=6)
    args = parser.parse_args()
    asyncio.run(main(args.frames, args.period))
