from __future__ import annotations

import json
import random
from datetime import UTC, datetime

import httpx
import pytest

from cpstands.domain.contest import ContestPhase
from cpstands.sources.base import SourcePort
from cpstands.sources.codeforces import ClientConfig, CodeforcesClient, CodeforcesSource
from tests.support.clock import FakeClock
from tests.support.synth import load_fixture

KNOWN = {"tourist": "tourist", "jiangly": "jiangly", "benq": "Benq", "um_nik": "Um_nik"}


def make_source(
    handler: httpx.MockTransport | None = None,
) -> tuple[CodeforcesSource, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        path = request.url.path
        if path.endswith("contest.list"):
            return httpx.Response(200, content=load_fixture("contest_list.json"))
        if path.endswith("contest.standings"):
            return httpx.Response(200, content=load_fixture("standings_small.json"))
        if path.endswith("user.info"):
            requested = request.url.params["handles"].split(";")
            for handle in requested:
                if handle.lower() not in KNOWN:
                    body = {
                        "status": "FAILED",
                        "comment": f"handles: User with handle {handle} not found",
                    }
                    return httpx.Response(400, content=json.dumps(body).encode())
            result = [{"handle": KNOWN[h.lower()]} for h in requested]
            return httpx.Response(
                200, content=json.dumps({"status": "OK", "result": result}).encode()
            )
        return httpx.Response(404)

    http = httpx.AsyncClient(transport=httpx.MockTransport(respond), follow_redirects=False)
    client = CodeforcesClient(
        ClientConfig(),
        http=http,
        clock=FakeClock(),
        rng=random.Random(2),
        now=lambda: datetime(2026, 11, 8, tzinfo=UTC),
    )
    return CodeforcesSource(client), seen


def test_source_satisfies_the_port() -> None:
    source, _ = make_source()
    assert isinstance(source, SourcePort)
    assert source.platform == "codeforces"


async def test_list_contests() -> None:
    source, _ = make_source()
    result = await source.list_contests()
    assert len(result.contests) == 12
    assert result.skipped == 0
    assert any(c.phase is ContestPhase.BEFORE for c in result.contests)
    assert result.meta.decoded_bytes > 0


async def test_fetch_standings_filters_to_watched_handles() -> None:
    source, seen = make_source()
    fetch = await source.fetch_standings(2249, frozenset({"user_00001", "user_00002"}))
    assert {r.key for r in fetch.snapshot.results} == {"user_00001", "user_00002"}
    assert fetch.snapshot.rows_scanned == 120
    assert seen[0].url.params["contestId"] == "2249"
    assert "handles" not in seen[0].url.params  # server-side filtering is forbidden (EVID-002)
    assert set(seen[0].url.params.keys()) == {"contestId"}


async def test_resolve_handles_all_known_returns_canonical_spelling() -> None:
    source, seen = make_source()
    result = await source.resolve_handles(["BENQ", "Tourist"])
    assert result.known == {"benq": "Benq", "tourist": "tourist"}
    assert result.unknown == ()
    assert len(seen) == 1


async def test_resolve_handles_reports_unknown_and_keeps_the_valid_ones() -> None:
    source, seen = make_source()
    result = await source.resolve_handles(
        ["tourist", "no_such_user_zzq", "jiangly", "also_missing"]
    )
    assert set(result.known) == {"tourist", "jiangly"}
    assert set(result.unknown) == {"no_such_user_zzq", "also_missing"}
    assert len(seen) == 3  # each unknown handle costs one extra request


async def test_invalid_handle_format_never_reaches_the_network() -> None:
    source, seen = make_source()
    result = await source.resolve_handles(["bad handle!", "x" * 40, "", "tourist"])
    assert set(result.known) == {"tourist"}
    assert set(result.unknown) == {"bad handle!", "x" * 40, ""}
    assert len(seen) == 1
    assert "bad handle" not in str(seen[0].url)


async def test_duplicate_handles_are_sent_once() -> None:
    source, seen = make_source()
    result = await source.resolve_handles(["tourist", "TOURIST", "Tourist"])
    assert set(result.known) == {"tourist"}
    assert seen[0].url.params["handles"] == "tourist"


async def test_large_input_is_split_into_batches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("cpstands.sources.codeforces.source.USER_INFO_BATCH", 2)
    source, seen = make_source()
    result = await source.resolve_handles(["tourist", "jiangly", "benq", "um_nik", "tourist"])
    assert set(result.known) == {"tourist", "jiangly", "benq", "um_nik"}
    assert [r.url.params["handles"] for r in seen] == ["tourist;jiangly", "benq;um_nik"]
