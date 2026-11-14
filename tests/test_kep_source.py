from __future__ import annotations

import json
import random
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from cpstands.domain.contest import ContestPhase
from cpstands.sources.base import (
    CircuitOpenError,
    PermanentSourceError,
    ResponseTooLargeError,
    RetryableSourceError,
    SourcePort,
    UnknownHandleError,
)
from cpstands.sources.kep import KepClient, KepClientConfig, KepSource
from cpstands.sources.kep.client import DEFAULT_USER_AGENT
from cpstands.sources.kep.parser import ContestUnavailableError
from tests.support.clock import FakeClock

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "kep"
NOT_FOUND = b'{"detail":"Not found.","message":"Not found."}'
UNAUTHORIZED = b'{"detail":"Authentication credentials were not provided."}'
USERS = {"demo_user": "fixture:rating_user.json", "demo_new": "fixture:rating_unrated.json"}


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def contest_detail(contest_id: int, **changes: Any) -> bytes:
    document: dict[str, Any] = json.loads(fixture("contest_502.json"))
    document.update(id=contest_id, **changes)
    return json.dumps(document).encode()


def make_source(
    *,
    contests: dict[int, bytes] | None = None,
    config: KepClientConfig | None = None,
    override: Callable[[httpx.Request], httpx.Response | None] | None = None,
) -> tuple[KepSource, list[httpx.Request], FakeClock]:
    seen: list[httpx.Request] = []
    details = contests or {502: fixture("contest_502.json"), 504: fixture("contest_504.json")}

    def respond(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if override is not None and (answer := override(request)) is not None:
            return answer
        path = request.url.path.removeprefix("/api").strip("/")
        parts = path.split("/")
        if parts == ["contests"]:
            return httpx.Response(200, content=fixture("contests_page1.json"))
        if parts[0] == "contests" and len(parts) >= 2:
            cid = int(parts[1])
            if cid not in details:
                return httpx.Response(404, content=NOT_FOUND)
            if len(parts) == 2:
                return httpx.Response(200, content=details[cid])
            if json.loads(details[cid])["status"] == -1:
                return httpx.Response(401, content=UNAUTHORIZED)
            if parts[2] == "problems":
                return httpx.Response(200, content=fixture("problems_502.json"))
            if parts[2] == "contestants":
                return httpx.Response(200, content=fixture("contestants_502.json"))
        if parts[0] == "contests-rating" and len(parts) >= 2:
            name = parts[1].lower()
            if name not in USERS:
                return httpx.Response(404, content=NOT_FOUND)
            if len(parts) == 3:
                return httpx.Response(200, content=fixture("rating_changes_user.json"))
            body = json.loads(fixture(USERS[name].removeprefix("fixture:")))
            body["username"] = name  # server echoes its canonical spelling
            return httpx.Response(200, content=json.dumps(body).encode())
        if parts == ["attempts"]:
            return httpx.Response(200, content=fixture("attempts_user_p1.json"))
        return httpx.Response(404, content=NOT_FOUND)

    clock = FakeClock()
    http = httpx.AsyncClient(transport=httpx.MockTransport(respond), follow_redirects=False)
    client = KepClient(
        config or KepClientConfig(),
        http=http,
        clock=clock,
        rng=random.Random(2),
        now=lambda: datetime(2026, 11, 8, tzinfo=UTC),
    )
    return KepSource(client), seen, clock


def paths(seen: list[httpx.Request]) -> list[str]:
    return [r.url.path.removeprefix("/api") for r in seen]


def test_source_satisfies_the_port() -> None:
    source, _, _ = make_source()
    assert isinstance(source, SourcePort)
    assert source.platform == "kep"


# --- contests -------------------------------------------------------------------------------


async def test_list_contests_reads_two_pages() -> None:
    source, seen, _ = make_source()
    result = await source.list_contests()
    assert [r.url.params["page"] for r in seen] == ["1", "2"]
    assert len(result.contests) == 20  # the same fixture answers both pages
    assert result.skipped == 0
    assert any(c.phase is ContestPhase.BEFORE for c in result.contests)
    assert result.meta.decoded_bytes == 2 * len(fixture("contests_page1.json"))


async def test_list_contests_stops_after_the_last_page() -> None:
    one_page = json.loads(fixture("contests_page1.json"))
    one_page["pagesCount"] = 1
    source, seen, _ = make_source(override=lambda r: httpx.Response(200, json=one_page))
    result = await source.list_contests()
    assert len(seen) == 1
    assert len(result.contests) == 10


# --- standings ------------------------------------------------------------------------------


async def test_fetch_standings_filters_to_watched_and_caches_problems() -> None:
    source, seen, _ = make_source()
    fetch = await source.fetch_standings(502, frozenset({"user_004", "user_005"}))
    assert [r.key for r in fetch.snapshot.results] == ["user_004", "user_005"]
    assert fetch.snapshot.rows_scanned == 65
    assert len(fetch.snapshot.problems) == 12
    assert fetch.meta.decoded_bytes == len(fixture("contestants_502.json"))
    assert paths(seen) == [
        "/contests/502/",
        "/contests/502/problems/",
        "/contests/502/contestants/",
    ]
    assert all(not r.url.params for r in seen)  # no server-side filtering exists or is used
    seen.clear()
    await source.fetch_standings(502, frozenset({"user_004"}))
    assert paths(seen) == ["/contests/502/", "/contests/502/contestants/"]  # problems are cached


async def test_fetch_full_standings() -> None:
    source, _, _ = make_source()
    full = await source.fetch_full_standings(502)
    assert len(full.rows) == 56  # the 9 virtual rows are left out, as on the site
    assert full.contest.external_id == 502
    assert full.fetched_at.tzinfo is not None


async def test_standings_of_a_contest_that_has_not_started() -> None:
    source, seen, _ = make_source()
    with pytest.raises(ContestUnavailableError):
        await source.fetch_standings(504, frozenset({"x"}))
    assert paths(seen) == ["/contests/504/"]  # the 401-protected tables are never requested


async def test_standings_of_an_unknown_contest() -> None:
    source, _, _ = make_source()
    with pytest.raises(ContestUnavailableError):
        await source.fetch_standings(999, frozenset())
    assert issubclass(ContestUnavailableError, PermanentSourceError)


async def test_contest_rating_changes() -> None:
    source, seen, _ = make_source()
    changes = await source.fetch_contest_rating_changes(502)
    assert len(changes) == 56
    assert paths(seen) == ["/contests/502/", "/contests/502/contestants/"]


async def test_rating_changes_refuse_unrated_and_unfinished_contests() -> None:
    source, seen, _ = make_source(
        contests={
            1: contest_detail(1, isRated=False),
            2: contest_detail(2, status=0),
        }
    )
    with pytest.raises(ContestUnavailableError):
        await source.fetch_contest_rating_changes(1)
    with pytest.raises(ContestUnavailableError):
        await source.fetch_contest_rating_changes(2)
    assert all(r.url.path.endswith(("/1/", "/2/")) for r in seen)


# --- users ----------------------------------------------------------------------------------


async def test_resolve_handles_reports_canonical_and_unknown() -> None:
    source, seen, _ = make_source()
    result = await source.resolve_handles(["DEMO_USER", "demo_user", "ghost_zq", "demo_new"])
    assert result.known == {"demo_user": "demo_user", "demo_new": "demo_new"}
    assert result.unknown == ("ghost_zq",)
    assert len(seen) == 3  # duplicates (case-insensitive) cost nothing


async def test_invalid_handle_format_never_reaches_the_network() -> None:
    source, seen, _ = make_source()
    result = await source.resolve_handles(["bad handle!", "x" * 80, "../etc", "demo_user"])
    assert set(result.known) == {"demo_user"}
    assert set(result.unknown) == {"bad handle!", "x" * 80, "../etc"}
    assert len(seen) == 1
    assert "bad" not in str(seen[0].url)


async def test_handles_are_percent_encoded_in_the_path() -> None:
    source, seen, _ = make_source()
    await source.resolve_handles(["a+b@c.d"])
    assert seen[0].url.raw_path.decode().endswith("/contests-rating/a%2Bb%40c.d/")


async def test_fetch_ratings() -> None:
    source, _, _ = make_source()
    result = await source.fetch_ratings(["demo_user", "ghost_zq", "demo_new"])
    by_handle = {r.handle: r for r in result.ratings}
    assert by_handle["demo_user"].rating == 1914
    assert by_handle["demo_new"].rating is None  # no rated contest: kep's 1200 is a default
    assert result.unknown == ("ghost_zq",)


async def test_rating_history_and_unknown_user() -> None:
    source, seen, _ = make_source()
    history = await source.fetch_rating_history("demo_user")
    assert [c.contest_id for c in history] == [497, 498, 502]
    assert paths(seen) == ["/contests-rating/demo_user/rating-changes/"]
    with pytest.raises(UnknownHandleError) as caught:
        await source.fetch_rating_history("ghost_zq")
    assert caught.value.handle == "ghost_zq"


async def test_user_submissions_ask_for_a_bounded_number_of_pages() -> None:
    source, seen, _ = make_source()
    submissions = await source.fetch_user_submissions("demo_user", count=30)
    assert [dict(r.url.params) for r in seen] == [
        {"username": "demo_user", "page": "1"},
        {"username": "demo_user", "page": "2"},
    ]
    assert len(submissions) == 30  # 15 contest attempts per fixture page, two pages
    assert submissions == tuple(sorted(submissions, key=lambda s: s.created_at, reverse=True))


async def test_user_submissions_with_a_small_count_use_one_request() -> None:
    source, seen, _ = make_source()
    submissions = await source.fetch_user_submissions("demo_user", count=5)
    assert len(seen) == 1
    assert len(submissions) == 5


# --- transport behavior ---------------------------------------------------------------------


async def test_requests_are_paced_at_least_one_second_apart() -> None:
    source, seen, clock = make_source()
    await source.fetch_standings(502, frozenset())
    assert len(seen) == 3
    assert len(clock.sleeps) == 2
    assert all(s >= 1.0 for s in clock.sleeps)


def test_pacing_below_one_second_is_refused() -> None:
    with pytest.raises(ValueError, match="min_interval_s"):
        KepClientConfig(min_interval_s=0.5)


async def test_retries_503_then_succeeds() -> None:
    calls = {"n": 0}

    def flaky(request: httpx.Request) -> httpx.Response | None:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503)
        return None

    source, seen, clock = make_source(override=flaky)
    result = await source.list_contests()
    assert len(result.contests) == 20
    assert len(seen) == 3  # one failure + two pages
    assert any(s >= 1.0 for s in clock.sleeps)


