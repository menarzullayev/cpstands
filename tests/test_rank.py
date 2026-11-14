from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

import pytest

from cpstands.bot import rank_view
from cpstands.domain.contest import UserRating
from cpstands.i18n import I18n
from cpstands.services.ratings import RatingService, RatingTable, sort_key
from cpstands.sources.base import PermanentSourceError, RetryableSourceError, UnknownHandleError
from cpstands.sources.codeforces.parser import parse_user_ratings
from cpstands.sources.codeforces.source import CodeforcesSource
from tests.support.clock import FakeClock
from tests.support.sources import FakeSource

SAY = I18n().bound("en")
NOW = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)


def user(
    handle: str, rating: int | None, top: int | None = None, rank: str | None = None
) -> UserRating:
    return UserRating(handle, rating, top if top is not None else rating, rank, rank)


def body(users: list[dict[str, object]]) -> bytes:
    return json.dumps({"status": "OK", "result": users}).encode()


def test_parser_reads_rated_and_unrated_users() -> None:
    parsed = parse_user_ratings(
        body(
            [
                {"handle": "tourist", "rating": 3800, "maxRating": 3979, "rank": "legendary grandmaster",
                 "maxRank": "legendary grandmaster"},
                {"handle": "newbie"},
                {"handle": "odd", "rating": "n/a", "rank": 5},
            ]
        )
    )  # fmt: skip
    assert parsed[0] == UserRating(
        "tourist", 3800, 3979, "legendary grandmaster", "legendary grandmaster"
    )
    assert parsed[1] == UserRating("newbie", None, None, None, None)
    assert parsed[2] == UserRating("odd", None, None, None, None)  # wrong types are ignored


def test_parser_rejects_failures_and_garbage() -> None:
    with pytest.raises(UnknownHandleError):
        parse_user_ratings(
            b'{"status":"FAILED","comment":"handles: User with handle zz not found"}'
        )
    with pytest.raises(RetryableSourceError):
        parse_user_ratings(b"not json")
    with pytest.raises(PermanentSourceError):
        parse_user_ratings(b'{"status":"OK","result":[{"rating":1}]}')
    with pytest.raises(PermanentSourceError):
        parse_user_ratings(b'{"status":"OK","result":{}}')


class StubClient:
    """Answers user.info like Codeforces: the whole batch fails on the first unknown handle."""

    def __init__(self, existing: Mapping[str, UserRating]) -> None:
        self.existing = {k.lower(): v for k, v in existing.items()}
        self.calls: list[list[str]] = []

    async def fetch(self, method: str, params: Mapping[str, str]) -> object:
        assert method == "user.info"
        handles = params["handles"].split(";")
        self.calls.append(handles)
        for handle in handles:
            if handle.lower() not in self.existing:
                text = f'{{"status":"FAILED","comment":"handles: User with handle {handle} not found"}}'
                return type("Raw", (), {"body": text.encode()})()
        users = [
            {"handle": u.handle, "rating": u.rating, "maxRating": u.max_rating}
            for u in (self.existing[h.lower()] for h in handles)
        ]
        return type("Raw", (), {"body": body(users)})()  # type: ignore[arg-type]


async def test_source_drops_unknown_handles_one_by_one_and_reports_them() -> None:
    client = StubClient({"tourist": user("tourist", 3800), "petr": user("Petr", 3000)})
    source = CodeforcesSource(client)  # type: ignore[arg-type]
    result = await source.fetch_ratings(["tourist", "ghost", "Petr", "bad!name"])
    assert [r.handle for r in result.ratings] == ["tourist", "Petr"]
    assert sorted(result.unknown) == ["bad!name", "ghost"]
    assert len(client.calls) == 2  # the first batch failed on ghost, the second succeeded


# -------------------------------------------------------------------------------- service


def service(**kwargs: object) -> tuple[RatingService, FakeSource, FakeClock]:
    clock = FakeClock()
    source = FakeSource(
        [],
        ratings={
            "tourist": user("tourist", 3800, 3979, "legendary grandmaster"),
            "petr": user("Petr", 3300, 3500),
            "jiangly": user("jiangly", 3800),
            "newbie": user("newbie", None),
        },
        **kwargs,  # type: ignore[arg-type]
    )
    return RatingService(source, clock=clock.monotonic, now=lambda: NOW), source, clock  # type: ignore[arg-type]


