"""Command line entry point: ``python -m cpstands <command>`` or the ``cpstands`` script."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from cpstands import __version__
from cpstands.config import Settings, get_settings
from cpstands.db.engine import create_engine
from cpstands.logging import configure_logging


def alembic_config(database_url: str | None = None) -> Config:
    """Build the Alembic config; the URL comes from settings or the argument, never the ini file."""
    ini = Path(os.environ.get("ALEMBIC_CONFIG", "alembic.ini"))
    config = Config(str(ini))
    if database_url is not None:
        config.attributes["database_url"] = database_url
    return config


def _out(message: str) -> None:
    sys.stdout.write(message + "\n")


def cmd_version(_args: argparse.Namespace, _settings: Settings) -> int:
    _out(__version__)
    return 0


def cmd_config_check(_args: argparse.Namespace, settings: Settings) -> int:
    for key, value in sorted(settings.describe().items()):
        _out(f"{key}={value}")
    return 0


def cmd_migrate(_args: argparse.Namespace, settings: Settings) -> int:
    command.upgrade(alembic_config(settings.database_url.get_secret_value()), "head")
    _out("migrations applied")
    return 0


async def _db_state(settings: Settings) -> tuple[str | None, str | None]:
    engine = create_engine(settings.database_url.get_secret_value(), pool_size=1)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
            exists = (
                await connection.execute(text("SELECT to_regclass('public.alembic_version')"))
            ).scalar()
            current = None
            if exists:
                current = (
                    await connection.execute(text("SELECT version_num FROM alembic_version"))
                ).scalar()
    finally:
        await engine.dispose()
    head = ScriptDirectory.from_config(alembic_config()).get_current_head()
    return current, head


def cmd_db_check(_args: argparse.Namespace, settings: Settings) -> int:
    current, head = asyncio.run(_db_state(settings))
    if current != head:
        _out(f"database is not at head: current={current} head={head}")
        return 1
    _out(f"database ok at {head}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cpstands", description="cpstands operations")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("version", help="print the version").set_defaults(func=cmd_version)
    sub.add_parser("config-check", help="list configured keys without secret values").set_defaults(
        func=cmd_config_check
    )
    sub.add_parser("migrate", help="apply database migrations to head").set_defaults(
        func=cmd_migrate
    )
    sub.add_parser("db-check", help="verify the database is reachable and at head").set_defaults(
        func=cmd_db_check
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = get_settings()
    salt = settings.log_hash_salt.get_secret_value().encode() if settings.log_hash_salt else None
    configure_logging(settings.log_level, salt=salt)
    return int(args.func(args, settings))


if __name__ == "__main__":
    raise SystemExit(main())
