"""Signed group links: Python and SQL agree, and app_group refuses anything else."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from collections.abc import AsyncIterator, Iterator
from urllib.parse import urlencode

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from cpstands.services import applink
from tests.test_miniapp_api import TOKEN

GROUP = -1001234567890


@pytest.fixture(autouse=True)
def signed_links() -> Iterator[None]:
    applink.configure(TOKEN)
    yield
    applink._secret = None


@pytest.fixture
async def engine(migrated_database: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(migrated_database)
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO private.app_secrets VALUES ('bot_token', :t)"), {"t": TOKEN}
        )
        await conn.execute(
            text(
                "INSERT INTO chats (chat_id, chat_type, title, status, language) "
                "VALUES (:g, 'supergroup', 'CP Club', 'active', 'uz')"
            ),
            {"g": GROUP},
        )
        await conn.execute(
            text(
                "INSERT INTO watched_handles (chat_id, platform, handle_key, handle_display) VALUES "
                "(:g, 'codeforces', 'tourist', 'tourist'), (:g, 'codeforces', 'petr', 'Petr')"
            ),
            {"g": GROUP},
        )
    yield engine
    await engine.dispose()


def opened_with(param: str) -> str:
    """Init data as Telegram signs it when the Mini App opens from a link with ``param``."""
    fields = {
        "user": json.dumps({"id": 4242, "first_name": "A"}),
        "auth_date": str(int(time.time())),
        "start_param": param,
    }
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


async def group(engine: AsyncEngine, data: str) -> dict[str, object]:
    async with engine.begin() as conn:
        value: dict[str, object] = (
            await conn.execute(text("SELECT app_group(:d)"), {"d": data})
        ).scalar_one()
        return value


def test_group_links_are_signed_and_plain_links_stay_plain() -> None:
    link = applink.link("standings_2279", GROUP)
    assert link.startswith("https://t.me/cpstandsbot?startapp=g1001234567890_")
    assert link.endswith("_s2279")
    assert (
        applink.link("profile_tourist", 77) == "https://t.me/cpstandsbot?startapp=profile_tourist"
    )


def test_without_a_secret_groups_get_plain_links() -> None:
    applink._secret = None
    assert applink.link("contests", GROUP) == "https://t.me/cpstandsbot?startapp=contests"


async def test_a_signed_link_opens_the_group(engine: AsyncEngine) -> None:
    param = applink.group_param(GROUP, 2279)
    assert param is not None
    view = await group(engine, opened_with(param))
    assert view["chatId"] == GROUP
    assert view["title"] == "CP Club"
    assert sorted(view["handles"]) == ["Petr", "tourist"]  # type: ignore[call-overload]
    assert view["contestId"] == 2279
    assert view["viewer"] == 4242


@pytest.mark.parametrize(
    "param",
    [
        "g1001234567890_0000000000000000",  # wrong signature
        "g9999999999_" + applink.group_signature(GROUP, TOKEN.encode()),  # another group's id
        "profile_tourist",  # not a group link
        "",
    ],
    ids=["forged", "other-group", "not-group", "none"],
)
async def test_other_links_are_refused(engine: AsyncEngine, param: str) -> None:
    with pytest.raises(DBAPIError):
        await group(engine, opened_with(param))


async def test_the_telegram_signature_is_still_required(engine: AsyncEngine) -> None:
    param = applink.group_param(GROUP)
    assert param is not None
    forged = opened_with(param).replace("hash=", "hash=0")
    with pytest.raises(DBAPIError):
        await group(engine, forged)


async def test_an_inactive_group_is_refused(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE chats SET status = 'removed' WHERE chat_id = :g"), {"g": GROUP}
        )
    param = applink.group_param(GROUP)
    assert param is not None
    with pytest.raises(DBAPIError, match="group not active"):
        await group(engine, opened_with(param))