async def test_retry_after_is_honoured() -> None:
    calls = {"n": 0}

    def limited(request: httpx.Request) -> httpx.Response | None:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "7"})
        return None

    source, _, clock = make_source(override=limited)
    await source.fetch_rating_history("demo_user")
    assert 7.0 in clock.sleeps


async def test_persistent_5xx_gives_up_as_retryable() -> None:
    source, seen, _ = make_source(
        config=KepClientConfig(max_retries=2), override=lambda r: httpx.Response(500)
    )
    with pytest.raises(RetryableSourceError):
        await source.list_contests()
    assert len(seen) == 3


async def test_circuit_opens_after_repeated_failures() -> None:
    source, seen, _ = make_source(
        config=KepClientConfig(max_retries=5, breaker_threshold=2),
        override=lambda r: httpx.Response(500),
    )
    with pytest.raises(CircuitOpenError):
        await source.list_contests()
    assert len(seen) == 2


async def test_unexpected_client_error_is_permanent() -> None:
    source, seen, _ = make_source(override=lambda r: httpx.Response(403))
    with pytest.raises(PermanentSourceError):
        await source.list_contests()
    assert len(seen) == 1


async def test_declared_oversize_body_is_refused() -> None:
    source, _, _ = make_source(
        config=KepClientConfig(max_body_bytes=1000),
        override=lambda r: httpx.Response(200, content=b"[]", headers={"Content-Length": "5000"}),
    )
    with pytest.raises(ResponseTooLargeError):
        await source.fetch_full_standings(502)


