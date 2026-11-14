# cpstands Mini App

The Telegram Mini App of [@cpstandsbot](https://t.me/cpstandsbot). It is hosted on
[Telegram Serverless](https://core.telegram.org/bots/serverless) at
`https://app9170246912.tgcloud.ai/`.

- `src/`: the React + Vite + TypeScript front end, built with Tailwind CSS v4 and shadcn/ui
  (`src/components/ui`). Recharts draws the charts and Motion the animations. The design
  decisions are in `docs/decisions/2026-11-08-miniapp-design.md`.
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

Every endpoint gets the verified Telegram user from `ctx.initData`.

| Endpoint | Input | What it returns | Cache |
|---|---|---|---|
| `contests` | nothing | running, upcoming and recently finished contests | 10 min |
| `profile` | `{ handle }` | user info and statistics from all submissions | 30 min |
| `compare` | `{ handles }`, 1 to 6 handles | rating histories and head-to-head results | 30 min |
| `friends` | `{ action, handles }`, action is `list`, `add` or `remove` | the caller's friend list | 15 min |
| `activity` | `{ me? }` | recent accepted solutions and rating changes of the friends | 15 min |
| `standings` | `{ me?, contestId? }` | standings filtered to the friends | 60 s live, 15 min finished |

The friend list lives in the SQLite `friends` table, keyed by Telegram user id, at most 200 handles.

- **Standings:** Codeforces serves full standings only to an unfiltered request, which can be
  several MB. `lib/standings.js` streams the answer, keeps only the friends' rows and stops early.
- **Activity:** refreshes at most two handles per call, because Codeforces allows about one call
  every 2 s and the sandbox has no timers. The answer says how many handles are still `pending`,
  and the client asks again after 3 s.

Errors carry `parameters.code`:

| Code | Meaning |
|---|---|
| `NOT_FOUND` | No such handle or contest |
| `BAD_HANDLE` | The handle is not valid |
| `BAD_COUNT` | Wrong number of handles |
| `NO_FRIENDS` | Standings with no friends and no own handle |
| `CF_DOWN` | Codeforces did not answer |
| `CF_BUSY` | Codeforces rate limit; the client retries once after 2 s |

The sandbox has no `URLSearchParams`, `URL` or `setTimeout`.

## Deep links

`https://t.me/cpstandsbot?startapp=<route>` opens a screen:

| Route | Screen |
|---|---|
| `profile_<handle>` | a profile |
| `compare_<h1>-<h2>-...` | a comparison |
| `standings_<contestId>` | contest standings |
| `home`, `contests`, `standings`, `friends`, `me` | a tab |

A bad route opens Home.

## Quality gates (CI job `miniapp`)

| Command | Checks |
|---|---|
| `npx tsc -b` | types |
| `npm run budget` | initial load at most 250 KB gzip, each lazy chunk at most 150 KB |
| `npm run test:budget` | proves the budget check fails when over budget |
| `npx playwright test` | `e2e/app.spec.ts`: navigation, deep links, the Back button, friends, settings |
| | `e2e/quality.spec.ts`: WCAG AA contrast of every text token in both themes, and LCP under 1.5 s |
| | `e2e/visual.spec.ts`: screenshots of every screen at 375 px and 768 px |

Telegram is mocked in `e2e/mock.ts`. Its answers are real endpoint output, captured by
`npm run fixtures`, which needs `TGCLOUD_TOKEN`.

Visual baselines are rendered in the `mcr.microsoft.com/playwright:v1.65.0-noble` image, the
same one CI uses. To refresh them after a deliberate design change:

```bash
docker run --rm --ipc=host -e CI=1 -v "$PWD:/work" -v cpstands-miniapp-nm:/work/node_modules -w /work   mcr.microsoft.com/playwright:v1.65.0-noble   sh -c "npm ci && npm run build && npx playwright test e2e/visual.spec.ts --update-snapshots"
```

The story background `public/story.png` is rendered by `node scripts/render-story.mjs`.

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
