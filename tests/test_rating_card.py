"""RatingService.card: one user's rating, contest count and last change, with a short cache."""

from __future__ import annotations

from datetime import UTC, datetime

from cpstands.domain.contest import RatingChange, UserRating
from cpstands.services.ratings import TTL_S, RatingService
from tests.support.clock import FakeClock
from tests.support.sources import FakeSource

AT = datetime(2026, 10, 1, tzinfo=UTC)


def make(clock: FakeClock) -> tuple[RatingService, FakeSource]:
    source = FakeSource(
        ["tourist", "petr"],
        ratings={
            "tourist": UserRating("tourist", 3800, 3979, "legendary grandmaster", "x"),
            "petr": UserRating("Petr", None, None, None, None),
        },
        histories={
            "tourist": [
                RatingChange(1, "First", 4, 1500, 1600, AT),
                RatingChange(2, "Second", 2, 1600, 1550, AT.replace(month=11)),
            ]
        },
    )
    return RatingService(source, clock=clock.monotonic), source  # type: ignore[arg-type]


async def test_card_counts_contests_and_keeps_the_last_change() -> None:
    service, _ = make(FakeClock())
    card = await service.card("TOURIST")
    assert card is not None
    assert (card.user.handle, card.contests) == ("tourist", 2)
    assert card.last is not None
    assert (card.last.contest_name, card.last.delta) == ("Second", -50)


async def test_card_of_an_unrated_user_has_no_history() -> None:
    service, _ = make(FakeClock())
    card = await service.card("petr")
    assert card is not None
    assert (card.user.rating, card.contests, card.last) == (None, 0, None)


async def test_card_of_an_unknown_user_is_none_and_cached_too() -> None:
    service, source = make(FakeClock())
    assert await service.card("nobody") is None
    assert await service.card("NOBODY") is None
    assert source.rating_fetches == 1


async def test_card_is_cached_until_the_ttl_ends() -> None:
    clock = FakeClock()
    service, source = make(clock)
    first = await service.card("tourist")
    assert await service.card("tourist") is first
    assert source.rating_fetches == 1
    clock.advance(TTL_S + 1)
    assert await service.card("tourist") is not first
    assert source.rating_fetches == 2
