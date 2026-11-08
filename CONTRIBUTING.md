# Contributing

Thanks for your interest. The project is documented stage by stage with the Project Alpha documentation system; the specification in
`docs/` is the source of truth for what the bot should do.

## Development setup

Requirements: [uv](https://docs.astral.sh/uv/), Docker (for PostgreSQL), Git.

```bash
uv sync                       # create the virtual environment (Python 3.13)
docker compose --profile dev up -d db       # PostgreSQL on 127.0.0.1:5440
uv run pytest                 # tests (database tests need the container above)
uv run ruff format . && uv run ruff check . && uv run mypy
```

Copy `.env.example` to `.env` for local settings; never commit `.env`.

## Rules

- Commits and pull requests follow Conventional Commits, in English (`fix(api): allow blank username in register`).
- Every behavior change comes with tests; a new check needs a negative test proving it can fail.
- User-visible texts must exist in uz, ru and en.
- Do not add secrets, personal data or chat content to code, tests, logs or documentation.
- Pull requests from forks are welcome; workflows from outside contributors need maintainer approval before they run.

## Documentation

Requirements, decisions and the architecture are in `docs/` and `.project-alpha/`. Changes that alter them must update the matching stage
output and, if material, add a decision record.
