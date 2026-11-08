"""Group view in the Mini App: chat titles and a signed, read-only group API

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-08 08:00:00+00:00

A Mini App opened from a group link gets no group id from Telegram (only chat_instance), so
the bot posts links whose start parameter carries the group id and a signature:
``g<abs(chat id)>_<16 hex>[_s<contest id>]`` where the hex is the first 16 characters of
HMAC-SHA256(key = bot token, message = 'group:<chat id>'). The start parameter is part of the
Telegram-signed init data, so ``app_group`` verifies both signatures and then returns the
group's followed handles. It is read-only: settings still change through /settings in the
group, where the bot checks admin rights.

No colon may directly precede a word in this SQL: Alembic wraps it in text() and would read
that as a bind parameter (so the optional contest part uses a plain group, not a non-capturing
one).
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = r"""
ALTER TABLE chats ADD COLUMN IF NOT EXISTS title text;

-- The url-decoded value of one init data field; call only after private.tg_user_id succeeded.
CREATE OR REPLACE FUNCTION private.init_field(init_data text, name text) RETURNS text
LANGUAGE sql IMMUTABLE SET search_path = pg_catalog, public, private, extensions AS $$
  SELECT private.url_decode(substr(p, length(split_part(p, '=', 1)) + 2))
  FROM unnest(string_to_array(init_data, '&')) AS p
  WHERE private.url_decode(split_part(p, '=', 1)) = name
  LIMIT 1
$$;

CREATE OR REPLACE FUNCTION public.app_group(init_data text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, private, extensions AS $$
DECLARE
  uid bigint := private.tg_user_id(init_data);   -- verifies the Telegram signature first
  param text := private.init_field(init_data, 'start_param');
  m text[];
  gid bigint;
  token text;
  expected text;
  chat record;
BEGIN
  m := regexp_match(coalesce(param, ''), '^g([0-9]{1,15})_([0-9a-f]{16})(_s([0-9]{1,7}))?$');
  IF m IS NULL THEN
    RAISE EXCEPTION 'not a group link' USING ERRCODE = '22023';
  END IF;
  gid := -(m[1]::bigint);
  SELECT value INTO token FROM private.app_secrets WHERE name = 'bot_token';
  expected := left(encode(hmac(convert_to('group:' || gid, 'UTF8'), convert_to(token, 'UTF8'), 'sha256'), 'hex'), 16);
  IF m[2] <> expected THEN
    RAISE EXCEPTION 'invalid group link' USING ERRCODE = '28000';
  END IF;
  SELECT c.chat_id, c.title, c.language, c.time_zone, c.status INTO chat
  FROM chats c WHERE c.chat_id = gid AND c.chat_type IN ('group', 'supergroup');
  IF NOT FOUND OR chat.status <> 'active' THEN
    RAISE EXCEPTION 'group not active' USING ERRCODE = '22023';
  END IF;
  RETURN jsonb_build_object(
    'chatId', chat.chat_id,
    'title', chat.title,
    'language', chat.language,
    'timeZone', chat.time_zone,
    'contestId', m[4]::integer,
    'viewer', uid,
    'handles', coalesce((
      SELECT jsonb_agg(w.handle_display ORDER BY w.added_at, w.handle_key)
      FROM watched_handles w
      WHERE w.chat_id = gid AND w.platform = 'codeforces' AND w.show_in_list), '[]'::jsonb));
END
$$;

REVOKE ALL ON FUNCTION private.init_field(text, text) FROM PUBLIC;

REVOKE ALL ON FUNCTION public.app_group(text) FROM PUBLIC;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    EXECUTE 'GRANT EXECUTE ON FUNCTION public.app_group(text) TO anon';
  END IF;
END
$$;
"""

DOWNGRADE = r"""
DROP FUNCTION IF EXISTS public.app_group(text);

DROP FUNCTION IF EXISTS private.init_field(text, text);

ALTER TABLE chats DROP COLUMN IF EXISTS title;
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
