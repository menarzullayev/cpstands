"""Standings table styles: emoji (default) and classic, first solves, medals, followed rows."""

from __future__ import annotations

from datetime import UTC, datetime

from cpstands.bot import standings_view as view
from cpstands.domain.contest import (
    Contest,
    ContestPhase,
    FullStandings,
    Problem,
    ProblemResult,
    ProblemStatus,
    StandingRow,
)
from cpstands.i18n import I18n

SAY = I18n(custom_emoji=True).bound("en", "neutral")
EMOJI = view.ViewContext(style="emoji")
OK = ProblemStatus.ACCEPTED
NO = ProblemStatus.REJECTED
NOT = ProblemStatus.NOT_TRIED


def _row(rank: int, who: str, *cells: tuple[ProblemStatus, int, int | None]) -> StandingRow:
    problems = tuple(ProblemResult(s, tries, t, 1.0 if s is OK else 0.0) for s, tries, t in cells)
    solved = sum(1 for p in problems if p.status is OK)
    return StandingRow(rank, who, (who,), float(solved), 100 + rank, "CONTESTANT", problems)


def table(rows: int = 4) -> FullStandings:
    """alice solved A first; bob solved B first after one wrong try; carol tried B twice."""
    base = [
        _row(1, "alice", (OK, 0, 300), (OK, 0, 900)),
        _row(2, "bob", (OK, 0, 420), (OK, 1, 600)),
        _row(3, "carol", (OK, 0, 480), (NO, 2, None)),
        _row(4, "dave", (NOT, 0, None), (NOT, 0, None)),
    ]
    extra = [_row(i, f"user{i}", (OK, 0, 9000), (NOT, 0, None)) for i in range(5, rows + 1)]
    contest = Contest("kep", 504, "KEP Contest #23", ContestPhase.CODING, "ICPC", None, 7200)
    return FullStandings(
        contest=contest,
        problems=(Problem("A", "A", None), Problem("B", "B", None)),
        rows=tuple(base + extra),
        fetched_at=datetime(2026, 11, 8, 15, 40, tzinfo=UTC),
    )


def _rows(html: str) -> list[str]:
    return html.split("<tr>")[2:]


def test_the_emoji_style() -> None:
    html = view.render(table(), 0, 0, SAY, time_zone="UTC", ctx=EMOJI)
    assert "<table bordered compact>" in html
    alice, bob, carol, dave = _rows(html)
    assert view._emoji("🥇") in alice
    assert view._emoji("🥉") in carol
    assert "<td>4</td>" in dave
    # A first solve gets ⚡ and a bold time; any other solve 🟢; a failed try 🔴 with the count.
    assert f"{view._emoji('⚡')} <b>00:05</b>" in alice  # A: alice was first
    assert f"{'🟢'} 00:15" in alice  # B: bob was first
    assert f"{view._emoji('⚡')}<sup>1</sup> <b>00:10</b>" in bob
    assert f"{'🔴'}<sup>2</sup>" in carol
    assert "🟢" not in dave
    assert "🔴" not in dave


def test_the_classic_style_marks_first_solves_and_raises_attempts() -> None:
    ctx = view.ViewContext(style="classic")
    html = view.render(table(), 0, 0, SAY, time_zone="UTC", ctx=ctx)
    assert "<table bordered striped>" in html
    alice, bob, carol, _ = _rows(html)
    assert "<mark>+ 00:05</mark>" in alice
    assert "<td>+ 00:15</td>" in alice  # not first: no mark
    assert "<mark>+<sup>1</sup> 00:10</mark>" in bob
    assert "<td>-2</td>" in carol
    assert "🟢" not in html
    assert "⚡" not in html


def test_first_solves_count_the_whole_table_not_one_page() -> None:
    standings = table(rows=60)
    assert view.first_solves(standings) == [300, 600]
    second_page = view.render(standings, 1, 0, SAY, time_zone="UTC", ctx=EMOJI)
    assert "⚡" not in second_page  # the 9000 s solves on page two are not first


