from __future__ import annotations

import asyncio

import pytest

import cpstands.__main__ as cli
from cpstands import __version__
from cpstands.config import Settings

TOKEN = "1234567890:" + "Z" * 35


def _settings(**kwargs: object) -> Settings:
    return Settings(_env_file=None, **kwargs)  # type: ignore[arg-type]


def test_version_command(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "get_settings", lambda: _settings())
    assert cli.main(["version"]) == 0
    assert capsys.readouterr().out.strip() == __version__


def test_config_check_lists_keys_without_secret_values(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        cli,
        "get_settings",
        lambda: _settings(
            telegram_bot_token=TOKEN, database_url="postgresql+asyncpg://u:pw-secret@h/d"
        ),
    )
    assert cli.main(["config-check"]) == 0
    out = capsys.readouterr().out
    assert "telegram_bot_token=set" in out
    assert "database_url=set" in out
    assert TOKEN not in out
    assert "pw-secret" not in out


def test_unknown_command_is_rejected() -> None:
    with pytest.raises(SystemExit):
        cli.main(["nope"])


@pytest.mark.db
async def test_db_check_fails_before_migration_and_passes_after(
    temp_database: str,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli, "get_settings", lambda: _settings(database_url=temp_database))
    assert await asyncio.to_thread(cli.main, ["db-check"]) == 1
    assert "not at head" in capsys.readouterr().out
    assert await asyncio.to_thread(cli.main, ["migrate"]) == 0
    assert await asyncio.to_thread(cli.main, ["db-check"]) == 0
    assert "database ok" in capsys.readouterr().out
