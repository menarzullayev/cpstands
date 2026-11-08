"""``/import``: copy the owner's Codeforces friends into the watch list, with a one-shot API key.

Owner decision on REQ-013, with these guarantees: it works only in a private chat; the message
holding the key is deleted before anything else happens; the key is used for one signed
``user.friends`` call and then dropped; it is never stored, logged or echoed back.
"""

from __future__ import annotations

import re

import structlog
from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import BaseFilter, Command
from aiogram.types import Message

from cpstands.bot.common import ensure_chat, say
from cpstands.bot.deps import Deps
from cpstands.sources.base import SourceError
from cpstands.sources.codeforces.friends import InvalidCredentialsError

log = structlog.get_logger(__name__)

_CREDENTIAL_RE = re.compile(r"(?<![0-9A-Za-z])[0-9a-fA-F]{40}(?![0-9A-Za-z])")


class Awaiting(BaseFilter):
    """Plain text in a private chat that has asked for ``/import``."""

    async def __call__(self, message: Message, deps: Deps) -> bool:
        return (
            message.chat.type == "private"
            and bool(message.text)
            and not (message.text or "").startswith("/")
            and deps.imports.waiting(message.chat.id)
        )


async def on_import(message: Message, deps: Deps) -> None:
    chat = await ensure_chat(deps, message.chat)
    if chat is None:
        return
    tr = say(deps, chat)
    if message.chat.type != "private":
        await message.answer(tr("import-private-only"))
        return
    deps.imports.arm(message.chat.id)
    await message.answer(tr("import-intro"))


async def on_cancel(message: Message, deps: Deps) -> None:
    if not deps.imports.waiting(message.chat.id):
        return
    deps.imports.disarm(message.chat.id)
    chat = await ensure_chat(deps, message.chat)
    await message.answer(say(deps, chat)("import-cancelled"))


async def on_credentials(message: Message, deps: Deps) -> None:
    text = message.text or ""
    # Remove the message first, before anything can fail: the key must not stay in the chat.
    deleted = True
    try:
        await message.delete()
    except TelegramAPIError:
        deleted = False
    chat = await ensure_chat(deps, message.chat)
    if chat is None:
        return
    tr = say(deps, chat)
    pair = _CREDENTIAL_RE.findall(text)
    del text
    if len(pair) != 2:
        notice = tr("import-bad-format")
        await message.answer(notice if deleted else notice + "\n" + tr("import-not-deleted"))
        return
    deps.imports.disarm(message.chat.id)  # one attempt per /import
    api_key, api_secret = pair
    del pair
    warning = "" if deleted else "\n\n" + tr("import-not-deleted")
    try:
        friends = await deps.fetch_friends(api_key, api_secret)
    except InvalidCredentialsError:
        await message.answer(tr("import-bad-credentials") + warning)
        return
    except SourceError:
        log.warning("import_failed")
        await message.answer(tr("import-source-error") + warning)
        return
    finally:
        del api_key, api_secret
    if not friends:
        await message.answer(tr("import-none") + warning)
        return
    try:
        result = await deps.watchlist.add(message.chat.id, ",".join(friends))
    except SourceError:
        await message.answer(tr("import-source-error") + warning)
        return
    log.info("friends_imported", chat_id=message.chat.id, added=len(result.added))
    lines = [tr("import-done", count=len(result.added), already=len(result.already))]
    if result.over_limit:
        lines.append(tr("import-over-limit", count=len(result.over_limit)))
    lines.append(tr("import-revoke"))
    await message.answer("\n".join(lines) + warning)


def create_import_router() -> Router:
    router = Router(name="import")
    router.message.register(on_import, Command("import"))
    router.message.register(on_cancel, Command("cancel"))
    router.message.register(on_credentials, Awaiting(), F.text)
    return router
