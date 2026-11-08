"""The one-shot API-key friend import: signing, the call, and the chat flow that guards the key."""

from __future__ import annotations

import hashlib
import json

import httpx
import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import DeleteMessage
from sqlalchemy import text

from cpstands.bot.import_gate import WAIT_S, ImportGate
from cpstands.db import repos
from cpstands.sources.base import PermanentSourceError, RetryableSourceError
from cpstands.sources.codeforces import friends as cf
from tests.support.clock import FakeClock
from tests.support.telegram import message_update
from tests.test_bot import I18N, PRIVATE, Harness
from tests.test_bot import harness as harness  # the shared fixture

KEY = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"
SECRET = "0f1e2d3c4b5a69788796a5b4c3d2e1f001122334"
RAND = "abcdef"


# ------------------------------------------------------------------ signing


def test_signature_follows_the_documented_recipe() -> None:
    params = {"time": "1700000000", "apiKey": "K"}
    expected = hashlib.sha512(b"abcdef/user.friends?apiKey=K&time=1700000000#S").hexdigest()
    assert cf.sign("user.friends", params, "S", "abcdef") == "abcdef" + expected


def test_signature_depends_on_every_part() -> None:
    base = cf.sign("user.friends", {"apiKey": "K", "time": "1"}, "S", RAND)
    assert cf.sign("user.friends", {"apiKey": "K", "time": "2"}, "S", RAND) != base
    assert cf.sign("user.friends", {"apiKey": "K", "time": "1"}, "T", RAND) != base
    assert cf.sign("user.info", {"apiKey": "K", "time": "1"}, "S", RAND) != base
    assert cf.sign("user.friends", {"apiKey": "K", "time": "1"}, "S", "ffffff") != base


# ------------------------------------------------------------------ the call


def client(handler: httpx.MockTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=handler)


async def call(response: httpx.Response | Exception) -> tuple[str, ...]:
    seen: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if isinstance(response, Exception):
            raise response
        return response

    return await cf.fetch_friends(
        KEY,
        SECRET,
        http=client(httpx.MockTransport(respond)),
        now=lambda: 1_700_000_000.0,
        rand=lambda: RAND,
    )


def ok(result: object) -> httpx.Response:
    return httpx.Response(200, content=json.dumps({"status": "OK", "result": result}).encode())


def failed(comment: str) -> httpx.Response:
    return httpx.Response(
        400, content=json.dumps({"status": "FAILED", "comment": comment}).encode()
    )


async def test_the_request_is_signed_and_never_carries_the_secret() -> None:
    seen: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return ok(["tourist", "Petr"])

    friends = await cf.fetch_friends(
        KEY,
        SECRET,
        http=client(httpx.MockTransport(respond)),
        now=lambda: 1_700_000_000.0,
        rand=lambda: RAND,
    )
    assert friends == ("tourist", "Petr")
    (request,) = seen
    assert request.url.path.endswith("/user.friends")
    params = dict(request.url.params)
    assert set(params) == {"apiKey", "time", "apiSig"}
    assert params["apiKey"] == KEY
    assert params["apiSig"] == cf.sign(
        "user.friends", {"apiKey": KEY, "time": params["time"]}, SECRET, RAND
    )
    assert SECRET not in str(request.url)


async def test_an_empty_list_and_junk_entries() -> None:
    assert await call(ok([])) == ()
    assert await call(ok(["tourist", 5, None, "Petr"])) == ("tourist", "Petr")


@pytest.mark.parametrize(
    "comment",
    ["apiKey: Incorrect API key", "apiSig: Incorrect signature", "time: Time is out of range"],
)
async def test_a_rejected_key_is_an_invalid_credentials_error(comment: str) -> None:
    with pytest.raises(cf.InvalidCredentialsError):
        await call(failed(comment))


async def test_other_refusals_are_permanent_but_not_a_credentials_error() -> None:
    with pytest.raises(PermanentSourceError) as info:
        await call(failed("Call limit exceeded"))
    assert not isinstance(info.value, cf.InvalidCredentialsError)


async def test_outages_are_retryable_and_never_leak_the_key() -> None:
    for response in (
        httpx.Response(503),
        httpx.Response(429),
        httpx.Response(200, content=b"<html>maintenance</html>"),
        httpx.ConnectError(f"boom {KEY} {SECRET}"),
    ):
        with pytest.raises(RetryableSourceError) as info:
            await call(response)
        assert KEY not in str(info.value)
        assert SECRET not in str(info.value)
        assert info.value.__cause__ is None
        if isinstance(response, Exception):
            assert info.value.__suppress_context__  # httpx's text may hold the URL


async def test_odd_answers_are_refused() -> None:
    with pytest.raises(PermanentSourceError):
        await call(ok({"not": "a list"}))
    with pytest.raises(PermanentSourceError):
        await call(httpx.Response(200, content=b"[1, 2]"))
    with pytest.raises(PermanentSourceError):
        await call(httpx.Response(200, content=b"x" * (cf.MAX_BODY + 1)))


# ------------------------------------------------------------------ the gate


def test_the_gate_expires_and_can_be_closed() -> None:
    clock = FakeClock()
    gate = ImportGate(clock.monotonic)
    assert not gate.waiting(1)
    gate.arm(1)
    assert gate.waiting(1)
    assert not gate.waiting(2)
    clock.advance(WAIT_S - 1)
    assert gate.waiting(1)
    clock.advance(2)
    assert not gate.waiting(1)
    gate.arm(1)
    gate.disarm(1)
    assert not gate.waiting(1)


# ------------------------------------------------------------------ the chat flow


def secret_text() -> str:
    return f"{KEY} {SECRET}"