async def test_ratings_are_sorted_best_first_with_unrated_and_unknown_separated() -> None:
    svc, _, _ = service()
    table = await svc.get(["newbie", "petr", "ghost", "Tourist", "jiangly"])
    assert [r.handle for r in table.rows] == ["jiangly", "tourist", "Petr", "newbie"]
    assert table.unknown == ("ghost",)
    assert table.fetched_at == NOW


async def test_only_missing_handles_are_requested_and_the_cache_expires() -> None:
    svc, source, clock = service()
    await svc.get(["tourist", "petr"])
    await svc.get(["petr", "tourist"])
    assert source.rating_fetches == 1
    await svc.get(["tourist", "jiangly"])  # one handle is new
    assert source.rating_fetches == 2
    clock.advance(601)
    await svc.get(["tourist"])
    assert source.rating_fetches == 3


async def test_refresh_is_throttled() -> None:
    svc, source, clock = service()
    await svc.get(["tourist"])
    clock.advance(10)
    await svc.get(["tourist"], refresh=True)
    assert source.rating_fetches == 1
    clock.advance(25)
    await svc.get(["tourist"], refresh=True)
    assert source.rating_fetches == 2


async def test_a_failed_fetch_is_not_cached() -> None:
    svc, source, _ = service()
    source.fail = True
    with pytest.raises(RetryableSourceError):
        await svc.get(["tourist"])
    source.fail = False
    assert [r.handle for r in (await svc.get(["tourist"])).rows] == ["tourist"]


def test_sort_key_orders_ties_by_handle() -> None:
    rows = [user("b", 100), user("A", 100), user("c", None), user("z", 200)]
    assert [r.handle for r in sorted(rows, key=sort_key)] == ["z", "A", "b", "c"]


# ------------------------------------------------------------------------------------ view


def table_of(count: int, unknown: tuple[str, ...] = ()) -> RatingTable:
    rows = tuple(user(f"user{i}", 3000 - i, rank="grandmaster") for i in range(count))
    return RatingTable(rows, unknown, NOW)


def test_pages_cover_every_row_exactly_once() -> None:
    table = table_of(60)
    seen: list[str] = []
    for page in range(rank_view.pages(60)):
        html = rank_view.render(table, page, SAY, time_zone="Asia/Tashkent")
        seen += [part.split("</td>")[0] for part in html.split("<tr><td>")[1:]]
    assert seen == [str(i) for i in range(1, 61)]
    assert [rank_view.pages(n) for n in (0, 1, 25, 26)] == [1, 1, 1, 2]


def test_render_shows_dashes_for_unrated_clips_names_and_lists_unknown_handles() -> None:
    rows = (UserRating("<script>x</script>" + "y" * 30, None, None, None, None),)
    html = rank_view.render(RatingTable(rows, ("ghost", "a&b"), NOW), 0, SAY, time_zone=None)
    assert "<script>" not in html
    assert html.count("<td>-</td>") == 3
    assert "…" in html
    assert "Not found on Codeforces: ghost, a&amp;b" in html  # escaped once, not twice
    assert "17:00" not in html
    assert "12:00" in html  # UTC when the chat has no zone


def test_render_clamps_pages_and_handles_an_empty_table() -> None:
    html = rank_view.render(table_of(30), 99, SAY, time_zone=None)
    assert "Rows 26–30 of 30" in html
    empty = rank_view.render(table_of(0), 0, SAY, time_zone=None)
    assert "<table>" not in empty


def test_keyboard_navigation() -> None:
    one = rank_view.keyboard(10, 0, SAY, icons=False)
    assert [b.callback_data for row in one.inline_keyboard for b in row] == ["rk:0:r"]
    many = rank_view.keyboard(60, 1, SAY, icons=False)
    data = [b.callback_data for row in many.inline_keyboard for b in row]
    assert data == ["rk:0", "rk:0", "rk:noop", "rk:2", "rk:2", "rk:1:r"]
    assert all(len((d or "").encode()) <= 64 for d in data)


def handles(items: Sequence[str]) -> list[str]:
    return list(items)
