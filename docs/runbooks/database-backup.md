# Database backup and restore

The bot's database is hosted on Supabase: project `upztrvigdloqzxcgdkwi`, Frankfurt, Free plan.
The Free plan has no backups of its own, so they are made locally.

## Schedule

- **Automatic:** Windows Task Scheduler runs `cpstands\monthly-db-backup` every 30 days at 03:00.
  This is the owner decision of 2026-11-08.
- **By hand:** at any time, from the repository root:

  ```bash
  uv run python scripts/backup_db.py
  ```

- **Where:**
  - Dumps go to `~/backups/cpstands/cpstands-<UTC time>.dump`; the newest 6 are kept.
  - The log is `~/backups/cpstands/backup.log`.
- **What:**
  - The `public` and `private` schemas.
  - Each dump is read back with `pg_restore --list` before older ones are pruned.
- **No secrets inside:** the bot token in `private.app_secrets` is left out. The bot writes it
  again at start-up.
- **Needs:** Docker running, and the DB password in `~/.secrets/cpstands/supabase_db_password.txt`.

## Check that a dump restores (no risk to production)

```bash
docker run -d --rm --name restore-test -e POSTGRES_PASSWORD=t postgres:17-alpine
docker exec -i restore-test pg_restore -U postgres -d postgres --no-owner < ~/backups/cpstands/<file>.dump
docker exec restore-test psql -U postgres -tAc "select count(*) from chats"
docker stop restore-test
```

`--rm` makes Docker delete the container, and the anonymous data volume the postgres image creates,
when it stops. Without it `docker rm -f restore-test` would leave that volume behind.

"schema public already exists" is expected and harmless.

## Restore into Supabase (destructive: replaces live data)

1. Stop the bot: `docker compose stop bot`.
2. Take a fresh dump of the current state first: `uv run python scripts/backup_db.py`.
3. Restore with `--clean`, so objects are dropped and recreated:

   ```bash
   docker run --rm -i -e PGPASSWORD postgres:17-alpine pg_restore --clean --if-exists --no-owner \
     -d "host=aws-1-eu-central-1.pooler.supabase.com port=5432 user=postgres.upztrvigdloqzxcgdkwi dbname=postgres sslmode=require" \
     < ~/backups/cpstands/<file>.dump
   ```

4. Start the bot: `docker compose up -d bot`. It stores its token again and resumes.
5. Check the result: `/readyz`, and the `app_status` heartbeat on the Mini App status page.

The restore replaces the live data, so it is never run without the owner's go-ahead.
