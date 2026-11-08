# Runbook: deploy to the home PC

The bot runs as a Docker Compose stack (`db`, `migrate`, `bot`) on the maintainer's PC.
Only one instance may poll Telegram: stop any `uv run python -m cpstands run` before deploying.

## Automatic (preferred)

`.github/workflows/deploy.yml` runs on a self-hosted runner (labels `self-hosted`, `windows`,
`cpstands`) after the CI workflow succeeded on a push to `main`. It builds the image with
`GIT_SHA`, runs migrations, starts the bot, waits for `/readyz`, and fails unless the running
commit equals the tested commit. On failure it puts the previous image back.

The workflow never runs for forks or pull requests: the job condition requires a push event
from this repository. Keep "Require approval for all outside collaborators" enabled for
workflows in the repository settings.

## Manual

```bash
GIT_SHA=$(git rev-parse HEAD) docker compose up -d --build
curl -s http://127.0.0.1:8080/readyz     # ready, commit, checks
curl -s http://127.0.0.1:8080/metrics | head
```

Secrets live in `.env` (or the file named by `CPSTANDS_ENV_FILE`), never in the repository.

## Rollback

```bash
docker tag cpstands:previous cpstands:latest
docker compose up -d --no-build bot
```

## Checks after a deploy

- `/readyz` answers 200 with the expected `commit`
- `/status` to the bot (owner only) shows the source ok and no open operator alerts
- `docker compose logs --tail 50 bot` has `bot_started` and no `*_failed` events