async def test_streamed_oversize_body_is_refused() -> None:
    source, _, _ = make_source(config=KepClientConfig(max_body_bytes=1000))
    with pytest.raises(ResponseTooLargeError):
        await source.list_contests()  # the contests fixture is ~5 KB


async def test_default_client_identifies_itself() -> None:
    client = KepClient()
    try:
        assert client._http.headers["User-Agent"] == DEFAULT_USER_AGENT
        assert "cpstands" in DEFAULT_USER_AGENT
        assert client.config.base_url == "https://kep.uz/api"
    finally:
        await client.aclose()


async def test_full_names_in_a_live_payload_never_reach_results() -> None:
    canary = "Zyxwvut Qponmlkj"
    rows = json.loads(fixture("contestants_502.json"))
    for row in rows:
        row["userFullName"] = canary
        row["avatar"] = "https://cdn.example/avatars/canary.webp"
        row["country"] = "zz"
    payload = json.dumps(rows).encode()

    def with_names(request: httpx.Request) -> httpx.Response | None:
        if request.url.path.endswith("/contestants/"):
            return httpx.Response(200, content=payload)
        return None

    source, _, _ = make_source(override=with_names)
    fetch = await source.fetch_standings(502, frozenset(r["username"] for r in rows))
    full = await source.fetch_full_standings(502)
    changes = await source.fetch_contest_rating_changes(502)
    for dumped in (repr(fetch), repr(full), repr(changes)):
        assert canary not in dumped
        assert "canary.webp" not in dumped
        assert "'zz'" not in dumped
