from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

import pytest

from cpstands.bot import standings_view as view
from cpstands.bot.handlers import parse_contest_id
from cpstands.domain.contest import ContestPhase, ProblemResult, ProblemStatus, StandingRow
from cpstands.i18n import I18n
from cpstands.services.standings import StandingsService
from cpstands.sources.base import PermanentSourceError, RetryableSourceError
from cpstands.sources.codeforces.parser import parse_full_standings
from tests.support.clock import FakeClock
from tests.support.sources import FakeSource, make_standings

SAY = I18n().bound("en")
NOW = datetime(2026, 11, 8, tzinfo=UTC)


def test_pages_and_column_ranges() -> None:
    assert [view.row_pages(n) for n in (0, 1, 25, 26, 827)] == [1, 1, 1, 2, 34]
    assert view.column_ranges(0) == [(0, 0)]
    assert view.column_ranges(16) == [(0, 16)]
    assert view.column_ranges(21) == [(0, 16), (16, 21)]
    assert view.column_ranges(40) == [(0, 16), (16, 32), (32, 40)]


@pytest.mark.parametrize(
    ("result", "icpc", "expected"),
    [
        (ProblemResult(ProblemStatus.ACCEPTED, 0, 183, 1.0), True, "+ 0:03"),
        (ProblemResult(ProblemStatus.ACCEPTED, 2, 11520, 1.0), True, "+2 3:12"),
        (ProblemResult(ProblemStatus.PROVISIONAL, 0, 60, 1.0), True, "+ 0:01*"),
        (ProblemResult(ProblemStatus.REJECTED, 3, None, 0.0), True, "-3"),
        (ProblemResult(ProblemStatus.NOT_TRIED, 0, None, 0.0), True, ""),
        (ProblemResult(ProblemStatus.ACCEPTED, 1, 600, 1250.0), False, "1250"),
        (ProblemResult(ProblemStatus.ACCEPTED, 0, 600, 499.5), False, "499.5"),
    ],
)
def test_cells(result: ProblemResult, icpc: bool, expected: str) -> None:
    assert view.cell(result, icpc=icpc) == expected


def test_every_page_fits_telegram_limits_and_shows_every_row_once() -> None:
    standings = make_standings(rows=60, problems=21)
    seen: list[str] = []
    for rp in range(view.row_pages(60)):
        for cp in range(2):
            html = view.render(standings, rp, cp, SAY, time_zone="Asia/Tashkent")
            assert html.count("<th>") <= 20
            if cp == 0:
                seen += [part.split("</td>")[0] for part in html.split("<tr><td>")[1:]]
    medals = [view._emoji(view.MEDALS[i]) for i in (1, 2, 3)]
    assert seen == medals + [str(i) for i in range(4, 61)]


def test_every_problem_column_is_reachable() -> None:
    standings = make_standings(rows=3, problems=21)
    headers: list[str] = []
    for cp in range(2):
        html = view.render(standings, 0, cp, SAY, time_zone=None)
        headers += html.split("</tr>")[0].split("<th>")[5:]
    assert [h.replace("</th>", "") for h in headers] == [f"P{i}" for i in range(1, 22)]


def test_names_are_clipped_and_escaped() -> None:
    standings = make_standings(rows=1, problems=2)
    template = standings.rows[0]
    row = StandingRow(
        rank=1,
        who="<b>evil</b> & | *team* with a long name",
        handles=("x",),
        points=2.0,
        penalty=5,
        participant_type="CONTESTANT",
        problems=template.problems,
    )
    table = type(standings)(standings.contest, standings.problems, (row,), NOW)
    html = view.render(table, 0, 0, SAY, time_zone=None)
    assert "<b>evil" not in html
    assert "&lt;b&gt;evil&lt;/b&gt; &amp;" in html
    assert "…" in html


def test_out_of_range_pages_are_clamped_and_empty_tables_say_so() -> None:
    standings = make_standings(rows=30, problems=3)
    last = view.render(standings, 99, 99, SAY, time_zone=None)
    assert "Rows 26–30 of 30" in last
    empty = view.render(make_standings(rows=0, problems=3), 0, 0, SAY, time_zone=None)
    assert "<table>" not in empty
    assert "No rows yet." in empty


def test_status_line_uses_the_chat_time_zone() -> None:
    html = view.render(make_standings(rows=2, problems=2), 0, 0, SAY, time_zone="Asia/Tashkent")
    assert "17:00" in html  # 12:00 UTC
    running = view.render(
        make_standings(rows=2, problems=2, phase=ContestPhase.CODING), 0, 0, SAY, time_zone="UTC"
    )
    assert "Running" in running


def test_keyboard_callbacks_fit_the_limit_even_for_extreme_values() -> None:
    standings = make_standings(contest_id=9_999_999, rows=2, problems=40)
    for rp, cp in ((0, 0), (9_999, 2), (123_456, 99)):
        markup = view.keyboard(standings, rp, cp, SAY, icons=False)
        for row in markup.inline_keyboard:
            for b in row:
                assert len((b.callback_data or "").encode()) <= 64
    assert len(view.callback(9_999_999, 99_999, 99, refresh=True).encode()) <= 64


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1970", 1970),
        ("  42 ", 42),
        ("https://codeforces.com/contest/1970", 1970),
        ("codeforces.com/contests/2001/standings", 2001),
        ("", None),
        ("0", None),
        ("-5", None),
        ("12345678", None),
        ("abc", None),
        ("https://example.com/contest/1", None),
        ("\uff11\uff19\uff17\uff10", None),  # fullwidth digits
    ],
)
def test_parse_contest_id(text: str, expected: int | None) -> None:
    assert parse_contest_id(text) == expected


