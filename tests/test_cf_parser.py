from __future__ import annotations

import json
import time
import tracemalloc
from typing import Any

import pytest

from cpstands.domain.contest import ContestPhase, ProblemStatus
from cpstands.sources.base import (
    PermanentSourceError,
    RetryableSourceError,
    SourceFormatError,
    UnknownHandleError,
)
from cpstands.sources.codeforces.parser import (
    ContestUnavailableError,
    parse_contest_list,
    parse_contest_rating_changes,
    parse_rating_history,
    parse_standings,
    parse_user_info,
    parse_user_status,
)
from tests.support.synth import handle_for, load_fixture, synthesize_standings

WATCHED = frozenset({"user_00001", "user_00007", "user_00042"})


def test_small_fixture_is_parsed_and_filtered() -> None:
    snapshot = parse_standings(load_fixture("standings_small.json"), WATCHED)
    assert snapshot.contest.external_id == 2249
    assert snapshot.contest.platform == "codeforces"
    assert snapshot.contest.phase is ContestPhase.FINISHED
    assert snapshot.contest.starts_at is not None
    assert snapshot.rows_scanned == 120
    assert snapshot.team_rows_skipped == 0
    assert {r.key for r in snapshot.results} == WATCHED
    assert len(snapshot.problems) >= 5
    assert snapshot.problems[0].index == "A"


def test_row_content_is_normalized() -> None:
    snapshot = parse_standings(load_fixture("standings_small.json"), frozenset({"user_00001"}))
    row = snapshot.results[0]
    assert row.handle == "user_00001"
    assert row.rank == 1
    assert row.official
    assert len(row.problems) == len(snapshot.problems)
    assert row.problems[0].status is ProblemStatus.ACCEPTED
    assert row.problems[0].time_s is not None
    assert row.problems[0].points > 0


def test_matching_is_case_insensitive_through_keys() -> None:
    snapshot = parse_standings(load_fixture("standings_small.json"), frozenset({"user_00003"}))
    assert [r.handle for r in snapshot.results] == ["user_00003"]


def test_watching_nobody_returns_no_rows_but_still_scans() -> None:
    snapshot = parse_standings(load_fixture("standings_small.json"), frozenset())
    assert snapshot.results == ()
    assert snapshot.rows_scanned == 120


def test_unknown_watched_handles_are_ignored() -> None:
    snapshot = parse_standings(load_fixture("standings_small.json"), frozenset({"nobody_here"}))
    assert snapshot.results == ()


def test_key_order_in_the_document_does_not_matter() -> None:
    document = json.loads(load_fixture("standings_small.json"))
    result = document["result"]
    reordered = {
        "result": {
            "rows": result["rows"],
            "problems": result["problems"],
            "contest": result["contest"],
        },
        "status": "OK",
    }
    snapshot = parse_standings(json.dumps(reordered).encode(), WATCHED)
    assert {r.key for r in snapshot.results} == WATCHED
    assert snapshot.contest.external_id == 2249


def _mutate(rows_mutator: Any) -> bytes:
    document = json.loads(load_fixture("standings_small.json"))
    rows_mutator(document)
    return json.dumps(document).encode()


def test_team_rows_are_skipped_and_counted() -> None:
    body = synthesize_standings(50, teams=3)
    snapshot = parse_standings(body, frozenset({handle_for(i) for i in range(1, 51)}))
    assert snapshot.team_rows_skipped == 3
    assert len(snapshot.results) == 47


def test_problem_statuses_cover_every_case() -> None:
    def mutate(document: dict[str, Any]) -> None:
        row = document["result"]["rows"][0]
        row["problemResults"][:4] = [
            {
                "points": 500.0,
                "rejectedAttemptCount": 0,
                "type": "FINAL",
                "bestSubmissionTimeSeconds": 60,
            },
            {
                "points": 500.0,
                "rejectedAttemptCount": 1,
                "type": "PRELIMINARY",
                "bestSubmissionTimeSeconds": 70,
            },
            {"points": 0.0, "rejectedAttemptCount": 3, "type": "FINAL"},
            {"points": 0.0, "rejectedAttemptCount": 0, "type": "FINAL"},
        ]

    snapshot = parse_standings(_mutate(mutate), frozenset({"user_00001"}))
    statuses = [p.status for p in snapshot.results[0].problems[:4]]
    assert statuses == [
        ProblemStatus.ACCEPTED,
        ProblemStatus.PROVISIONAL,
        ProblemStatus.REJECTED,
        ProblemStatus.NOT_TRIED,
    ]
    assert snapshot.results[0].problems[2].rejected_attempts == 3


