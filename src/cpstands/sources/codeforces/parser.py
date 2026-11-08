"""Parsing of Codeforces API responses (pure functions, no I/O).

Standings are parsed with ijson's C backend row by row, so only rows of watched handles are
turned into domain objects and peak memory stays tiny even for ~7 MB bodies (NFR-002).
Key order in the JSON is not relied upon: contest, problems and rows are read in separate passes.
"""

from __future__ import annotations

import io
import json
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import ijson

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
from cpstands.sources.base import (
    PermanentSourceError,
    RetryableSourceError,
    SourceFormatError,
    UnknownHandleError,
)

PLATFORM = "codeforces"
_UNKNOWN_HANDLE_RE = re.compile(
    r"handles?: User with handle (?P<handle>.+?) not found", re.IGNORECASE
)


class ContestUnavailableError(PermanentSourceError):
    """The contest does not exist or has not started, so it has no standings."""


def raise_for_failed(comment: str) -> None:
    """Translate a Codeforces ``FAILED`` comment into a typed error."""
    match = _UNKNOWN_HANDLE_RE.search(comment)
    if match:
        raise UnknownHandleError(match.group("handle"))
    lowered = comment.lower()
    if "limit exceeded" in lowered:
        raise RetryableSourceError(f"rate limited: {comment}")
    if "contestid" in lowered and ("not found" in lowered or "has not started" in lowered):
        raise ContestUnavailableError(comment)
    raise PermanentSourceError(f"codeforces error: {comment}")


def check_envelope(status: object, comment: object) -> None:
    if status == "OK":
        return
    if status == "FAILED":
        raise_for_failed(str(comment or ""))
    raise SourceFormatError(f"unexpected status value: {status!r}")


def _timestamp(value: object) -> datetime | None:
    if isinstance(value, int | float):
        return datetime.fromtimestamp(float(value), tz=UTC)
    return None


def parse_phase(value: object) -> ContestPhase:
    try:
        return ContestPhase(str(value))
    except ValueError as exc:
        raise SourceFormatError(f"unknown contest phase: {value!r}") from exc


