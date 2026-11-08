"""Application settings loaded from environment variables and an optional git-ignored ``.env`` file.

Secrets are ``SecretStr`` so they never show up in ``repr``, logs or error messages.
Use :meth:`Settings.describe` to report which keys are configured without revealing values.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BOT_TOKEN_RE = re.compile(r"^\d{6,12}:[A-Za-z0-9_-]{30,}$")
LANGUAGES = ("uz", "ru", "en")
SECRET_FIELDS = frozenset(
    {"telegram_bot_token", "telegram_webhook_secret", "database_url", "log_hash_salt"}
)


class Settings(BaseSettings):
    """Runtime configuration (ADR-013)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Telegram
    telegram_bot_token: SecretStr | None = None
    telegram_bot_username: str = "cpstandsbot"
    telegram_owner_id: int | None = None
    telegram_use_webhook: bool = False
    telegram_webhook_url: str | None = None
    telegram_webhook_secret: SecretStr | None = None

    # Application
    app_env: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_hash_salt: SecretStr | None = None
    default_language: str = "uz"
    supported_languages: Annotated[list[str], NoDecode] = list(LANGUAGES)
    default_timezone: str = "Asia/Tashkent"
    # Health and metrics endpoints; port 0 turns them off.
    http_host: str = "127.0.0.1"
    # The commit this build was made from (set by the image build, shown by /readyz and /metrics).
    git_sha: str = "dev"
    http_port: int = 9180
    # Custom emoji in message text need Telegram Premium on the bot owner (Bot API 9.4).
    custom_emoji: bool = True
    # Custom-emoji icons on buttons (Bot API 9.4); verified to render in Telegram Desktop 7.4.
    button_icons: bool = True
    database_url: SecretStr = SecretStr(
        "postgresql+asyncpg://cpstands:cpstands@127.0.0.1:5440/cpstands"
    )

    # Sources
    cf_api_base: str = "https://codeforces.com/api"
    cf_min_request_interval_seconds: float = 2.0
    kep_api_base: str = "https://kep.uz/api"
    kep_enabled: bool = False

    @field_validator("supported_languages", mode="before")
    @classmethod
    def _split_languages(cls, value: object) -> object:
        if isinstance(value, str):
            return [part.strip().lower() for part in value.split(",") if part.strip()]
        return value

    @field_validator(
        "telegram_bot_token", "telegram_webhook_secret", "log_hash_salt", mode="before"
    )
    @classmethod
    def _empty_secret_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("telegram_webhook_url", "telegram_owner_id", mode="before")
    @classmethod
    def _empty_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("telegram_bot_token")
    @classmethod
    def _token_shape(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and not BOT_TOKEN_RE.match(value.get_secret_value()):
            raise ValueError("telegram_bot_token has an invalid format")
        return value

    @field_validator("telegram_owner_id")
    @classmethod
    def _owner_positive(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("telegram_owner_id must be a positive Telegram user id")
        return value

    @field_validator("database_url")
    @classmethod
    def _db_driver(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().startswith("postgresql+asyncpg://"):
            raise ValueError("database_url must use the postgresql+asyncpg driver")
        return value

    @field_validator("cf_min_request_interval_seconds")
    @classmethod
    def _cf_interval(cls, value: float) -> float:
        # Codeforces allows about one request per two seconds (EVID-012); never go below it.
        if value < 2.0:
            raise ValueError("cf_min_request_interval_seconds must be at least 2")
        return value

    @model_validator(mode="after")
    def _cross_checks(self) -> Settings:
        unknown = [code for code in self.supported_languages if code not in LANGUAGES]
        if unknown or not self.supported_languages:
            raise ValueError(f"supported_languages must be a non-empty subset of {LANGUAGES}")
        if self.default_language not in self.supported_languages:
            raise ValueError("default_language must be one of supported_languages")
        try:
            ZoneInfo(self.default_timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("default_timezone is not a valid IANA zone") from exc
        if self.telegram_use_webhook and not (
            self.telegram_webhook_url and self.telegram_webhook_secret
        ):
            raise ValueError("webhook mode needs telegram_webhook_url and telegram_webhook_secret")
        return self

    def describe(self) -> dict[str, str]:
        """Return ``{key: "set" | "unset" | value}`` with every secret reduced to set or unset."""
        result: dict[str, str] = {}
        for name in type(self).model_fields:
            value = getattr(self, name)
            if name in SECRET_FIELDS:
                result[name] = "set" if value is not None else "unset"
            elif value is None:
                result[name] = "unset"
            else:
                result[name] = str(value)
        return result


@lru_cache
def get_settings() -> Settings:
    return Settings()
