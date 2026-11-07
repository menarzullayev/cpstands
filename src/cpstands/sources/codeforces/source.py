"""The Codeforces implementation of the ``SourcePort`` contract."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Sequence
from datetime import UTC, datetime

from cpstands.domain.contest import (
    ContestList,
    FullStandings,
    HandleResolution,
    StandingsFetch,
    handle_key,
)
from cpstands.sources.base import UnknownHandleError
from cpstands.sources.codeforces.client import CodeforcesClient
from cpstands.sources.codeforces.parser import (
    PLATFORM,
    parse_contest_list,
    parse_full_standings,
    parse_standings,
    parse_user_info,
)

HANDLE_RE = re.compile(r"^[A-Za-z0-9_.-]{1,24}$")
USER_INFO_BATCH = 200
OFFLOAD_THRESHOLD_BYTES = 1_000_000


class CodeforcesSource:
    platform = PLATFORM

    def __init__(self, client: CodeforcesClient) -> None:
        self._client = client

    async def list_contests(self) -> ContestList:
        raw = await self._client.fetch("contest.list", {"gym": "false"})
        contests, skipped = parse_contest_list(raw.body)
        return ContestList(contests=tuple(contests), skipped=skipped, meta=raw.meta)

    async def fetch_standings(self, contest_id: int, watched: frozenset[str]) -> StandingsFetch:
        """Fetch the full anonymous standings (no server filter exists); keep watched rows."""
        raw = await self._client.fetch("contest.standings", {"contestId": str(contest_id)})
        if len(raw.body) >= OFFLOAD_THRESHOLD_BYTES:
            snapshot = await asyncio.to_thread(parse_standings, raw.body, watched)
        else:
            snapshot = parse_standings(raw.body, watched)
        return StandingsFetch(snapshot=snapshot, meta=raw.meta)

    async def fetch_full_standings(self, contest_id: int) -> FullStandings:
        """Fetch the whole anonymous standings table (every row, teams included)."""
        raw = await self._client.fetch("contest.standings", {"contestId": str(contest_id)})
        fetched_at = datetime.now(UTC)
        if len(raw.body) >= OFFLOAD_THRESHOLD_BYTES:
            return await asyncio.to_thread(parse_full_standings, raw.body, fetched_at=fetched_at)
        return parse_full_standings(raw.body, fetched_at=fetched_at)

    async def resolve_handles(self, handles: Sequence[str]) -> HandleResolution:
        """Validate handles via user.info, dropping unknown ones until the batch succeeds."""
        known: dict[str, str] = {}
        unknown: list[str] = []
        pending: list[str] = []
        for handle in handles:
            cleaned = handle.strip()
            if HANDLE_RE.match(cleaned):
                if handle_key(cleaned) not in {handle_key(p) for p in pending}:
                    pending.append(cleaned)
            else:
                unknown.append(cleaned)
        for start in range(0, len(pending), USER_INFO_BATCH):
            batch = pending[start : start + USER_INFO_BATCH]
            while batch:
                try:
                    raw = await self._client.fetch("user.info", {"handles": ";".join(batch)})
                    known.update(parse_user_info(raw.body))
                    break
                except UnknownHandleError as exc:
                    unknown.append(exc.handle)
                    bad = handle_key(exc.handle)
                    remaining = [h for h in batch if handle_key(h) != bad]
                    if len(remaining) == len(
                        batch
                    ):  # the reported handle is not in our batch: give up
                        unknown.extend(batch)
                        break
                    batch = remaining
        return HandleResolution(known=known, unknown=tuple(unknown))
