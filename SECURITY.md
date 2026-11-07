# Security policy

cpstands is a pre-release project run by one maintainer on a personal machine (best-effort availability).

## Reporting a vulnerability

Please report security problems privately through GitHub: **Security -> Report a vulnerability** on
<https://github.com/menarzullayev/cpstands/security/advisories/new>. Do not open a public issue for vulnerabilities
and do not post tokens or personal data anywhere.

You can expect an acknowledgement within a few days. There is no bounty.

## What is in scope

- Leaks of the bot token or other secrets through code, logs or the container image.
- Bypasses of the chat-admin authorization model.
- Ways to read or delete another chat's data.
- Supply-chain issues in the build and deployment pipeline.

## Handling secrets

Secrets live only in a git-ignored `.env` file. If a token ever leaks, revoke it in @BotFather (`/revoke`) first and then report it.
