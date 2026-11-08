"""Which private chats are expected to send an API key right now (memory only, never stored)."""

from __future__ import annotations

import time
from collections.abc import Callable

WAIT_S = 300.0


class ImportGate:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._until: dict[int, float] = {}

    def arm(self, chat_id: int) -> None:
        self._until[chat_id] = self._clock() + WAIT_S

    def disarm(self, chat_id: int) -> None:
        self._until.pop(chat_id, None)

    def waiting(self, chat_id: int) -> bool:
        until = self._until.get(chat_id)
        if until is None:
            return False
        if self._clock() >= until:
            del self._until[chat_id]
            return False
        return True
