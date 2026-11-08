"""Live standings as a comment under a channel post."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cpstands.bot.comments import CommentPoster, CommentTarget, parse_targets
from cpstands.bot.deps import PlatformKit
from cpstands.db import repos
from cpstands.db.engine import create_engine, create_session_factory
from cpstands.domain.contest import ContestPhase
from cpstands.i18n import I18n
from cpstands.services.contests import ContestService
from cpstands.services.ratings import RatingService
from cpstands.services.standings import StandingsService
from cpstands.services.summary import SummaryService
from tests.support.sources import FakeSource, make_standings
from tests.support.telegram import FakeSession, make_bot

GROUP = -1001305284030
POST = 140896
CONTEST = 1973
START = datetime(2026, 11, 8, 15, 35, tzinfo=UTC)


def test_targets_are_parsed_and_bad_ones_refused() -> None:
    assert parse_targets(["kep:504@-1001305284030:140896", "1970@-100123456:7"]) == [
        CommentTarget("kep", 504, -1001305284030, 140896),
        CommentTarget("codeforces", 1970, -100123456, 7),
    ]
    for bad in ("kep:504", "kep:504@x:1", "atcoder:1@-1001:2", "504@-1001305284030"):
        with pytest.raises(ValueError, match="LIVE_COMMENTS"):
            parse_targets([bad])


@pytest.fixture
async def sessions(migrated_database: str) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_engine(migrated_database, pool_size=3)
    factory = create_session_factory(engine)
    async with factory() as session, session.begin():
        await repos.upsert_contest(session, "codeforces", CONTEST, "Round", "BEFORE", START, 7200)
    yield factory
    await engine.dispose()


def _poster(
    sessions: async_sessionmaker[AsyncSession],
    fake: FakeSession,
    now: datetime,
    phase: ContestPhase,
) -> CommentPoster:
    source = FakeSource(
        [], standings={CONTEST: make_standings(contest_id=CONTEST, phase=phase, rows=30)}
    )
    standings = StandingsService(source)  # type: ignore[arg-type]
    kit = PlatformKit(
        standings,
        ContestService(sessions, source),  # type: ignore[arg-type]
        RatingService(source),  # type: ignore[arg-type]
        SummaryService(source, standings),  # type: ignore[arg-type]
    )
    return CommentPoster(
        make_bot(fake),
        sessions,
        {"codeforces": kit},
        I18n(),
        [CommentTarget("codeforces", CONTEST, GROUP, POST)],
        now=lambda: now,
    )


async def test_nothing_is_posted_before_the_start(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    fake = FakeSession()
    poster = _poster(sessions, fake, START - timedelta(minutes=1), ContestPhase.CODING)
    assert await poster.tick() == 0
    assert fake.calls == []
    assert poster.pending  # still waiting


async def test_one_reply_with_link_buttons_when_the_contest_runs(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    fake = FakeSession()
    poster = _poster(sessions, fake, START + timedelta(minutes=1), ContestPhase.CODING)
    assert await poster.tick() == 1
    [call] = fake.calls
    assert call.method == "SendRichMessage"
    assert call.data["chat_id"] == GROUP
    assert call.data["reply_parameters"]["message_id"] == POST
    buttons = [b for row in call.data["reply_markup"]["inline_keyboard"] for b in row]
    assert buttons
    assert all("url" in b and "callback_data" not in b for b in buttons)
    async with sessions() as session:
        live = await repos.live_messages(session, "codeforces", CONTEST)
        chat = await repos.get_chat(session, GROUP)
    assert [m.chat_id for m in live] == [GROUP]  # the live updater edits it from now on
    assert chat is not None
    assert chat.status == "onboarding"
    assert (chat.language, chat.time_zone) == ("uz", "Asia/Tashkent")

    # Done: later ticks and a restarted poster send nothing more.
    assert await poster.tick() == 0
    again = _poster(sessions, fake, START + timedelta(minutes=5), ContestPhase.CODING)
    assert await again.tick() == 0
    assert len(fake.calls) == 1


async def test_a_table_that_is_not_live_yet_waits(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    fake = FakeSession()
    poster = _poster(sessions, fake, START + timedelta(seconds=20), ContestPhase.BEFORE)
    assert await poster.tick() == 0
    assert fake.calls == []
    assert poster.pending


async def test_a_finished_contest_gets_no_comment(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    fake = FakeSession()
    poster = _poster(sessions, fake, START + timedelta(hours=3), ContestPhase.FINISHED)
    assert await poster.tick() == 0
    assert fake.calls == []
    assert not poster.pending
