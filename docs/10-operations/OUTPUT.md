# Quality & Operations

Scope: release R1 on the maintainer's home PC (ADR-007) with the owner's accepted risks (ADR-009, ADR-014). All commitments here are best-effort unless stated.
This stage defines how R1 is tested, delivered, observed, recovered and launched. It documents launch criteria; the launch itself is a separate decision recorded at the launch review in milestone M8.

## Test strategy

| Level | What | Tools and data | Requirements |
|---|---|---|---|
| Unit | Domain rules, parsers, renderers, planners, authorization | pytest, property-based tests for keys and invariants | REQ-001 to REQ-022 |
| Contract | Codeforces JSON shapes and error responses | recorded fixtures (small, medium, largest contest), schema checks | REQ-N01, REQ-N07, REQ-N10 |
| Integration | Repositories, migrations, queue claims, outbox, retention | real PostgreSQL 16 in CI, Alembic up and down | REQ-N02, REQ-018 |
| End to end | Update in, Telegram call out, using a fake Telegram transport and fake clocks | replay of recorded contests at accelerated speed | REQ-001, REQ-004, REQ-007 |
| Localization | Catalog completeness, argument parity, plural forms | CI test over all `.ftl` files | REQ-015, REQ-014 |
| Performance | Cadence and payload experiment, load at 500 chats and 20 000 handles | replay harness, synthetic chats | REQ-N01, REQ-N03, REQ-N05 |
| Soak | 24 hours of continuous replay and idle periods | memory and queue-depth tracking | REQ-N02, REQ-N05 |
| Failure injection | Codeforces outage, Telegram 429 and 5xx, database restart, process kill, clock jump | scripted faults | REQ-N02, REQ-022, REQ-020 |
| Security | Secret scan, dependency audit, authorization tests, input fuzzing of handles and callbacks | gitleaks or equivalent, pip-audit, pytest | REQ-N09, REQ-013, REQ-021 |
| Documentation | Project Alpha validation and semantic audit | `project-alpha validate` and `audit` in CI | REQ-N10 |

Gates: a change merges only if lint, strict typing, unit, contract, integration and localization tests pass and coverage targets hold (NFR-012). Performance, soak and failure injection run before each release candidate and are required for `v1.0.0`.

## CI/CD

- CI: GitHub Actions on every push and pull request: install with uv, ruff, mypy, pytest with PostgreSQL service, pip-audit, secret scan, documentation validation, container build.
- Artifacts: container image tagged with the commit and the release tag, pushed to the GitHub Container Registry; software bill of materials generated with the build.
- CD: **automatic through a self-hosted GitHub runner on the home PC** (owner decision 2026-11-08, ADR-015). GitHub warns that self-hosted runners should almost never be used with public repositories (EVID-018), so the runner is confined: images are built and tested only on GitHub-hosted runners; the self-hosted runner executes one deploy workflow that only pulls a tagged image, runs migrations as an explicit step, restarts the stack and checks `/readyz`; that workflow starts only from a release tag or a manual dispatch by the owner, behind a protected GitHub Environment that requires the owner's approval; repository settings require approval before any workflow from an outside contributor runs; the runner never receives pull-request events; it runs as an unprivileged account, is registered with a dedicated label, and is updated regularly; workflow actions are pinned to commit SHAs; the deploy token has minimal permissions. The manual deploy script remains as the fallback.
- Environments: development (local Compose), beta and first release (home PC), later a dedicated host with the same image.
- Releases: semantic version tags; changelog in the repository; the previous image tag stays available for rollback.

## Monitoring

Metrics endpoint (NFR-009) and a local dashboard (optional Compose profile); owner-only `/status`. Tracked signals: standings age, fetch duration and errors per source, queue depth, delivery latency, Telegram errors by class, reminders due and sent, process uptime, database health. Availability is computed from the bot's own heartbeat records and published with the caveat that full-host outages are not observable (ADR-009).

## Logging

Structured JSON without message content, with correlation ids; the chat id appears hashed; rotation keeps at most 30 days (NFR-011). Logs never contain the bot token, URLs with tokens or user text; a redaction test runs in CI.

## Alerting

In-app alerts by direct message to the owner (ADR-009) using the thresholds in NFR-010: stale standings over 180 s during a contest, a reminder more than 60 s late, send failures above 5 percent over 5 minutes, three consecutive source errors, repeated restarts. Alerts are deduplicated and capped per hour. There is no external page; if the process or host is down, the owner notices personally.

## Backup

No automated backups (ADR-014). A one-command manual dump exists for the owner. Rules for any manual dump: protected location, deleted within 30 days of creation, never restored for chats whose deletion was requested; the dump is taken before every migration on the home PC.

## Disaster recovery

