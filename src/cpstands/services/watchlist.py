"""The per-chat watch list: parsing, validation against the platform, and the limit.

Codeforces handles are written bare (``tourist``); handles of other platforms carry their prefix
(``kep:alice``). The database keeps the bare handle together with its platform.
"""

from __future__ import annotations

import builtins
import re
from collections.abc import Mapping
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cpstands import platforms
from cpstands.db import repos
from cpstands.domain.contest import handle_key
from cpstands.sources.base import SourcePort

PLATFORM = platforms.CODEFORCES
DEFAULT_LIMIT = 200  # owner decision 2026-11-08 (was 100); counted per platform
INPUT_CAP = 200  # most tokens read from one message; a full /import fits
HANDLE_RE = re.compile(r"^[A-Za-z0-9_.-]{1,24}$")
_SPLIT_RE = re.compile(r"[,;\s]+")


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
    """Split free text into handles; reads at most ``max_items`` tokens (the input cap).

    Codeforces handles come back bare (``tourist``); others keep their prefix (``kep:alice``),
    and a profile link becomes the handle of its platform.
    """
    tokens = [t for t in _SPLIT_RE.split(text.strip()) if t]
    truncated = len(tokens) > max_items
    seen: set[str] = set()
    valid: list[str] = []
    invalid: list[str] = []
    for raw in tokens[:max_items]:
        platform, rest = platforms.split(raw)
        token = rest.lstrip("@").rstrip("/")
        if not HANDLE_RE.match(token):
            invalid.append(raw[:32])
            continue
        shown = platform.shown(token)
        key = handle_key(shown)
        if key not in seen:
            seen.add(key)
            valid.append(shown)
    return ParsedHandles(tuple(valid), tuple(invalid), truncated)


def by_platform(shown: tuple[str, ...]) -> dict[str, list[str]]:
    """Group parsed handles by platform name, without their prefixes."""
    groups: dict[str, list[str]] = {}
    for item in shown:
        platform, bare = platforms.split(item)
        groups.setdefault(platform.name, []).append(bare)
    return groups


class WatchlistService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        source: SourcePort,
        *,
        limit: int = DEFAULT_LIMIT,
        extra: Mapping[str, SourcePort] | None = None,
    ) -> None:
        self._sessions = session_factory
        self._sources: dict[str, SourcePort] = {PLATFORM: source, **(extra or {})}
        self._limit = limit

    @property
    def limit(self) -> int:
        return self._limit

    @property
    def platforms(self) -> tuple[str, ...]:
        return tuple(self._sources)

    async def add(self, chat_id: int, text: str) -> AddResult:
        """Validate handles with their platforms first, then store them under a row lock.

        Source errors propagate before anything is written, so a failed call changes nothing.
        Handles of a platform the bot does not follow count as unknown.
        """
        parsed = parse_handles(text)
        known: dict[str, dict[str, str]] = {}  # platform -> bare key -> bare display
        unknown: list[str] = []
        for name, handles in by_platform(parsed.valid).items():
            platform = platforms.get(name)
            source = self._sources.get(name)
            if source is None:
                unknown.extend(platform.shown(h) for h in handles)
                continue
            resolution = await source.resolve_handles(handles)
            known[name] = dict(resolution.known)
            unknown.extend(platform.shown(h) for h in resolution.unknown)

        added: list[str] = []
        already: list[str] = []
        over_limit: list[str] = []
        async with self._sessions() as session, session.begin():
            if any(known.values()):
                await repos.get_chat(session, chat_id, for_update=True)
            for name, found in known.items():
                if not found:
                    continue
                platform = platforms.get(name)
                existing = {k for k, _ in await repos.list_handles(session, chat_id, name)}
                room = self._limit - len(existing)
                to_insert: dict[str, str] = {}
                for key, display in found.items():
                    if key in existing:
                        already.append(platform.shown(display))
                    elif room > 0:
                        to_insert[key] = display
                        room -= 1
                    else:
                        over_limit.append(platform.shown(display))
                inserted = await repos.add_handles(session, chat_id, name, to_insert)
                added.extend(platform.shown(d) for k, d in to_insert.items() if k in inserted)
                already.extend(platform.shown(d) for k, d in to_insert.items() if k not in inserted)
        return AddResult(
            added=tuple(added),
            already=tuple(already),
            unknown=tuple(unknown),
            invalid=parsed.invalid,
            over_limit=tuple(over_limit),
            truncated=parsed.truncated,
        )

    async def remove(self, chat_id: int, text: str) -> RemoveResult:
        parsed = parse_handles(text)
        removed: list[str] = []
        missing: list[str] = []
        async with self._sessions() as session, session.begin():
            for name, handles in by_platform(parsed.valid).items():
                platform = platforms.get(name)
                keys = [handle_key(h) for h in handles]
                deleted = await repos.remove_handles(session, chat_id, name, keys)
                removed.extend(platform.shown(d) for d in deleted.values())
                missing.extend(platform.shown(h) for h in handles if handle_key(h) not in deleted)
        return RemoveResult(removed=tuple(removed), not_found=tuple(missing) + parsed.invalid)

    async def list(self, chat_id: int, platform: str = PLATFORM) -> list[str]:
        """The followed handles of one platform, without a prefix."""
        async with self._sessions() as session:
            return [d for _, d in await repos.list_handles(session, chat_id, platform)]

    async def list_all(self, chat_id: int) -> builtins.list[str]:
        """Every followed handle as users write it: Codeforces first, then ``kep:...``."""
        shown: builtins.list[str] = []
        async with self._sessions() as session:
            for name, platform in platforms.PLATFORMS.items():
                rows = await repos.list_handles(session, chat_id, name)
                shown.extend(platform.shown(d) for _, d in rows)
        return shown