def parse_contest(raw: dict[str, Any]) -> Contest:
    try:
        duration = raw.get("durationSeconds")
        return Contest(
            platform=PLATFORM,
            external_id=int(raw["id"]),
            name=str(raw["name"]),
            phase=parse_phase(raw["phase"]),
            kind=str(raw.get("type", "")),
            starts_at=_timestamp(raw.get("startTimeSeconds")),
            duration_s=int(duration) if duration is not None else None,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise SourceFormatError(f"malformed contest entry: {type(exc).__name__}") from exc


def parse_contest_list(body: bytes) -> tuple[list[Contest], int]:
    """Parse ``contest.list``; entries that cannot be normalized are counted, not fatal."""
    try:
        document = json.loads(body)
    except ValueError as exc:
        raise RetryableSourceError("contest.list body is not valid JSON") from exc
    if not isinstance(document, dict):
        raise SourceFormatError("contest.list is not an object")
    check_envelope(document.get("status"), document.get("comment"))
    result = document.get("result")
    if not isinstance(result, list):
        raise SourceFormatError("contest.list has no result array")
    contests: list[Contest] = []
    skipped = 0
    for entry in result:
        try:
            contests.append(parse_contest(entry))
        except SourceFormatError:
            skipped += 1
    return contests, skipped


def parse_user_info(body: bytes) -> dict[str, str]:
    """Parse ``user.info`` into ``{handle_key: canonical handle}``."""
    try:
        document = json.loads(body)
    except ValueError as exc:
        raise RetryableSourceError("user.info body is not valid JSON") from exc
    if not isinstance(document, dict):
        raise SourceFormatError("user.info is not an object")
    check_envelope(document.get("status"), document.get("comment"))
    result = document.get("result")
    if not isinstance(result, list):
        raise SourceFormatError("user.info has no result array")
    known: dict[str, str] = {}
    for user in result:
        try:
            canonical = str(user["handle"])
        except (KeyError, TypeError) as exc:
            raise SourceFormatError("user.info entry without handle") from exc
        known[handle_key(canonical)] = canonical
    return known


def _problem_result(raw: dict[str, Any]) -> ProblemResult:
    points = float(raw.get("points", 0.0))
    rejected = int(raw.get("rejectedAttemptCount", 0))
    time_s = raw.get("bestSubmissionTimeSeconds")
    if points > 0:
        status = (
            ProblemStatus.PROVISIONAL
            if raw.get("type") == "PRELIMINARY"
            else ProblemStatus.ACCEPTED
        )
    elif rejected > 0:
        status = ProblemStatus.REJECTED
    else:
        status = ProblemStatus.NOT_TRIED
    return ProblemResult(
        status=status,
        rejected_attempts=rejected,
        time_s=int(time_s) if time_s is not None else None,
        points=points,
    )


def parse_row(raw: dict[str, Any]) -> ParticipantResult | None:
    """Normalize one standings row; return ``None`` for team rows (not supported in R1)."""
    try:
        party = raw["party"]
        members = party["members"]
        if len(members) != 1:
            return None
        handle = str(members[0]["handle"])
        return ParticipantResult(
            handle=handle,
            key=handle_key(handle),
            rank=int(raw["rank"]),
            points=float(raw.get("points", 0.0)),
            penalty=int(raw.get("penalty", 0)),
            participant_type=str(party.get("participantType", "")),
            problems=tuple(_problem_result(item) for item in raw["problemResults"]),
        )
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise SourceFormatError(f"malformed standings row: {type(exc).__name__}") from exc


def _items(body: bytes, prefix: str) -> Iterator[Any]:
    return iter(ijson.items(io.BytesIO(body), prefix, use_float=True))


def parse_standings(body: bytes, watched: frozenset[str]) -> StandingsSnapshot:
    """Parse a ``contest.standings`` body, keeping only rows of ``watched`` handle keys."""
    try:
        status = next(_items(body, "status"), None)
        comment = next(_items(body, "comment"), None)
    except ijson.JSONError as exc:
        raise RetryableSourceError("standings body is not valid JSON (truncated?)") from exc
    check_envelope(status, comment)
    try:
        raw_contest = next(_items(body, "result.contest"), None)
        if not isinstance(raw_contest, dict):
            raise SourceFormatError("standings response has no contest object")
        problems = tuple(
            Problem(
                index=str(item["index"]),
                name=str(item.get("name", "")),
                points=float(item["points"]) if "points" in item else None,
            )
            for item in _items(body, "result.problems.item")
        )
        results: list[ParticipantResult] = []
        scanned = 0
        skipped_teams = 0
        for raw_row in _items(body, "result.rows.item"):
            scanned += 1
            try:
                members = raw_row["party"]["members"]
                key = handle_key(str(members[0]["handle"]))
            except (KeyError, TypeError, IndexError) as exc:
                raise SourceFormatError("malformed standings row") from exc
            if len(members) != 1:
                skipped_teams += 1
                continue
            if key not in watched:
                continue
            row = parse_row(raw_row)
            if row is not None:
                results.append(row)
    except ijson.JSONError as exc:
        raise RetryableSourceError("standings body is not valid JSON (truncated?)") from exc
    return StandingsSnapshot(
        contest=parse_contest(raw_contest),
        problems=problems,
        results=tuple(results),
        rows_scanned=scanned,
        team_rows_skipped=skipped_teams,
    )


def _standing_row(raw: dict[str, Any]) -> StandingRow:
    try:
        party = raw["party"]
        handles = tuple(str(m["handle"]) for m in party["members"])
        who = str(party.get("teamName") or ", ".join(handles))
        return StandingRow(
            rank=int(raw["rank"]),
            who=who,
            handles=handles,
            points=float(raw.get("points", 0.0)),
            penalty=int(raw.get("penalty", 0)),
            participant_type=str(party.get("participantType", "")),
            problems=tuple(_problem_result(item) for item in raw["problemResults"]),
        )
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise SourceFormatError(f"malformed standings row: {type(exc).__name__}") from exc


def parse_full_standings(body: bytes, *, fetched_at: datetime) -> FullStandings:
    """Parse a ``contest.standings`` body into the whole table (teams included)."""
    try:
        check_envelope(next(_items(body, "status"), None), next(_items(body, "comment"), None))
        raw_contest = next(_items(body, "result.contest"), None)
        if not isinstance(raw_contest, dict):
            raise SourceFormatError("standings response has no contest object")
        problems = tuple(
            Problem(
                index=str(item["index"]),
                name=str(item.get("name", "")),
                points=float(item["points"]) if "points" in item else None,
            )
            for item in _items(body, "result.problems.item")
        )
        rows = tuple(_standing_row(raw) for raw in _items(body, "result.rows.item"))
    except ijson.JSONError as exc:
        raise RetryableSourceError("standings body is not valid JSON (truncated?)") from exc
    return FullStandings(
        contest=parse_contest(raw_contest), problems=problems, rows=rows, fetched_at=fetched_at
    )


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def parse_user_ratings(body: bytes) -> list[UserRating]:
    """Parse ``user.info`` into rating facts; unrated users have ``None`` ratings."""
    try:
        document = json.loads(body)
    except ValueError as exc:
        raise RetryableSourceError("user.info body is not valid JSON") from exc
    if not isinstance(document, dict):
        raise SourceFormatError("user.info is not an object")
    check_envelope(document.get("status"), document.get("comment"))
    result = document.get("result")
    if not isinstance(result, list):
        raise SourceFormatError("user.info has no result array")
    ratings: list[UserRating] = []
    for user in result:
        try:
            handle = str(user["handle"])
        except (KeyError, TypeError) as exc:
            raise SourceFormatError("user.info entry without handle") from exc
        rank = user.get("rank")
        max_rank = user.get("maxRank")
        ratings.append(
            UserRating(
                handle=handle,
                rating=_optional_int(user.get("rating")),
                max_rating=_optional_int(user.get("maxRating")),
                rank=rank if isinstance(rank, str) else None,
                max_rank=max_rank if isinstance(max_rank, str) else None,
            )
        )
    return ratings


def _result_list(body: bytes, what: str) -> list[dict[str, Any]]:
    try:
        document = json.loads(body)
    except ValueError as exc:
        raise RetryableSourceError(f"{what} body is not valid JSON") from exc
    if not isinstance(document, dict):
        raise SourceFormatError(f"{what} is not an object")
    check_envelope(document.get("status"), document.get("comment"))
    result = document.get("result")
    if not isinstance(result, list):
        raise SourceFormatError(f"{what} has no result array")
    return [item for item in result if isinstance(item, dict)]


def parse_rating_history(body: bytes) -> list[RatingChange]:
    """Parse ``user.rating`` into the rated contests of a user, oldest first."""
    changes: list[RatingChange] = []
    for item in _result_list(body, "user.rating"):
        try:
            changes.append(
                RatingChange(
                    contest_id=int(item["contestId"]),
                    contest_name=str(item["contestName"]),
                    rank=int(item["rank"]),
                    old_rating=int(item["oldRating"]),
                    new_rating=int(item["newRating"]),
                    at=datetime.fromtimestamp(float(item["ratingUpdateTimeSeconds"]), tz=UTC),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SourceFormatError("malformed user.rating entry") from exc
    return sorted(changes, key=lambda c: c.at)


def parse_contest_rating_changes(body: bytes) -> list[ContestRatingChange]:
    """Parse ``contest.ratingChanges`` into one entry per rated participant."""
    changes: list[ContestRatingChange] = []
    for item in _result_list(body, "contest.ratingChanges"):
        try:
            changes.append(
                ContestRatingChange(
                    handle=str(item["handle"]),
                    rank=int(item["rank"]),
                    old_rating=int(item["oldRating"]),
                    new_rating=int(item["newRating"]),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SourceFormatError("malformed contest.ratingChanges entry") from exc
    return changes


def parse_user_status(body: bytes) -> list[Submission]:
    """Parse ``user.status`` into submissions, newest first; gym and malformed rows are skipped."""
    found: list[Submission] = []
    for item in _result_list(body, "user.status"):
        problem = item.get("problem")
        author = item.get("author")
        if not isinstance(problem, dict) or not isinstance(author, dict):
            continue
        contest_id = item.get("contestId")
        if not isinstance(contest_id, int) or not isinstance(item.get("id"), int):
            continue  # a submission outside any contest has nothing to upsolve
        try:
            found.append(
                Submission(
                    submission_id=int(item["id"]),
                    contest_id=contest_id,
                    problem_index=str(problem["index"]),
                    problem_name=str(problem.get("name", "")),
                    verdict=str(item["verdict"]) if item.get("verdict") else None,
                    participant_type=str(author.get("participantType", "")),
                    created_at=datetime.fromtimestamp(float(item["creationTimeSeconds"]), tz=UTC),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SourceFormatError("malformed user.status entry") from exc
    return sorted(found, key=lambda x: x.created_at, reverse=True)
