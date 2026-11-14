"""Links that open the Mini App on a given screen (owner decision 2026-11-08).

A group gets a signed link instead: Telegram does not tell a Mini App which group it was
opened from, so the start parameter carries the group id plus the first 16 hex characters of
HMAC-SHA256(bot token, 'group:<chat id>'). Migration 0006 (app_group) checks the same
signature, so a link for one group cannot be edited into another group's link.
"""

from __future__ import annotations

import hashlib
import hmac
import re

APP_LINK = "https://t.me/cpstandsbot?startapp={param}"
_STANDINGS = re.compile(r"^standings_(\d{1,7})$")

_secret: bytes | None = None


def configure(bot_token: str) -> None:
    """Called once at start-up; without it group links fall back to plain screens."""
    global _secret
    _secret = bot_token.encode()


def group_signature(chat_id: int, secret: bytes) -> str:
    return hmac.new(secret, f"group:{chat_id}".encode(), hashlib.sha256).hexdigest()[:16]


def group_param(chat_id: int, contest_id: int | None = None) -> str | None:
    if _secret is None or chat_id >= 0:
        return None
    param = f"g{abs(chat_id)}_{group_signature(chat_id, _secret)}"
    return f"{param}_s{contest_id}" if contest_id else param


def link(route: str, chat_id: int | None = None) -> str:
    """The Mini App link for ``route``; in a group, the signed group view instead."""
    if chat_id is not None and chat_id < 0:
        match = _STANDINGS.match(route)
        group = group_param(chat_id, int(match.group(1)) if match else None)
        if group:
            return APP_LINK.format(param=group)
    return APP_LINK.format(param=route)
