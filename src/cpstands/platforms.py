"""The contest platforms the bot follows: names, handle prefixes and web links.

Codeforces is the default, so its handles and contest ids are written bare (``tourist``,
``1970``). Every other platform is written with its prefix: ``kep:alice``, ``kep:504``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

CODEFORCES = "codeforces"
KEP = "kep"


@dataclass(frozen=True, slots=True)
class Platform:
    name: str
    prefix: str  # "" for the default platform, else "kep:" and so on
    label: str
    site: str
    contest: str
    standings: str
    problem: str
    profile: str
    register: str
    # A contest link on this site, with the contest id as the first group.
    contest_link: re.Pattern[str]
    profile_link: re.Pattern[str]

    def contest_url(self, contest_id: int) -> str:
        return self.contest.format(id=contest_id)

    def standings_url(self, contest_id: int) -> str:
        return self.standings.format(id=contest_id)

    def problem_url(self, contest_id: int, problem: str) -> str:
        return self.problem.format(id=contest_id, problem=problem)

    def profile_url(self, handle: str) -> str:
        return self.profile.format(handle=handle)

    def register_url(self, contest_id: int) -> str:
        return self.register.format(id=contest_id)

    def shown(self, text: str | int) -> str:
        """A handle or contest id the way a user writes it: ``tourist``, ``kep:alice``."""
        return f"{self.prefix}{text}"

    def slug(self, text: str | int) -> str:
        """The same for a Mini App start parameter, where ``:`` is not allowed: ``kep504``."""
        return f"{self.prefix.rstrip(':')}{text}"


PLATFORMS: dict[str, Platform] = {
    CODEFORCES: Platform(
        name=CODEFORCES,
        prefix="",
        label="Codeforces",
        site="https://codeforces.com",
        contest="https://codeforces.com/contest/{id}",
        standings="https://codeforces.com/contest/{id}/standings",
        problem="https://codeforces.com/contest/{id}/problem/{problem}",
        profile="https://codeforces.com/profile/{handle}",
        register="https://codeforces.com/contestRegistration/{id}",
        contest_link=re.compile(r"codeforces\.com/(?:contest|contests)/(\d{1,7})", re.IGNORECASE),
        profile_link=re.compile(
            r"^(?:https?://)?(?:www\.)?codeforces\.com/profile/", re.IGNORECASE
        ),
    ),
    KEP: Platform(
        name=KEP,
        prefix="kep:",
        label="kep.uz",
        site="https://kep.uz",
        contest="https://kep.uz/competitions/contests/contest/{id}",
        standings="https://kep.uz/competitions/contests/contest/{id}/standings",
        problem="https://kep.uz/competitions/contests/contest/{id}/problem/{problem}",
        profile="https://kep.uz/users/{handle}",
        # kep.uz registers on the contest page itself.
        register="https://kep.uz/competitions/contests/contest/{id}",
        contest_link=re.compile(r"kep\.uz/competitions/contests/contest/(\d{1,7})", re.IGNORECASE),
        profile_link=re.compile(
            r"^(?:https?://)?(?:www\.)?kep\.uz/users/(?:user/)?", re.IGNORECASE
        ),
    ),
}
DEFAULT = PLATFORMS[CODEFORCES]
_PREFIXES = {p.prefix.lower(): p for p in PLATFORMS.values() if p.prefix}


def get(name: str) -> Platform:
    """The platform called ``name``; unknown names fall back to Codeforces."""
    return PLATFORMS.get(name, DEFAULT)


def split(token: str) -> tuple[Platform, str]:
    """``kep:alice`` -> (kep, ``alice``); a profile link picks its platform; else Codeforces."""
    lowered = token.lower()
    for prefix, platform in _PREFIXES.items():
        if lowered.startswith(prefix):
            return platform, token[len(prefix) :]
    for platform in PLATFORMS.values():
        match = platform.profile_link.match(token)
        if match:
            return platform, token[match.end() :]
    return DEFAULT, token


def parse_contest(text: str) -> tuple[Platform, int] | None:
    """Accept ``1970``, ``kep:504`` or a contest link of any platform."""
    cleaned = text.strip()
    platform, rest = split(cleaned)
    if rest.isascii() and rest.isdigit() and len(rest) <= 7:
        number = int(rest)
        return (platform, number) if number else None
    for candidate in PLATFORMS.values():
        match = candidate.contest_link.search(cleaned)
        if match:
            return candidate, int(match.group(1))
    return None