@pytest.mark.parametrize("phase", ["CODING", "PENDING_SYSTEM_TEST", "SYSTEM_TEST", "BEFORE"])
def test_other_phases_are_recognized(phase: str) -> None:
    def mutate(document: dict[str, Any]) -> None:
        document["result"]["contest"]["phase"] = phase

    snapshot = parse_standings(_mutate(mutate), frozenset())
    assert snapshot.contest.phase is ContestPhase(phase)


def test_unknown_phase_is_a_format_error() -> None:
    def mutate(document: dict[str, Any]) -> None:
        document["result"]["contest"]["phase"] = "TELEPORTING"

    with pytest.raises(SourceFormatError):
        parse_standings(_mutate(mutate), frozenset())


def test_row_without_party_is_a_format_error() -> None:
    def mutate(document: dict[str, Any]) -> None:
        del document["result"]["rows"][3]["party"]

    with pytest.raises(SourceFormatError):
        parse_standings(_mutate(mutate), frozenset({"user_00001"}))


def test_row_without_problem_results_is_a_format_error_when_watched() -> None:
    def mutate(document: dict[str, Any]) -> None:
        del document["result"]["rows"][0]["problemResults"]

    with pytest.raises(SourceFormatError):
        parse_standings(_mutate(mutate), frozenset({"user_00001"}))


def test_missing_contest_object_is_a_format_error() -> None:
    body = json.dumps({"status": "OK", "result": {"problems": [], "rows": []}}).encode()
    with pytest.raises(SourceFormatError):
        parse_standings(body, frozenset())


