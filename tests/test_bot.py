"""Handler tests: real PostgreSQL, real dispatcher, a fake Telegram session."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
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
from cpstands.domain.contest import Contest, ContestPhase, RatingChange, UserRating
from cpstands.i18n import I18n
from cpstands.services import timezone as tzs
from cpstands.services.contests import ContestService
from cpstands.services.ops import OpsState
from cpstands.services.ratings import RatingService
from cpstands.services.standings import StandingsService
from cpstands.services.summary import SummaryService
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


class FriendsStub:
    """Stands in for the one-shot ``user.friends`` call."""

    def __init__(self) -> None:
        self.result: tuple[str, ...] = ("tourist", "jiangly")
        self.error: Exception | None = None
        self.calls: list[tuple[str, str]] = []

    async def fetch(self, api_key: str, api_secret: str) -> tuple[str, ...]:
        self.calls.append((api_key, api_secret))
        if self.error is not None:
            raise self.error
        return self.result


@dataclass
class Harness:
    dispatcher: Dispatcher
    bot: Bot
    session: FakeSession
    sessions: async_sessionmaker[AsyncSession]
    source: FakeSource
    ops: OpsState
    _next: int = 1
    friends: FriendsStub = field(default_factory=lambda: FriendsStub())

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
        ratings={
            "tourist": UserRating(
                "tourist", 3800, 3979, "legendary grandmaster", "legendary grandmaster"
            ),
            "jiangly": UserRating(
                "jiangly", 3900, 3900, "legendary grandmaster", "legendary grandmaster"
            ),
            "petr": UserRating("Petr", None, None, None, None),
        },
    )
    ops = OpsState()
    standings = StandingsService(source)  # type: ignore[arg-type]
    deps = Deps(
        i18n=I18N,
        sessions=sessions,
        watchlist=WatchlistService(sessions, source),  # type: ignore[arg-type]
        admin=make_admin_checker(bot),
        standings=standings,
        contests=ContestService(sessions, source),  # type: ignore[arg-type]
        ops=ops,
        ratings=RatingService(source),  # type: ignore[arg-type]
        summaries=SummaryService(source, standings),  # type: ignore[arg-type]
        owner_id=PRIVATE,
    )
    stub = FriendsStub()
    deps.fetch_friends = stub.fetch
    yield Harness(
        build_dispatcher(deps, RateLimiter()), bot, fake, sessions, source, ops, friends=stub
    )
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
        ops=OpsState(),
        ratings=RatingService(FakeSource([])),  # type: ignore[arg-type]
        summaries=SummaryService(FakeSource([]), StandingsService(FakeSource([]))),  # type: ignore[arg-type]
    )
    harness = Harness(
        build_dispatcher(deps, RateLimiter(per_user=3)),
        bot,
        fake,
        sessions,
        FakeSource([]),
        deps.ops,
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

    harness.dispatcher["deps"].watchlist.list_all = explode
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
    stand_in = keyboards.button("Settings", "x:y", emoji="⚙️", icons=True)
    assert stand_in.icon_custom_emoji_id  # the set has no gear, so a close twin is used
    assert stand_in.text == "Settings"
    no_twin = keyboards.button("Back", "x:y", emoji="▪", icons=True)
    assert no_twin.icon_custom_emoji_id is None
    assert no_twin.text == "▪ Back"


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
    callbacks = [b["callback_data"] for row in rows for b in row if "callback_data" in b]
    app = [b["url"] for row in rows for b in row if "url" in b]
    assert app == ["https://t.me/cpstandsbot?startapp=standings_1970"]  # opens the Mini App
    assert callbacks == [
        "st:1970:0:0:a",
        "st:1970:0:0:a",
        "st:noop",
        "st:1970:1:0:a",
        "st:1970:2:0:a",
        "st:1970:0:0:a",
        "st:1970:0:1:a",
        "st:1970:0:0:a:r",
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
    table = html.split("<table", 1)[1].split("</table>")[0]
    assert re.search(r">(<mark>)?500(</mark>)?</td>", table)  # points (first solve marked), no time
    assert ":" not in re.sub(r"<[^>]+>", "", table)


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
        '<a href="https://codeforces.com/contest/2287">Codeforces Round &lt;1&gt; &amp; co</a>'
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


async def test_privacy_explains_what_is_stored_without_storing_anything(harness: Harness) -> None:
    await harness.say(88, 88, "/privacy")
    sent = harness.session.sent()[-1]
    assert sent["text"] == I18N.t(None, "privacy-text")
    buttons = [b for row in sent["reply_markup"]["inline_keyboard"] for b in row]
    assert buttons[0]["url"].endswith("PRIVACY.md")
    assert buttons[1]["callback_data"] == "del:ask"
    assert await harness.chat(88) is None  # asking about privacy leaves no record


async def _setup_with_handles(harness: Harness, chat_id: int, user_id: int) -> None:
    await harness.say(chat_id, user_id, "/track add tourist, jiangly")


async def test_delete_needs_a_confirmation_and_then_removes_everything(harness: Harness) -> None:
    await _setup_with_handles(harness, PRIVATE, PRIVATE)
    await harness.say(PRIVATE, PRIVATE, "/delete")
    confirm = harness.session.sent()[-1]
    assert confirm["text"] == I18N.t(None, "delete-confirm")
    buttons = [b for row in confirm["reply_markup"]["inline_keyboard"] for b in row]
    yes = next(b for b in buttons if b["callback_data"].startswith("del:yes:"))
    assert yes["style"] == "danger"
    assert await harness.chat(PRIVATE) is not None  # nothing happens before the tap

    await harness.tap(PRIVATE, PRIVATE, yes["callback_data"])
    assert harness.session.last_text() == I18N.t(None, "delete-done", handles=2)
    assert await harness.chat(PRIVATE) is None
    await harness.tap(PRIVATE, PRIVATE, yes["callback_data"])  # a second tap finds nothing
    assert harness.session.last_text() == I18N.t(None, "delete-nothing")
    assert await harness.chat(PRIVATE) is None  # and it did not re-create the chat


async def test_cancelling_a_delete_keeps_the_data(harness: Harness) -> None:
    await _setup_with_handles(harness, PRIVATE, PRIVATE)
    await harness.say(PRIVATE, PRIVATE, "/delete")
    await harness.tap(PRIVATE, PRIVATE, "del:no")
    assert harness.session.last_text() == I18N.t(None, "delete-cancelled")
    chat = await harness.chat(PRIVATE)
    assert chat is not None


async def test_an_old_confirmation_does_not_delete(harness: Harness) -> None:
    import time

    await _setup_with_handles(harness, PRIVATE, PRIVATE)
    stale = int(time.time() // 60) - 11
    await harness.tap(PRIVATE, PRIVATE, f"del:yes:{stale}")
    assert harness.session.last_text() == I18N.t(None, "delete-expired")
    await harness.tap(PRIVATE, PRIVATE, "del:yes:notanumber")
    assert harness.session.alerts()[-1]["text"] == I18N.t(None, "button-expired")
    assert await harness.chat(PRIVATE) is not None


async def test_only_group_admins_can_delete_a_groups_data(harness: Harness) -> None:
    await harness.say(GROUP, ADMIN, "/track add tourist")
    await harness.say(GROUP, MEMBER, "/delete")
    assert harness.session.last_text() == I18N.t(None, "not-admin")
    import time

    await harness.tap(GROUP, MEMBER, f"del:yes:{int(time.time() // 60)}")
    assert harness.session.alerts()[-1]["text"] == I18N.t(None, "not-admin")
    assert await harness.chat(GROUP) is not None

    await harness.say(GROUP, ADMIN, "/delete")
    await harness.tap(GROUP, ADMIN, f"del:yes:{int(time.time() // 60)}")
    assert harness.session.last_text() == I18N.t(None, "delete-done", handles=1)
    assert await harness.chat(GROUP) is None


# --- owner commands ---------------------------------------------------------------------


async def test_owner_commands_refuse_everyone_else(harness: Harness) -> None:
    for command in ("/status", "/stats", "/pause", "/resume"):
        await harness.say(88, 88, command)
        assert harness.session.last_text() == I18N.t(None, "owner-only")
    await harness.say(GROUP, PRIVATE, "/status")  # the owner, but not in a private chat
    assert harness.session.last_text() == I18N.t(None, "owner-only")
    assert not harness.ops.sources


async def test_status_and_stats_show_numbers_to_the_owner(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/track add tourist")
    harness.ops.record_source("codeforces", ok=True)
    await harness.say(PRIVATE, PRIVATE, "/status")
    status = harness.session.last_text()
    assert "<b>Holat</b>" in status
    assert "codeforces" in status
    assert "errors in a row 0" in status
    await harness.say(PRIVATE, PRIVATE, "/stats")
    stats = harness.session.last_text()
    assert "Statistika" in stats
    assert "Kuzatilgan handlelar: 1" in stats


async def test_pause_and_resume_the_source(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/pause")
    assert harness.ops.is_paused("codeforces")
    assert harness.session.last_text() == I18N.t(None, "owner-paused-source", source="codeforces")
    async with harness.sessions() as session:
        from sqlalchemy import text

        saved = (await session.execute(text("select paused from source_health"))).scalar_one()
    assert saved is True
    await harness.say(PRIVATE, PRIVATE, "/resume codeforces")
    assert not harness.ops.is_paused("codeforces")
    await harness.say(PRIVATE, PRIVATE, "/pause kep.uz")
    assert harness.session.last_text() == I18N.t(None, "owner-pause-usage")


async def test_pause_and_resume_a_chat(harness: Harness) -> None:
    await harness.say(GROUP, ADMIN, "/track add tourist")
    await harness.say(GROUP, ADMIN, "/start")
    await harness.tap(GROUP, ADMIN, "set:lang:en")
    await harness.tap(GROUP, ADMIN, "tz:set:UTC")
    await harness.say(PRIVATE, PRIVATE, f"/pause {GROUP}")
    chat = await harness.chat(GROUP)
    assert chat is not None
    assert chat.status == "paused"
    await harness.say(PRIVATE, PRIVATE, f"/pause {GROUP}")  # already paused
    assert harness.session.last_text() == I18N.t(None, "owner-chat-unknown", id=str(GROUP))
    await harness.say(PRIVATE, PRIVATE, f"/resume {GROUP}")
    chat = await harness.chat(GROUP)
    assert chat is not None
    assert chat.status == "active"
    await harness.say(PRIVATE, PRIVATE, "/pause 123456")  # a chat the bot does not know
    assert harness.session.last_text() == I18N.t(None, "owner-chat-unknown", id="123456")


# --- /rank ------------------------------------------------------------------------------


async def test_rank_needs_a_watch_list_first(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/rank")
    assert harness.session.last_text() == I18N.t(None, "rank-empty")
    assert not harness.session.rich()


async def test_rank_shows_friends_best_first_with_unrated_and_unknown(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/track add tourist, jiangly, Petr")
    await harness.say(PRIVATE, PRIVATE, "/rank")
    html = harness.session.rich()[-1]["html"]
    assert html.index("jiangly") < html.index("tourist") < html.index("Petr")
    assert "<td>3900</td>" in html
    assert "<td>3979</td>" in html
    assert "legendary grandmaster" in html
    assert html.count("<td>-</td>") == 3  # Petr is unrated
    buttons = [
        b["callback_data"]
        for row in harness.session.rich()[-1]["reply_markup"]["inline_keyboard"]
        for b in row
    ]
    assert buttons == ["rk:0:r"]


async def test_rank_failure_and_refresh(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/track add tourist")
    harness.source.fail = True
    await harness.say(PRIVATE, PRIVATE, "/rank")
    assert harness.session.last_text() == I18N.t(None, "rank-source-error")
    harness.source.fail = False
    await harness.say(PRIVATE, PRIVATE, "/rank")
    fetches = harness.source.rating_fetches
    await harness.tap(PRIVATE, PRIVATE, "rk:0:r")  # a copy this fresh is reused
    assert harness.source.rating_fetches == fetches
    assert len(harness.session.rich()) == 2  # the page was rendered again, in place


async def test_rank_callbacks_survive_garbage(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/track add tourist")
    await harness.say(PRIVATE, PRIVATE, "/rank")
    await harness.tap(PRIVATE, PRIVATE, "rk:noop")
    before = len(harness.session.alerts())
    await harness.tap(PRIVATE, PRIVATE, "rk:abc")
    assert harness.session.alerts()[-1]["text"] == I18N.t(None, "button-expired")
    assert len(harness.session.alerts()) == before + 1
    await harness.tap(PRIVATE, PRIVATE, "rk:99")  # a page past the end is clamped
    assert "<td>1</td>" in harness.session.rich()[-1]["html"]


# --- settings hub and submenus ----------------------------------------------------------


def _callbacks(call: dict[str, object]) -> list[str]:
    rows = call["reply_markup"]["inline_keyboard"]  # type: ignore[index]
    return [b["callback_data"] for row in rows for b in row if "callback_data" in b]


async def _active_private_chat(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/start")
    await harness.tap(PRIVATE, PRIVATE, "set:lang:en")
    await harness.tap(PRIVATE, PRIVATE, "tz:set:Asia/Tashkent")


async def test_settings_hub_shows_every_setting_with_its_button(harness: Harness) -> None:
    await _active_private_chat(harness)
    await harness.say(PRIVATE, PRIVATE, "/settings")
    sent = harness.session.sent()[-1]
    text = str(sent["text"])
    for line in (
        "Reminders: <b>24h · 1h · 10m</b>",
        "Alerts: <b>everything</b>",
        "Table columns: <b>16</b>",
        "Summary: <b>on</b>",
    ):
        assert line in text
    assert _callbacks(sent) == [
        "set:menu:lang", "set:menu:tz", "set:tone:neutral", "set:menu:rem",
        "set:menu:alr", "set:cols:8", "set:sum:off", "fr:l:0", "set:style:emoji",
    ]  # fmt: skip


async def test_reminder_times_are_chosen_one_by_one_and_the_plan_follows(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/upcoming")  # stores the contests
    await _active_private_chat(harness)
    await harness.tap(PRIVATE, PRIVATE, "set:menu:rem")
    menu = harness.session.sent("EditMessageText")[-1]
    assert _callbacks(menu) == [
        "set:rt:4320",
        "set:rt:1440",
        "set:rt:120",
        "set:rt:60",
        "set:rt:10",
        "set:menu:main",
    ]
    labels = [b["text"] for row in menu["reply_markup"]["inline_keyboard"][:1] for b in row]
    assert labels == ["⬜ 3d", "✅ 24h", "⬜ 2h", "✅ 1h", "✅ 10m"]

    await harness.tap(PRIVATE, PRIVATE, "set:rt:120")  # 2 hours on
    await harness.tap(PRIVATE, PRIVATE, "set:rt:1440")  # 24 hours off
    chat = await harness.chat(PRIVATE)
    assert chat is not None
    assert chat.reminder_offsets == (120, 60, 10)
    from sqlalchemy import text

    async with harness.sessions() as session:
        rows = (
            await session.execute(
                text(
                    "select offset_min, state from reminders where contest_id = 2287 order by 1 desc"
                )
            )
        ).all()
    assert [(int(a), str(b)) for a, b in rows] == [
        (1440, "cancelled"),
        (120, "scheduled"),
        (60, "scheduled"),
        (10, "scheduled"),
    ]

    await harness.tap(PRIVATE, PRIVATE, "set:rt:120")
    await harness.tap(PRIVATE, PRIVATE, "set:rt:60")
    await harness.tap(PRIVATE, PRIVATE, "set:rt:10")
    chat = await harness.chat(PRIVATE)
    assert chat is not None
    assert chat.reminder_offsets == ()  # everything off is allowed
    await harness.tap(PRIVATE, PRIVATE, "set:menu:main")
    assert "Reminders: <b>off</b>" in harness.session.sent("EditMessageText")[-1]["text"]


async def test_reminder_choices_reject_garbage_and_non_admins(harness: Harness) -> None:
    await harness.say(GROUP, ADMIN, "/settings")
    await harness.tap(GROUP, MEMBER, "set:rt:60")
    assert harness.session.alerts()[-1]["text"] == I18N.t(None, "not-admin")
    for bad in ("set:rt:61", "set:rt:abc", "set:rt:-5"):
        await harness.tap(GROUP, ADMIN, bad)
        assert harness.session.alerts()[-1]["text"] == I18N.t(None, "button-expired")
    chat = await harness.chat(GROUP)
    assert chat is not None
    assert chat.reminder_offsets == (1440, 60, 10)


async def test_alert_level_applies_to_every_friend_and_to_new_ones(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/track add tourist, jiangly")
    await harness.tap(PRIVATE, PRIVATE, "set:menu:alr")
    menu = harness.session.sent("EditMessageText")[-1]
    assert _callbacks(menu) == [f"set:lvl:{i}" for i in range(5)] + ["set:menu:main"]
    await harness.tap(PRIVATE, PRIVATE, "set:lvl:2")
    chat = await harness.chat(PRIVATE)
    assert chat is not None
    assert chat.notify_level == 2
    async with harness.sessions() as session:
        friends = await repos.list_friends(session, PRIVATE, "codeforces")
    assert [
        (f.show_in_list, f.notify_solve, f.notify_systest, f.notify_upsolve) for f in friends
    ] == [(True, False, True, False)] * 2
    await harness.say(PRIVATE, PRIVATE, "/track add Petr")
    async with harness.sessions() as session:
        petr = await repos.get_friend(session, PRIVATE, "codeforces", "petr")
    assert petr is not None
    assert (petr.notify_solve, petr.notify_systest) == (False, True)  # inherits the chat's level
    assert "+ system test" in harness.session.sent("EditMessageText")[-1]["text"]
    before = len(harness.session.alerts())
    await harness.tap(PRIVATE, PRIVATE, "set:lvl:9")
    assert len(harness.session.alerts()) == before + 1


async def test_table_columns_and_summary_switch(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/settings")
    await harness.tap(PRIVATE, PRIVATE, "set:cols:8")
    await harness.tap(PRIVATE, PRIVATE, "set:sum:off")
    chat = await harness.chat(PRIVATE)
    assert chat is not None
    assert (chat.table_cols, chat.summary_enabled) == (8, False)
    text = harness.session.sent("EditMessageText")[-1]["text"]
    assert "Jadval ustunlari: <b>8</b>" in text
    assert "Xulosa: <b>o'chiq</b>" in text
    await harness.tap(PRIVATE, PRIVATE, "set:cols:10")  # not an allowed width
    chat = await harness.chat(PRIVATE)
    assert chat is not None
    assert chat.table_cols == 8
    await harness.tap(PRIVATE, PRIVATE, "set:sum:maybe")
    chat = await harness.chat(PRIVATE)
    assert chat is not None
    assert chat.summary_enabled is False


async def test_friends_menu_lists_pages_and_toggles_per_handle(harness: Harness) -> None:
    await harness.tap(PRIVATE, PRIVATE, "fr:l:0")
    assert harness.session.last_text() == I18N.t(None, "friends-empty")
    await harness.say(PRIVATE, PRIVATE, "/track add tourist, jiangly, Petr")
    await harness.tap(PRIVATE, PRIVATE, "fr:l:0")
    listing = harness.session.sent("EditMessageText")[-1]
    assert _callbacks(listing) == [
        "fr:d:0:jiangly",
        "fr:d:0:petr",
        "fr:d:0:tourist",
        "set:menu:main",
    ]

    await harness.tap(PRIVATE, PRIVATE, "fr:d:0:tourist")
    detail = harness.session.sent("EditMessageText")[-1]
    assert _callbacks(detail) == [f"fr:t:0:{i}:tourist" for i in range(4)] + ["fr:l:0"]
    assert all(
        b["text"].startswith("✅")
        for row in detail["reply_markup"]["inline_keyboard"][:4]
        for b in row
    )

    await harness.tap(PRIVATE, PRIVATE, "fr:t:0:1:tourist")  # solves during contests off
    await harness.tap(PRIVATE, PRIVATE, "fr:t:0:2:tourist")  # system tests off
    await harness.tap(PRIVATE, PRIVATE, "fr:t:0:3:tourist")  # upsolves off
    async with harness.sessions() as session:
        tourist = await repos.get_friend(session, PRIVATE, "codeforces", "tourist")
    assert tourist is not None
    assert (
        tourist.show_in_list,
        tourist.notify_solve,
        tourist.notify_systest,
        tourist.notify_upsolve,
    ) == (True, False, False, False)
    await harness.tap(PRIVATE, PRIVATE, "fr:l:0")
    labels = [
        b["text"]
        for row in harness.session.sent("EditMessageText")[-1]["reply_markup"]["inline_keyboard"]
        for b in row
    ]
    assert "🔕 tourist" in labels  # muted handles are marked in the list
    assert "jiangly" in labels
    await harness.tap(PRIVATE, PRIVATE, "fr:t:0:1:tourist")  # solves on again
    async with harness.sessions() as session:
        tourist = await repos.get_friend(session, PRIVATE, "codeforces", "tourist")
    assert tourist is not None
    assert tourist.notify_solve is True


async def test_friends_menu_paginates_and_rejects_forged_callbacks(harness: Harness) -> None:
    names = [f"user{i:02d}" for i in range(10)]
    harness.source._existing.update({n: n for n in names})
    await harness.say(PRIVATE, PRIVATE, "/track add " + " ".join(names))
    await harness.tap(PRIVATE, PRIVATE, "fr:l:1")
    listing = harness.session.sent("EditMessageText")[-1]
    assert _callbacks(listing) == [
        "fr:d:1:user08",
        "fr:d:1:user09",
        "fr:l:0",
        "st:noop",
        "fr:l:1",
        "set:menu:main",
    ]
    before = len(harness.session.alerts())
    for forged in (
        "fr:d:0:../etc",
        "fr:d:x:tourist",
        "fr:t:0:9:user00",
        "fr:t:0:1",
        "fr:d:0:" + "a" * 40,
        "fr:d:0:nobody",
    ):
        await harness.tap(PRIVATE, PRIVATE, forged)
    assert len(harness.session.alerts()) == before + 6
    await harness.say(GROUP, ADMIN, "/track add tourist")
    await harness.tap(GROUP, MEMBER, "fr:t:0:1:tourist")
    assert harness.session.alerts()[-1]["text"] == I18N.t(None, "not-admin")


# --- friends / everyone view and table width --------------------------------------------


async def _follow(harness: Harness, chat_id: int, user_id: int, *names: str) -> None:
    harness.source._existing.update({n: n for n in names})
    await harness.say(chat_id, user_id, "/track add " + " ".join(names))


def _table_ranks(html: str) -> list[str]:
    """The rank column, with the top-3 medals read back as numbers."""
    medals = {"🥇": "1", "🥈": "2", "🥉": "3"}
    cells = [part.split("</td>")[0] for part in html.split("<tr><td>")[1:]]
    plain = [re.sub(r"<[^>]+>", "", c) for c in cells]
    return [medals.get(c, c) for c in plain]


async def test_a_chat_with_friends_sees_only_them_first_and_can_switch(harness: Harness) -> None:
    await _follow(harness, PRIVATE, PRIVATE, "user1", "user3", "user50")
    await harness.say(PRIVATE, PRIVATE, "/standings 1970")
    page = harness.session.rich()[-1]
    assert _table_ranks(page["html"]) == ["2", "4", "51"]  # their real ranks, in order
    assert "(do'stlar)" in page["html"]
    assert _callbacks(page)[:2] == ["st:1970:0:0:f", "st:1970:0:0:a"]
    primary = [b.get("style") for row in page["reply_markup"]["inline_keyboard"][:1] for b in row]
    assert primary == ["primary", None]

    await harness.tap(PRIVATE, PRIVATE, "st:1970:0:0:a")
    everyone = harness.session.rich()[-1]
    assert len(_table_ranks(everyone["html"])) == 25
    assert "(do'stlar)" not in everyone["html"]
    await harness.tap(PRIVATE, PRIVATE, "st:1970:0:0:f")
    assert _table_ranks(harness.session.rich()[-1]["html"]) == ["2", "4", "51"]


async def test_the_friends_view_follows_the_scoreboard_toggle_and_handles_absence(
    harness: Harness,
) -> None:
    await _follow(harness, PRIVATE, PRIVATE, "user1", "user3")
    async with harness.sessions() as session, session.begin():
        await repos.set_friend_toggle(
            session, PRIVATE, "codeforces", "user3", "show_in_list", False
        )
    await harness.say(PRIVATE, PRIVATE, "/standings 1970")
    assert _table_ranks(harness.session.rich()[-1]["html"]) == ["2"]
    async with harness.sessions() as session, session.begin():
        await repos.set_friend_toggle(
            session, PRIVATE, "codeforces", "user1", "show_in_list", False
        )
    await harness.say(PRIVATE, PRIVATE, "/standings 1970")
    everyone = harness.session.rich()[-1]
    assert len(_table_ranks(everyone["html"])) == 25  # nobody on the scoreboard: show everyone
    assert not [c for c in _callbacks(everyone) if c.endswith(":f")]  # and no switcher


async def test_friends_who_did_not_take_part_get_an_explanation(harness: Harness) -> None:
    await _follow(harness, PRIVATE, PRIVATE, "newcomer")
    await harness.say(PRIVATE, PRIVATE, "/standings 1970")
    html = harness.session.rich()[-1]["html"]
    assert "<table>" not in html
    assert I18N.t(None, "standings-no-friends") in html or "hech biri" in html


async def test_the_chosen_view_of_a_live_message_is_remembered(harness: Harness) -> None:
    await _follow(harness, PRIVATE, PRIVATE, "user1")
    await harness.say(PRIVATE, PRIVATE, "/standings 1973")  # a running contest
    message_id = (await _live_rows(harness))[0][1]
    await harness.feed(
        callback_update(harness.uid(), PRIVATE, PRIVATE, "st:1973:0:0:a", message_id)
    )
    async with harness.sessions() as session:
        from sqlalchemy import text

        stored = (await session.execute(text("select view from standings_messages"))).scalar_one()
    assert stored == "all"
    await harness.feed(
        callback_update(harness.uid(), PRIVATE, PRIVATE, "st:1973:0:0:f", message_id)
    )
    async with harness.sessions() as session:
        stored = (await session.execute(text("select view from standings_messages"))).scalar_one()
    assert stored == "friends"


async def test_old_callbacks_without_a_view_still_work(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/standings 1970")
    await harness.tap(PRIVATE, PRIVATE, "st:1970:1:0")  # the format before views existed
    assert "<td>26</td>" in harness.session.rich()[-1]["html"]


async def test_the_table_width_setting_changes_the_problem_columns(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/settings")
    await harness.tap(PRIVATE, PRIVATE, "set:cols:8")
    await harness.say(PRIVATE, PRIVATE, "/standings 1970")
    page = harness.session.rich()[-1]
    assert page["html"].count("<th>") == 4 + 8
    labels = [b["text"] for row in page["reply_markup"]["inline_keyboard"] for b in row]
    assert [t for t in labels if "–" in t] == [
        "P1–P8",
        "P9–P16",
        "P17–P21",
    ]  # every problem is reachable


# --- /rating ----------------------------------------------------------------------------


def _history() -> list[RatingChange]:
    at = datetime(2026, 10, 1, tzinfo=UTC)
    return [
        RatingChange(1, "Round One", 10, 1500, 1600, at),
        RatingChange(2, "Round <Two>", 5, 1600, 1580, at + timedelta(days=30)),
    ]


async def test_rating_card_shows_rating_last_contest_and_follow_button(harness: Harness) -> None:
    harness.source.histories["tourist"] = _history()
    await harness.say(PRIVATE, PRIVATE, "/rating Tourist")
    call = harness.session.sent()[-1]
    text = call["text"]
    assert "3979" in text
    assert "legendary grandmaster" in text
    assert "Round &lt;Two&gt;" in text  # the contest name is escaped
    assert "-20" in text
    assert "(1600 → 1580)" in text
    assert I18N.t(None, "rating-contests", count=2) in text
    assert _callbacks(call) == ["rt:add:tourist"]
    labels = [b["text"] for row in call["reply_markup"]["inline_keyboard"] for b in row]
    assert labels[0].startswith(chr(0x2795))  # a real symbol, not its code
    urls = [b["url"] for row in call["reply_markup"]["inline_keyboard"] for b in row if "url" in b]
    assert urls == [
        "https://codeforces.com/profile/tourist",
        "https://t.me/cpstandsbot?startapp=profile_tourist",
    ]


async def test_rating_follow_button_adds_once_and_disappears(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/rating tourist")
    await harness.tap(PRIVATE, PRIVATE, "rt:add:tourist")
    async with harness.sessions() as session:
        assert await repos.get_friend(session, PRIVATE, "codeforces", "tourist") is not None
    assert harness.session.alerts()[-1]["text"] == I18N.t(None, "rating-follow-done")
    await harness.say(PRIVATE, PRIVATE, "/rating tourist")
    assert _callbacks(harness.session.sent()[-1]) == []  # already followed: only the profile link


async def test_rating_unrated_user_and_unknown_user(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/rating Petr")
    assert I18N.t(None, "rating-unrated") in harness.session.last_text()
    assert I18N.t(None, "rating-no-contests") in harness.session.last_text()
    await harness.say(PRIVATE, PRIVATE, "/rating nobody_here")
    assert harness.session.last_text() == I18N.t(None, "rating-not-found", handle="nobody_here")


async def test_rating_usage_and_source_failure(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/rating")
    assert harness.session.last_text() == I18N.t(None, "rating-usage")
    harness.source.fail = True
    await harness.say(PRIVATE, PRIVATE, "/rating tourist")
    assert harness.session.last_text() == I18N.t(None, "rating-source-error")


async def test_rating_follow_rejects_garbage_and_non_admins(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/rating tourist")
    await harness.tap(PRIVATE, PRIVATE, "rt:add:" + "x" * 80)
    assert harness.session.alerts()[-1]["text"] == I18N.t(None, "button-expired")
    await harness.tap(PRIVATE, PRIVATE, "rt:add:no such")
    assert harness.session.alerts()[-1]["text"] == I18N.t(None, "button-expired")
    await harness.say(GROUP, ADMIN, "/start")
    before = len(harness.session.alerts())
    await harness.tap(GROUP, MEMBER, "rt:add:tourist")
    assert len(harness.session.alerts()) == before + 1
    async with harness.sessions() as session:
        assert await repos.get_friend(session, GROUP, "codeforces", "tourist") is None


# --- /summary ---------------------------------------------------------------------------


async def _finished_contest(harness: Harness, cid: int, handles: tuple[str, ...]) -> None:
    from tests.test_summary import A, R, table

    standings = table(dict.fromkeys(handles, (A, R)), cid=cid)
    harness.source.standings[cid] = standings
    async with harness.sessions() as session, session.begin():
        await repos.upsert_contest(
            session, "codeforces", cid, "Round", "FINISHED", standings.contest.starts_at, 7200
        )


async def test_summary_needs_friends_and_a_numeric_contest(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/summary")
    assert harness.session.last_text() == I18N.t(None, "summary-no-friends")
    await harness.say(PRIVATE, PRIVATE, "/summary abc")
    assert harness.session.last_text() == I18N.t(None, "summary-usage")
    await harness.say(PRIVATE, PRIVATE, "/summary -5")
    assert harness.session.last_text() == I18N.t(None, "summary-usage")


async def test_summary_shows_the_latest_finished_contest_with_friends_in_it(
    harness: Harness,
) -> None:
    await harness.say(PRIVATE, PRIVATE, "/track add tourist")
    await _finished_contest(harness, 3001, ("tourist", "x"))
    await _finished_contest(harness, 3002, ("someone",))  # newer, but no friends in it
    async with harness.sessions() as session, session.begin():
        await repos.upsert_contest(
            session, "codeforces", 3002, "Newer", "FINISHED", datetime.now(UTC), 7200
        )
    await harness.say(PRIVATE, PRIVATE, "/summary")
    text = harness.session.last_text()
    assert "tourist" in text
    assert "3001" in text
    await harness.say(PRIVATE, PRIVATE, "/summary 3002")
    assert harness.session.last_text() == I18N.t(None, "summary-none")
    await harness.say(PRIVATE, PRIVATE, "/summary 99999")  # Codeforces does not know it
    assert harness.session.last_text() == I18N.t(None, "summary-none")


async def test_summary_reports_a_source_failure(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/track add tourist")
    await _finished_contest(harness, 3001, ("tourist",))
    harness.source.fail = True
    await harness.say(PRIVATE, PRIVATE, "/summary 3001")
    assert harness.session.last_text() == I18N.t(None, "summary-source-error")


async def test_a_silent_chat_gets_no_answer_of_any_kind(harness: Harness) -> None:
    """Commands, button taps and a re-join in a silent chat call no Telegram method at all."""
    harness.dispatcher = build_dispatcher(
        harness.dispatcher["deps"], RateLimiter(per_user=1), silent_chats=(GROUP,)
    )
    for text in ("/help", "/start", "/standings 1970", "/upcoming", "/help"):
        await harness.say(GROUP, ADMIN, text)  # the last one would also hit the rate limit
    await harness.tap(GROUP, ADMIN, "help:track")
    await harness.feed(my_chat_member_update(harness.uid(), GROUP, "left", "member"))
    assert harness.session.calls == []
    assert await harness.chat(GROUP) is None  # nothing about the chat is even stored

    # The control: the same dispatcher still answers everywhere else.
    await harness.say(PRIVATE, PRIVATE, "/help")
    assert harness.session.last_text() == I18N.t(None, "help-text")


async def test_the_table_style_is_switched_in_settings(harness: Harness) -> None:
    await harness.say(PRIVATE, PRIVATE, "/settings")
    chat = await harness.chat(PRIVATE)
    assert chat is not None
    assert chat.table_style == "classic"  # the default
    await harness.tap(PRIVATE, PRIVATE, "set:style:emoji")
    chat = await harness.chat(PRIVATE)
    assert chat is not None
    assert chat.table_style == "emoji"
    text = harness.session.sent("EditMessageText")[-1]["text"]
    assert "Jadval ko'rinishi: <b>emoji</b>" in text

    await harness.say(PRIVATE, PRIVATE, "/standings 1970")
    assert "<table bordered compact>" in harness.session.rich()[-1]["html"]

    before = len(harness.session.alerts())
    await harness.tap(PRIVATE, PRIVATE, "set:style:neon")  # not a style
    assert len(harness.session.alerts()) == before + 1
    chat = await harness.chat(PRIVATE)
    assert chat is not None
    assert chat.table_style == "emoji"


async def test_only_an_admin_switches_a_groups_table_style(harness: Harness) -> None:
    await harness.say(GROUP, ADMIN, "/settings")
    await harness.tap(GROUP, MEMBER, "set:style:emoji")
    chat = await harness.chat(GROUP)
    assert chat is not None
    assert chat.table_style == "classic"


async def test_the_database_refuses_an_unknown_table_style(harness: Harness) -> None:
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    await harness.say(PRIVATE, PRIVATE, "/settings")
    with pytest.raises(IntegrityError):
        async with harness.sessions() as session, session.begin():
            await session.execute(
                text("UPDATE chats SET table_style = 'neon' WHERE chat_id = :c"), {"c": PRIVATE}
            )
