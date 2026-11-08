"""The Mini App's database API: init-data signatures, friends, settings and status."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlencode

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

TOKEN = "123456:TEST-token_for_signatures"
USER = 4242


def init_data(
    user_id: int = USER,
    *,
    token: str = TOKEN,
    auth_date: int | None = None,
    first_name: str = "Saidakbar Ыйк",
    tamper: dict[str, str] | None = None,
) -> str:
    """Init data signed exactly as Telegram signs it for a Mini App."""
    fields = {
        "query_id": "AAH-test",
        "user": json.dumps(
            {"id": user_id, "first_name": first_name, "language_code": "uz"}, ensure_ascii=False
        ),
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
    }
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    fields.update(tamper or {})
    return urlencode(fields)


@pytest.fixture
async def engine(migrated_database: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(migrated_database)
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO private.app_secrets (name, value) VALUES ('bot_token', :t)"),
            {"t": TOKEN},
        )
    yield engine
    await engine.dispose()


async def rpc(engine: AsyncEngine, sql: str, **params: Any) -> Any:
    async with engine.begin() as conn:
        return (await conn.execute(text(sql), params)).scalar_one()


async def friends(engine: AsyncEngine, data: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = await rpc(
        engine, "SELECT app_friends(:d)", d=init_data() if data is None else data
    )
    return result


def test_python_signature_matches_the_documented_recipe() -> None:
    # Negative control for the helper: a different token gives a different hash.
    assert init_data(token="other:token") != init_data()


async def test_a_valid_caller_gets_their_own_empty_list(engine: AsyncEngine) -> None:
    assert await friends(engine) == {"max": 200, "friends": []}
    chat_type = await rpc(engine, "SELECT chat_type FROM chats WHERE chat_id = :u", u=USER)
    assert chat_type == "private"


@pytest.mark.parametrize(
    "data",
    [
        init_data(token="999:wrong"),  # signed with another bot's token
        init_data(tamper={"user": json.dumps({"id": 1, "first_name": "X"})}),  # someone else's id
        init_data(tamper={"hash": "0" * 64}),
        init_data(auth_date=int(time.time()) - 2 * 86400),  # expired
        "",
        "user=%7B%22id%22%3A1%7D",  # no hash at all
    ],
    ids=["other-token", "swapped-user", "zero-hash", "expired", "empty", "unsigned"],
)
async def test_bad_init_data_is_refused(engine: AsyncEngine, data: str) -> None:
    with pytest.raises(DBAPIError):
        await friends(engine, data)
    count = await rpc(engine, "SELECT count(*) FROM chats")
    assert count == 0  # nothing was created for a refused caller


async def test_unconfigured_api_refuses_everyone(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM private.app_secrets"))
    with pytest.raises(DBAPIError, match="api not configured"):
        await friends(engine)


async def test_add_list_and_remove_friends(engine: AsyncEngine) -> None:
    res = await rpc(
        engine, "SELECT app_friends_add(:d, :h)", d=init_data(), h=["tourist", "Petr", "tourist"]
    )
    assert res["friends"] == ["tourist", "Petr"]
    assert res["added"] == ["tourist", "Petr"]
    assert res["already"] == 1
    res = await rpc(engine, "SELECT app_friends_remove(:d, :h)", d=init_data(), h=["PETR"])
    assert res["friends"] == ["tourist"]
    # Another user's list is separate.
    other = await friends(engine, init_data(user_id=5555))
    assert other["friends"] == []


async def test_bad_handles_are_refused(engine: AsyncEngine) -> None:
    with pytest.raises(DBAPIError, match="bad handle"):
        await rpc(engine, "SELECT app_friends_add(:d, :h)", d=init_data(), h=["ok", "drop table;"])
    assert (await friends(engine))["friends"] == []  # the whole call was rolled back


async def test_the_list_stops_at_200(engine: AsyncEngine) -> None:
    first = [f"u{i}" for i in range(199)]
    await rpc(engine, "SELECT app_friends_add(:d, :h)", d=init_data(), h=first)
    res = await rpc(engine, "SELECT app_friends_add(:d, :h)", d=init_data(), h=["x1", "x2", "u0"])
    assert res["added"] == ["x1"]
    assert res["overLimit"] == 1
    assert res["already"] == 1
    assert len(res["friends"]) == 200


async def test_settings_read_and_update(engine: AsyncEngine) -> None:
    s = await rpc(engine, "SELECT app_settings(:d)", d=init_data())
    assert s["status"] == "onboarding"  # a new chat: language is chosen later
    assert s["language"] is None
    patch = {
        "language": "ru",
        "timeZone": "Europe/Moscow",
        "reminders": [60, 1440],
        "notifyLevel": 2,
        "tableCols": 12,
        "summary": False,
    }
    s = await rpc(
        engine,
        "SELECT app_settings_update(:d, CAST(:p AS jsonb))",
        d=init_data(),
        p=json.dumps(patch),
    )
    assert s["language"] == "ru"
    assert s["timeZone"] == "Europe/Moscow"
    assert s["reminders"] == [1440, 60]
    assert s["notifyLevel"] == 2
    assert s["tableCols"] == 12
    assert s["summary"] is False


@pytest.mark.parametrize(
    "patch",
    [
        {"timeZone": "Mars/Base"},
        {"reminders": [7]},
        {"language": "de"},
        {"tableCols": 9},
        {"notifyLevel": 9},
    ],
    ids=["zone", "offset", "language", "cols", "level"],
)
async def test_invalid_settings_are_refused(engine: AsyncEngine, patch: dict[str, Any]) -> None:
    with pytest.raises(DBAPIError):
        await rpc(
            engine,
            "SELECT app_settings_update(:d, CAST(:p AS jsonb))",
            d=init_data(),
            p=json.dumps(patch),
        )


async def test_status_is_public_and_anonymous(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO runtime_state (key, value) VALUES ('bot.heartbeat', "
                '\'{"at": 1, "commit": "abc"}\')'
            )
        )
    status = await rpc(engine, "SELECT app_status()")
    assert status["heartbeat"]["commit"] == "abc"
    assert {
        "chats",
        "handles",
        "remindersSent24h",
        "liveContests",
        "nextContest",
        "now",
    } <= status.keys()
