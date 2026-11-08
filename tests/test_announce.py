"""The project channel is registered as a reminder-only chat, and only when the bot may post."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import GetChat
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cpstands.db import repos
from cpstands.db.engine import create_engine, create_session_factory
from cpstands.services.announce import register_channel

CHANNEL = -1004388100807


class FakeBot:
    def __init__(
        self, *, can_post: bool = True, missing: bool = False, kind: str = "channel"
    ) -> None:
        self.can_post = can_post
        self.missing = missing
        self.kind = kind

    async def get_chat(self, chat_id: str) -> SimpleNamespace:
        if self.missing:
            raise TelegramBadRequest(method=GetChat(chat_id=chat_id), message="chat not found")
        return SimpleNamespace(id=CHANNEL, type=self.kind)

    async def get_me(self) -> SimpleNamespace:
        return SimpleNamespace(id=42)

    async def get_chat_member(self, chat_id: int, user_id: int) -> SimpleNamespace:
        status = "administrator" if self.can_post else "member"
        return SimpleNamespace(status=status, can_post_messages=self.can_post)


@pytest.fixture
async def sessions(migrated_database: str) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_engine(migrated_database, pool_size=2)
    yield create_session_factory(engine)
    await engine.dispose()


async def register(sessions: async_sessionmaker[AsyncSession], bot: FakeBot) -> int | None:
    return await register_channel(
        bot,  # type: ignore[arg-type]
        sessions,
        "@cpstands",
        offsets=[60, 1440],
        language="uz",
        time_zone="Asia/Tashkent",
    )


async def test_a_postable_channel_becomes_a_reminder_only_chat(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    assert await register(sessions, FakeBot()) == CHANNEL
    async with sessions() as session:
        chat = await repos.get_chat(session, CHANNEL)
    assert chat is not None
    assert chat.status == "active"
    assert chat.reminder_offsets == (1440, 60)
    assert chat.language == "uz"
    assert not chat.alerts_enabled
    assert not chat.summary_enabled


async def test_reminders_are_planned_for_the_channel(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    await register(sessions, FakeBot())
    start = datetime.now(UTC) + timedelta(days=3)
    async with sessions() as session, session.begin():
        await session.execute(
            text(
                "INSERT INTO contests (platform, external_id, name, phase, starts_at, duration_s)"
                " VALUES ('codeforces', 777001, 'Round X', 'BEFORE', :s, 7200)"
            ),
            {"s": start},
        )
        await repos.plan_reminders(session, "codeforces", now=datetime.now(UTC))
        offsets = (
            (
                await session.execute(
                    text("SELECT offset_min FROM reminders WHERE chat_id = :c ORDER BY 1"),
                    {"c": CHANNEL},
                )
            )
            .scalars()
            .all()
        )
    assert offsets == [60, 1440]


@pytest.mark.parametrize(
    "bot",
    [FakeBot(can_post=False), FakeBot(missing=True), FakeBot(kind="supergroup")],
    ids=["no-post-right", "not-found", "not-a-channel"],
)
async def test_nothing_is_stored_when_the_bot_cannot_post(
    sessions: async_sessionmaker[AsyncSession], bot: FakeBot
) -> None:
    assert await register(sessions, bot) is None
    async with sessions() as session:
        assert await repos.get_chat(session, CHANNEL) is None
