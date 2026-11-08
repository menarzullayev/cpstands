"""One-shot ``user.friends`` call with the owner's own API key (owner decision on REQ-013).

The key and secret exist only as arguments of :func:`fetch_friends`: they are never stored, never
logged and never part of an exception message. This module deliberately does not use the shared
client, whose logs and error messages carry request URLs.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import time
from collections.abc import Callable, Mapping

import httpx

from cpstands.sources.base import PermanentSourceError, RetryableSourceError
from cpstands.sources.codeforces.client import DEFAULT_BASE_URL, DEFAULT_USER_AGENT

METHOD = "user.friends"
TIMEOUT_S = 15.0
MAX_BODY = 1_000_000
_SIG_MARKERS = ("apikey", "apisig", "signature", "time:", "authoriz", "api key")


class InvalidCredentialsError(PermanentSourceError):
    """Codeforces rejected the API key or the signature."""


def sign(method: str, params: Mapping[str, str], api_secret: str, rand: str) -> str:
    """``apiSig`` as documented: rand + sha512(rand/method?sorted_params#secret)."""
    query = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    digest = hashlib.sha512(f"{rand}/{method}?{query}#{api_secret}".encode()).hexdigest()
    return rand + digest


def _rand() -> str:
    return secrets.token_hex(3)


async def fetch_friends(
    api_key: str,
    api_secret: str,
    *,
    http: httpx.AsyncClient | None = None,
    base_url: str = DEFAULT_BASE_URL,
    now: Callable[[], float] = time.time,
    rand: Callable[[], str] = _rand,
) -> tuple[str, ...]:
    """The handles the key's owner has marked as friends on Codeforces."""
    params = {"apiKey": api_key, "time": str(int(now()))}
    params["apiSig"] = sign(METHOD, params, api_secret, rand())
    own = http is None
    client = http or httpx.AsyncClient(
        timeout=TIMEOUT_S, headers={"User-Agent": DEFAULT_USER_AGENT}, follow_redirects=False
    )
    try:
        response = await client.get(f"{base_url}/{METHOD}", params=params)
    except httpx.HTTPError:
        # Not chained and without httpx's text: it may contain the URL, which holds the key.
        raise RetryableSourceError("could not reach Codeforces") from None
    finally:
        if own:
            await client.aclose()
    if response.status_code >= 500 or response.status_code == 429:
        raise RetryableSourceError(f"Codeforces answered HTTP {response.status_code}")
    if len(response.content) > MAX_BODY:
        raise PermanentSourceError("the answer is too large")
    try:
        document = json.loads(response.content)
    except ValueError:
        raise RetryableSourceError("Codeforces sent something that is not JSON") from None
    if not isinstance(document, dict):
        raise PermanentSourceError("unexpected answer")
    if document.get("status") != "OK":
        comment = str(document.get("comment", "")).lower()
        if any(marker in comment for marker in _SIG_MARKERS):
            raise InvalidCredentialsError("Codeforces rejected the API key")
        raise PermanentSourceError("Codeforces refused the request")
    result = document.get("result")
    if not isinstance(result, list):
        raise PermanentSourceError("unexpected answer")
    return tuple(str(item) for item in result if isinstance(item, str))
