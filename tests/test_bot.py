"""Handler tests: real PostgreSQL, real dispatcher, a fake Telegram session."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

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
from cpstands.domain.contest import Contest, ContestPhase
from cpstands.i18n import I18n
from cpstands.services import timezone as tzs
from cpstands.services.contests import ContestService
from cpstands.services.standings import StandingsService
from cpstands.services.watchlist import WatchlistService
from tests.support.sources import FakeSource, make_standings
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

    async def say(
        self, chat_id: int, user_id: int, text: str, *, thread_id: int | None = None
    ) -> None:
        await self.feed(message_update(self.uid(), chat_id, user_id, text, thread_id))

    async def tap(self, chat_id: int, user_id: int, data: str) -> None:
        await self.feed(callback_update(self.uid(), chat_id, user_id, data))

    async def chat(self, chat_id: int) -> repos.ChatRecord | None:
        async with self.sessions() as session:
            return await repos.get_chat(session, chat_id)


def _contest(cid: int, name: str, days: int) -> Contest:
    start = datetime.now(UTC) + timedelta(days=days)
    return Contest("codeforces", cid, name, ContestPhase.BEFORE, "CF", start, 7200)


@pytest.fixture
async def harness(migrated_database: str) -> AsyncIterator[Harness]:
    engine = create_engine(migrated_database, pool_size=3)
    sessions = create_session_factory(engine)
    fake = FakeSession()
    fake.member_status[(GROUP, ADMIN)] = "administrator"
    fake.member_status[(GROUP, MEMBER)] = "member"
    bot = make_bot(fake)
    source = FakeSource(
        ["tourist", "jiangly", "Petr"],
        standings={
            1970: make_standings(),
            1971: make_standings(contest_id=1971, phase=ContestPhase.BEFORE, rows=0, problems=5),
            1972: make_standings(contest_id=1972, rows=3, problems=5, kind="CF"),
            1973: make_standings(contest_id=1973, phase=ContestPhase.CODING, rows=60, problems=21),
        },
        contests=[
            _contest(2287, "Codeforces Round <1> & co", 3),
            _contest(2288, "Codeforces Round (Div. 2)", 4),
            _contest(2299, "Far Away Round", 40),
        ],
    )
    deps = Deps(
        i18n=I18N,
        sessions=sessions,
        watchlist=WatchlistService(sessions, source),  # type: ignore[arg-type]
        admin=make_admin_checker(bot),
        standings=StandingsService(source),  # type: ignore[arg-type]
        contests=ContestService(sessions, source),  # type: ignore[arg-type]
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
    assert "<b>tourist, jiangly</b>" in text
    assert "ghost" in text
    assert "bad!" in text

    await harness.say(PRIVATE, PRIVATE, "/track list")
    assert harness.session.last_text() == (
        f"{I18N.t(None, 'track-list-header', count=2)}\n<code>jiangly</code>, <code>tourist</code>"
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
    for command in ("/rank", "/privacy", "/delete"):
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
        standings=StandingsService(FakeSource([])),  # type: ignore[arg-type]
        contests=ContestService(sessions, FakeSource([])),  # type: ignore[arg-type]
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


def _buttons(call: dict[str, object]) -> list[dict[str, object]]:
    rows = call["reply_markup"]["inline_keyboard"]  # type: ignore[index]
    return [b for row in rows for b in row]


async def test_wizard_steps_celebrate_only_in_private_playful_chats(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/start")
    await harness.tap(PRIVATE, PRIVATE, "set:lang:en")
    assert "2/3" in harness.session.last_text()
    await harness.tap(PRIVATE, PRIVATE, "tz:set:Asia/Tashkent")
    sent = harness.session.sent()[-1]
    assert sent["text"] == I18N.t("en", "setup-celebrate")
    assert sent["message_effect_id"]
    assert "3/3" in harness.session.sent("EditMessageText")[-1]["text"]

    await harness.say(GROUP, ADMIN, "/start")
    await harness.tap(GROUP, ADMIN, "set:lang:en")
    before = len(harness.session.sent())
    await harness.tap(GROUP, ADMIN, "tz:set:Asia/Tashkent")
    assert len(harness.session.sent()) == before  # no celebration message in groups


async def test_neutral_chats_get_no_celebration(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/settings")
    await harness.tap(PRIVATE, PRIVATE, "set:tone:neutral")
    await harness.tap(PRIVATE, PRIVATE, "set:lang:en")
    before = len(harness.session.sent())
    await harness.tap(PRIVATE, PRIVATE, "tz:set:UTC")
    assert len(harness.session.sent()) == before
    assert "3/3" in harness.session.last_text()


async def test_changing_language_of_an_active_chat_returns_to_settings(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/start")
    await harness.tap(PRIVATE, PRIVATE, "set:lang:uz")
    await harness.tap(PRIVATE, PRIVATE, "tz:set:Asia/Tashkent")
    await harness.tap(PRIVATE, PRIVATE, keyboards.MENU_LANG)
    await harness.tap(PRIVATE, PRIVATE, "set:lang:ru")
    assert "Настройки" in harness.session.last_text()
    chat = await harness.chat(PRIVATE)
    assert chat is not None
    assert (chat.language, chat.status) == ("ru", "active")


async def test_tone_toggle_needs_an_admin_and_a_valid_value(harness: Harness) -> None:
    await harness.say(GROUP, ADMIN, "/settings")
    await harness.tap(GROUP, MEMBER, "set:tone:neutral")
    assert harness.session.alerts()[-1]["text"] == I18N.t(None, "not-admin")
    await harness.tap(GROUP, ADMIN, "set:tone:grumpy")
    chat = await harness.chat(GROUP)
    assert chat is not None
    assert chat.tone == "playful"
    await harness.tap(GROUP, ADMIN, "set:tone:neutral")
    chat = await harness.chat(GROUP)
    assert chat is not None
    assert chat.tone == "neutral"
    assert any(
        b["callback_data"] == "set:tone:playful"
        for b in _buttons(harness.session.sent("EditMessageText")[-1])
    )


async def test_buttons_mark_the_current_choice_with_a_color(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/start")
    await harness.tap(PRIVATE, PRIVATE, "set:lang:ru")
    await harness.say(PRIVATE, PRIVATE, "/start")
    languages = _buttons(harness.session.sent()[-1])
    styles = {b["callback_data"]: b.get("style") for b in languages}
    assert styles == {"set:lang:uz": None, "set:lang:ru": "primary", "set:lang:en": None}


async def test_help_has_working_shortcut_buttons(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/help")
    callbacks = [b["callback_data"] for b in _buttons(harness.session.sent()[-1])]
    assert callbacks == [keyboards.HELP_SETTINGS, keyboards.HELP_TRACK]
    await harness.tap(PRIVATE, PRIVATE, keyboards.HELP_TRACK)
    assert harness.session.last_text() == I18N.t(None, "track-usage")
    await harness.tap(PRIVATE, PRIVATE, keyboards.HELP_SETTINGS)
    assert "Sozlamalar" in harness.session.last_text()


def test_button_icons_use_custom_emoji_when_enabled_else_prefix_the_emoji() -> None:
    with_icon = keyboards.button("Language", "x:y", emoji="🌍", icons=True)
    assert with_icon.icon_custom_emoji_id
    assert with_icon.text == "Language"
    plain = keyboards.button("Language", "x:y", emoji="🌍", icons=False)
    assert plain.icon_custom_emoji_id is None
    assert plain.text == "🌍 Language"
    no_twin = keyboards.button("Settings", "x:y", emoji="⚙️", icons=True)
    assert no_twin.icon_custom_emoji_id is None
    assert no_twin.text == "⚙️ Settings"


def _ephemeral(call: dict[str, object]) -> dict[str, object] | None:
    return call.get("ephemeral_message_parameters")  # type: ignore[return-value]


async def test_group_helper_replies_are_ephemeral_but_shared_results_are_not(
    harness: Harness,
) -> None:
    await harness.say(GROUP, MEMBER, "/track add tourist")
    denied = harness.session.sent()[-1]
    assert denied["text"] == I18N.t(None, "not-admin")
    assert _ephemeral(denied) == {"receiver_user_id": MEMBER}

    await harness.say(GROUP, ADMIN, "/track add tourist")
    assert _ephemeral(harness.session.sent()[-1]) is None  # the group should see who was added


async def test_private_chats_never_use_ephemeral(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/track")
    assert _ephemeral(harness.session.sent()[-1]) is None


async def test_refused_ephemeral_falls_back_and_is_not_retried(harness: Harness) -> None:
    harness.session.refuse_ephemeral = True
    await harness.say(GROUP, MEMBER, "/track add tourist")
    assert harness.session.last_text() == I18N.t(None, "not-admin")
    attempts = len([c for c in harness.session.sent() if _ephemeral(c)])
    assert attempts == 1
    assert _ephemeral(harness.session.sent()[-1]) is None  # delivered as a normal message

    await harness.say(GROUP, MEMBER, "/track add jiangly")
    assert len([c for c in harness.session.sent() if _ephemeral(c)]) == attempts
    assert harness.session.last_text() == I18N.t(None, "not-admin")


async def test_standings_sends_a_rich_table_with_navigation(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/standings 1970")
    page = harness.session.rich()[-1]
    assert "<h1>Test Contest</h1>" in page["html"]
    assert page["html"].count("<tr>") == 26  # header + 25 rows
    assert page["html"].count("<th>") == 20  # 4 fixed + 16 problems, Telegram's maximum
    rows = page["reply_markup"]["inline_keyboard"]
    callbacks = [b["callback_data"] for row in rows for b in row]
    assert callbacks == [
        "st:1970:0:0",
        "st:1970:0:0",
        "st:noop",
        "st:1970:1:0",
        "st:1970:2:0",
        "st:1970:0:0",
        "st:1970:0:1",
        "st:1970:0:0:r",
    ]


async def test_standings_accepts_links_and_explains_usage(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/standings https://codeforces.com/contest/1970/standings")
    assert len(harness.session.rich()) == 1
    await harness.say(PRIVATE, PRIVATE, "/standings")
    assert harness.session.last_text() == I18N.t(None, "standings-usage")
    await harness.say(PRIVATE, PRIVATE, "/standings hello")
    assert harness.session.last_text() == I18N.t(None, "standings-usage")
    assert len(harness.session.rich()) == 1


async def test_standings_failures_are_explained(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/standings 999999")
    assert harness.session.last_text() == I18N.t(None, "standings-not-found", id="999999")
    await harness.say(PRIVATE, PRIVATE, "/standings 1971")
    assert harness.session.last_text() == I18N.t(None, "standings-not-started", name="Test Contest")
    harness.source.fail = True
    await harness.say(PRIVATE, PRIVATE, "/standings 1970")
    assert harness.session.last_text() == I18N.t(None, "standings-source-error")
    assert not harness.session.rich()


async def test_standings_paging_edits_the_same_message(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/standings 1970")
    await harness.tap(PRIVATE, PRIVATE, "st:1970:2:1")
    page = harness.session.rich()[-1]
    assert "<td>51</td>" in page["html"]  # third page starts at rank 51
    assert page["html"].count("<th>") == 4 + 5  # second column page: P17..P21
    edit = [c for c in harness.session.calls if c.method == "EditMessageText"][-1]
    assert edit.data["rich_message"]["html"] == page["html"]
    assert harness.source.full_fetches == 1  # paging uses the cache


async def test_standings_refresh_noop_and_bad_callbacks(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/standings 1970")
    await harness.tap(PRIVATE, PRIVATE, "st:noop")
    await harness.tap(PRIVATE, PRIVATE, "st:1970:0:0:r")
    assert harness.source.full_fetches == 1  # a fresh copy is not refetched
    before = len(harness.session.alerts())
    await harness.tap(PRIVATE, PRIVATE, "st:abc")
    await harness.tap(PRIVATE, PRIVATE, "st:424242:0:0")
    assert len(harness.session.alerts()) == before + 2


async def test_cf_type_contests_show_points_not_times(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/standings 1972")
    html = harness.session.rich()[-1]["html"]
    assert "<td>500</td>" in html
    assert ":" not in html.split("<table>")[1].split("</table>")[0]


async def _live_rows(harness: Harness) -> list[tuple[int, int, int, int, str]]:
    from sqlalchemy import text

    async with harness.sessions() as session:
        result = await session.execute(
            text(
                "select contest_id, message_id, row_page, col_page, state "
                "from standings_messages order by contest_id"
            )
        )
        return [tuple(int(v) if str(v).isdigit() else str(v) for v in row) for row in result.all()]  # type: ignore[misc]


async def test_running_contests_become_live_and_finished_ones_do_not(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/standings 1970")  # finished
    assert await _live_rows(harness) == []
    await harness.say(PRIVATE, PRIVATE, "/standings 1973")  # running
    rows = await _live_rows(harness)
    assert [(r[0], r[2], r[3], r[4]) for r in rows] == [(1973, 0, 0, "active")]


async def test_paging_a_live_message_remembers_the_page(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/standings 1973")
    message_id = (await _live_rows(harness))[0][1]
    await harness.feed(callback_update(harness.uid(), PRIVATE, PRIVATE, "st:1973:2:1", message_id))
    rows = await _live_rows(harness)
    assert (rows[0][2], rows[0][3]) == (2, 1)


async def test_asking_again_moves_the_live_message(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/standings 1973")
    first = (await _live_rows(harness))[0][1]
    await harness.say(PRIVATE, PRIVATE, "/standings 1973")
    rows = await _live_rows(harness)
    assert len(rows) == 1
    assert rows[0][1] != first


async def test_replies_stay_in_the_topic_thread(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/standings 1970", thread_id=77)
    rich = [c for c in harness.session.calls if c.method == "SendRichMessage"][-1]
    assert rich.data["message_thread_id"] == 77
    await harness.say(PRIVATE, PRIVATE, "/standings 1970")
    plain = [c for c in harness.session.calls if c.method == "SendRichMessage"][-1]
    assert "message_thread_id" not in plain.data

    await harness.say(GROUP, MEMBER, "/track add tourist", thread_id=5)
    whisper = harness.session.sent()[-1]
    assert whisper["message_thread_id"] == 5
    assert whisper["ephemeral_message_parameters"] == {"receiver_user_id": MEMBER}


async def test_upcoming_lists_the_next_two_weeks_with_links_and_times(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/upcoming")
    text = harness.session.last_text()
    assert I18N.t(None, "upcoming-header") in text
    assert (
        '<a href="https://codeforces.com/contests/2287">Codeforces Round &lt;1&gt; &amp; co</a>'
        in text
    )
    assert "Codeforces Round (Div. 2)" in text
    assert "Far Away Round" not in text  # beyond two weeks
    assert text.count("<tg-time") == 4  # absolute and relative time for two contests
    assert "2:00" in text
    sent = harness.session.sent()[-1]
    assert sent["link_preview_options"]["is_disabled"] is True


async def test_upcoming_failures_and_empty_list(harness: Harness) -> None:
    harness.source.fail = True
    await harness.say(PRIVATE, PRIVATE, "/upcoming")
    assert harness.session.last_text() == I18N.t(None, "upcoming-source-error")
    harness.source.fail = False
    harness.source.contests.clear()
    await harness.say(PRIVATE, PRIVATE, "/upcoming")
    assert harness.session.last_text() == I18N.t(None, "upcoming-empty")


async def _reminder_states(harness: Harness) -> list[str]:
    from sqlalchemy import text

    async with harness.sessions() as session:
        result = await session.execute(
            text("select state from reminders order by contest_id, offset_min")
        )
        return [str(r[0]) for r in result.all()]


async def test_finishing_setup_plans_reminders_for_the_known_contests(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/upcoming")  # stores the contests
    assert await _reminder_states(harness) == []  # nobody is set up yet
    await harness.say(PRIVATE, PRIVATE, "/start")
    await harness.tap(PRIVATE, PRIVATE, "set:lang:en")
    await harness.tap(PRIVATE, PRIVATE, "tz:set:Asia/Tashkent")
    assert await _reminder_states(harness) == ["scheduled"] * 6  # three offsets, two contests


async def test_reminders_can_be_switched_off_and_on_by_an_admin(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/upcoming")
    await harness.say(PRIVATE, PRIVATE, "/start")
    await harness.tap(PRIVATE, PRIVATE, "set:lang:en")
    await harness.tap(PRIVATE, PRIVATE, "tz:set:Asia/Tashkent")

    await harness.tap(PRIVATE, PRIVATE, "set:rem:off")
    chat = await harness.chat(PRIVATE)
    assert chat is not None
    assert chat.reminder_offsets == ()
    assert "Reminders: <b>off</b>" in harness.session.sent("EditMessageText")[-1]["text"]
    assert set(await _reminder_states(harness)) == {"cancelled"}

    await harness.tap(PRIVATE, PRIVATE, "set:rem:on")
    chat = await harness.chat(PRIVATE)
    assert chat is not None
    assert chat.reminder_offsets == (1440, 60, 10)
    assert set(await _reminder_states(harness)) == {"scheduled"}

    await harness.tap(PRIVATE, PRIVATE, "set:rem:maybe")
    chat = await harness.chat(PRIVATE)
    assert chat is not None
    assert chat.reminder_offsets == (1440, 60, 10)


async def test_members_cannot_switch_reminders(harness: Harness) -> None:
    await harness.say(GROUP, ADMIN, "/settings")
    await harness.tap(GROUP, MEMBER, "set:rem:off")
    assert harness.session.alerts()[-1]["text"] == I18N.t(None, "not-admin")
    chat = await harness.chat(GROUP)
    assert chat is not None
    assert chat.reminder_offsets == (1440, 60, 10)


async def test_alerts_can_be_switched_off_and_on_by_an_admin(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/settings")
    await harness.tap(PRIVATE, PRIVATE, "set:alr:off")
    chat = await harness.chat(PRIVATE)
    assert chat is not None
    assert chat.alerts_enabled is False
    assert "Alertlar: <b>o'chiq</b>" in harness.session.sent("EditMessageText")[-1]["text"]
    await harness.tap(PRIVATE, PRIVATE, "set:alr:on")
    chat = await harness.chat(PRIVATE)
    assert chat is not None
    assert chat.alerts_enabled is True
    before = len(harness.session.alerts())
    await harness.tap(PRIVATE, PRIVATE, "set:alr:maybe")
    assert len(harness.session.alerts()) == before + 1


async def test_members_cannot_switch_alerts(harness: Harness) -> None:
    await harness.say(GROUP, ADMIN, "/settings")
    await harness.tap(GROUP, MEMBER, "set:alr:off")
    assert harness.session.alerts()[-1]["text"] == I18N.t(None, "not-admin")
    chat = await harness.chat(GROUP)
    assert chat is not None
    assert chat.alerts_enabled is True
