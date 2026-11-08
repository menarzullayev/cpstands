# Mini App design decisions, 2026-11-08

Owner decisions for the professional redesign of `miniapp/`. They add to
[the owner decisions of the same day](2026-11-08-owner-decisions.md).

## Look and feel

| Topic | Decision |
|---|---|
| Visual style | Own brand, dark-first: dark background, neon accents, "terminal" mood. It does not follow the Telegram theme by default. |
| Palette | Background `#0a0e14`, card `#111823`, accent cyan `#22d3ee`, second accent violet `#a78bfa`, text `#e6edf3`, hint `#7d8590`. Codeforces rank colours stay as data colours. |
| Light mode | Yes, as a setting. Options: Dark (default), Light, Follow Telegram. |
| Fonts | Inter for text; JetBrains Mono for numbers, timers and handles. Self-hosted, about 60 KB, with Cyrillic and Uzbek Latin. |
| Components | Tailwind CSS + shadcn/ui, restyled with our tokens. |
| Charts | Recharts: tooltips, zoom/brush, animation. |
| Motion | Rich: page transitions, counters, glow, timer pulse (Framer Motion). |
| Effects switch | The user chooses: a setting Effects on/off. `prefers-reduced-motion` turns them off by default. |

## Structure

The app has a bottom tab bar with five tabs:

| Tab | Content |
|---|---|
| Home | Countdown to the next contest, my rating card (rating, last change, distance to the next rank), friends' activity feed |
| Contests | The contest calendar |
| Standings | Live standings |
| Friends | The friend list |
| Me | My profile and settings |

Profile and compare become inner pages.

- **First launch:** a short onboarding asks for the user's own Codeforces handle ("Me"). It is kept in
  Telegram CloudStorage, not in the bot database.
- **Friend list:** for now the Mini App keeps its own list in the Serverless SQLite store, keyed by
  Telegram user id. It merges with the bot's `/track` list after the database moves to Supabase.
- **Language:** follows the Telegram language (uz, ru or en); the user can switch it on the Me page.

## Telegram features

- Fullscreen mode and safe-area insets.
- `BackButton` on inner pages, plus haptic feedback.
- Add to home screen (`addToHomeScreen`).
- Share to story (`shareToStory`) for profile and result cards.
- Deep links: `t.me/cpstandsbot?startapp=<route>` opens a page, for example `profile_tourist`.
  Every page has a Share button, and buttons in bot messages can open the Mini App.

## Quality gates

- **Playwright visual tests** at 375 px and 768 px wide, in CI.
- **WCAG AA contrast:** at least 4.5:1 for text, checked automatically in both themes.
- **Performance budget:** at most 250 KB gzip and LCP under 1.5 s; CI fails above it.
- **Manual check** in Telegram Desktop and mobile before each release.