def _service(clock: FakeClock) -> tuple[StandingsService, FakeSource]:
    source = FakeSource([], standings={1: make_standings(contest_id=1)})
    return StandingsService(source, clock=clock.monotonic), source  # type: ignore[arg-type]


async def test_cache_lifetime_depends_on_the_phase() -> None:
    clock = FakeClock()
    service, source = _service(clock)
    await service.get(1)
    clock.advance(599)
    await service.get(1)
    assert source.full_fetches == 1  # finished contests are kept for ten minutes
    clock.advance(2)
    await service.get(1)
    assert source.full_fetches == 2

    live = FakeSource([], standings={2: make_standings(contest_id=2, phase=ContestPhase.CODING)})
    svc = StandingsService(live, clock=clock.monotonic)  # type: ignore[arg-type]
    await svc.get(2)
    clock.advance(61)
    await svc.get(2)
    assert live.full_fetches == 2  # running contests only one minute


async def test_manual_refresh_is_throttled() -> None:
    clock = FakeClock()
    service, source = _service(clock)
    await service.get(1)
    clock.advance(10)
    await service.get(1, refresh=True)
    assert source.full_fetches == 1
    clock.advance(6)
    await service.get(1, refresh=True)
    assert source.full_fetches == 2


async def test_concurrent_requests_share_one_fetch() -> None:
    source = FakeSource([], standings={1: make_standings(contest_id=1)}, delay_s=0.05)
    service = StandingsService(source)  # type: ignore[arg-type]
    await asyncio.gather(*(service.get(1) for _ in range(10)))
    assert source.full_fetches == 1


async def test_cache_is_bounded_and_failures_are_not_cached() -> None:
    standings = {i: make_standings(contest_id=i, rows=1, problems=1) for i in range(1, 12)}
    source = FakeSource([], standings=standings)
    service = StandingsService(source)  # type: ignore[arg-type]
    for i in range(1, 12):
        await service.get(i)
    await service.get(1)  # evicted long ago
    assert source.full_fetches == 12

    source.fail = True
    with pytest.raises(RetryableSourceError):
        await service.get(2)
    source.fail = False
    await service.get(2)
    assert source.full_fetches == 14


def _body(rows: str, status: str = "OK") -> bytes:
    contest = {
        "id": 7,
        "name": "C",
        "type": "ICPC",
        "phase": "FINISHED",
        "durationSeconds": 7200,
        "startTimeSeconds": 1700000000,
    }
    problems = json.dumps([{"index": "A", "name": "a"}, {"index": "B", "name": "b"}])
    head = f'{{"status":"{status}","result":{{"contest":{json.dumps(contest)},'
    return (head + f'"problems":{problems},"rows":[{rows}]}}}}').encode()


def test_full_parser_keeps_teams_and_every_problem() -> None:
    solo = {
        "party": {"members": [{"handle": "solo"}], "participantType": "CONTESTANT"},
        "rank": 1,
        "points": 2.0,
        "penalty": 90,
        "problemResults": [
            {"points": 1.0, "rejectedAttemptCount": 1, "bestSubmissionTimeSeconds": 600},
            {"points": 0.0, "rejectedAttemptCount": 2, "type": "FINAL"},
        ],
    }
    team = {
        "party": {
            "members": [{"handle": "a"}, {"handle": "b"}],
            "teamName": "The Team",
            "participantType": "CONTESTANT",
        },
        "rank": 2,
        "points": 1.0,
        "penalty": 300,
        "problemResults": [
            {
                "points": 1.0,
                "rejectedAttemptCount": 0,
                "bestSubmissionTimeSeconds": 60,
                "type": "PRELIMINARY",
            },
            {"points": 0.0, "rejectedAttemptCount": 0},
        ],
    }
    parsed = parse_full_standings(_body(json.dumps(solo) + "," + json.dumps(team)), fetched_at=NOW)
    assert [p.index for p in parsed.problems] == ["A", "B"]
    assert [r.who for r in parsed.rows] == ["solo", "The Team"]
    assert parsed.rows[1].handles == ("a", "b")
    assert parsed.rows[0].problems[1].status is ProblemStatus.REJECTED
    assert parsed.rows[1].problems[0].status is ProblemStatus.PROVISIONAL
    assert parsed.contest.kind == "ICPC"


def test_full_parser_rejects_failures_and_truncation() -> None:
    with pytest.raises(PermanentSourceError):
        parse_full_standings(
            b'{"status":"FAILED","comment":"contestId: Contest with id 1 not found"}',
            fetched_at=NOW,
        )
    with pytest.raises(RetryableSourceError):
        parse_full_standings(_body("")[:-30], fetched_at=NOW)
