"""The per-chat watch list: parsing, validation against the platform, and the limit."""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cpstands.db import repos
from cpstands.domain.contest import handle_key
from cpstands.sources.base import SourcePort

PLATFORM = "codeforces"
DEFAULT_LIMIT = 200  # owner decision 2026-11-08 (was 100)
INPUT_CAP = 200  # most tokens read from one message; a full /import fits
HANDLE_RE = re.compile(r"^[A-Za-z0-9_.-]{1,24}$")
_SPLIT_RE = re.compile(r"[,;\s]+")
_PROFILE_PREFIX_RE = re.compile(r"^(?:https?://)?(?:www\.)?codeforces\.com/profile/", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ParsedHandles:
    valid: tuple[str, ...]
    invalid: tuple[str, ...]
    truncated: bool


@dataclass(frozen=True, slots=True)
class AddResult:
    added: tuple[str, ...] = ()
    already: tuple[str, ...] = ()
    unknown: tuple[str, ...] = ()
    invalid: tuple[str, ...] = ()
    over_limit: tuple[str, ...] = ()
    truncated: bool = False


@dataclass(frozen=True, slots=True)
class RemoveResult:
    removed: tuple[str, ...] = ()
    not_found: tuple[str, ...] = ()


def parse_handles(text: str, *, max_items: int = INPUT_CAP) -> ParsedHandles:
    """Split free text into handles; reads at most ``max_items`` tokens (the input cap)."""
    tokens = [t for t in _SPLIT_RE.split(text.strip()) if t]
    truncated = len(tokens) > max_items
    seen: set[str] = set()
    valid: list[str] = []
    invalid: list[str] = []
    for raw in tokens[:max_items]:
        token = _PROFILE_PREFIX_RE.sub("", raw).lstrip("@").rstrip("/")
        if not HANDLE_RE.match(token):
            invalid.append(raw[:32])
            continue
        key = handle_key(token)
        if key not in seen:
            seen.add(key)
            valid.append(token)
    return ParsedHandles(tuple(valid), tuple(invalid), truncated)


class WatchlistService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        source: SourcePort,
        *,
        limit: int = DEFAULT_LIMIT,
    ) -> None:
        self._sessions = session_factory
        self._source = source
        self._limit = limit

    @property
    def limit(self) -> int:
        return self._limit

    async def add(self, chat_id: int, text: str) -> AddResult:
        """Validate handles with the platform first, then store them under a row lock.

        Source errors propagate before anything is written, so a failed call changes nothing.
        """
        parsed = parse_handles(text)
        resolution = await self._source.resolve_handles(parsed.valid) if parsed.valid else None
        known = resolution.known if resolution else {}
        unknown = tuple(resolution.unknown) if resolution else ()

        added: list[str] = []
        already: list[str] = []
        over_limit: list[str] = []
        async with self._sessions() as session, session.begin():
            if known:
                await repos.get_chat(session, chat_id, for_update=True)
                existing = {k for k, _ in await repos.list_handles(session, chat_id, PLATFORM)}
                room = self._limit - len(existing)
                to_insert: dict[str, str] = {}
                for key, display in known.items():
                    if key in existing:
                        already.append(display)
                    elif room > 0:
                        to_insert[key] = display
                        room -= 1
                    else:
                        over_limit.append(display)
                inserted = await repos.add_handles(session, chat_id, PLATFORM, to_insert)
                added = [d for k, d in to_insert.items() if k in inserted]
                already.extend(d for k, d in to_insert.items() if k not in inserted)
        return AddResult(
            added=tuple(added),
            already=tuple(already),
            unknown=unknown,
            invalid=parsed.invalid,
            over_limit=tuple(over_limit),
            truncated=parsed.truncated,
        )

    async def remove(self, chat_id: int, text: str) -> RemoveResult:
        parsed = parse_handles(text)
        keys = [handle_key(h) for h in parsed.valid]
        async with self._sessions() as session, session.begin():
            deleted = await repos.remove_handles(session, chat_id, PLATFORM, keys)
        removed = tuple(deleted.values())
        missing = tuple(h for h in parsed.valid if handle_key(h) not in deleted)
        return RemoveResult(removed=removed, not_found=missing + parsed.invalid)

    async def list(self, chat_id: int) -> list[str]:
        async with self._sessions() as session:
            return [d for _, d in await repos.list_handles(session, chat_id, PLATFORM)]
