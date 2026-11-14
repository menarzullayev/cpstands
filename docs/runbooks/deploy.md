# Runbook: deploy to the home PC

The bot runs as a Docker Compose stack (`db`, `migrate`, `bot`) on the maintainer's PC.
Only one instance may poll Telegram: stop any `uv run python -m cpstands run` before deploying.

## Manual (the path in use)

From the checkout on the PC, on the commit to deploy (normally `main` after CI is green):

```bash
git pull --ff-only
```

```bash
docker tag cpstands:latest cpstands:previous
```

```bash
GIT_SHA=$(git rev-parse HEAD) docker compose up -d --build
```

```bash
curl -s http://127.0.0.1:9180/readyz     # ready, commit, checks
```

The deploy is done when `/readyz` answers `ready: true` and its `commit` equals
`git rev-parse HEAD`. If it does not, roll back (below).

Secrets live in `.env` (or the file named by `CPSTANDS_ENV_FILE`), never in the repository.

## Through the workflow (not in use)

`.github/workflows/deploy.yml` does the same steps on a self-hosted runner (labels
`self-hosted`, `windows`, `cpstands`): it builds the image with `GIT_SHA`, runs migrations,
starts the bot, waits for `/readyz`, fails unless the running commit equals the deployed one,
and puts the previous image back on failure.

No such runner is registered on the PC. Until 2026-11-15 the workflow started by itself after
every green CI run on `main`, and each run stayed queued until GitHub dropped it. The automatic
trigger was removed then (owner decision); the workflow now starts only from "Run workflow".
Registering the runner of ADR-015 and restoring the trigger is a separate decision. If that is
done, keep "Require approval for all outside collaborators" enabled for workflows in the
repository settings: the job runs on the maintainer's machine.

## Rollback

```bash
docker tag cpstands:previous cpstands:latest
docker compose up -d --no-build bot
```

## Checks after a deploy

- `/readyz` answers 200 with the expected `commit`
- `/status` to the bot (owner only) shows the source ok and no open operator alerts
- `docker compose logs --tail 50 bot` has `bot_started` and no `*_failed` events
