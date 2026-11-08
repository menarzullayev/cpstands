import { table, integer, text, index } from 'sdk/db';

// Short-lived copies of public Codeforces answers, so many Mini App users share one request.
// Only public data is stored here; chat settings stay in the bot's own database.
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