| Scenario | Impact | Recovery | Objective |
|---|---|---|---|
| Process crash or reboot | Short interruption | Container restart policy and auto-start; state resumes from the database | minutes |
| Database corruption or disk loss | Data loss | Reinstall stack, optionally restore the latest manual dump, otherwise start empty and let admins reconfigure | best effort, hours; data loss accepted by the owner |
| Bot token leak | Impersonation risk | Revoke in BotFather, put the new token into `.env`, restart, announce if needed | within the hour after detection |
| Codeforces API change or block | Standings stale | Degrade with notices, adjust parser or cadence, publish a status note | best effort |
| Home PC lost | Service down | Rebuild on another machine from the repository and image; secrets from the owner's records | best effort, days |

## Runbooks

Maintained in `docs/runbooks/` (created in milestone M7): start and stop; deploy and rollback; rotate the bot token; Codeforces outage or restriction; Telegram flood or 429 storm; stuck queue; reminder missed; handle a deletion request (including manual dumps); restore from a manual dump; migrate to a dedicated host; update dependencies; renew the home PC power and sleep settings checklist; self-hosted runner maintenance (update, re-register, remove).

## Incident readiness

Severity levels: SEV1 data exposure or token compromise; SEV2 service wrong or down during a contest; SEV3 degraded or a single source failing. Roles: the owner is incident commander and communicator. Communication: a short status post in `t.me/cpstands` for SEV1 and SEV2; a blameless post-mortem note in the repository for SEV1 and SEV2 within seven days. Detection depends on in-app alerts and the owner's attention (ADR-009).

## Security / compliance readiness

- Privacy policy published and linked in the bot profile; `/privacy` and `/delete` implemented and tested (REQ-017, REQ-018); 30-day retention jobs verified (REQ-N06).
- Secrets only in `.env` (git-ignored); repository scanned for secrets; token rotation rehearsed once before launch (REQ-N09, REQ-013).
- Self-hosted runner confinement (ADR-015, EVID-018) is verified before launch: fork-workflow approval policy, protected deploy environment, tag-only trigger, unprivileged runner account, and a test showing that a pull request from a fork cannot reach the runner.
- Dependency and image scans pass; no high-severity findings open.
- Terms of use of Codeforces for automated access reviewed and recorded before launch; the integration respects the documented request rate (REQ-N07).
- kep.uz remains disabled until written confirmation exists.
- Public statements (README, bot description, channel) say that availability is best-effort.

## Release / rollback plan

Release candidate tag, full CI, performance and failure-injection runs, closed beta over at least two real rounds, launch review, `v1.0.0`. Rollback: redeploy the previous image tag; if a migration was applied, use its tested down path or restore the pre-migration manual dump; announce in `t.me/cpstands` when users are affected.

## Production launch criteria

R1 may be launched publicly only when all thirteen of the following are true and the evidence is recorded:

1. All R1 requirements REQ-001 to REQ-022 have passing automated tests in CI, and REQ-N10 gates are green.
2. The freshness and latency experiments (REQ-N01, REQ-N03) ran; results meet the targets or the published figures state the measured values.
3. A 24-hour soak test shows no duplicate or missing reminders and no memory growth beyond the limit in NFR-007 (512 MB).
4. Failure-injection scenarios (Codeforces outage, Telegram 429, database restart, process kill) end with correct recovery and correct owner alerts.
5. The closed beta covered at least two real contest rounds in at least two chats without duplicated alerts or lost reminders.
6. Localization completeness (REQ-015) and tone guard checks pass in uz, ru and en.
7. `/privacy` and `/delete` work end to end; the retention job ran; no personal data appears in logs.
8. The secret scan is clean, the dependency audit has no open high findings, and the token rotation runbook was rehearsed.
9. Codeforces terms of use were reviewed and the conclusion is recorded.
10. README, bot description and channel state the best-effort availability and the privacy policy link.
11. Runbooks exist for the scenarios above and the restore-from-dump path was exercised once.
12. `project-alpha validate` and the global audit are green; the owner records an explicit launch approval after the launch review.
13. The self-hosted runner confinement listed under security readiness is verified, including a negative test with a pull request from a fork.

## Evidence

Evidence for these criteria is produced during implementation (test reports, experiment results, soak logs, beta notes) and recorded as evidence entries at the launch review. Currently available: the stage 03 evidence register and the verified vendor facts (EVID-016, EVID-017, which were evaluated and not adopted).

## Assumptions

- The home PC stays powered and reachable during contests; the owner accepts outages (ADR-007).
- GitHub Actions and the GitHub Container Registry remain available on free plans for a public repository.
- The runner confinement measures stay available in GitHub settings (fork-workflow approval, protected environments).
- The Codeforces terms of use permit read-only automated access at the documented rate (to be verified at launch criterion 9).

## Open questions

- Does the optional local dashboard stay in the default Compose file or in an opt-in profile?
- Which secret scanner is used in CI (decided in milestone M0)?
- Is a status page needed beyond posts in `t.me/cpstands`?

## Approvals

The owner approved on 2026-11-08 (Saidakbar Narzullayev) the operational commitments (best-effort availability, no external alerting, no automated backups), the thirteen launch criteria, and deployment through a self-hosted runner despite the documented risk (EVID-018), under the confinement measures above. Formal records are stored under `.project-alpha/decisions/` and `.project-alpha/approvals/` (approval APR-010).
