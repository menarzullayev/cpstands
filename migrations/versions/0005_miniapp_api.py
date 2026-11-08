"""Mini App API: RPC functions guarded by Telegram init data, and a locked-down public schema

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-08 23:00:00+00:00

Owner decision 2026-11-08: the database moves to Supabase and the Mini App reads and writes the
bot's own data. The Mini App calls these functions through Supabase's REST API with the public
anon key; every function first checks the Telegram init data signature (HMAC-SHA256 keyed by the
bot token, kept in the unexposed ``private`` schema), so a caller only ever reaches the private
chat whose id is their own Telegram user id. Tables stay closed to the API roles.

On a plain PostgreSQL (tests, local Docker) the Supabase roles do not exist; the grants are
skipped and the functions still work, so they are tested the same way.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = r"""
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS private;

CREATE TABLE IF NOT EXISTS private.app_secrets (
    name  text PRIMARY KEY,
    value text NOT NULL
);

-- application/x-www-form-urlencoded decoding, as URLSearchParams does it.
CREATE OR REPLACE FUNCTION private.url_decode(s text) RETURNS text
LANGUAGE sql IMMUTABLE STRICT AS $$
  SELECT coalesce(convert_from(string_agg(
           CASE WHEN tok ~ '^%[0-9A-Fa-f]{2}$' THEN decode(substr(tok, 2), 'hex')
                ELSE convert_to(tok, 'UTF8') END, ''::bytea ORDER BY ord), 'UTF8'), '')
  FROM regexp_matches(replace(s, '+', ' '), '%[0-9A-Fa-f]{2}|[^%]+|%', 'g')
       WITH ORDINALITY AS m(arr, ord),
       LATERAL (SELECT arr[1] AS tok) t
$$;

-- The Telegram user id of a valid init data string; raises on a bad or stale signature.
-- https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
CREATE OR REPLACE FUNCTION private.tg_user_id(init_data text, max_age_s integer DEFAULT 86400)
RETURNS bigint
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, private AS $$
DECLARE
  token text;
  pairs text[][];
  check_string text;
  given text;
  expected text;
  auth_date bigint;
  user_json jsonb;
BEGIN
  SELECT value INTO token FROM private.app_secrets WHERE name = 'bot_token';
  IF token IS NULL THEN
    RAISE EXCEPTION 'api not configured' USING ERRCODE = 'P0001';
  END IF;
  IF init_data IS NULL OR length(init_data) > 8192 THEN
    RAISE EXCEPTION 'invalid init data' USING ERRCODE = '28000';
  END IF;
  SELECT array_agg(ARRAY[k, v] ORDER BY k) INTO pairs
  FROM (
    SELECT private.url_decode(split_part(p, '=', 1)) AS k,
           private.url_decode(substr(p, length(split_part(p, '=', 1)) + 2)) AS v
    FROM unnest(string_to_array(init_data, '&')) AS p
    WHERE p <> ''
  ) kv;
  SELECT string_agg(pairs[i][1] || '=' || pairs[i][2], E'\n' ORDER BY pairs[i][1])
    INTO check_string
  FROM generate_subscripts(pairs, 1) AS i
  WHERE pairs[i][1] <> 'hash';
  SELECT pairs[i][2] INTO given FROM generate_subscripts(pairs, 1) AS i WHERE pairs[i][1] = 'hash';
  expected := encode(
    hmac(convert_to(check_string, 'UTF8'), hmac(convert_to(token, 'UTF8'), 'WebAppData'::bytea, 'sha256'), 'sha256'),
    'hex');
  IF given IS NULL OR given <> expected THEN
    RAISE EXCEPTION 'invalid init data' USING ERRCODE = '28000';
  END IF;
  SELECT pairs[i][2]::bigint INTO auth_date FROM generate_subscripts(pairs, 1) AS i WHERE pairs[i][1] = 'auth_date';
  IF auth_date IS NULL OR extract(epoch FROM now())::bigint - auth_date > max_age_s THEN
    RAISE EXCEPTION 'init data expired' USING ERRCODE = '28000';
  END IF;
  SELECT pairs[i][2]::jsonb INTO user_json FROM generate_subscripts(pairs, 1) AS i WHERE pairs[i][1] = 'user';
  IF user_json IS NULL OR NOT (user_json ? 'id') THEN
    RAISE EXCEPTION 'invalid init data' USING ERRCODE = '28000';
  END IF;
  RETURN (user_json->>'id')::bigint;
END
$$;

