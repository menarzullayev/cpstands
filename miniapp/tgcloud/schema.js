import { table, integer, text, index, uniqueIndex } from 'sdk/db';

// Short-lived copies of public Codeforces answers, so many Mini App users share one request.
export const cfCache = table(
  'cf_cache',
  {
    key: text('key').primaryKey(),
    body: text('body').notNull(),
    expiresAt: integer('expires_at').notNull(), // unix seconds
  },
  (t) => ({
    expiresIdx: index('idx_cf_cache_expires').on(t.expiresAt),
  }),
);

// The Mini App's own friend list, per Telegram user. It merges with the bot's /track list
// after the move to Supabase (docs/decisions/2026-11-08-miniapp-design.md).
export const friends = table(
  'friends',
  {
    id: integer('id').primaryKey({ autoIncrement: true }),
    userId: integer('user_id').notNull(), // Telegram user id from verified init data
    handle: text('handle').notNull(), // as Codeforces spells it
    handleKey: text('handle_key').notNull(), // lower case
    addedAt: integer('added_at').notNull(),
  },
  (t) => ({
    userHandle: uniqueIndex('uidx_friends_user_handle').on(t.userId, t.handleKey),
  }),
);