async def start(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/import")


async def test_import_refuses_groups_and_explains_in_private(harness: Harness) -> None:
    await harness.say(-100, 5, "/import")
    assert harness.session.last_text() == I18N.t(None, "import-private-only")
    await harness.say(-100, 5, secret_text())  # a group is never listening
    assert harness.friends.calls == []
    await start(harness)
    assert harness.session.last_text() == I18N.t(None, "import-intro")


async def test_text_is_ignored_until_import_was_asked_for(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, secret_text())
    assert harness.friends.calls == []
    assert harness.session.sent("DeleteMessage") == []


async def test_credentials_are_deleted_used_once_and_friends_are_added(harness: Harness) -> None:
    await start(harness)
    await harness.say(PRIVATE, PRIVATE, secret_text())
    deleted = harness.session.sent("DeleteMessage")
    assert len(deleted) == 1
    assert harness.friends.calls == [(KEY, SECRET)]
    async with harness.sessions() as session:
        keys = {k for k, _ in await repos.list_handles(session, PRIVATE, "codeforces")}
    assert keys == {"tourist", "jiangly"}
    reply = harness.session.last_text()
    assert reply.startswith(I18N.t(None, "import-done", count=2, already=0))
    assert I18N.t(None, "import-revoke") in reply
    # one attempt per /import: the same text again is just text
    await harness.say(PRIVATE, PRIVATE, secret_text())
    assert len(harness.friends.calls) == 1


async def test_the_key_never_reaches_the_replies_the_database_or_the_logs(
    harness: Harness, capsys: pytest.CaptureFixture[str]
) -> None:
    await start(harness)
    await harness.say(PRIVATE, PRIVATE, secret_text())
    assert KEY not in repr(harness.session.calls)
    assert SECRET not in repr(harness.session.calls)
    out = capsys.readouterr()
    assert KEY not in out.out + out.err
    assert SECRET not in out.out + out.err
    async with harness.sessions() as session:
        tables = (
            (
                await session.execute(
                    text("select tablename from pg_tables where schemaname = 'public'")
                )
            )
            .scalars()
            .all()
        )
        for table in tables:
            found = (
                await session.execute(
                    text(
                        f'select count(*) from "{table}" t where t::text like :k or t::text like :s'
                    ),
                    {"k": f"%{KEY}%", "s": f"%{SECRET}%"},
                )
            ).scalar_one()
            assert found == 0, table


async def test_a_message_without_two_codes_is_deleted_and_the_wait_continues(
    harness: Harness,
) -> None:
    await start(harness)
    await harness.say(PRIVATE, PRIVATE, f"{KEY} only-one")
    assert len(harness.session.sent("DeleteMessage")) == 1
    assert harness.session.last_text() == I18N.t(None, "import-bad-format")
    assert harness.friends.calls == []
    await harness.say(PRIVATE, PRIVATE, f"{KEY} {SECRET} {KEY}")  # three codes are no better
    assert harness.friends.calls == []
    await harness.say(PRIVATE, PRIVATE, secret_text())  # still listening
    assert len(harness.friends.calls) == 1


async def test_a_failed_delete_is_reported_so_the_owner_can_remove_the_message(
    harness: Harness,
) -> None:
    harness.session.delete_error = TelegramBadRequest(
        method=DeleteMessage(chat_id=1, message_id=1), message="message can't be deleted"
    )
    await start(harness)
    await harness.say(PRIVATE, PRIVATE, secret_text())
    assert I18N.t(None, "import-not-deleted") in harness.session.last_text()
    assert len(harness.friends.calls) == 1


@pytest.mark.parametrize(
    ("error", "key"),
    [
        (cf.InvalidCredentialsError("no"), "import-bad-credentials"),
        (RetryableSourceError("down"), "import-source-error"),
    ],
)
async def test_failures_are_explained_and_end_the_attempt(
    harness: Harness, error: Exception, key: str
) -> None:
    harness.friends.error = error
    await start(harness)
    await harness.say(PRIVATE, PRIVATE, secret_text())
    assert harness.session.last_text() == I18N.t(None, key)
    async with harness.sessions() as session:
        assert await repos.list_handles(session, PRIVATE, "codeforces") == []
    await harness.say(PRIVATE, PRIVATE, secret_text())
    assert len(harness.friends.calls) == 1  # the attempt is over


async def test_an_empty_friend_list_and_cancel(harness: Harness) -> None:
    harness.friends.result = ()
    await start(harness)
    await harness.say(PRIVATE, PRIVATE, secret_text())
    assert harness.session.last_text() == I18N.t(None, "import-none")
    await start(harness)
    await harness.say(PRIVATE, PRIVATE, "/cancel")
    assert harness.session.last_text() == I18N.t(None, "import-cancelled")
    await harness.say(PRIVATE, PRIVATE, secret_text())
    assert len(harness.friends.calls) == 1  # cancelled: nothing was listening


async def test_friends_beyond_the_limit_are_reported(harness: Harness) -> None:
    harness.friends.result = ("tourist", "jiangly", "Petr")
    await start(harness)
    async with harness.sessions() as session, session.begin():
        filler = {f"h{i}": f"h{i}" for i in range(99)}
        await repos.add_handles(session, PRIVATE, "codeforces", filler)
    await harness.say(PRIVATE, PRIVATE, secret_text())
    assert I18N.t(None, "import-over-limit", count=2) in harness.session.last_text()


async def test_a_command_is_never_taken_for_credentials(harness: Harness) -> None:
    await start(harness)
    await harness.feed(message_update(harness.uid(), PRIVATE, PRIVATE, f"/help {KEY} {SECRET}"))
    assert harness.friends.calls == []
    assert harness.session.sent("DeleteMessage") == []
