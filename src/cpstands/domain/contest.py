"""Contest-data domain types (stage 05: DOM-003, DOM-004, DOM-012, DOM-016).

These types know nothing about Telegram or HTTP. Sources normalize their data into them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ContestPhase(StrEnum):
    BEFORE = "BEFORE"
    CODING = "CODING"
    PENDING_SYSTEM_TEST = "PENDING_SYSTEM_TEST"
    SYSTEM_TEST = "SYSTEM_TEST"
    FINISHED = "FINISHED"
    CANCELLED = "CANCELLED"

    @property
    def is_active(self) -> bool:
        """True while results can still change (coding or testing)."""
        return self in {
            ContestPhase.CODING,
            ContestPhase.PENDING_SYSTEM_TEST,
            ContestPhase.SYSTEM_TEST,
        }


class ProblemStatus(StrEnum):
    NOT_TRIED = "not_tried"
    REJECTED = "rejected"
    ACCEPTED = "accepted"
    PROVISIONAL = "provisional"  # accepted before system tests finished


def handle_key(handle: str) -> str:
    """Canonical comparison key of a handle (case-insensitive)."""
    return handle.strip().lower()


@dataclass(frozen=True, slots=True)
class Contest:
    platform: str
    external_id: int
    name: str
    phase: ContestPhase
    kind: str
    starts_at: datetime | None
    duration_s: int | None


@dataclass(frozen=True, slots=True)
class Problem:
    index: str
    name: str
    points: float | None


@dataclass(frozen=True, slots=True)
class ProblemResult:
    status: ProblemStatus
    rejected_attempts: int
    time_s: int | None
    points: float


@dataclass(frozen=True, slots=True)
class ParticipantResult:
    handle: str
    key: str
    rank: int
    points: float
    penalty: int
    participant_type: str
    problems: tuple[ProblemResult, ...]

    @property
    def official(self) -> bool:
        return self.participant_type == "CONTESTANT"


@dataclass(frozen=True, slots=True)
class StandingRow:
    """One line of the full standings table: a participant or a team."""

    rank: int
    who: str  # team name, or the handle of a single participant
    handles: tuple[str, ...]
    points: float
    penalty: int
    participant_type: str
    problems: tuple[ProblemResult, ...]


@dataclass(frozen=True, slots=True)
class FetchMeta:
    """What we learned about a fetch besides the data itself."""

    fetched_at: datetime
    duration_s: float
    wire_bytes: int
    decoded_bytes: int
    expires_at: datetime | None
    cache_status: str | None  # value of X-Proxy-Cache when present, e.g. HIT or EXPIRED


@dataclass(frozen=True, slots=True)
class StandingsSnapshot:
    contest: Contest
    problems: tuple[Problem, ...]
    results: tuple[ParticipantResult, ...]  # watched handles only
    rows_scanned: int
    team_rows_skipped: int


@dataclass(frozen=True, slots=True)
class FullStandings:
    """The whole standings table of a contest, every row and every problem column."""

    contest: Contest
    problems: tuple[Problem, ...]
    rows: tuple[StandingRow, ...]
    fetched_at: datetime
    expires_at: datetime | None = None  # when the platform's cache for this copy ends


@dataclass(frozen=True, slots=True)
class StandingsFetch:
    snapshot: StandingsSnapshot
    meta: FetchMeta


@dataclass(frozen=True, slots=True)
class ContestList:
    contests: tuple[Contest, ...]
    skipped: int  # entries that could not be normalized (unknown phase or malformed)
    meta: FetchMeta


@dataclass(frozen=True, slots=True)
class UserRating:
    """A user's Codeforces rating facts; ``None`` fields mean unrated."""

    handle: str
    rating: int | None
    max_rating: int | None
    rank: str | None
    max_rank: str | None


@dataclass(frozen=True, slots=True)
class RatingChange:
    """One rated contest in a user's history."""

    contest_id: int
    contest_name: str
    rank: int
    old_rating: int
    new_rating: int
    at: datetime

    @property
    def delta(self) -> int:
        return self.new_rating - self.old_rating


@dataclass(frozen=True, slots=True)
class ContestRatingChange:
    """A participant's rating change in one contest (``contest.ratingChanges``)."""

    handle: str
    rank: int
    old_rating: int
    new_rating: int

    @property
    def delta(self) -> int:
        return self.new_rating - self.old_rating


@dataclass(frozen=True, slots=True)
class RatingResult:
    ratings: tuple[UserRating, ...]
    unknown: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HandleResolution:
    """Result of validating handles: canonical spelling for known ones, the rest unknown."""

    known: dict[str, str]  # key -> canonical display handle
    unknown: tuple[str, ...]
