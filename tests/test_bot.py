"""Handler tests: real PostgreSQL, real dispatcher, a fake Telegram session."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cpstands.bot import keyboards
from cpstands.bot.app import build_dispatcher, make_admin_checker
from cpstands.bot.deps import Deps
from cpstands.bot.ratelimit import RateLimiter
from cpstands.db import repos
from cpstands.db.engine import create_engine, create_session_factory
from cpstands.i18n import I18n
from cpstands.services import timezone as tzs
from cpstands.services.watchlist import WatchlistService
from tests.support.sources import FakeSource
from tests.support.telegram import (
    FakeSession,
    callback_update,
    chat_member_update,
    make_bot,
    message_update,
    my_chat_member_update,
)

PRIVATE = 77
GROUP = -1001111
ADMIN = 10
MEMBER = 11
I18N = I18n()


@dataclass
class Harness:
    dispatcher: Dispatcher
    bot: Bot
    session: FakeSession
    sessions: async_sessionmaker[AsyncSession]
    source: FakeSource
    _next: int = 1

    async def feed(self, update: Update) -> None:
        bound = Update.model_validate(
            update.model_dump(mode="json", by_alias=True, exclude_none=True),
            context={"bot": self.bot},
        )
        await self.dispatcher.feed_update(self.bot, bound)

    def uid(self) -> int:
        self._next += 1
        return self._next

    async def say(self, chat_id: int, user_id: int, text: str) -> None:
        await self.feed(message_update(self.uid(), chat_id, user_id, text))

    async def tap(self, chat_id: int, user_id: int, data: str) -> None:
        await self.feed(callback_update(self.uid(), chat_id, user_id, data))

    async def chat(self, chat_id: int) -> repos.ChatRecord | None:
        async with self.sessions() as session:
            return await repos.get_chat(session, chat_id)


@pytest.fixture
async def harness(migrated_database: str) -> AsyncIterator[Harness]:
    engine = create_engine(migrated_database, pool_size=3)
    sessions = create_session_factory(engine)
    fake = FakeSession()
    fake.member_status[(GROUP, ADMIN)] = "administrator"
    fake.member_status[(GROUP, MEMBER)] = "member"
    bot = make_bot(fake)
    source = FakeSource(["tourist", "jiangly", "Petr"])
    deps = Deps(
        i18n=I18N,
        sessions=sessions,
        watchlist=WatchlistService(sessions, source),  # type: ignore[arg-type]
        admin=make_admin_checker(bot),
    )
    yield Harness(build_dispatcher(deps, RateLimiter()), bot, fake, sessions, source)
    await engine.dispose()


async def test_start_in_private_chat_offers_languages(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/start")
    sent = harness.session.sent()[-1]
    assert sent["text"] == I18N.t(None, "pick-language")
    buttons = sent["reply_markup"]["inline_keyboard"][0]
    assert [b["callback_data"] for b in buttons] == ["set:lang:uz", "set:lang:ru", "set:lang:en"]
    chat = await harness.chat(PRIVATE)
    assert chat is not None
    assert chat.status == "onboarding"


async def test_full_onboarding_in_a_group_by_an_admin(harness: Harness) -> None:
    await harness.say(GROUP, ADMIN, "/start")
    await harness.tap(GROUP, ADMIN, "set:lang:ru")
    assert harness.session.last_text() == (
        f"{I18N.t('ru', 'onboarding-intro')}\n\n{I18N.t('ru', 'onboarding-pick-timezone')}"
    )
    await harness.tap(GROUP, ADMIN, "tz:set:Asia/Tashkent")
    chat = await harness.chat(GROUP)
    assert chat is not None
    assert (chat.language, chat.time_zone, chat.status) == ("ru", "Asia/Tashkent", "active")
    assert harness.session.last_text() == I18N.t(
        "ru", "setup-done", language="Русский", zone="Asia/Tashkent"
    )


async def test_non_admin_cannot_start_setup_or_tap_buttons(harness: Harness) -> None:
    await harness.say(GROUP, MEMBER, "/start")
    assert harness.session.last_text() == I18N.t(None, "setup-admin-needed")
    assert "reply_markup" not in harness.session.sent()[-1]

    await harness.tap(GROUP, MEMBER, "set:lang:en")
    alert = harness.session.alerts()[-1]
    assert alert["text"] == I18N.t(None, "not-admin")
    assert alert["show_alert"] is True
    chat = await harness.chat(GROUP)
    assert chat is not None
    assert chat.language is None


async def test_unknown_language_and_zone_buttons_are_rejected(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/start")
    await harness.tap(PRIVATE, PRIVATE, "set:lang:xx")
    await harness.tap(PRIVATE, PRIVATE, "tz:set:Asia/Nowhere")
    await harness.tap(PRIVATE, PRIVATE, "tz:set:../../etc/passwd")
    chat = await harness.chat(PRIVATE)
    assert chat is not None
    assert (chat.language, chat.time_zone) == (None, None)
    assert len(harness.session.alerts()) == 3


async def test_admin_status_change_is_picked_up_through_chat_member_updates(
    harness: Harness,
) -> None:
    await harness.say(GROUP, ADMIN, "/start")
    assert harness.session.last_text() == I18N.t(None, "pick-language")
    harness.session.member_status[(GROUP, ADMIN)] = "member"
    await harness.say(GROUP, ADMIN, "/start")  # still cached as admin
    assert harness.session.last_text() == I18N.t(None, "pick-language")
    await harness.feed(chat_member_update(harness.uid(), GROUP, ADMIN, "member"))
    await harness.say(GROUP, ADMIN, "/start")
    assert harness.session.last_text() == I18N.t(None, "setup-admin-needed")


async def test_admin_lookup_failure_denies(harness: Harness) -> None:
    class Boom(FakeSession):
        pass

    await harness.say(GROUP, 999, "/start")  # unknown user defaults to "member" -> denied
    assert harness.session.last_text() == I18N.t(None, "setup-admin-needed")


async def test_timezone_command_exact_choices_and_unknown(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/timezone Tashkent")
    chat = await harness.chat(PRIVATE)
    assert chat is not None
    assert chat.time_zone == "Asia/Tashkent"
    assert "Asia/Tashkent" in harness.session.last_text()

    await harness.say(PRIVATE, PRIVATE, "/timezone new_y")
    sent = harness.session.sent()[-1]
    callbacks = [b["callback_data"] for row in sent["reply_markup"]["inline_keyboard"] for b in row]
    assert "tz:set:America/New_York" in callbacks
    chat = await harness.chat(PRIVATE)
    assert chat is not None
    assert chat.time_zone == "Asia/Tashkent"  # choices do not change anything until tapped

    await harness.say(PRIVATE, PRIVATE, "/timezone qqqqqqqqqq")
    assert harness.session.last_text() == I18N.t(None, "timezone-not-found", query="qqqqqqqqqq")

    await harness.say(GROUP, MEMBER, "/timezone Tokyo")
    assert harness.session.last_text() == I18N.t(None, "not-admin")


async def test_track_add_list_remove(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/track add tourist, jiangly, ghost, bad!")
    text = harness.session.last_text()
    assert "tourist, jiangly" in text
    assert "ghost" in text
    assert "bad!" in text

    await harness.say(PRIVATE, PRIVATE, "/track list")
    assert harness.session.last_text() == (
        f"{I18N.t(None, 'track-list-header', count=2)}\njiangly, tourist"
    )
    await harness.say(PRIVATE, PRIVATE, "/friends remove TOURIST")
    assert harness.session.last_text() == I18N.t(None, "track-removed", handles="tourist")
    await harness.say(PRIVATE, PRIVATE, "/track")
    assert harness.session.last_text() == I18N.t(None, "track-usage")
    await harness.say(PRIVATE, PRIVATE, "/track add")
    assert harness.session.last_text() == I18N.t(None, "track-nothing")


async def test_track_changes_need_an_admin_but_listing_does_not(harness: Harness) -> None:
    await harness.say(GROUP, ADMIN, "/track add tourist")
    await harness.say(GROUP, MEMBER, "/track add jiangly")
    assert harness.session.last_text() == I18N.t(None, "not-admin")
    await harness.say(GROUP, MEMBER, "/track remove tourist")
    assert harness.session.last_text() == I18N.t(None, "not-admin")
    await harness.say(GROUP, MEMBER, "/track list")
    assert "tourist" in harness.session.last_text()


async def test_track_reports_a_source_outage_and_changes_nothing(harness: Harness) -> None:
    harness.source.fail = True
    await harness.say(PRIVATE, PRIVATE, "/track add tourist")
    assert harness.session.last_text() == I18N.t(None, "track-source-error")
    harness.source.fail = False
    await harness.say(PRIVATE, PRIVATE, "/track list")
    assert harness.session.last_text() == I18N.t(None, "track-list-empty")


async def test_settings_shows_summary_and_menu_buttons(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/settings")
    sent = harness.session.sent()[-1]
    assert "Sozlamalar" in sent["text"]
    callbacks = [b["callback_data"] for b in sent["reply_markup"]["inline_keyboard"][0]]
    assert callbacks == [keyboards.MENU_LANG, keyboards.MENU_TZ]
    await harness.tap(PRIVATE, PRIVATE, keyboards.MENU_LANG)
    assert harness.session.last_text() == I18N.t(None, "pick-language")


async def test_unfinished_commands_answer_coming_soon(harness: Harness) -> None:
    for command in ("/standings", "/upcoming", "/rank", "/privacy", "/delete"):
        await harness.say(PRIVATE, PRIVATE, command)
        assert harness.session.last_text() == I18N.t(None, "coming-soon")


async def test_help(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/help")
    assert harness.session.last_text() == I18N.t(None, "help-text")


async def test_bot_added_to_and_removed_from_a_group(harness: Harness) -> None:
    await harness.feed(my_chat_member_update(harness.uid(), GROUP, "left", "member"))
    assert harness.session.last_text() == I18N.t(None, "group-added")
    chat = await harness.chat(GROUP)
    assert chat is not None
    assert chat.status == "onboarding"

    await harness.feed(my_chat_member_update(harness.uid(), GROUP, "member", "administrator"))
    assert len(harness.session.sent()) == 1  # promotion is not a new join

    await harness.feed(my_chat_member_update(harness.uid(), GROUP, "administrator", "kicked"))
    chat = await harness.chat(GROUP)
    assert chat is not None
    assert chat.status == "removed"


async def test_rate_limit_answers_once_then_stays_quiet(migrated_database: str) -> None:
    engine = create_engine(migrated_database, pool_size=2)
    sessions = create_session_factory(engine)
    fake = FakeSession()
    bot = make_bot(fake)
    deps = Deps(
        i18n=I18N,
        sessions=sessions,
        watchlist=WatchlistService(sessions, FakeSource([])),  # type: ignore[arg-type]
        admin=make_admin_checker(bot),
    )
    harness = Harness(
        build_dispatcher(deps, RateLimiter(per_user=3)), bot, fake, sessions, FakeSource([])
    )
    for _ in range(3):
        await harness.say(PRIVATE, PRIVATE, "/help")
    before = len(fake.sent())
    await harness.say(PRIVATE, PRIVATE, "/help")
    assert fake.last_text() == I18N.t(None, "rate-limited")
    await harness.say(PRIVATE, PRIVATE, "/help")
    await harness.say(PRIVATE, PRIVATE, "/help")
    assert len(fake.sent()) == before + 1
    await engine.dispose()


async def test_unexpected_errors_are_logged_and_answered(harness: Harness) -> None:
    async def explode(*_: object, **__: object) -> object:
        raise RuntimeError("boom")

    harness.dispatcher["deps"].watchlist.list = explode
    await harness.say(PRIVATE, PRIVATE, "/track list")
    assert harness.session.last_text() == I18N.t(None, "error-generic")


def test_every_callback_fits_telegrams_limit() -> None:
    longest = max(tzs.known_zones(), key=len)
    for data in (f"{keyboards.TZ_PREFIX}{longest}", f"{keyboards.LANG_PREFIX}uz"):
        assert len(data.encode()) <= keyboards.MAX_CALLBACK_BYTES
    for language in ("uz", "ru", "en"):
        keyboards.timezone_keyboard(tzs.popular_zones(language))
    with pytest.raises(ValueError, match="longer than"):
        keyboards.timezone_keyboard(["X" * 80])
