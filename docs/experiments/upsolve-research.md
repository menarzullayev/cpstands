# Research: how @codeforces_live_bot handled upsolving (input for a later decision)

Sources: our analysis of the exported chat (`cfbot/ANALYSIS.md`) and of the upstream code
(`cfbot/UPSTREAM_ANALYSIS.md`), checked 2026-11-08.

- Share: 1119 of 7366 solve events in 18 months were upsolves (about 15 percent).
- Mechanism: the bot compared full contest standings fetched with `showUnofficial=true`; rows
  with rank 0 were treated as upsolving. A new accepted problem on such a row became a
  "[UPSOLVING]" line, only for friends with the upsolving switch on.
- Status: broken since Codeforces rejects any extra parameter on `contest.standings` for
  non-admin users (the upstream author removed `showUnofficial` on 2026-05-10). Upsolving lines in
  the export: about 100 per month until March 2026, 38 in April, none afterwards.
- Alternative that still works anonymously: `user.status?handle=<h>&count=N` lists a user's
  recent submissions with `verdict`, `problem` and `relativeTimeSeconds`; a submission made after
  the contest ends (or by a PRACTICE or VIRTUAL participant) is an upsolve.
- Cost of that alternative: one request per followed handle per cycle at one request per two
  seconds (the limit we respect): 100 distinct handles need about 3.5 minutes per cycle.

Decision pending (owner): skip for R1, poll `user.status` for a short window after each contest,
or offer on-demand "who solved what yesterday".
