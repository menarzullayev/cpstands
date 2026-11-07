from __future__ import annotations

import json
import logging

import pytest
import structlog

from cpstands.logging import (
    REDACTED,
    configure_logging,
    hash_identifier,
    redact,
    redact_string,
)

TOKEN = "1234567890:" + "AbCdEfGhIj" * 4
SALT = b"unit-test-salt"


def test_token_inside_text_is_redacted() -> None:
    cleaned = redact_string(f"calling https://api.telegram.org/bot{TOKEN}/getMe failed")
    assert TOKEN not in cleaned
    assert REDACTED in cleaned


def test_database_url_password_is_redacted() -> None:
    cleaned = redact_string("connect postgresql+asyncpg://cpstands:hunter2@db:5432/cpstands")
    assert "hunter2" not in cleaned
    assert "cpstands:" in cleaned


@pytest.mark.parametrize(
    "key",
    [
        "bot_token",
        "TELEGRAM_WEBHOOK_SECRET",
        "password",
        "api_key",
        "Authorization",
        "database_url",
    ],
)
def test_sensitive_keys_are_replaced(key: str) -> None:
    assert redact({key: "value-that-must-not-leak"}) == {key: REDACTED}


def test_nested_structures_are_cleaned() -> None:
    cleaned = redact({"outer": [{"note": f"x {TOKEN} y"}, ("a", f"{TOKEN}")]})
    assert TOKEN not in json.dumps(cleaned)


def test_message_text_is_dropped() -> None:
    cleaned = redact({"text": "private words", "message_text": "more", "caption": "c", "ok": 1})
    assert cleaned == {"ok": 1}


def test_identifiers_are_hashed_consistently() -> None:
    cleaned = redact({"chat_id": 123456789, "user_id": 42}, SALT)
    assert cleaned["chat_id"] == hash_identifier(123456789, SALT)
    assert "123456789" not in json.dumps(cleaned)
    assert cleaned["chat_id"] != cleaned["user_id"]
    assert hash_identifier(1, b"a") != hash_identifier(1, b"b")


def test_json_pipeline_redacts_event_fields_and_exceptions(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging("INFO", salt=SALT)
    log = structlog.get_logger()
    try:
        raise RuntimeError(f"boom with {TOKEN}")
    except RuntimeError:
        log.error("failed", token=TOKEN, chat_id=987654321, text="secret chat words", exc_info=True)
    out = capsys.readouterr().out
    assert out.strip(), "a log line must be written"
    assert TOKEN not in out
    assert "987654321" not in out
    assert "secret chat words" not in out
    record = json.loads(out.strip().splitlines()[-1])
    assert record["level"] == "error"
    assert record["event"] == "failed"
    assert record["token"] == REDACTED


def test_standard_library_logging_is_redacted(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO", salt=SALT)
    logging.getLogger("httpx").info("GET https://api.telegram.org/bot%s/getUpdates", TOKEN)
    out = capsys.readouterr().out
    assert "getUpdates" in out
    assert TOKEN not in out


def test_level_filtering_is_applied(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("WARNING", salt=SALT)
    structlog.get_logger().info("hidden")
    structlog.get_logger().warning("shown")
    out = capsys.readouterr().out
    assert "hidden" not in out
    assert "shown" in out
