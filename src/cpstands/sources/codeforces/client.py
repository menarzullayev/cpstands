"""Rate-governed HTTP client for the public Codeforces API (REQ-N07, ADR-004).

Behavior:
* one request start per ``min_interval_s`` (default 2 s) across all methods, with jitter;
* retries with backoff on timeouts, transport errors, HTTP 429 and 5xx (Retry-After kept);
* one circuit breaker per API method, so a failing method does not block the others;
* the body is read with a hard size limit; gzip is decoded and both sizes are reported;
* ``Expires`` and ``X-Proxy-Cache`` are captured because the platform caches standings for a minute.

HTTP 400 counts as a transport success: Codeforces reports API errors (``status: FAILED``) with it,
and callers translate the JSON envelope into typed errors.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx
import structlog

from cpstands.domain.contest import FetchMeta
from cpstands.sources.base import (
    PermanentSourceError,
    ResponseTooLargeError,
    RetryableSourceError,
)
from cpstands.sources.governor import (
    CircuitBreaker,
    Clock,
    RateGovernor,
    SystemClock,
    backoff_delay,
)

log = structlog.get_logger(__name__)

DEFAULT_BASE_URL = "https://codeforces.com/api"
DEFAULT_USER_AGENT = "cpstands/0.1 (+https://github.com/menarzullayev/cpstands)"


@dataclass(frozen=True, slots=True)
class ClientConfig:
    base_url: str = DEFAULT_BASE_URL
    user_agent: str = DEFAULT_USER_AGENT
    min_interval_s: float = 2.0
    timeout_s: float = 15.0
    max_retries: int = 3
    backoff_base_s: float = 2.0
    backoff_cap_s: float = 60.0
    backoff_jitter: float = 0.25
    breaker_threshold: int = 3
    breaker_cooldown_s: float = 30.0
    max_body_bytes: int = 32 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class RawResponse:
    body: bytes
    meta: FetchMeta
    status_code: int


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        moment = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return max(0.0, (moment - datetime.now(UTC)).total_seconds())


def _parse_http_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        moment = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


class CodeforcesClient:
    def __init__(
        self,
        config: ClientConfig | None = None,
        *,
        http: httpx.AsyncClient | None = None,
        clock: Clock | None = None,
        rng: random.Random | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.config = config or ClientConfig()
        self._clock: Clock = clock or SystemClock()
        self._rng = rng or random.Random()  # noqa: S311 - jitter only, not security
        self._now = now
        self._http = http or httpx.AsyncClient(
            timeout=httpx.Timeout(self.config.timeout_s),
            headers={"User-Agent": self.config.user_agent},
            follow_redirects=False,
        )
        self._owns_http = http is None
        self._governor = RateGovernor(self.config.min_interval_s, clock=self._clock, rng=self._rng)
        self._breakers: dict[str, CircuitBreaker] = {}

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    def breaker(self, method: str) -> CircuitBreaker:
        if method not in self._breakers:
            self._breakers[method] = CircuitBreaker(
                name=method,
                threshold=self.config.breaker_threshold,
                cooldown_s=self.config.breaker_cooldown_s,
                clock=self._clock,
            )
        return self._breakers[method]

    async def fetch(self, method: str, params: Mapping[str, str] | None = None) -> RawResponse:
        """GET ``<base>/<method>`` with pacing, retries and circuit breaking."""
        breaker = self.breaker(method)
        attempt = 0
        while True:
            breaker.before_call()
            await self._governor.acquire()
            try:
                response = await self._attempt(method, params or {})
            except RetryableSourceError as exc:
                breaker.record_failure()
                if attempt >= self.config.max_retries:
                    log.warning("source_request_failed", method=method, attempts=attempt + 1)
                    raise
                delay = exc.retry_after_s
                if delay is None:
                    delay = backoff_delay(
                        attempt,
                        base_s=self.config.backoff_base_s,
                        cap_s=self.config.backoff_cap_s,
                        jitter_fraction=self.config.backoff_jitter,
                        rng=self._rng,
                    )
                log.info(
                    "source_retry", method=method, attempt=attempt + 1, delay_s=round(delay, 2)
                )
                await self._clock.sleep(delay)
                attempt += 1
                continue
            except PermanentSourceError:
                raise
            breaker.record_success()
            return response

    async def _attempt(self, method: str, params: Mapping[str, str]) -> RawResponse:
        url = f"{self.config.base_url}/{method}"
        started = self._clock.monotonic()
        try:
            async with self._http.stream("GET", url, params=dict(params)) as response:
                status = response.status_code
                if status == 429 or status >= 500:
                    raise RetryableSourceError(
                        f"HTTP {status} from {method}",
                        retry_after_s=_parse_retry_after(response.headers.get("Retry-After")),
                    )
                if status not in (200, 400):
                    raise PermanentSourceError(f"HTTP {status} from {method}")
                declared = response.headers.get("Content-Length")
                if (
                    declared is not None
                    and declared.isdigit()
                    and int(declared) > self.config.max_body_bytes
                ):
                    raise ResponseTooLargeError(f"declared body {declared} bytes exceeds the limit")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > self.config.max_body_bytes:
                        raise ResponseTooLargeError("body exceeded the size limit while streaming")
                headers = response.headers
                wire = response.num_bytes_downloaded
        except httpx.TimeoutException as exc:
            raise RetryableSourceError(f"timeout calling {method}") from exc
        except httpx.TransportError as exc:
            raise RetryableSourceError(
                f"transport error calling {method}: {type(exc).__name__}"
            ) from exc
        meta = FetchMeta(
            fetched_at=self._now(),
            duration_s=self._clock.monotonic() - started,
            wire_bytes=wire,
            decoded_bytes=len(body),
            expires_at=_parse_http_date(headers.get("Expires")),
            cache_status=headers.get("X-Proxy-Cache"),
        )
        return RawResponse(body=bytes(body), meta=meta, status_code=status)