def test_a_followed_handle_stands_out_only_in_the_full_table() -> None:
    friends = frozenset({"bob"})
    full = view.render(table(), 0, 0, SAY, time_zone="UTC", ctx=view.ViewContext("all", friends))
    assert "<mark><b>bob</b></mark>" in full
    assert "<mark><b>alice</b></mark>" not in full
    mine = view.render(
        table(), 0, 0, SAY, time_zone="UTC", ctx=view.ViewContext("friends", friends)
    )
    assert "<mark><b>" not in mine  # every row there is a friend: nothing to pick out


def test_an_unknown_style_falls_back_to_plain_cells() -> None:
    result = ProblemResult(OK, 1, 600, 1.0)
    assert view.styled_cell(result, icpc=True, padded=True, style="neon", first=True) == "+1 00:10"


def test_kep_uz_names_one_first_solver_per_problem() -> None:
    """Contest 502: four people solved A at 00:00 (minutes only), kep.uz marks one of them."""
    from pathlib import Path

    from cpstands.sources.kep.parser import parse_full_standings, parse_problems

    root = Path(__file__).parent.parent / "fixtures" / "kep"
    problems = parse_problems((root / "problems_502.json").read_bytes())
    contest = table().contest
    standings = parse_full_standings(
        contest,
        problems,
        (root / "contestants_502.json").read_bytes(),
        fetched_at=datetime(2026, 11, 8, tzinfo=UTC),
    )
    at_zero = [r for r in standings.rows if r.problems[0].time_s == 0]
    assert len(at_zero) > 1
    firsts = [r.who for r in standings.rows if r.problems[0].first]
    assert firsts == ["user_026"]
    html = view.render(standings, 0, 0, SAY, time_zone="UTC", ctx=EMOJI)
    assert (
        html.count("⚡")
        == len(problems)
        - sum(  # one per solved problem on this page
            1
            for i in range(len(problems))
            if not any(r.problems[i].first for r in standings.rows[:25])
        )
    )


def test_a_solved_cell_uses_the_owners_green_dot() -> None:
    """The owner picked a minimal green dot (2026-11-08); a plain ✅ looked like spam."""
    html = view.render(table(), 0, 0, SAY, time_zone="UTC", ctx=EMOJI)
    assert "<td>🟢 00:15</td>" in html  # plain: it does not count toward the 100 limit
    assert "✅" not in html


def test_a_failed_problem_uses_the_owners_red_dot() -> None:
    """The owner picked a red dot for failed tries too (2026-11-08), replacing ❌."""
    html = view.render(table(), 0, 0, SAY, time_zone="UTC", ctx=EMOJI)
    assert "<td>🔴<sup>2</sup></td>" in html
    assert "❌" not in html


def test_a_page_never_carries_more_than_100_custom_emoji() -> None:
    """Telegram keeps the first 100 and shows the rest plain (measured: 201 sent, 100 kept)."""
    from tests.support.sources import make_standings

    big = make_standings(rows=60, problems=21)  # equal times: every solve ties for first
    html = view.render(big, 0, 0, SAY, time_zone="UTC", ctx=EMOJI)
    assert html.count("<tg-emoji") == view.MAX_CUSTOM_EMOJI
    assert "⚡" in html.split("<tg-emoji")[-1]  # the rest are still shown, as plain emoji


def test_the_cap_keeps_the_first_ones_and_unwraps_the_rest() -> None:
    tag = '<tg-emoji emoji-id="1">⚡</tg-emoji>'
    capped = view.cap_custom_emoji(tag * 3 + "x", limit=2)
    assert capped == tag * 2 + "⚡x"
    assert view.cap_custom_emoji(tag * 3, limit=5) == tag * 3  # under the limit: untouched


def test_the_classic_style_is_the_default() -> None:
    """Owner decision 2026-11-08: the striped classic table is the default."""
    assert view.ViewContext().style == "classic"
    html = view.render(table(), 0, 0, SAY, time_zone="UTC")
    assert "<table bordered striped>" in html
    assert "🟢" not in html
