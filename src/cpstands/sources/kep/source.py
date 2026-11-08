"""The kep.uz implementation of the ``SourcePort`` contract."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from cpstands.domain.contest import (
    Contest,
    ContestList,
    ContestPhase,
    ContestRatingChange,
    FetchMeta,
    FullStandings,
    HandleResolution,
    Problem,
    RatingChange,
    RatingResult,
    StandingsFetch,
    Submission,
    UserRating,
    handle_key,
)
from cpstands.sources.base import UnknownHandleError
from cpstands.sources.kep.client import KepClient, RawResponse
from cpstands.sources.kep.parser import (
    PLATFORM,
    ContestUnavailableError,
    parse_attempts,
    parse_contest_detail,
    parse_contest_page,
    parse_contest_rating_changes,
    parse_full_standings,
    parse_problems,
    parse_rating_history,
    parse_standings,
    parse_user_rating,
)

HANDLE_RE = re.compile(r"^[A-Za-z0-9_.@+-]{1,64}$")
LIST_PAGES = 2  # newest 20 contests: upcoming, running and recently finished
ATTEMPTS_PAGE_SIZE = 20  # fixed by the server
MAX_ATTEMPT_PAGES = 5
OFFLOAD_THRESHOLD_BYTES = 1_000_000
PROBLEM_CACHE_LIMIT = 64
# kep.uz sends no cache headers; a running table is re-read this often (owner decision).
LIVE_REFRESH_S = 30


def _merge_meta(metas: Sequence[FetchMeta]) -> FetchMeta:
    first = metas[0]
    return FetchMeta(
        fetched_at=first.fetched_at,
        duration_s=sum(m.duration_s for m in metas),
        wire_bytes=sum(m.wire_bytes for m in metas),
        decoded_bytes=sum(m.decoded_bytes for m in metas),
        expires_at=None,
        cache_status=first.cache_status,
    )


class KepSource:
    platform = PLATFORM

    def __init__(self, client: KepClient) -> None:
        self._client = client
        self._problem_cache: dict[int, tuple[Problem, ...]] = {}

    async def list_contests(self) -> ContestList:
        """The newest ``LIST_PAGES`` pages of ``/contests/`` (newest first on the server)."""
        contests: list[Contest] = []
        skipped = 0
        metas: list[FetchMeta] = []
        page = 1
        while page <= LIST_PAGES:
            raw = await self._client.fetch("contests/", {"page": str(page)})
            parsed = parse_contest_page(raw.body)
            contests.extend(parsed.contests)
            skipped += parsed.skipped
            metas.append(raw.meta)
            if page >= parsed.pages_count:
                break
            page += 1
        return ContestList(contests=tuple(contests), skipped=skipped, meta=_merge_meta(metas))

    async def _contest(self, contest_id: int) -> tuple[Contest, bool, FetchMeta]:
        raw = await self._client.fetch(f"contests/{contest_id}/")
        if raw.status_code == 404:
            raise ContestUnavailableError(f"contest {contest_id} not found")
        contest, rated = parse_contest_detail(raw.body)
        return contest, rated, raw.meta

    async def _problems(self, contest_id: int) -> tuple[Problem, ...]:
        cached = self._problem_cache.get(contest_id)
        if cached is not None:
            return cached
        raw = await self._client.fetch(f"contests/{contest_id}/problems/")
        if raw.status_code == 404:
            raise ContestUnavailableError(f"contest {contest_id} not found")
        problems = parse_problems(raw.body)
        if problems:
            if len(self._problem_cache) >= PROBLEM_CACHE_LIMIT:
                self._problem_cache.pop(next(iter(self._problem_cache)))
            self._problem_cache[contest_id] = problems
        return problems

    async def _tables(self, contest_id: int) -> tuple[Contest, tuple[Problem, ...], RawResponse]:
        """Contest, its problems and the contestants table; refuses a contest not yet started."""
        contest, _, _ = await self._contest(contest_id)
        if contest.phase is ContestPhase.BEFORE:
            raise ContestUnavailableError(f"contest {contest_id} has not started")
        problems = await self._problems(contest_id)
        raw = await self._client.fetch(f"contests/{contest_id}/contestants/")
        if raw.status_code == 404:
            raise ContestUnavailableError(f"contest {contest_id} not found")
        return contest, problems, raw

    async def fetch_standings(self, contest_id: int, watched: frozenset[str]) -> StandingsFetch:
        """Fetch the whole (unpaginated) table once and keep the rows of watched handle keys."""
        contest, problems, raw = await self._tables(contest_id)
        if len(raw.body) >= OFFLOAD_THRESHOLD_BYTES:
            snapshot = await asyncio.to_thread(
                parse_standings, contest, problems, raw.body, watched
            )
        else:
            snapshot = parse_standings(contest, problems, raw.body, watched)
        return StandingsFetch(snapshot=snapshot, meta=raw.meta)

    async def fetch_full_standings(self, contest_id: int) -> FullStandings:
        contest, problems, raw = await self._tables(contest_id)
        fetched_at = datetime.now(UTC)
        if len(raw.body) >= OFFLOAD_THRESHOLD_BYTES:
            parsed = await asyncio.to_thread(
                parse_full_standings, contest, problems, raw.body, fetched_at=fetched_at
            )
        else:
            parsed = parse_full_standings(contest, problems, raw.body, fetched_at=fetched_at)
        expires = raw.meta.expires_at
        if expires is None and contest.phase.is_active:
            expires = fetched_at + timedelta(seconds=LIVE_REFRESH_S)
        return replace(parsed, expires_at=expires)

    async def _user_rating(self, handle: str) -> UserRating | None:
        """One user's rating facts, or ``None`` when kep does not know the handle."""
        cleaned = handle.strip()
        if not HANDLE_RE.match(cleaned):
            return None
        raw = await self._client.fetch(f"contests-rating/{quote(cleaned, safe='')}/")
        if raw.status_code == 404:
            return None
        return parse_user_rating(raw.body)

    @staticmethod
    def _unique(handles: Sequence[str]) -> list[str]:
        seen: set[str] = set()
        unique: list[str] = []
        for handle in handles:
            cleaned = handle.strip()
            if handle_key(cleaned) not in seen:
                seen.add(handle_key(cleaned))
                unique.append(cleaned)
        return unique

    async def resolve_handles(self, handles: Sequence[str]) -> HandleResolution:
        """Validate handles one by one (kep has no batch endpoint); one request per new handle."""
        known: dict[str, str] = {}
        unknown: list[str] = []
        for handle in self._unique(handles):
            rating = await self._user_rating(handle)
            if rating is None:
                unknown.append(handle)
            else:
                known[handle_key(handle)] = rating.handle
        return HandleResolution(known=known, unknown=tuple(unknown))

    async def fetch_ratings(self, handles: Sequence[str]) -> RatingResult:
        found: list[UserRating] = []
        unknown: list[str] = []
        for handle in self._unique(handles):
            rating = await self._user_rating(handle)
            if rating is None:
                unknown.append(handle)
            else:
                found.append(rating)
        return RatingResult(ratings=tuple(found), unknown=tuple(unknown))

    async def fetch_rating_history(self, handle: str) -> tuple[RatingChange, ...]:
        """The rated contests of one user, oldest first; ``at`` has day precision."""
        cleaned = handle.strip()
        if not HANDLE_RE.match(cleaned):
            raise UnknownHandleError(cleaned)
        raw = await self._client.fetch(f"contests-rating/{quote(cleaned, safe='')}/rating-changes/")
        if raw.status_code == 404:
            raise UnknownHandleError(cleaned)
        return parse_rating_history(raw.body)

    async def fetch_contest_rating_changes(
        self, contest_id: int
    ) -> tuple[ContestRatingChange, ...]:
        """Rating changes of a finished rated contest, derived from the contestants table."""
        contest, rated, _ = await self._contest(contest_id)
        if not rated:
            raise ContestUnavailableError(f"contest {contest_id} is not rated")
        if contest.phase is not ContestPhase.FINISHED:
            raise ContestUnavailableError(f"contest {contest_id} is not finished")
        raw = await self._client.fetch(f"contests/{contest_id}/contestants/")
        if raw.status_code == 404:
            raise ContestUnavailableError(f"contest {contest_id} not found")
        return parse_contest_rating_changes(raw.body)

    async def fetch_user_submissions(self, handle: str, count: int = 50) -> tuple[Submission, ...]:
        """The newest contest submissions of one user (practice-only attempts are skipped).

        Uses the public ``/attempts/?username=`` list (20 per page, newest first). ``count``
        also bounds the raw attempts scanned, so fewer contest submissions may come back.
        """
        cleaned = handle.strip()
        if not HANDLE_RE.match(cleaned):
            raise UnknownHandleError(cleaned)
        pages_wanted = min(MAX_ATTEMPT_PAGES, max(1, -(-count // ATTEMPTS_PAGE_SIZE)))
        found: list[Submission] = []
        page = 1
        while page <= pages_wanted:
            raw = await self._client.fetch("attempts/", {"username": cleaned, "page": str(page)})
            if raw.status_code == 404:
                raise UnknownHandleError(cleaned)
            parsed = parse_attempts(raw.body)
            found.extend(parsed.submissions)
            if page >= parsed.pages_count:
                break
            page += 1
        found.sort(key=lambda s: s.created_at, reverse=True)
        return tuple(found[:count])