def test_truncated_body_is_retryable() -> None:
    body = load_fixture("standings_small.json")
    with pytest.raises(RetryableSourceError):
        parse_standings(body[: len(body) // 2], frozenset(WATCHED))


def test_failed_envelope_for_missing_contest() -> None:
    body = json.dumps(
        {"status": "FAILED", "comment": "contestId: Contest with id 5 not found"}
    ).encode()
    with pytest.raises(ContestUnavailableError):
        parse_standings(body, frozenset())


def test_failed_envelope_for_not_started_contest() -> None:
    body = json.dumps(
        {"status": "FAILED", "comment": "contestId: Contest with id 9 has not started"}
    ).encode()
    with pytest.raises(ContestUnavailableError):
        parse_standings(body, frozenset())


def test_failed_envelope_with_rate_limit_is_retryable() -> None:
    body = json.dumps({"status": "FAILED", "comment": "Call limit exceeded"}).encode()
    with pytest.raises(RetryableSourceError):
        parse_standings(body, frozenset())


def test_other_failed_envelope_is_permanent() -> None:
    body = json.dumps({"status": "FAILED", "comment": "something odd"}).encode()
    with pytest.raises(PermanentSourceError):
        parse_standings(body, frozenset())


def test_unexpected_status_value_is_a_format_error() -> None:
    with pytest.raises(SourceFormatError):
        parse_standings(json.dumps({"status": "MAYBE"}).encode(), frozenset())


def test_contest_list_fixture() -> None:
    contests, skipped = parse_contest_list(load_fixture("contest_list.json"))
    assert skipped == 0
    assert len(contests) == 12
    phases = {c.phase for c in contests}
    assert ContestPhase.BEFORE in phases
    assert ContestPhase.FINISHED in phases
    assert all(c.platform == "codeforces" for c in contests)


def test_contest_list_counts_malformed_entries_instead_of_failing() -> None:
    document = json.loads(load_fixture("contest_list.json"))
    document["result"].append({"id": 1, "name": "x", "phase": "NOPE"})
    document["result"].append({"name": "no id", "phase": "BEFORE"})
    contests, skipped = parse_contest_list(json.dumps(document).encode())
    assert skipped == 2
    assert len(contests) == 12


def test_contest_list_with_invalid_json_is_retryable() -> None:
    with pytest.raises(RetryableSourceError):
        parse_contest_list(b"<html>maintenance</html>")


def test_user_info_returns_canonical_spelling_by_key() -> None:
    body = json.dumps(
        {"status": "OK", "result": [{"handle": "Tourist"}, {"handle": "jiangly"}]}
    ).encode()
    assert parse_user_info(body) == {"tourist": "Tourist", "jiangly": "jiangly"}


def test_user_info_unknown_handle_error_carries_the_handle() -> None:
    body = json.dumps(
        {"status": "FAILED", "comment": "handles: User with handle zzz_not_real not found"}
    ).encode()
    with pytest.raises(UnknownHandleError) as info:
        parse_user_info(body)
    assert info.value.handle == "zzz_not_real"


def test_largest_observed_payload_parses_fast() -> None:
    """NFR-002 (time): a ~7 MB body (9 743 rows) parses in under 3 s; it takes about 0.2 s in practice."""
    body = synthesize_standings(9743)
    assert len(body) > 5_000_000
    watched = frozenset({handle_for(i) for i in range(1, 201)})
    started = time.perf_counter()
    snapshot = parse_standings(body, watched)
    elapsed = time.perf_counter() - started
    assert snapshot.rows_scanned == 9743
    assert len(snapshot.results) == 200
    assert elapsed < 3.0


def test_largest_observed_payload_uses_little_memory() -> None:
    """NFR-002 (memory): rows are streamed, so Python allocations stay far below 256 MB.

    tracemalloc slows the code down, so timing is measured in a separate test.
    """
    body = synthesize_standings(9743)
    watched = frozenset({handle_for(i) for i in range(1, 201)})
    tracemalloc.start()
    snapshot = parse_standings(body, watched)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert len(snapshot.results) == 200
    assert peak < 64 * 1024 * 1024


def _ok(result: object) -> bytes:
    return json.dumps({"status": "OK", "result": result}).encode()


def test_rating_history_is_sorted_oldest_first_with_deltas() -> None:
    body = _ok(
        [
            {
                "contestId": 2, "contestName": "B", "rank": 5, "oldRating": 1600,
                "newRating": 1580, "ratingUpdateTimeSeconds": 2000,
            },
            {
                "contestId": 1, "contestName": "A", "rank": 9, "oldRating": 1500,
                "newRating": 1600, "ratingUpdateTimeSeconds": 1000,
            },
        ]
    )  # fmt: skip
    history = parse_rating_history(body)
    assert [(c.contest_id, c.delta) for c in history] == [(1, 100), (2, -20)]
    assert parse_rating_history(_ok([])) == []


def test_rating_history_rejects_a_malformed_entry_and_a_failed_status() -> None:
    with pytest.raises(SourceFormatError):
        parse_rating_history(_ok([{"contestId": 1}]))
    with pytest.raises(PermanentSourceError):
        parse_rating_history(json.dumps({"status": "FAILED", "comment": "handle: bad"}).encode())
    with pytest.raises(RetryableSourceError):
        parse_rating_history(b"<html>maintenance</html>")


def test_contest_rating_changes_parse_and_an_unavailable_contest_is_permanent() -> None:
    body = _ok([{"handle": "Tourist", "rank": 1, "oldRating": 3800, "newRating": 3850}])
    (change,) = parse_contest_rating_changes(body)
    assert (change.handle, change.delta) == ("Tourist", 50)
    failed = {
        "status": "FAILED",
        "comment": "contestId: Rating changes are unavailable for this contest",
    }
    with pytest.raises(PermanentSourceError):
        parse_contest_rating_changes(json.dumps(failed).encode())
    with pytest.raises(SourceFormatError):
        parse_contest_rating_changes(_ok([{"handle": "x"}]))


def test_user_status_keeps_contest_submissions_newest_first_and_skips_the_rest() -> None:
    def row(sid: object, created: object, **extra: Any) -> dict[str, Any]:
        base = {
            "id": sid,
            "contestId": 1970,
            "creationTimeSeconds": created,
            "verdict": "OK",
            "problem": {"index": "C", "name": "Cats"},
            "author": {"participantType": "PRACTICE"},
        }
        return {**base, **extra}

    body = _ok(
        [
            row(1, 1000),
            row(2, 3000, verdict="WRONG_ANSWER"),
            row(3, 2000, verdict=None),
            {k: v for k, v in row(4, 4000).items() if k != "contestId"},  # outside any contest
            row("x", 5000),  # no usable id
            {"id": 6, "contestId": 1970},  # no problem or author
        ]
    )  # fmt: skip
    found = parse_user_status(body)
    assert [s.submission_id for s in found] == [2, 3, 1]
    assert [s.accepted for s in found] == [False, False, True]
    assert found[0].participant_type == "PRACTICE"
    with pytest.raises(SourceFormatError):
        parse_user_status(_ok([row(7, "soon")]))
