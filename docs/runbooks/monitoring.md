# Monitoring: being told when the bot stops

## How it works

1. **Heartbeat.** Every 60 s the bot writes a heartbeat row (`runtime_state` `bot.heartbeat`)
   and then pings Healthchecks.io. The code is in `src/cpstands/services/heartbeat.py`.
2. **Check.** On Healthchecks.io the check `cpstands-bot` expects a ping every 2 minutes and
   waits 3 minutes more. So if the bot, Docker or the PC stops, an alert arrives after about
   5 minutes.
3. **Database failure.** If the heartbeat cannot be written, the bot pings `<url>/fail`, and
   the alert comes at once.
4. **Where alerts go:**
   - Telegram: a direct message from @HealthchecksBot to the owner's account `menarzullayev`.
   - Email: `saidakbarnarzullayev@mail.ru`.

   The check is marked up again, with a "now UP" message, on the next successful ping.
5. **Configuration:** `HEALTHCHECKS_PING_URL` in `.env`. The URL is a secret: anyone who has it
   can fake pings. It is never logged; the ping goes through aiohttp, because httpx logs URLs.
   Without the variable, nothing is pinged.

## Checked on 2026-11-08

- **Up:** after deploy the check showed "up" with the last ping a few seconds ago.
- **Alert test:**
  - A manual `/fail` ping brought "🔴 cpstands-bot is DOWN" on Telegram within a second.
  - The bot's next ping brought "🟢 now UP" 39 s later.

## When an alert comes

1. Open `docker compose ps`; check that Docker Desktop is running.
2. Run `curl -s localhost:9180/readyz` and read the `checks`.
3. Run `docker compose logs bot --since 15m`.
4. If the database is the cause, check the Supabase dashboard (project `upztrvigdloqzxcgdkwi`).
5. Restart with `docker compose up -d`, and watch for the "UP" message.

## Related pages

- **Public status:** the Mini App status page (Me → Service status) reads the same heartbeat
  through `app_status`.
- **Dashboard:**
  `https://healthchecks.io/projects/02036d74-1b21-4ff1-b119-5a2aec67a410/checks/`
