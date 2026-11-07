"""Structured JSON logging with redaction (REQ-N06, REQ-N08, NFR-011, ADR-013).

Rules enforced here:
* values under keys that look secret are replaced;
* Telegram bot tokens and URLs that contain them are replaced inside any string;
* Telegram ids (``chat_id``, ``user_id``) are logged as a keyed hash, never raw;
* message text is never logged: the ``text``, ``message_text`` and ``caption`` keys are dropped.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
import secrets
import sys
from collections.abc import Mapping, MutableMapping
from typing import Any

import structlog

REDACTED = "[redacted]"
SENSITIVE_KEY_PARTS = (
    "token",
    "secret",
    "password",
    "passwd",
    "apikey",
    "api_key",
    "authorization",
    "dsn",
    "database_url",
)
DROPPED_KEYS = frozenset({"text", "message_text", "caption"})
HASHED_KEYS = frozenset({"chat_id", "user_id"})
TOKEN_RE = re.compile(r"(?<!\d)\d{6,12}:[A-Za-z0-9_-]{30,}")
URL_PASSWORD_RE = re.compile(
    r"(?P<scheme>[a-z][a-z0-9+.-]*://)(?P<user>[^:/@\s]+):(?P<pwd>[^@\s]+)@"
)

_process_salt = secrets.token_bytes(16)


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)


def redact_string(value: str) -> str:
    """Replace bot tokens and URL passwords inside a string."""
    value = TOKEN_RE.sub(REDACTED, value)
    return URL_PASSWORD_RE.sub(lambda m: f"{m['scheme']}{m['user']}:{REDACTED}@", value)


def hash_identifier(value: object, salt: bytes | None = None) -> str:
    """Keyed hash (12 hex chars) of an identifier for correlation without exposing it."""
    key = salt if salt is not None else _process_salt
    return hmac.new(key, str(value).encode(), hashlib.sha256).hexdigest()[:12]


def redact(value: Any, salt: bytes | None = None) -> Any:
    """Recursively redact a log value."""
    if isinstance(value, str):
        return redact_string(value)
    if isinstance(value, Mapping):
        cleaned: dict[Any, Any] = {}
        for key, item in value.items():
            name = str(key)
            if name in DROPPED_KEYS:
                continue
            if _is_sensitive_key(name):
                cleaned[key] = REDACTED
            elif name in HASHED_KEYS and item is not None:
                cleaned[key] = hash_identifier(item, salt)
            else:
                cleaned[key] = redact(item, salt)
        return cleaned
    if isinstance(value, list | tuple | set):
        return [redact(item, salt) for item in value]
    return value


def make_redaction_processor(salt: bytes | None = None) -> structlog.typing.Processor:
    def processor(
        _logger: Any, _method: str, event_dict: MutableMapping[str, Any]
    ) -> MutableMapping[str, Any]:
        return dict(redact(dict(event_dict), salt))

    return processor


def configure_logging(
    level: str = "INFO", *, salt: bytes | None = None, json_output: bool = True
) -> None:
    """Configure structlog and the standard library to emit redacted JSON lines on stdout."""
    renderer: structlog.typing.Processor = (
        structlog.processors.JSONRenderer() if json_output else structlog.dev.ConsoleRenderer()
    )
    shared: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        make_redaction_processor(salt),
    ]
    structlog.configure(
        processors=[*shared, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelNamesMapping()[level]),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=False,
    )
    logging.basicConfig(
        level=level,
        handlers=[logging.StreamHandler(sys.stdout)],
        format="%(message)s",
        force=True,
    )
    logging.getLogger().handlers[0].addFilter(_StdlibRedactionFilter())


class _StdlibRedactionFilter(logging.Filter):
    """Redact secrets in records coming from third-party libraries (httpx, aiogram, sqlalchemy)."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_string(record.getMessage())
        record.args = None
        return True
