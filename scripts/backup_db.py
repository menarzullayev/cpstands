"""Back up the hosted (Supabase) database to a local folder; run monthly or by hand.

Owner decision 2026-11-08: one backup every 30 days, plus manual runs when needed.

Usage: python scripts/backup_db.py [--keep 6] [--out DIR]
  - The password is read from ~/.secrets/cpstands/supabase_db_password.txt (never printed).
  - pg_dump runs in the postgres:17-alpine image, so no local client is needed.
  - Each dump is checked with pg_restore --list before older ones are pruned.
Restore: docs/runbooks/database-backup.md
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import shutil
import subprocess
import sys
from pathlib import Path

HOST = "aws-1-eu-central-1.pooler.supabase.com"
USER = "postgres.upztrvigdloqzxcgdkwi"
IMAGE = "postgres:17-alpine"
SECRET = Path.home() / ".secrets" / "cpstands" / "supabase_db_password.txt"
DEFAULT_OUT = Path.home() / "backups" / "cpstands"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep", type=int, default=6, help="dumps to keep (default 6)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    docker = shutil.which("docker")
    if docker is None:
        print("FAIL docker is not on PATH")
        return 1
    password = SECRET.read_text(encoding="utf-8-sig").strip()
    args.out.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d-%H%M%S")
    target = args.out / f"cpstands-{stamp}.dump"
    env = dict(os.environ, PGPASSWORD=password)
    conn = f"host={HOST} port=5432 user={USER} dbname=postgres sslmode=require"

    # Only the bot's data: public and private schemas. The bot token in private.app_secrets is left
    # out (the bot writes it again at start-up), so a backup file never holds a secret.
    # Fixed arguments only; nothing here comes from user input.
    dump = subprocess.run(  # noqa: S603
        [docker, "run", "--rm", "-e", "PGPASSWORD", IMAGE, "pg_dump", conn, "-Fc",
         "--schema=public", "--schema=private", "--exclude-table-data=private.app_secrets",
         "--no-owner", "--no-privileges"],
        env=env, capture_output=True,
    )  # fmt: skip
    if dump.returncode != 0 or not dump.stdout:
        print(
            "FAIL pg_dump:", dump.stderr.decode("utf-8", "replace").replace(password, "***")[-500:]
        )
        return 1
    target.write_bytes(dump.stdout)

    check = subprocess.run(  # noqa: S603
        [docker, "run", "--rm", "-i", IMAGE, "pg_restore", "--list"],
        input=dump.stdout, capture_output=True,
    )  # fmt: skip
    entries = check.stdout.decode("utf-8", "replace").count("TABLE DATA")
    if check.returncode != 0 or entries == 0:
        print(f"FAIL the dump {target.name} does not read back; older dumps kept")
        return 1

    dumps = sorted(args.out.glob("cpstands-*.dump"))
    for old in dumps[: max(0, len(dumps) - args.keep)]:
        old.unlink()
    size_kb = target.stat().st_size / 1024
    print(
        f"ok {target} ({size_kb:.0f} KB, {entries} tables with data); keeping {min(len(dumps), args.keep)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
