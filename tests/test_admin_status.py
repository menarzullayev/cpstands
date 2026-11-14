"""The admin check reads the member status however aiogram types it (regression: 2026-11-08).

aiogram 3.31 returns ChatMemberOwner.status as the plain string "creator"; reading `.value`
raised AttributeError, so no one in a group counted as an admin and /start never answered.
"""

from __future__ import annotations

from enum import Enum

import pytest
from aiogram.types import ChatMemberAdministrator, ChatMemberMember, ChatMemberOwner, User

from cpstands.bot.app import make_admin_checker

USER = User(id=5, is_bot=False, first_name="U")


class OldStatus(Enum):
    CREATOR = "creator"


class FakeBot:
    def __init__(self, member: object) -> None:
        self.member = member

    async def get_chat_member(self, chat_id: int, user_id: int) -> object:
        return self.member


def admin_member() -> ChatMemberAdministrator:
    # Built from API-shaped JSON, as aiogram parses getChatMember: status stays a plain string.
    return ChatMemberAdministrator.model_validate(
        {
            "status": "administrator",
            "user": USER.model_dump(),
            "can_be_edited": False,
            "is_anonymous": False,
            "can_manage_chat": True,
            "can_delete_messages": True,
            "can_manage_video_chats": False,
            "can_restrict_members": False,
            "can_promote_members": False,
            "can_change_info": True,
            "can_invite_users": True,
            "can_post_stories": False,
            "can_edit_stories": False,
            "can_delete_stories": False,
            "can_send_welcome_messages": True,
        }
    )


@pytest.mark.parametrize(
    ("member", "admin"),
    [
        (
            ChatMemberOwner.model_validate(
                {"status": "creator", "user": USER.model_dump(), "is_anonymous": False}
            ),
            True,
        ),
        (admin_member(), True),
        (ChatMemberMember.model_validate({"status": "member", "user": USER.model_dump()}), False),
    ],
    ids=["owner", "administrator", "member"],
)
async def test_real_aiogram_members(member: object, admin: bool) -> None:
    checker = make_admin_checker(FakeBot(member))  # type: ignore[arg-type]
    assert await checker.is_admin(-100, 5, private=False) is admin


async def test_an_enum_status_still_works() -> None:
    class Old:
        status = OldStatus.CREATOR

    checker = make_admin_checker(FakeBot(Old()))  # type: ignore[arg-type]
    assert await checker.is_admin(-100, 5, private=False) is True