-- The caller's private chat row, created on first use (it stays in onboarding until /start).
CREATE OR REPLACE FUNCTION private.caller_chat(init_data text) RETURNS bigint
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, private AS $$
DECLARE uid bigint := private.tg_user_id(init_data);
BEGIN
  INSERT INTO chats (chat_id, chat_type) VALUES (uid, 'private') ON CONFLICT (chat_id) DO NOTHING;
  RETURN uid;
END
$$;

CREATE OR REPLACE FUNCTION private.friend_list(uid bigint) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, public, private AS $$
  SELECT jsonb_build_object(
    'max', 200,
    'friends', coalesce(jsonb_agg(w.handle_display ORDER BY w.added_at, w.handle_key), '[]'::jsonb))
  FROM watched_handles w
  WHERE w.chat_id = uid AND w.platform = 'codeforces'
$$;

CREATE OR REPLACE FUNCTION public.app_friends(init_data text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, private AS $$
BEGIN
  RETURN private.friend_list(private.caller_chat(init_data));
END
$$;

CREATE OR REPLACE FUNCTION public.app_friends_add(init_data text, handles text[]) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, private AS $$
DECLARE
  uid bigint := private.caller_chat(init_data);
  room integer;
  added text[] := '{}';
  already integer := 0;
  over integer := 0;
  h text;
BEGIN
  IF handles IS NULL OR cardinality(handles) = 0 OR cardinality(handles) > 200 THEN
    RAISE EXCEPTION 'bad handle count' USING ERRCODE = '22023';
  END IF;
  PERFORM 1 FROM chats WHERE chat_id = uid FOR UPDATE;  -- one writer per chat at a time
  SELECT 200 - count(*) INTO room FROM watched_handles WHERE chat_id = uid AND platform = 'codeforces';
  FOREACH h IN ARRAY handles LOOP
    IF h IS NULL OR h !~ '^[A-Za-z0-9_.-]{1,24}$' THEN
      RAISE EXCEPTION 'bad handle' USING ERRCODE = '22023';
    END IF;
    IF EXISTS (SELECT 1 FROM watched_handles
               WHERE chat_id = uid AND platform = 'codeforces' AND handle_key = lower(h)) THEN
      already := already + 1;
    ELSIF room <= 0 THEN
      over := over + 1;
    ELSE
      -- clock_timestamp keeps the order of one call (now() is fixed per transaction).
      INSERT INTO watched_handles (chat_id, platform, handle_key, handle_display, added_at)
      VALUES (uid, 'codeforces', lower(h), h, clock_timestamp());
      added := added || h;
      room := room - 1;
    END IF;
  END LOOP;
  RETURN private.friend_list(uid)
    || jsonb_build_object('added', to_jsonb(added), 'already', already, 'overLimit', over);
END
$$;

CREATE OR REPLACE FUNCTION public.app_friends_remove(init_data text, handles text[]) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, private AS $$
DECLARE uid bigint := private.caller_chat(init_data);
BEGIN
  DELETE FROM watched_handles
  WHERE chat_id = uid AND platform = 'codeforces'
    AND handle_key = ANY(SELECT lower(x) FROM unnest(handles) x);
  RETURN private.friend_list(uid);
END
$$;

CREATE OR REPLACE FUNCTION private.settings_of(uid bigint) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, public, private AS $$
  SELECT jsonb_build_object(
    'status', c.status, 'language', c.language, 'timeZone', c.time_zone, 'tone', c.tone,
    'reminders', to_jsonb(c.reminder_offsets), 'alerts', c.alerts_enabled,
    'notifyLevel', c.notify_level, 'tableCols', c.table_cols, 'summary', c.summary_enabled)
  FROM chats c WHERE c.chat_id = uid
$$;

CREATE OR REPLACE FUNCTION public.app_settings(init_data text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, private AS $$
BEGIN
  RETURN private.settings_of(private.caller_chat(init_data));
END
$$;

CREATE OR REPLACE FUNCTION public.app_settings_update(init_data text, patch jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, private AS $$
DECLARE
  uid bigint := private.caller_chat(init_data);
  offsets integer[];
BEGIN
  IF patch ? 'language' THEN
    UPDATE chats SET language = patch->>'language', updated_at = now() WHERE chat_id = uid;
  END IF;
  IF patch ? 'timeZone' THEN
    IF NOT EXISTS (SELECT 1 FROM pg_timezone_names WHERE name = patch->>'timeZone') THEN
      RAISE EXCEPTION 'bad time zone' USING ERRCODE = '22023';
    END IF;
    UPDATE chats SET time_zone = patch->>'timeZone', updated_at = now() WHERE chat_id = uid;
  END IF;
  IF patch ? 'tone' THEN
    UPDATE chats SET tone = patch->>'tone', updated_at = now() WHERE chat_id = uid;
  END IF;
  IF patch ? 'alerts' THEN
    UPDATE chats SET alerts_enabled = (patch->>'alerts')::boolean, updated_at = now() WHERE chat_id = uid;
  END IF;
  IF patch ? 'summary' THEN
    UPDATE chats SET summary_enabled = (patch->>'summary')::boolean, updated_at = now() WHERE chat_id = uid;
  END IF;
  IF patch ? 'notifyLevel' THEN
    UPDATE chats SET notify_level = (patch->>'notifyLevel')::integer, updated_at = now() WHERE chat_id = uid;
  END IF;
  IF patch ? 'tableCols' THEN
    UPDATE chats SET table_cols = (patch->>'tableCols')::integer, updated_at = now() WHERE chat_id = uid;
  END IF;
  IF patch ? 'reminders' THEN
    SELECT coalesce(array_agg(DISTINCT x::integer ORDER BY x::integer DESC), '{}') INTO offsets
    FROM jsonb_array_elements_text(patch->'reminders') x;
    IF NOT offsets <@ ARRAY[4320, 1440, 120, 60, 10] THEN
      RAISE EXCEPTION 'bad reminder offset' USING ERRCODE = '22023';
    END IF;
    UPDATE chats SET reminder_offsets = offsets, updated_at = now() WHERE chat_id = uid;
    -- Same rule as the bot: deselected offsets are cancelled, the planner adds new ones.
    UPDATE reminders SET state = 'cancelled'
    WHERE chat_id = uid AND state = 'scheduled' AND offset_min > 0 AND NOT (offset_min = ANY(offsets));
  END IF;
  RETURN private.settings_of(uid);
END
$$;

-- Public health summary for the status page: no personal data.
CREATE OR REPLACE FUNCTION public.app_status() RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, private AS $$
  SELECT jsonb_build_object(
    'now', extract(epoch FROM now())::bigint,
    'heartbeat', (SELECT value FROM runtime_state WHERE key = 'bot.heartbeat'),
    'chats', (SELECT count(*) FROM chats WHERE status = 'active'),
    'handles', (SELECT count(DISTINCT handle_key) FROM watched_handles),
    'remindersSent24h', (SELECT count(*) FROM reminders WHERE state = 'sent' AND sent_at > now() - interval '1 day'),
    'liveContests', (SELECT count(*) FROM contests WHERE phase IN ('CODING','PENDING_SYSTEM_TEST','SYSTEM_TEST')),
    'nextContest', (SELECT jsonb_build_object('name', name, 'startsAt', extract(epoch FROM starts_at)::bigint)
                    FROM contests WHERE phase = 'BEFORE' AND starts_at > now() ORDER BY starts_at LIMIT 1))
$$;

REVOKE ALL ON SCHEMA private FROM PUBLIC;

REVOKE ALL ON ALL FUNCTIONS IN SCHEMA private FROM PUBLIC;

REVOKE ALL ON FUNCTION public.app_friends(text), public.app_friends_add(text, text[]),
  public.app_friends_remove(text, text[]), public.app_settings(text),
  public.app_settings_update(text, jsonb), public.app_status() FROM PUBLIC;

DO $$
DECLARE t record;
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    -- Supabase: the API roles reach only the app_* functions, never a table.
    EXECUTE 'REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated';
    EXECUTE 'REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated';
    EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM anon, authenticated';
    EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM anon, authenticated';
    FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
      EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t.tablename);
    END LOOP;
    EXECUTE 'GRANT EXECUTE ON FUNCTION public.app_friends(text), public.app_friends_add(text, text[]),
      public.app_friends_remove(text, text[]), public.app_settings(text),
      public.app_settings_update(text, jsonb), public.app_status() TO anon';
  END IF;
END
$$;
"""

DOWNGRADE = r"""
DROP FUNCTION IF EXISTS public.app_status();

DROP FUNCTION IF EXISTS public.app_settings_update(text, jsonb);

DROP FUNCTION IF EXISTS public.app_settings(text);

DROP FUNCTION IF EXISTS public.app_friends_remove(text, text[]);

DROP FUNCTION IF EXISTS public.app_friends_add(text, text[]);

DROP FUNCTION IF EXISTS public.app_friends(text);

DROP SCHEMA IF EXISTS private CASCADE;
"""


def _statements(script: str) -> list[str]:
    """asyncpg runs one command per call; statements here end with ';' and a blank line."""
    return [part.strip() for part in re.split(r";[ \t]*\n[ \t]*\n", script) if part.strip()]


def upgrade() -> None:
    for statement in _statements(UPGRADE):
        op.execute(statement)


def downgrade() -> None:
    for statement in _statements(DOWNGRADE):
        op.execute(statement)
