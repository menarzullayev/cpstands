from __future__ import annotations

import gzip
import itertools
import json
import random
from collections.abc import Callable
from datetime import UTC, datetime

import httpx
import pytest

from cpstands.sources.base import (
    CircuitOpenError,
    PermanentSourceError,
    ResponseTooLargeError,
    RetryableSourceError,
)
from cpstands.sources.codeforces.client import ClientConfig, CodeforcesClient
from tests.support.clock import FakeClock

OK = json.dumps({"status": "OK", "result": []}).encode()
Handler = Callable[[httpx.Request], httpx.Response]


def make_client(
    handler: Handler,
    clock: FakeClock | None = None,
    **config: object,
) -> tuple[CodeforcesClient, FakeClock, list[httpx.Request]]:
    clock = clock or FakeClock()
    seen: list[httpx.Request] = []

    def recording(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    http = httpx.AsyncClient(transport=httpx.MockTransport(recording), follow_redirects=False)
    client = CodeforcesClient(
        ClientConfig(**config),  # type: ignore[arg-type]
        http=http,
        clock=clock,
        rng=random.Random(5),
        now=lambda: datetime(2026, 11, 8, 12, 0, tzinfo=UTC),
    )
    return client, clock, seen


async def test_success_returns_body_and_meta() -> None:
    client, _clock, seen = make_client(lambda _r: httpx.Response(200, content=OK))
    raw = await client.fetch("contest.list", {"gym": "false"})
    assert raw.body == OK
    assert raw.status_code == 200
    assert raw.meta.decoded_bytes == len(OK)
    assert str(seen[0].url) == "https://codeforces.com/api/contest.list?gym=false"


async def test_user_agent_identifies_the_project() -> None:
    client, _c, seen = make_client(lambda _r: httpx.Response(200, content=OK))
    await client.fetch("contest.list")
    # The mock transport bypasses the client's default headers, so check the configured value instead.
    assert "cpstands" in client.config.user_agent
    assert "github.com/menarzullayev/cpstands" in client.config.user_agent
    assert len(seen) == 1


async def test_gzip_is_decoded_and_both_sizes_are_reported() -> None:
    payload = json.dumps({"status": "OK", "result": ["x" * 20] * 500}).encode()
    compressed = gzip.compress(payload)
    client, _c, _s = make_client(
        lambda _r: httpx.Response(
            200, stream=httpx.ByteStream(compressed), headers={"Content-Encoding": "gzip"}
        )
    )
    raw = await client.fetch("contest.standings", {"contestId": "1"})
    assert raw.body == payload
    assert raw.meta.decoded_bytes == len(payload)
    assert raw.meta.wire_bytes == len(compressed)
    assert raw.meta.wire_bytes < raw.meta.decoded_bytes / 5


async def test_cache_headers_are_captured() -> None:
    headers = {"Expires": "Sat, 07 Nov 2026 21:30:35 GMT", "X-Proxy-Cache": "HIT"}
    client, _c, _s = make_client(lambda _r: httpx.Response(200, content=OK, headers=headers))
    raw = await client.fetch("contest.standings", {"contestId": "1"})
    assert raw.meta.cache_status == "HIT"
    assert raw.meta.expires_at == datetime(2026, 11, 7, 21, 30, 35, tzinfo=UTC)


async def test_missing_cache_headers_are_none() -> None:
    client, _c, _s = make_client(lambda _r: httpx.Response(200, content=OK))
    raw = await client.fetch("contest.list")
    assert raw.meta.cache_status is None
    assert raw.meta.expires_at is None


async def test_requests_are_paced_across_methods() -> None:
    client, clock, _s = make_client(lambda _r: httpx.Response(200, content=OK))
    starts = []
    for method in ("contest.list", "user.info", "contest.standings"):
        await client.fetch(method)
        starts.append(clock.now)
    gaps = [b - a for a, b in itertools.pairwise(starts)]
    assert all(gap >= 2.0 for gap in gaps)


async def test_server_error_is_retried_with_backoff_then_succeeds() -> None:
    answers = iter([httpx.Response(503), httpx.Response(502), httpx.Response(200, content=OK)])
    client, clock, seen = make_client(lambda _r: next(answers))
    raw = await client.fetch("contest.list")
    assert raw.body == OK
    assert len(seen) == 3
    backoffs = [s for s in clock.sleeps if s > 0]
    assert len(backoffs) >= 2
    assert backoffs[0] < backoffs[1] or backoffs[0] <= 4.0 * 1.25  # grows (within jitter)


async def test_retry_after_header_is_honored() -> None:
    answers = iter(
        [httpx.Response(429, headers={"Retry-After": "17"}), httpx.Response(200, content=OK)]
    )
    client, clock, _s = make_client(lambda _r: next(answers))
    await client.fetch("contest.list")
    assert 17.0 in clock.sleeps


async def test_retries_are_bounded() -> None:
    client, _c, seen = make_client(
        lambda _r: httpx.Response(500), max_retries=2, breaker_threshold=99
    )
    with pytest.raises(RetryableSourceError):
        await client.fetch("contest.list")
    assert len(seen) == 3  # first attempt plus two retries


async def test_timeouts_are_retried() -> None:
    calls = {"n": 0}

    def handler(_r: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ReadTimeout("slow")
        return httpx.Response(200, content=OK)

    client, _c, _s = make_client(handler)
    raw = await client.fetch("contest.list")
    assert raw.body == OK
    assert calls["n"] == 3


async def test_transport_errors_are_retryable() -> None:
    def handler(_r: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    client, _c, seen = make_client(handler, max_retries=1, breaker_threshold=99)
    with pytest.raises(RetryableSourceError):
        await client.fetch("contest.list")
    assert len(seen) == 2


async def test_http_400_is_returned_not_retried() -> None:
    body = json.dumps(
        {"status": "FAILED", "comment": "handles: User with handle x not found"}
    ).encode()
    client, _c, seen = make_client(lambda _r: httpx.Response(400, content=body))
    raw = await client.fetch("user.info", {"handles": "x"})
    assert raw.status_code == 400
    assert raw.body == body
    assert len(seen) == 1


@pytest.mark.parametrize("status", [401, 403, 404, 418])
async def test_other_client_errors_are_permanent_and_not_retried(status: int) -> None:
    client, _c, seen = make_client(lambda _r: httpx.Response(status))
    with pytest.raises(PermanentSourceError):
        await client.fetch("contest.list")
    assert len(seen) == 1


async def test_redirects_are_not_followed() -> None:
    client, _c, seen = make_client(
        lambda _r: httpx.Response(302, headers={"Location": "https://evil.example/"})
    )
    with pytest.raises(PermanentSourceError):
        await client.fetch("contest.list")
    assert len(seen) == 1


async def test_declared_oversize_body_is_refused() -> None:
    client, _c, _s = make_client(
        lambda _r: httpx.Response(200, content=b"x", headers={"Content-Length": "999999999"}),
        max_body_bytes=1024,
    )
    with pytest.raises(ResponseTooLargeError):
        await client.fetch("contest.standings", {"contestId": "1"})


async def test_streamed_oversize_body_is_refused() -> None:
    client, _c, _s = make_client(
        lambda _r: httpx.Response(200, content=b"x" * 5000), max_body_bytes=1024
    )
    with pytest.raises(ResponseTooLargeError):
        await client.fetch("contest.standings", {"contestId": "1"})


async def test_circuit_opens_after_consecutive_failures_and_stops_calling() -> None:
    client, _c, seen = make_client(
        lambda _r: httpx.Response(500), max_retries=0, breaker_threshold=3, breaker_cooldown_s=30.0
    )
    for _ in range(3):
        with pytest.raises(RetryableSourceError):
            await client.fetch("contest.standings", {"contestId": "1"})
    assert len(seen) == 3
    with pytest.raises(CircuitOpenError):
        await client.fetch("contest.standings", {"contestId": "1"})
    assert len(seen) == 3  # no network call while open


async def test_circuits_are_independent_per_method() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("contest.standings"):
            return httpx.Response(500)
        return httpx.Response(200, content=OK)

    client, _c, _s = make_client(handler, max_retries=0, breaker_threshold=1)
    with pytest.raises(RetryableSourceError):
        await client.fetch("contest.standings", {"contestId": "1"})
    with pytest.raises(CircuitOpenError):
        await client.fetch("contest.standings", {"contestId": "1"})
    raw = await client.fetch("contest.list")
    assert raw.body == OK


async def test_circuit_recovers_after_cooldown() -> None:
    answers = iter([httpx.Response(500), httpx.Response(200, content=OK)])
    client, clock, _s = make_client(
        lambda _r: next(answers), max_retries=0, breaker_threshold=1, breaker_cooldown_s=30.0
    )
    with pytest.raises(RetryableSourceError):
        await client.fetch("contest.list")
    with pytest.raises(CircuitOpenError):
        await client.fetch("contest.list")
    clock.advance(31.0)
    raw = await client.fetch("contest.list")
    assert raw.body == OK
    assert client.breaker("contest.list").state == "closed"


async def test_permanent_errors_do_not_open_the_circuit() -> None:
    client, _c, _s = make_client(lambda _r: httpx.Response(404), breaker_threshold=1)
    for _ in range(3):
        with pytest.raises(PermanentSourceError):
            await client.fetch("contest.list")
    assert client.breaker("contest.list").state == "closed"
