"""Parsing of kep.uz API responses (pure functions, no I/O).

Measured facts about the undocumented API (2026-11-08) that the parsers rely on:

* contest ``status``: -1 not started, 0 running, 1 finished (the site's own constants);
* a contestants row lists ``problemsInfo`` in arbitrary order, keyed by ``problemSymbol``;
  a problem is solved when ``points > 0``; ``attemptsCount`` is the number of rejected attempts
  before the accepted one (solved: ``penalties == minutes + 10 * attemptsCount`` for ACM10M);
* ``contestTime`` is ``HH:MM`` from the start of the contest for solved problems, else null;
* before the start, ``/problems/`` and ``/contestants/`` answer 401 (the contest detail is public);
* virtual participants are separate rows (``isVirtual``) that share the table and its ranks;
  the site's own standings hide them and rank the rest, so the parsers do the same
  (checked against kep.uz for contest 502: potato167 is rank 4 in the API, 1 on the site);
* ``rowType`` and ``isOfficial`` carry no usable signal.

Privacy: only the public ``username`` is read from a participant row. Full names, avatars and
countries are never looked at, so they cannot reach a domain object.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any

from cpstands.domain.contest import (
    Contest,
    ContestPhase,
    ContestRatingChange,
    FullStandings,
    ParticipantResult,
    Problem,
    ProblemResult,
    ProblemStatus,
    RatingChange,
    StandingRow,
    StandingsSnapshot,
    Submission,
    UserRating,
    handle_key,
)
from cpstands.sources.base import PermanentSourceError, SourceFormatError

PLATFORM = "kep"

_STATUS_PHASES = {-1: ContestPhase.BEFORE, 0: ContestPhase.CODING, 1: ContestPhase.FINISHED}

# Verdict codes of GET /attempts/verdicts/ (measured). Codes -2/-1 mean "not judged yet".
_PENDING_VERDICTS = frozenset({-2, -1})
_VERDICTS = {
    0: "JUDGE_ERROR",
    1: "OK",
    2: "WRONG_ANSWER",
    3: "TIME_LIMIT_EXCEEDED",
    4: "RUNTIME_ERROR",
    5: "PRESENTATION_ERROR",
    6: "MEMORY_LIMIT_EXCEEDED",
    7: "REJECTED",
    8: "COMPILATION_ERROR",
    9: "EXECUTION_ERROR",
    10: "IDLENESS_LIMIT_EXCEEDED",
    11: "SYNTAX_ERROR",
    12: "CHECKER_NOT_FOUND",
    15: "OK",
    16: "PARTIAL",
}


class ContestUnavailableError(PermanentSourceError):
    """The contest is unknown, not started (tables answer 401) or not usable for the request."""


@dataclass(frozen=True, slots=True)
class ContestPage:
    contests: tuple[Contest, ...]
    skipped: int
    pages_count: int


@dataclass(frozen=True, slots=True)
class AttemptsPage:
    submissions: tuple[Submission, ...]
    pages_count: int


def _load(body: bytes, what: str) -> Any:
    try:
        return json.loads(body)
    except (ValueError, RecursionError) as exc:
        raise SourceFormatError(f"{what} body is not valid JSON") from exc


def _object(body: bytes, what: str) -> dict[str, Any]:
    document = _load(body, what)
    if not isinstance(document, dict):
        raise SourceFormatError(f"{what} is not an object")
    return document


def _array(body: bytes, what: str) -> list[Any]:
    document = _load(body, what)
    if not isinstance(document, list):
        raise SourceFormatError(f"{what} is not an array")
    return document


def _page_data(body: bytes, what: str) -> tuple[list[Any], int]:
    document = _object(body, what)
    data = document.get("data")
    if not isinstance(data, list):
        raise SourceFormatError(f"{what} has no data array")
    pages = document.get("pagesCount")
    return data, pages if isinstance(pages, int) and not isinstance(pages, bool) else 1


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp is not a string")
    moment = datetime.fromisoformat(value)
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment.astimezone(UTC)


def contest_kind(code: str) -> str:
    """Normalize a kep contest type code: ACM* is ICPC-like, IOI is points; others pass through."""
    if code.upper().startswith("ACM"):
        return "ICPC"
    if code.upper() == "IOI":
        return "IOI"
    return code


def parse_contest(raw: object) -> Contest:
    try:
        if not isinstance(raw, dict):
            raise TypeError("contest entry is not an object")
        phase = _STATUS_PHASES[raw["status"]]
        start = _timestamp(raw["startTime"])
        finish = raw.get("finishTime")
        duration = int((_timestamp(finish) - start).total_seconds()) if finish else None
        return Contest(
            platform=PLATFORM,
            external_id=int(raw["id"]),
            name=str(raw["title"]),
            phase=phase,
            kind=contest_kind(str(raw.get("type", ""))),
            starts_at=start,
            duration_s=duration,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise SourceFormatError(f"malformed contest entry: {type(exc).__name__}") from exc


def parse_contest_page(body: bytes) -> ContestPage:
    """Parse ``/contests/?page=N``; entries that cannot be normalized are counted, not fatal."""
    data, pages = _page_data(body, "contest list")
    contests: list[Contest] = []
    skipped = 0
    for entry in data:
        try:
            contests.append(parse_contest(entry))
        except SourceFormatError:
            skipped += 1
    return ContestPage(contests=tuple(contests), skipped=skipped, pages_count=pages)


def parse_contest_detail(body: bytes) -> tuple[Contest, bool]:
    """Parse ``/contests/{id}/`` into the contest and whether it is rated."""
    document = _object(body, "contest detail")
    return parse_contest(document), document.get("isRated") is True


def parse_problems(body: bytes) -> tuple[Problem, ...]:
    """Parse ``/contests/{id}/problems/``; the order of the response is the contest order."""
    problems: list[Problem] = []
    for item in _array(body, "problem list"):
        try:
            ball = item.get("ball")
            problems.append(
                Problem(
                    index=str(item["symbol"]),
                    name=str(item["problem"]["title"]),
                    points=float(ball) if isinstance(ball, int | float) else None,
                )
            )
        except (KeyError, TypeError, AttributeError) as exc:
            raise SourceFormatError(f"malformed problem entry: {type(exc).__name__}") from exc
    return tuple(problems)


def _contest_seconds(value: object) -> int | None:
    """``HH:MM`` (or ``HH:MM:SS``) from the contest start, in seconds; ``None`` when absent."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("contestTime is not a string")
    parts = [int(p) for p in value.split(":")]
    if len(parts) not in (2, 3) or any(p < 0 for p in parts):
        raise ValueError("bad contestTime")
    seconds = parts[0] * 3600 + parts[1] * 60
    return seconds + (parts[2] if len(parts) == 3 else 0)


