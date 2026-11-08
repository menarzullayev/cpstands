"""A fake aiogram session: records every Bot API call and answers with valid objects."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import TelegramMethod
from aiogram.methods.base import TelegramType
from aiogram.types import (
    CallbackQuery,
    Chat,
    ChatMemberAdministrator,
    ChatMemberLeft,
    ChatMemberMember,
    ChatMemberOwner,
    ChatMemberUpdated,
    Message,
    Update,
    User,
)

BOT_ID = 4242
TOKEN = f"{BOT_ID}:AAH" + "x" * 32


@dataclass
class Call:
    method: str
    data: dict[str, Any]


@dataclass
class FakeSession(BaseSession):
    calls: list[Call] = field(default_factory=list)
    member_status: dict[tuple[int, int], str] = field(default_factory=dict)
    next_message_id: int = 1000
    refuse_ephemeral: bool = False
    edit_error: Exception | None = None
    delete_error: Exception | None = None
    send_error: Exception | None = None
    send_attempts: int = 0

    def __post_init__(self) -> None:
        BaseSession.__init__(self)

    async def close(self) -> None:
        return None

    async def make_request(
        self,
        bot: Bot,
        method: TelegramMethod[TelegramType],
        timeout: int | None = None,  # noqa: ASYNC109
    ) -> TelegramType:
        name = type(method).__name__
        data = method.model_dump(exclude_none=True)
        self.calls.append(Call(name, data))
        result: Any = True
        if name == "SendMessage":
            self.send_attempts += 1
            if self.send_error is not None:
                raise self.send_error
        if name == "EditMessageText" and self.edit_error is not None:
            raise self.edit_error
        if name == "DeleteMessage" and self.delete_error is not None:
            raise self.delete_error
        if (
            name == "SendMessage"
            and data.get("ephemeral_message_parameters")
            and self.refuse_ephemeral
        ):
            raise TelegramBadRequest(method=method, message="Bad Request: BOT_NOT_ADMIN")
        if name in {"SendMessage", "EditMessageText", "SendRichMessage"}:
            self.next_message_id += 1
            chat_id = data.get("chat_id", 0)
            result = Message(
                message_id=data.get("message_id", self.next_message_id),
                date=datetime.now(UTC),
                chat=Chat(
                    id=int(chat_id) if str(chat_id).lstrip("-").isdigit() else 0, type="private"
                ),
                text=data.get("text"),
            )
        elif name == "GetChatMember":
            status = self.member_status.get((data["chat_id"], data["user_id"]), "member")
            user = User(id=data["user_id"], is_bot=False, first_name="U")
            if status == "creator":
                result = ChatMemberOwner(user=user, is_anonymous=False)
            elif status == "administrator":
                result = ChatMemberAdministrator.model_validate(
                    {
                        "user": user.model_dump(),
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
            elif status == "left":
                result = ChatMemberLeft(user=user)
            else:
                result = ChatMemberMember(user=user)
        return result  # type: ignore[no-any-return]

    async def stream_content(  # pragma: no cover - never used by the fake
        self,
        url: str,
        headers: dict[str, Any] | None = None,
        timeout: int = 30,  # noqa: ASYNC109
        chunk_size: int = 65536,
        raise_for_status: bool = True,
    ) -> AsyncGenerator[bytes]:
        yield b""

    # --- helpers for tests ---

    def sent(self, name: str = "SendMessage") -> list[dict[str, Any]]:
        return [c.data for c in self.calls if c.method == name]

    def last_text(self) -> str:
        for call in reversed(self.calls):
            if call.method in {"SendMessage", "EditMessageText"}:
                return str(call.data["text"])
        raise AssertionError("no message was sent")

    def rich(self) -> list[dict[str, Any]]:
        """Every Rich Message sent or edited, as ``{"html": ..., "reply_markup": ...}``."""
        found = []
        for call in self.calls:
            payload = call.data.get("rich_message")
            if payload and call.method in {"SendRichMessage", "EditMessageText"}:
                found.append(
                    {"html": payload["html"], "reply_markup": call.data.get("reply_markup")}
                )
        return found

    def alerts(self) -> list[dict[str, Any]]:
        return [c.data for c in self.calls if c.method == "AnswerCallbackQuery"]


def make_bot(session: FakeSession) -> Bot:
    return Bot(TOKEN, session=session)


def _chat(chat_id: int) -> Chat:
    return Chat(id=chat_id, type="private" if chat_id > 0 else "supergroup", title="G")


def message_update(
    update_id: int, chat_id: int, user_id: int, text: str, thread_id: int | None = None
) -> Update:
    message = Message(
        message_id=update_id,
        date=datetime.now(UTC),
        chat=_chat(chat_id),
        from_user=User(id=user_id, is_bot=False, first_name="U"),
        text=text,
        message_thread_id=thread_id,
        is_topic_message=True if thread_id else None,
        entities=(
            [{"type": "bot_command", "offset": 0, "length": len(text.split()[0])}]  # type: ignore[list-item]
            if text.startswith("/")
            else None
        ),
    )
    return Update(update_id=update_id, message=message)


def callback_update(
    update_id: int, chat_id: int, user_id: int, data: str, message_id: int | None = None
) -> Update:
    message = Message(
        message_id=message_id if message_id is not None else update_id + 500,
        date=datetime.now(UTC),
        chat=_chat(chat_id),
        text="old",
    )
    callback = CallbackQuery(
        id=str(update_id),
        from_user=User(id=user_id, is_bot=False, first_name="U"),
        chat_instance="ci",
        message=message,
        data=data,
    )
    return Update(update_id=update_id, callback_query=callback)


def my_chat_member_update(update_id: int, chat_id: int, old: str, new: str) -> Update:
    def member(status: str) -> Any:
        user = User(id=BOT_ID, is_bot=True, first_name="bot")
        if status == "administrator":
            return {
                "status": status,
                "user": user.model_dump(),
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
        if status == "kicked":
            return {"status": status, "user": user.model_dump(), "until_date": 0}
        return {"status": status, "user": user.model_dump()}

    event = ChatMemberUpdated.model_validate(
        {
            "chat": _chat(chat_id).model_dump(),
            "from": User(id=7, is_bot=False, first_name="U").model_dump(),
            "date": datetime.now(UTC),
            "old_chat_member": member(old),
            "new_chat_member": member(new),
        }
    )
    return Update(update_id=update_id, my_chat_member=event)


def chat_member_update(update_id: int, chat_id: int, user_id: int, new: str) -> Update:
    user = User(id=user_id, is_bot=False, first_name="U").model_dump()
    event = ChatMemberUpdated.model_validate(
        {
            "chat": _chat(chat_id).model_dump(),
            "from": User(id=7, is_bot=False, first_name="U").model_dump(),
            "date": datetime.now(UTC),
            "old_chat_member": {"status": "member", "user": user},
            "new_chat_member": {"status": new, "user": user},
        }
    )
    return Update(update_id=update_id, chat_member=event)
