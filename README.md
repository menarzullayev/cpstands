# cpstands

Live competitive-programming contest tracker for Telegram: friends' standings, reminders, and solve notifications
for Codeforces and kep.uz, in Uzbek, Russian, and English.

> Status: **pre-alpha.** The design is complete (documentation set approved); implementation is at milestones **M0 and M1 done**
> (project skeleton, CI, image, database baseline, Codeforces client and standings parser). The bot does not respond to users yet. Bot handle: `@cpstandsbot`.

## Availability and support

The bot is hosted on the maintainer's own computer and offers **best-effort availability** with no formal uptime target. Outages from power, network or
reboots are possible; measured availability will be published. Details in [docs/10-operations/OUTPUT.md](docs/10-operations/OUTPUT.md).

## Documentation

The project is documented with the Project Alpha documentation system, stage by stage, with evidence and decision records:
[vision](docs/01-vision/OUTPUT.md), [problems](docs/02-problem-discovery/OUTPUT.md), [market](docs/03-market-research/OUTPUT.md),
[PRD](docs/04-prd/OUTPUT.md), [domain model](docs/05-domain-model/OUTPUT.md), [architecture](docs/06-architecture/OUTPUT.md),
[ADRs](docs/07-adr/OUTPUT.md), [technical specification](docs/08-technical-spec/OUTPUT.md), [development plan](docs/09-development-plan/OUTPUT.md),
[operations](docs/10-operations/OUTPUT.md). Privacy: [PRIVACY.md](PRIVACY.md).

## Goals

- Reliable live standings as a single message that edits in place.
- Contest reminders that actually arrive (per user, per chat, in the user's own timezone).
- Works in private chats and groups, for communities anywhere in the world.
- Built on the newest Telegram Bot API features, with tests and observability from day one.
- Multi-source: Codeforces first, kep.uz next (with the owner's permission).

## Inspiration

Inspired by [TobxD/codeforces_live_bot](https://github.com/TobxD/codeforces_live_bot) (Apache-2.0). This is an
independent rewrite; no code is copied from it.

## License

Apache-2.0. See [LICENSE](LICENSE).

## Development

```bash
uv sync                      # Python 3.13 environment
docker compose up -d db      # PostgreSQL on 127.0.0.1:5440
uv run pytest                # tests
uv run cpstands config-check # configured keys, never secret values
```

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).