def _problem_result(raw: dict[str, Any]) -> ProblemResult:
    points = float(raw.get("points", 0))
    rejected = int(raw.get("attemptsCount", 0))
    if points > 0:
        status = ProblemStatus.ACCEPTED
    elif rejected > 0:
        status = ProblemStatus.REJECTED
    else:
        status = ProblemStatus.NOT_TRIED
    return ProblemResult(
        status=status,
        rejected_attempts=rejected,
        time_s=_contest_seconds(raw.get("contestTime")) if points > 0 else None,
        points=points,
    )


_NOT_TRIED = ProblemResult(ProblemStatus.NOT_TRIED, 0, None, 0.0)


@dataclass(frozen=True, slots=True)
class _Row:
    username: str
    rank: int
    points: float
    penalty: int
    virtual: bool
    team: bool
    problems: dict[str, ProblemResult]

    @property
    def participant_type(self) -> str:
        return "VIRTUAL" if self.virtual else "CONTESTANT"

    def ordered(self, problems: tuple[Problem, ...]) -> tuple[ProblemResult, ...]:
        return tuple(self.problems.get(p.index, _NOT_TRIED) for p in problems)


def _username(raw: object) -> str:
    if not isinstance(raw, dict):
        raise SourceFormatError("malformed standings row: not an object")
    username = raw.get("username")
    if not isinstance(username, str) or not username.strip():
        raise SourceFormatError("malformed standings row: no username")
    return username


def _row(raw: dict[str, Any]) -> _Row:
    try:
        infos: dict[str, ProblemResult] = {}
        for info in raw["problemsInfo"]:
            infos.setdefault(str(info["problemSymbol"]), _problem_result(info))
        return _Row(
            username=_username(raw),
            rank=int(raw["rank"]),
            points=float(raw.get("points", 0)),
            penalty=int(raw.get("penalties", 0)),
            virtual=raw.get("isVirtual") is True,
            team=raw.get("team") is not None,
            problems=infos,
        )
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise SourceFormatError(f"malformed standings row: {type(exc).__name__}") from exc


def _contestant_items(body: bytes) -> list[Any]:
    return _array(body, "contestants")


def _official(items: list[Any]) -> list[tuple[_Row, int]]:
    """The non-virtual rows in table order, each with its rank among them.

    Rows with the same points and penalty share a rank, as on the site.
    """
    found: list[tuple[_Row, int]] = []
    previous: tuple[float, int] | None = None
    rank = 0
    for position, row in enumerate((r for r in map(_row, items) if not r.virtual), start=1):
        score = (row.points, row.penalty)
        if score != previous:
            rank, previous = position, score
        found.append((row, rank))
    return found


def parse_standings(
    contest: Contest, problems: tuple[Problem, ...], body: bytes, watched: frozenset[str]
) -> StandingsSnapshot:
    """Keep only the rows of ``watched`` handle keys (kep has no server-side filter)."""
    items = _contestant_items(body)
    for raw in items:
        _username(raw)  # every row must be well formed, watched or not
    results: list[ParticipantResult] = []
    skipped_teams = 0
    for row, rank in _official(items):
        if handle_key(row.username) not in watched:
            continue
        if row.team:
            skipped_teams += 1
            continue
        results.append(
            ParticipantResult(
                handle=row.username,
                key=handle_key(row.username),
                rank=rank,
                points=row.points,
                penalty=row.penalty,
                participant_type=row.participant_type,
                problems=row.ordered(problems),
            )
        )
    return StandingsSnapshot(
        contest=contest,
        problems=problems,
        results=tuple(results),
        rows_scanned=len(items),
        team_rows_skipped=skipped_teams,
    )


