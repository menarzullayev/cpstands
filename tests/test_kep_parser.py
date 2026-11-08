from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from cpstands.domain.contest import ContestPhase, ProblemStatus
from cpstands.sources.base import SourceFormatError
from cpstands.sources.kep.parser import (
    contest_kind,
    parse_attempts,
    parse_contest,
    parse_contest_detail,
    parse_contest_page,
    parse_contest_rating_changes,
    parse_full_standings,
    parse_problems,
    parse_rating_history,
    parse_standings,
    parse_user_rating,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "kep"
FETCHED_AT = datetime(2026, 11, 8, tzinfo=UTC)


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def raw_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = json.loads(fixture("contestants_502.json"))
    return rows


def contest_and_problems() -> tuple[Any, Any]:
    contest, _ = parse_contest_detail(fixture("contest_502.json"))
    return contest, parse_problems(fixture("problems_502.json"))


def test_fixtures_carry_no_personal_data() -> None:
    for path in FIXTURES.glob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert "s3.amazonaws.com/media/images/avatars" not in text, path.name
    for row in raw_rows():
        assert row["userFullName"] == ""
        assert row["avatar"] is None
        assert row["country"] is None


# --- contests -------------------------------------------------------------------------------


def test_contest_page_phases_kinds_and_times() -> None:
    page = parse_contest_page(fixture("contests_page1.json"))
    assert page.skipped == 0
    assert page.pages_count == 29
    assert len(page.contests) == 10
    first = page.contests[0]
    assert (first.platform, first.external_id, first.name) == ("kep", 504, "KEP Contest #23")
    assert first.phase is ContestPhase.BEFORE
    assert first.starts_at == datetime(2026, 11, 8, 15, 35, tzinfo=UTC)
    assert first.duration_s == 2 * 3600 + 30 * 60
    assert first.kind == "ICPC"
    assert {c.phase for c in page.contests[1:]} == {ContestPhase.FINISHED}
    assert {c.kind for c in page.contests} == {"ICPC", "IOI"}


@pytest.mark.parametrize(
    ("code", "kind"),
    [("ACM10M", "ICPC"), ("ACM", "ICPC"), ("IOI", "IOI"), ("ioi", "IOI"), ("LOL", "LOL")],
)
def test_contest_kind_mapping(code: str, kind: str) -> None:
    assert contest_kind(code) == kind


def entry(**changes: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": 7,
        "title": "T",
        "status": 0,
        "startTime": "2026-11-08T15:35:00Z",
        "finishTime": "2026-11-08T18:05:00Z",
        "type": "IOI",
    }
    base.update(changes)
    return base


def test_status_zero_is_a_running_contest() -> None:
    contest = parse_contest(entry(status=0))
    assert contest.phase is ContestPhase.CODING
    assert contest.phase.is_active
    assert contest.kind == "IOI"


def test_unnormalizable_list_entries_are_counted_not_fatal() -> None:
    body = json.dumps(
        {
            "pagesCount": 1,
            "data": [entry(), entry(status=5), entry(id="x"), entry(startTime="soon"), "junk"],
        }
    ).encode()
    page = parse_contest_page(body)
    assert len(page.contests) == 1
    assert page.skipped == 4


def test_contest_without_finish_time_has_no_duration() -> None:
    assert parse_contest(entry(finishTime=None)).duration_s is None


def test_detail_reports_rated_flag() -> None:
    contest, rated = parse_contest_detail(fixture("contest_502.json"))
    assert contest.phase is ContestPhase.FINISHED
    assert rated is True
    _, rated_off = parse_contest_detail(json.dumps({**entry(), "isRated": False}).encode())
    assert rated_off is False


# --- problems -------------------------------------------------------------------------------


def test_problems_keep_contest_order() -> None:
    problems = parse_problems(fixture("problems_502.json"))
    assert [p.index for p in problems] == [
        "A",
        "B1",
        "B2",
        "C1",
        "C2",
        "D",
        "E1",
        "E2",
        "F",
        "G",
        "H",
        "I",
    ]
    assert problems[0].name == "0gur4ik Nihoyat M"
    assert problems[0].points == 1.0


def test_problem_without_ball_has_no_points() -> None:
    (problem,) = parse_problems(json.dumps([{"symbol": "A", "problem": {"title": "t"}}]).encode())
    assert problem.points is None


# --- standings ------------------------------------------------------------------------------


def test_rows_are_returned_in_problem_order_not_response_order() -> None:
    contest, problems = contest_and_problems()
    rows = raw_rows()
    sample = next(r for r in rows if r["username"] == "user_004")
    symbols = [i["problemSymbol"] for i in sample["problemsInfo"]]
    assert symbols != sorted(symbols, key=[p.index for p in problems].index)  # shuffled upstream
    snapshot = parse_standings(
        contest, problems, fixture("contestants_502.json"), frozenset({"user_004"})
    )
    (result,) = snapshot.results
    assert len(result.problems) == len(problems)
    by_symbol = {i["problemSymbol"]: i for i in sample["problemsInfo"]}
    for problem, got in zip(problems, result.problems, strict=True):
        raw = by_symbol.get(problem.index, {"points": 0, "attemptsCount": 0})
        assert (got.points > 0) == (raw["points"] > 0)
        assert got.rejected_attempts == raw["attemptsCount"]


def test_standings_keep_only_watched_handles_case_insensitively() -> None:
    contest, problems = contest_and_problems()
    snapshot = parse_standings(
        contest,
        problems,
        fixture("contestants_502.json"),
        frozenset({"user_004", "user_005", "nobody"}),
    )
    assert [r.key for r in snapshot.results] == ["user_004", "user_005"]
    assert snapshot.rows_scanned == 65
    assert snapshot.team_rows_skipped == 0
    assert snapshot.contest is contest
    row = snapshot.results[0]
    # kep.uz says rank 4: three virtual rows are above it. The site, and so the bot, says 1.
    assert (row.handle, row.rank, row.points, row.penalty) == ("user_004", 1, 11.0, 385)
    assert row.official


def test_virtual_rows_are_left_out_like_on_the_site() -> None:
    contest, problems = contest_and_problems()
    snapshot = parse_standings(
        contest, problems, fixture("contestants_502.json"), frozenset({"user_003", "user_001"})
    )
    # user_003 has only virtual rows; user_001 one virtual and one real row (no points).
    assert [(r.key, r.participant_type) for r in snapshot.results] == [("user_001", "CONTESTANT")]
    full = parse_full_standings(
        contest, problems, fixture("contestants_502.json"), fetched_at=FETCHED_AT
    )
    assert len(full.rows) == 56  # 65 rows, 9 of them virtual
    assert all(r.participant_type == "CONTESTANT" for r in full.rows)


def test_official_ranks_match_the_kep_uz_standings_page() -> None:
    """Contest 502 on kep.uz (2026-11-08): 1 potato167 11 (385), 2 _sunflower_ 11 (390),
    3 physics 10 (348), ... and NarzullayevMe 23rd; the API gives them 4, 5, 7 and 27."""
    contest, problems = contest_and_problems()
    full = parse_full_standings(
        contest, problems, fixture("contestants_502.json"), fetched_at=FETCHED_AT
    )
    top = [(r.rank, r.points, r.penalty) for r in full.rows[:8]]
    assert top == [
        (1, 11, 385), (2, 11, 390), (3, 10, 348), (4, 10, 463),
        (5, 9, 353), (6, 9, 406), (7, 8, 284), (8, 8, 288),
    ]  # fmt: skip
    assert [r.rank for r in full.rows if (r.points, r.penalty) == (6, 68)] == [23]


def test_equal_scores_share_a_rank() -> None:
    contest, problems = contest_and_problems()
    rows = json.loads(fixture("contestants_502.json"))
    real = [r for r in rows if not r["isVirtual"]]
    real[1]["points"], real[1]["penalties"] = real[0]["points"], real[0]["penalties"]
    full = parse_full_standings(contest, problems, json.dumps(rows).encode(), fetched_at=FETCHED_AT)
    assert [r.rank for r in full.rows[:3]] == [1, 1, 3]


def test_solved_and_rejected_counts_match_the_icpc_formula() -> None:
    contest, problems = contest_and_problems()
    full = parse_full_standings(
        contest, problems, fixture("contestants_502.json"), fetched_at=FETCHED_AT
    )
    assert len(full.rows) == 56
    assert full.expires_at is None
    for row in full.rows:
        accepted = [p for p in row.problems if p.status is ProblemStatus.ACCEPTED]
        assert row.points == len(accepted)
        # penalty = sum(solve minutes + 10 * rejected attempts before the accepted one)
        expected = sum((p.time_s or 0) // 60 + 10 * p.rejected_attempts for p in accepted)
        assert row.penalty == expected
        for p in row.problems:
            if p.status is ProblemStatus.ACCEPTED:
                assert p.time_s is not None
            else:
                assert p.time_s is None
                assert p.points == 0


def test_problem_states() -> None:
    contest, problems = contest_and_problems()
    full = parse_full_standings(
        contest, problems, fixture("contestants_502.json"), fetched_at=FETCHED_AT
    )
    states = {p.status for row in full.rows for p in row.problems}
    assert states == {ProblemStatus.ACCEPTED, ProblemStatus.REJECTED, ProblemStatus.NOT_TRIED}
    rejected_only = next(
        r for r in full.rows if r.points == 0 and any(p.rejected_attempts for p in r.problems)
    )
    assert all(p.status is not ProblemStatus.ACCEPTED for p in rejected_only.problems)


def test_solve_time_is_hours_and_minutes_from_the_start() -> None:
    contest, problems = contest_and_problems()
    body = json.dumps(
        [
            {
                "username": "u",
                "rank": 1,
                "points": 1,
                "penalties": 93,
                "problemsInfo": [
                    {"problemSymbol": "E2", "points": 1, "attemptsCount": 1, "contestTime": "01:23"}
                ],
            }
        ]
    ).encode()
    (result,) = parse_standings(contest, problems, body, frozenset({"u"})).results
    solved = result.problems[problems.index(next(p for p in problems if p.index == "E2"))]
    assert solved.time_s == 83 * 60
    assert solved.rejected_attempts == 1
    assert sum(p.status is ProblemStatus.NOT_TRIED for p in result.problems) == len(problems) - 1


def test_team_rows_are_skipped_in_a_snapshot() -> None:
    contest, problems = contest_and_problems()
    body = json.dumps(
        [{"username": "squad", "team": {"id": 1}, "rank": 1, "points": 0, "problemsInfo": []}]
    ).encode()
    snapshot = parse_standings(contest, problems, body, frozenset({"squad"}))
    assert snapshot.results == ()
    assert snapshot.team_rows_skipped == 1


# --- privacy --------------------------------------------------------------------------------


def test_full_names_never_reach_domain_objects() -> None:
    contest, problems = contest_and_problems()
    canary = "Zyxwvut Qponmlkj"
    avatar = "https://cdn.example/avatars/canary-avatar.webp"
    rows = raw_rows()
    for row in rows[:6]:
        row["userFullName"] = canary
        row["avatar"] = avatar
        row["country"] = "zz"
    body = json.dumps(rows).encode()
    watched = frozenset(r["username"] for r in rows[:6])
    snapshot = parse_standings(contest, problems, body, watched)
    full = parse_full_standings(contest, problems, body, fetched_at=FETCHED_AT)
    changes = parse_contest_rating_changes(body)
    assert snapshot.results
    for dumped in (repr(snapshot), repr(full), repr(changes)):
        assert canary not in dumped
        assert "Zyxwvut" not in dumped
        assert "canary-avatar" not in dumped
        assert "'zz'" not in dumped


# --- rating changes -------------------------------------------------------------------------


def test_contest_rating_changes_skip_virtual_and_unrated_rows() -> None:
    changes = parse_contest_rating_changes(fixture("contestants_502.json"))
    assert len(changes) == 56
    first = next(c for c in changes if c.handle == "user_004")
    assert (first.rank, first.old_rating, first.new_rating, first.delta) == (4, 1785, 1997, 212)
    handles = [c.handle for c in changes]
    assert "user_003" not in handles  # only virtual rows
    assert handles.count("user_001") == 1  # its virtual row is skipped, its real row is kept


def test_unrated_real_row_is_skipped() -> None:
    body = json.dumps(
        [
            {"username": "a", "rank": 1, "rating": 1500, "newRating": 1510, "isUnrated": True},
            {"username": "b", "rank": 2, "rating": 1500, "newRating": 1490, "isUnrated": False},
        ]
    ).encode()
    assert [c.handle for c in parse_contest_rating_changes(body)] == ["b"]


def test_rating_history_old_is_new_minus_delta_oldest_first() -> None:
    history = parse_rating_history(fixture("rating_changes_user.json"))
    assert [c.contest_id for c in history] == [497, 498, 502]
    last = history[-1]
    assert (last.old_rating, last.new_rating, last.delta, last.rank) == (1787, 1914, 127, 5)
    assert last.at == datetime(2026, 9, 19, tzinfo=UTC)
    assert last.contest_name == "KEP Contest #22"
    assert parse_rating_history(b"[]") == ()


def test_user_rating_and_unrated_default() -> None:
    rated = parse_user_rating(fixture("rating_user.json"))
    assert (rated.handle, rated.rating, rated.max_rating) == ("demo_user", 1914, 1914)
    assert (rated.rank, rated.max_rank) == ("Master", "Master")
    fresh = parse_user_rating(fixture("rating_unrated.json"))
    assert fresh.handle == "demo_new"
    assert (fresh.rating, fresh.max_rating, fresh.rank, fresh.max_rank) == (None, None, None, None)


# --- attempts -------------------------------------------------------------------------------


def test_attempts_skip_non_contest_rows_and_map_verdicts() -> None:
    page = parse_attempts(fixture("attempts_user_p1.json"))
    assert page.pages_count == 3
    assert len(page.submissions) == 15  # 5 of the 20 attempts belong to no contest
    newest = page.submissions[0]
    assert (newest.submission_id, newest.contest_id, newest.problem_index) == (441620, 502, "I")
    assert newest.accepted
    assert newest.participant_type == "PRACTICE"  # solved after the contest (no contestTime)
    assert newest.created_at == datetime(2026, 9, 19, 17, 59, 54, 459880, tzinfo=UTC)
    verdicts = {s.verdict for s in page.submissions}
    assert {"OK", "MEMORY_LIMIT_EXCEEDED", "COMPILATION_ERROR"} <= verdicts
    in_contest = [s for s in page.submissions if s.participant_type == "CONTESTANT"]
    assert in_contest


def test_pending_and_unknown_verdict_codes() -> None:
    def attempt(code: int) -> dict[str, Any]:
        return {
            "id": code + 100,
            "verdict": code,
            "contestProblem": {"contest": 1, "symbol": "A"},
            "created": "2026-01-01T00:00:00+05:00",
        }

    body = json.dumps({"pagesCount": 1, "data": [attempt(-1), attempt(15), attempt(99)]}).encode()
    verdicts = {s.submission_id: s.verdict for s in parse_attempts(body).submissions}
    assert verdicts == {99: None, 115: "OK", 199: "KEP_99"}


# --- malformed input ------------------------------------------------------------------------

BAD_JSON = b"<html>Not Found</html>"


@pytest.mark.parametrize(
    "call",
    [
        lambda b: parse_contest_page(b),
        lambda b: parse_contest_detail(b),
        lambda b: parse_problems(b),
        lambda b: parse_contest_rating_changes(b),
        lambda b: parse_rating_history(b),
        lambda b: parse_user_rating(b),
        lambda b: parse_attempts(b),
    ],
)
@pytest.mark.parametrize("body", [BAD_JSON, b"", b"null", b"42", b'"text"', b"{"])
def test_garbage_bodies_raise_source_format_error(body: bytes, call: Any) -> None:
    with pytest.raises(SourceFormatError):
        call(body)


def test_wrong_inner_shapes_raise_source_format_error() -> None:
    contest, problems = contest_and_problems()
    with pytest.raises(SourceFormatError):
        parse_contest_page(b'{"data": "nope"}')
    with pytest.raises(SourceFormatError):
        parse_contest_detail(b'{"id": 1}')
    with pytest.raises(SourceFormatError):
        parse_problems(b'[{"symbol": "A"}]')
    with pytest.raises(SourceFormatError):
        parse_standings(contest, problems, b'{"rows": []}', frozenset())
    with pytest.raises(SourceFormatError):
        parse_standings(contest, problems, b'[{"rank": 1}]', frozenset({"x"}))
    with pytest.raises(SourceFormatError):
        parse_standings(contest, problems, b'["row"]', frozenset({"x"}))
    with pytest.raises(SourceFormatError):
        parse_full_standings(
            contest, problems, b'[{"username": "u", "rank": "high"}]', fetched_at=FETCHED_AT
        )
    with pytest.raises(SourceFormatError):
        parse_rating_history(b'[{"contestId": 1}]')
    with pytest.raises(SourceFormatError):
        parse_user_rating(b'{"rating": 1}')
    with pytest.raises(SourceFormatError):
        parse_contest_rating_changes(b'[{"username": "u", "rank": 1}]')
    with pytest.raises(SourceFormatError):
        parse_attempts(b'{"data": [{"verdict": 1, "contestProblem": {}}]}')


def test_malformed_solve_time_is_a_format_error() -> None:
    contest, problems = contest_and_problems()
    body = json.dumps(
        [
            {
                "username": "u",
                "rank": 1,
                "problemsInfo": [{"problemSymbol": "A", "points": 1, "contestTime": "soon"}],
            }
        ]
    ).encode()
    with pytest.raises(SourceFormatError):
        parse_standings(contest, problems, body, frozenset({"u"}))
