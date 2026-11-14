from __future__ import annotations

import pytest

from cpstands.services.admin import ANONYMOUS_ADMIN_ID, AdminChecker
from tests.support.clock import FakeClock


class Fetcher:
    def __init__(self, status: str = "administrator") -> None:
        self.status = status
        self.calls = 0
        self.fail = False

    async def __call__(self, chat_id: int, user_id: int) -> str:
        self.calls += 1
        if self.fail:
            raise RuntimeError("telegram down")
        return self.status


def _checker(fetcher: Fetcher, clock: FakeClock) -> AdminChecker:
    return AdminChecker(fetcher, ttl_s=300, clock=clock.monotonic)


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("creator", True),
        ("administrator", True),
        ("member", False),
        ("restricted", False),
        ("left", False),
        ("kicked", False),
    ],
)
async def test_status_decides(status: str, expected: bool) -> None:
    checker = _checker(Fetcher(status), FakeClock())
    assert await checker.is_admin(-100, 5) is expected


async def test_private_chats_and_anonymous_admin_need_no_lookup() -> None:
    fetcher = Fetcher("left")
    checker = _checker(fetcher, FakeClock())
    assert await checker.is_admin(5, 5, private=True)
    assert await checker.is_admin(-100, ANONYMOUS_ADMIN_ID)
    assert fetcher.calls == 0


async def test_answer_is_cached_for_five_minutes() -> None:
    fetcher, clock = Fetcher(), FakeClock()
    checker = _checker(fetcher, clock)
    await checker.is_admin(-100, 5)
    clock.advance(299)
    await checker.is_admin(-100, 5)
    assert fetcher.calls == 1
    clock.advance(2)
    await checker.is_admin(-100, 5)
    assert fetcher.calls == 2


async def test_invalidate_forces_a_fresh_lookup() -> None:
    fetcher, clock = Fetcher(), FakeClock()
    checker = _checker(fetcher, clock)
    assert await checker.is_admin(-100, 5)
    fetcher.status = "member"
    checker.invalidate(-100, 5)
    assert not await checker.is_admin(-100, 5)
    fetcher.status = "administrator"
    checker.invalidate_chat(-100)
    assert await checker.is_admin(-100, 5)


async def test_failure_is_denied_and_not_cached() -> None:
    fetcher, clock = Fetcher(), FakeClock()
    checker = _checker(fetcher, clock)
    fetcher.fail = True
    assert not await checker.is_admin(-100, 5)
    fetcher.fail = False
    assert await checker.is_admin(-100, 5)
    assert fetcher.calls == 2


async def test_cache_is_per_chat_and_user() -> None:
    fetcher = Fetcher()
    checker = _checker(fetcher, FakeClock())
    await checker.is_admin(-100, 5)
    await checker.is_admin(-100, 6)
    await checker.is_admin(-200, 5)
    assert fetcher.calls == 3