def parse_full_standings(
    contest: Contest, problems: tuple[Problem, ...], body: bytes, *, fetched_at: datetime
) -> FullStandings:
    rows: list[StandingRow] = []
    for row, rank in _official(_contestant_items(body)):
        rows.append(
            StandingRow(
                rank=rank,
                who=row.username,
                handles=(row.username,),
                points=row.points,
                penalty=row.penalty,
                participant_type=row.participant_type,
                problems=row.ordered(problems),
            )
        )
    return FullStandings(
        contest=contest, problems=problems, rows=tuple(rows), fetched_at=fetched_at
    )


def parse_contest_rating_changes(body: bytes) -> tuple[ContestRatingChange, ...]:
    """Rating changes derived from contestants rows; virtual and unrated rows are skipped."""
    changes: list[ContestRatingChange] = []
    for raw in _contestant_items(body):
        username = _username(raw)
        if raw.get("isVirtual") is True or raw.get("isUnrated") is True:
            continue
        try:
            changes.append(
                ContestRatingChange(
                    handle=username,
                    rank=int(raw["rank"]),
                    old_rating=int(raw["rating"]),
                    new_rating=int(raw["newRating"]),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SourceFormatError("malformed contestants rating fields") from exc
    return tuple(changes)


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def parse_user_rating(body: bytes) -> UserRating:
    """Parse ``/contests-rating/{username}/``; a user with no rated contest is unrated.

    kep reports a default rating of 1200 for users with ``contestantsCount == 0``; that is not
    a real rating, so those users get ``None`` fields.
    """
    document = _object(body, "user rating")
    handle = document.get("username")
    if not isinstance(handle, str) or not handle:
        raise SourceFormatError("user rating without username")
    if _optional_int(document.get("contestantsCount")) in (None, 0):
        return UserRating(handle=handle, rating=None, max_rating=None, rank=None, max_rank=None)
    return UserRating(
        handle=handle,
        rating=_optional_int(document.get("rating")),
        max_rating=_optional_int(document.get("maxRating")),
        rank=_optional_str(document.get("ratingTitle")),
        max_rank=_optional_str(document.get("maxRatingTitle")),
    )


def parse_rating_history(body: bytes) -> tuple[RatingChange, ...]:
    """Parse ``/contests-rating/{username}/rating-changes/``, oldest first.

    kep gives only the contest start *date*, so ``at`` is midnight UTC of that day.
    """
    changes: list[RatingChange] = []
    for item in _array(body, "rating history"):
        try:
            new = int(item["newRating"])
            changes.append(
                RatingChange(
                    contest_id=int(item["contestId"]),
                    contest_name=str(item["contestTitle"]),
                    rank=int(item["rank"]),
                    old_rating=new - int(item["delta"]),
                    new_rating=new,
                    at=datetime.combine(
                        date.fromisoformat(str(item["contestStartDate"])), time(), tzinfo=UTC
                    ),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SourceFormatError("malformed rating history entry") from exc
    return tuple(sorted(changes, key=lambda c: (c.at, c.contest_id)))


def parse_attempts(body: bytes) -> AttemptsPage:
    """Parse ``/attempts/?username=``; attempts outside any contest problem are skipped."""
    data, pages = _page_data(body, "attempts")
    found: list[Submission] = []
    for item in data:
        try:
            link = item.get("contestProblem")
            if not isinstance(link, dict):
                continue  # practice problem outside a contest: nothing to upsolve
            code = item["verdict"]
            verdict = None if code in _PENDING_VERDICTS else _VERDICTS.get(code, f"KEP_{code}")
            found.append(
                Submission(
                    submission_id=int(item["id"]),
                    contest_id=int(link["contest"]),
                    problem_index=str(link["symbol"]),
                    problem_name=str(item.get("problemTitle", "")),
                    verdict=verdict,
                    participant_type="CONTESTANT" if item.get("contestTime") else "PRACTICE",
                    created_at=_timestamp(item["created"]),
                )
            )
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise SourceFormatError(f"malformed attempt entry: {type(exc).__name__}") from exc
    return AttemptsPage(submissions=tuple(found), pages_count=pages)


__all__ = [
    "PLATFORM",
    "AttemptsPage",
    "ContestPage",
    "ContestUnavailableError",
    "contest_kind",
    "parse_attempts",
    "parse_contest",
    "parse_contest_detail",
    "parse_contest_page",
    "parse_contest_rating_changes",
    "parse_full_standings",
    "parse_problems",
    "parse_rating_history",
    "parse_standings",
    "parse_user_rating",
]
