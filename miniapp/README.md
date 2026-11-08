# cpstands Mini App

The Telegram Mini App of [@cpstandsbot](https://t.me/cpstandsbot). It is hosted on
[Telegram Serverless](https://core.telegram.org/bots/serverless) at
`https://app9170246912.tgcloud.ai/`.

- `src/`: the React + Vite + TypeScript front end.
- `tgcloud/`: the code Serverless runs.
  - `endpoints/`: functions the front end calls.
  - `lib/`: shared modules.
  - `schema.js`: the SQLite schema.

## Rules that keep the Python bot working

The bot itself runs elsewhere (`src/cpstands`) and receives updates by long polling.

- **Never add files to `tgcloud/handlers/`.** A handler makes the platform own the bot's webhook,
  and the Python bot would stop getting updates.
- **Never run `npx tgcloud webhook sync`.** It points the webhook at the platform.
- After every push, `npx tgcloud webhook` must show `url: (none set)`.

## Endpoints

Every endpoint serves public Codeforces data. Answers are cached in the `cf_cache` table.

| Endpoint | Input | Cache |
|---|---|---|
| `contests` | nothing | 10 min |
| `profile` | `{ handle }` | 30 min |
| `compare` | `{ handles: [...] }`, 1 to 6 handles | 30 min |

Errors carry `parameters.code`:

| Code | Meaning |
|---|---|
| `NOT_FOUND` | No such handle |
| `BAD_HANDLE` | The handle is not valid |
| `BAD_COUNT` | Wrong number of handles for `compare` |
| `CF_DOWN` | Codeforces did not answer |
| `CF_BUSY` | Codeforces rate limit; the client retries once after 2 s |

The sandbox has no `URLSearchParams`, `URL` or `setTimeout`.

## Working on it

The access token comes from BotFather: Serverless → CLI Access. Keep it outside the repo.

```bash
npm install
export TGCLOUD_TOKEN=...       # never commit it
npx tgcloud run endpoints/profile '{handle:"tourist"}' --ctx '{initData:{user:{id:1,first_name:"T"}}}'
npm run deploy                 # build, then push
npx tgcloud migrate --safe     # after a schema.js change
npx tgcloud webhook            # must still show url: (none set)
```
