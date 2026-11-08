"""Post-contest summaries: building, rendering, the worker, delivery and ``/summary``."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cpstands.bot import alerts as bot_alerts
from cpstands.bot import summary as bot_summary
from cpstands.db import repos
from cpstands.db.engine import create_engine, create_session_factory
from cpstands.domain.contest import (
    Contest,
    ContestPhase,
    ContestRatingChange,
    FullStandings,
    Problem,
    ProblemResult,
    ProblemStatus,
    StandingRow,
)
from cpstands.i18n import I18n
from cpstands.services import summary as svc
from cpstands.services.standings import StandingsService
from cpstands.services.summary import SummaryService
from tests.support.clock import FakeClock
from tests.support.sources import FakeSource
from tests.support.telegram import FakeSession, make_bot

START = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)
ENDED = START + timedelta(hours=2)
CID = 2290
CHAT, OTHER = -1001, -1002
A, R = ProblemStatus.ACCEPTED, ProblemStatus.REJECTED


def table(
    rows: dict[str, tuple[ProblemStatus, ...]],
    *,
    cid: int = CID,
    types: dict[str, str] | None = None,
) -> FullStandings:
    contest = Contest("codeforces", cid, "Round <1> & co", ContestPhase.FINISHED, "CF", START, 7200)
    width = max(len(v) for v in rows.values())
    standing = []
    for rank, (who, statuses) in enumerate(rows.items(), 1):
        problems = tuple(ProblemResult(s, 0, 600 if s is A else None, 0.0) for s in statuses)
        kind = (types or {}).get(who, "CONTESTANT")
        standing.append(StandingRow(rank, who, (who,), 0.0, 0, kind, problems))
    plist = tuple(Problem(chr(65 + i), f"P{i}", None) for i in range(width))
    return FullStandings(contest, plist, tuple(standing), ENDED)


def change(handle: str, old: int, new: int) -> ContestRatingChange:
    return ContestRatingChange(handle, 1, old, new)


FRIENDS = {"tourist": "tourist", "petr": "Petr"}


# ------------------------------------------------------------------ building (no database)


def test_summary_ranks_followed_handles_and_counts_solved_problems() -> None:
    standings = table({"x": (A, A, A), "Tourist": (A, A, R), "petr": (A, R, R), "z": (R, R, R)})
    summary = svc.build_summary(standings, FRIENDS, None)
    assert [(r.handle, r.rank, r.solved) for r in summary.results] == [
        ("tourist", 2, 2),
        ("Petr", 3, 1),
    ]
    assert summary.participants == 4
    assert not summary.rated
    assert all(r.delta is None for r in summary.results)


def test_summary_ignores_virtual_and_out_of_competition_rows() -> None:
    standings = table(
        {"tourist": (A,), "petr": (A,)}, types={"tourist": "VIRTUAL", "petr": "OUT_OF_COMPETITION"}
    )
    summary = svc.build_summary(standings, FRIENDS, None)
    assert summary.results == ()
    assert summary.participants == 0


def test_summary_carries_rating_changes_by_case_insensitive_handle() -> None:
    standings = table({"Tourist": (A, A), "petr": (A, R)})
    changes = {"tourist": change("Tourist", 3800, 3850), "petr": change("Petr", 1500, 1480)}
    summary = svc.build_summary(standings, FRIENDS, changes)
    assert summary.rated
    assert [r.delta for r in summary.results] == [50, -20]
    assert summary.payload()["results"][0] == {  # type: ignore[index]
        "handle": "tourist",
        "rank": 1,
        "solved": 2,
        "old": 3800,
        "new": 3850,
    }


async def test_rating_changes_are_cached_and_missing_ones_are_retried_later() -> None:
    source = FakeSource([], contest_changes={CID: [change("tourist", 1, 2)]})
    clock = FakeClock()
    service = SummaryService(source, StandingsService(source), clock=clock.monotonic)  # type: ignore[arg-type]
    first = await service.rating_changes(CID)
    assert first is not None
    assert await service.rating_changes(CID) is first
    assert source.changes_fetches == 1
    assert await service.rating_changes(999) is None  # nothing published
    assert await service.rating_changes(999) is None
    assert source.changes_fetches == 2  # the miss is remembered briefly
    clock.advance(svc.UNAVAILABLE_TTL_S + 1)
    source.contest_changes[999] = [change("tourist", 5, 6)]
    assert await service.rating_changes(999) is not None


# ------------------------------------------------------------------ rendering (no database)


def chat_record(language: str = "en", tone: str = "playful") -> repos.ChatRecord:
    return repos.ChatRecord(-1, "supergroup", language, "UTC", tone, "active", (1440,), True)


def render(summary: svc.Summary, language: str = "en") -> tuple[str, list[str]]:
    body, markup = bot_summary.render_summary(I18n(), chat_record(language), summary.payload())
    urls = [b.url for row in markup.inline_keyboard for b in row if b.url]
    return body, [u for u in urls if u]


def test_rendered_summary_escapes_names_and_links_to_the_results() -> None:
    standings = table({"tourist": (A, A), "petr": (A, R)})
    summary = svc.build_summary(standings, FRIENDS, None)
    body, urls = render(summary)
    assert "Round &lt;1&gt; &amp; co" in body
    assert "<Round" not in body
    assert "🥇" in body
    assert "🥈" in body
    assert urls == [f"https://codeforces.com/contest/{CID}/standings"]


def test_rendered_summary_shows_rating_moves_and_the_best_gain() -> None:
    standings = table({"tourist": (A, A), "petr": (A, R)})
    changes = {"tourist": change("tourist", 3800, 3850), "petr": change("Petr", 1500, 1480)}
    body, _ = render(svc.build_summary(standings, FRIENDS, changes))
    assert "+50 → 3850" in body
    assert "-20 → 1480" in body
    assert I18n().t("en", "summary-best", handle="x", delta="y").split("x")[0] in body
    assert I18n().t("en", "summary-unrated") not in body


def test_a_summary_without_a_gain_names_no_winner_and_a_rating_drop_is_plain_numbers() -> None:
    standings = table({"tourist": (A,), "petr": (R,)})
    changes = {"tourist": change("tourist", 3800, 3790), "petr": change("Petr", 1500, 1480)}
    body, _ = render(svc.build_summary(standings, FRIENDS, changes))
    assert "-10 → 3790" in body
    assert I18n().t("en", "summary-best", handle="x", delta="y").split("x")[0] not in body


def test_an_unrated_summary_says_so_and_a_long_one_is_cut() -> None:
    names = {f"user{i}": f"user{i}" for i in range(20)}
    standings = table(dict.fromkeys(names, (A,)))
    body, _ = render(svc.build_summary(standings, names, None))
    assert I18n().t("en", "summary-unrated") in body
    assert body.count("user") >= bot_summary.MAX_LINES
    assert "user19" not in body
    assert I18n().t("en", "summary-more", count=5) in body


@pytest.mark.parametrize("language", ["en", "ru", "uz"])
def test_every_language_renders_a_full_summary(language: str) -> None:
    standings = table({"tourist": (A, A), "petr": (A, R)})
    changes = {"tourist": change("tourist", 3800, 3850), "petr": change("Petr", 1500, 1480)}
    body, _ = render(svc.build_summary(standings, FRIENDS, changes), language)
    assert "{" not in body
    assert "summary-" not in body


# ------------------------------------------------------------------ worker (database)


@dataclass
class Rig:
    sessions: async_sessionmaker[AsyncSession]
    fake: FakeSession
    clock: FakeClock
    source: FakeSource
    now: datetime

    def worker(self) -> bot_summary.SummaryWorker:
        standings = StandingsService(self.source)  # type: ignore[arg-type]
        return bot_summary.SummaryWorker(
            self.sessions,
            SummaryService(self.source, standings, clock=self.clock.monotonic),  # type: ignore[arg-type]
            clock=self.clock.monotonic,
            now=lambda: self.now,
            sleep=self.clock.sleep,
        )

    def notifier(self) -> bot_alerts.AlertNotifier:
        return bot_alerts.AlertNotifier(
            make_bot(self.fake),
            self.sessions,
            I18n(),
            clock=self.clock.monotonic,
            now=lambda: self.now,
            sleep=self.clock.sleep,
        )

    async def chat(
        self,
        chat_id: int,
        *handles: str,
        summary: bool = True,
        alerts: bool = True,
        active: bool = True,
    ) -> None:
        async with self.sessions() as session, session.begin():
            await repos.upsert_chat(session, chat_id, "supergroup")
            await repos.set_language(session, chat_id, "en")
            await repos.set_alerts_enabled(session, chat_id, alerts)
            await repos.set_summary_enabled(session, chat_id, summary)
            if active:
                await repos.set_status(session, chat_id, "active")
            for handle in handles:
                await session.execute(
                    text(
                        "insert into watched_handles (chat_id, platform, handle_key, handle_display)"
                        " values (:c, 'codeforces', :k, :d)"
                    ),
                    {"c": chat_id, "k": handle.lower(), "d": handle},
                )

    async def contest(
        self, cid: int = CID, *, phase: str = "FINISHED", start: datetime = START
    ) -> None:
        async with self.sessions() as session, session.begin():
            await repos.upsert_contest(session, "codeforces", cid, "Round", phase, start, 7200)

    async def count(self, query: str) -> int:
        async with self.sessions() as session:
            return int((await session.execute(text(query))).scalar_one())


@pytest.fixture
async def rig(migrated_database: str) -> AsyncIterator[Rig]:
    engine = create_engine(migrated_database, pool_size=4)
    source = FakeSource(
        [],
        standings={CID: table({"tourist": (A, A), "petr": (A, R), "other": (A, A, A)})},
        contest_changes={CID: [change("tourist", 3800, 3850), change("Petr", 1500, 1480)]},
    )
    yield Rig(
        create_session_factory(engine),
        FakeSession(),
        FakeClock(),
        source,
        ENDED + timedelta(minutes=30),
    )
    await engine.dispose()


async def test_each_chat_gets_one_summary_with_only_its_own_friends(rig: Rig) -> None:
    await rig.chat(CHAT, "tourist")
    await rig.chat(OTHER, "Petr", "tourist")
    await rig.chat(-1003, "nobody")  # follows nobody who took part
    await rig.contest()
    worker = rig.worker()
    assert await worker.tick() == 2
    assert await worker.tick() == 0  # announced once
    assert await rig.count("select count(*) from deliveries") == 2
    notifier = rig.notifier()
    assert await notifier.tick() == 2
    texts = {m["chat_id"]: str(m["text"]) for m in rig.fake.sent()}
    assert "Petr" not in texts[CHAT]
    assert "tourist" in texts[CHAT]
    assert "Petr" in texts[OTHER]
    assert "tourist" in texts[OTHER]
    assert await notifier.tick() == 0  # delivered once


async def test_a_restarted_worker_cannot_make_a_chat_hear_it_twice(rig: Rig) -> None:
    await rig.chat(CHAT, "tourist")
    await rig.contest()
    assert await rig.worker().tick() == 1
    assert await rig.worker().tick() == 0  # a fresh worker has forgotten; the outbox has not
    assert await rig.count("select count(*) from deliveries") == 1


async def test_the_worker_waits_for_rating_changes_then_goes_without(rig: Rig) -> None:
    del rig.source.contest_changes[CID]
    await rig.chat(CHAT, "tourist")
    await rig.contest()
    worker = rig.worker()
    assert await worker.tick() == 0  # ratings not out yet: hold on
    rig.clock.advance(bot_summary.RETRY_S + 1)
    rig.now = ENDED + bot_summary.RATING_WAIT + timedelta(minutes=1)
    assert await worker.tick() == 1  # the wait is over: send without ratings
    await rig.notifier().tick()
    assert I18n().t("en", "summary-unrated") in str(rig.fake.sent()[-1]["text"])


async def test_the_worker_picks_up_ratings_that_appear_later(rig: Rig) -> None:
    saved = rig.source.contest_changes.pop(CID)
    await rig.chat(CHAT, "tourist")
    await rig.contest()
    worker = rig.worker()
    assert await worker.tick() == 0
    rig.source.contest_changes[CID] = saved
    rig.clock.advance(bot_summary.RETRY_S + 1)
    assert await worker.tick() == 1
    await rig.notifier().tick()
    assert "+50 → 3850" in str(rig.fake.sent()[-1]["text"])


async def test_nothing_is_queued_for_old_unfinished_or_unwatched_contests(rig: Rig) -> None:
    await rig.chat(CHAT, "tourist")
    await rig.contest(phase="CODING")
    assert await rig.worker().tick() == 0
    await rig.contest(phase="FINISHED", start=START - timedelta(days=2))
    assert await rig.worker().tick() == 0  # ended too long ago
    await rig.contest(start=START + timedelta(hours=9))
    assert await rig.worker().tick() == 0  # has not ended yet
    assert await rig.count("select count(*) from deliveries") == 0


async def test_chats_that_switched_summaries_off_or_left_are_skipped(rig: Rig) -> None:
    await rig.chat(CHAT, "tourist", summary=False)
    await rig.chat(OTHER, "tourist", active=False)
    await rig.contest()
    assert await rig.worker().tick() == 0
    assert rig.source.full_fetches == 0  # nobody to tell: not even a fetch


async def test_summary_is_independent_of_the_alerts_switch(rig: Rig) -> None:
    await rig.chat(CHAT, "tourist", alerts=False)  # no live alerts, but wants the summary
    await rig.contest()
    await rig.worker().tick()
    async with rig.sessions() as session, session.begin():
        await repos.set_alerts_enabled(session, CHAT, False)  # must not cancel it either
    assert await rig.notifier().tick() == 1


async def test_switching_summaries_off_after_queueing_drops_the_message(rig: Rig) -> None:
    await rig.chat(CHAT, "tourist")
    await rig.contest()
    await rig.worker().tick()
    async with rig.sessions() as session, session.begin():
        await repos.set_summary_enabled(session, CHAT, False)
    assert await rig.notifier().tick() == 0
    assert rig.fake.sent() == []
    assert await rig.count("select count(*) from deliveries where state = 'failed'") == 1


async def test_a_source_failure_is_retried_not_dropped(rig: Rig) -> None:
    await rig.chat(CHAT, "tourist")
    await rig.contest()
    rig.source.fail = True
    worker = rig.worker()
    assert await worker.tick() == 0
    rig.source.fail = False
    assert await worker.tick() == 0  # still backing off
    rig.clock.advance(bot_summary.RETRY_S + 1)
    assert await worker.tick() == 1
