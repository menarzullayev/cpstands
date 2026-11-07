from __future__ import annotations

import pytest
from pydantic import ValidationError

from cpstands.config import Settings

VALID_TOKEN = "1234567890:" + "A" * 35


def make(**kwargs: object) -> Settings:
    return Settings(_env_file=None, **kwargs)  # type: ignore[arg-type]


def test_defaults_are_safe_and_valid() -> None:
    settings = make()
    assert settings.default_language == "uz"
    assert settings.supported_languages == ["uz", "ru", "en"]
    assert settings.kep_enabled is False
    assert settings.telegram_use_webhook is False
    assert settings.cf_min_request_interval_seconds >= 2


def test_supported_languages_parse_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPPORTED_LANGUAGES", "uz, RU")
    monkeypatch.setenv("DEFAULT_LANGUAGE", "ru")
    settings = Settings(_env_file=None)
    assert settings.supported_languages == ["uz", "ru"]


def test_empty_optional_values_become_none() -> None:
    settings = make(telegram_bot_token="", telegram_owner_id="", telegram_webhook_url="")
    assert settings.telegram_bot_token is None
    assert settings.telegram_owner_id is None
    assert settings.telegram_webhook_url is None


def test_valid_token_is_accepted_and_hidden() -> None:
    settings = make(telegram_bot_token=VALID_TOKEN)
    assert settings.telegram_bot_token is not None
    assert settings.telegram_bot_token.get_secret_value() == VALID_TOKEN
    assert VALID_TOKEN not in repr(settings)
    assert VALID_TOKEN not in str(settings)
    assert VALID_TOKEN not in settings.model_dump_json()


@pytest.mark.parametrize("bad", ["abc", "123:short", "x" * 40, "1234567890:" + "!" * 35])
def test_invalid_token_is_rejected(bad: str) -> None:
    with pytest.raises(ValidationError):
        make(telegram_bot_token=bad)


def test_describe_never_reveals_secrets() -> None:
    settings = make(
        telegram_bot_token=VALID_TOKEN,
        telegram_webhook_secret="s3cret-value",
        database_url="postgresql+asyncpg://user:pa55word@host/db",
    )
    described = settings.describe()
    dump = "\n".join(f"{k}={v}" for k, v in described.items())
    assert described["telegram_bot_token"] == "set"
    assert described["database_url"] == "set"
    assert described["telegram_webhook_secret"] == "set"
    for secret in (VALID_TOKEN, "s3cret-value", "pa55word"):
        assert secret not in dump


def test_webhook_mode_requires_url_and_secret() -> None:
    with pytest.raises(ValidationError):
        make(telegram_use_webhook=True)
    ok = make(
        telegram_use_webhook=True,
        telegram_webhook_url="https://example.org/tg",
        telegram_webhook_secret="x" * 20,
    )
    assert ok.telegram_use_webhook is True


def test_default_language_must_be_supported() -> None:
    with pytest.raises(ValidationError):
        make(default_language="en", supported_languages="uz,ru")


def test_unknown_language_is_rejected() -> None:
    with pytest.raises(ValidationError):
        make(supported_languages="uz,xx")


def test_invalid_timezone_is_rejected() -> None:
    with pytest.raises(ValidationError):
        make(default_timezone="Mars/Olympus")


def test_codeforces_interval_cannot_go_below_documented_rate() -> None:
    with pytest.raises(ValidationError):
        make(cf_min_request_interval_seconds=0.5)


def test_database_driver_must_be_asyncpg() -> None:
    with pytest.raises(ValidationError):
        make(database_url="postgresql://user:pw@host/db")


def test_owner_id_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        make(telegram_owner_id=-5)
