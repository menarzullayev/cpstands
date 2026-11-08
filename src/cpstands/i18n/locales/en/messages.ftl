# English catalog (Telegram HTML). Message ids and variables must match the uz and ru catalogs.
# "<id>-neutral" is the serious variant of "<id>", used when a chat switches the tone to neutral.

pick-language =
    🌍 <b>1/3 · Til · Язык · Language</b>

    Tilni tanlang · Выберите язык · Choose your language
onboarding-intro =
    👋 <b>Hi, I'm cpstands!</b>
    Live contest standings, reminders, and alerts when your friends solve problems. Three quick steps and we're set.
onboarding-intro-neutral =
    <b>cpstands</b>
    Contest standings, reminders, and solve alerts. Setup takes three steps.
onboarding-pick-timezone =
    🧭 <b>2/3 · Time zone</b>

    Pick your time zone below. Not listed? Send your city: <code>/timezone Tashkent</code>
setup-done =
    ✅ <b>3/3 · All set!</b>

    🌍 { $language}
    🧭 { $zone }

    Last step: tell me who to follow.
    <code>/track add tourist, jiangly</code>
setup-done-neutral =
    ✅ <b>3/3 · Setup complete</b>

    🌍 { $language}
    🧭 { $zone }

    Add the handles to follow:
    <code>/track add tourist, jiangly</code>
setup-celebrate = 🎉 Welcome aboard! Your friends' results will show up here.
setup-admin-needed = 🔒 Only the chat admins can finish the setup. Ask an admin to send /start.
group-added =
    👋 <b>Thanks for adding me!</b>
    An admin should send /start to pick the language and time zone. It takes ten seconds.
group-added-neutral =
    <b>cpstands is in the chat.</b>
    An admin should send /start to choose the language and time zone.

timezone-set =
    🧭 Time zone set: <b>{ $zone }</b>
    🕐 It is <b>{ $time }</b> there now
timezone-choose = 🧭 Several matches for “<b>{ $query }</b>”. Choose one:
timezone-not-found =
    ❌ No time zone found for “<b>{ $query }</b>”.
    Send your city in English, for example: <code>/timezone Tashkent</code>
timezone-invalid-button = ❌ That time zone is not valid. Send /timezone and try again.

settings-summary =
    ⚙️ <b>Settings</b>

    🌍 Language: <b>{ $language }</b>
    🧭 Time zone: <b>{ $zone }</b>
    🎭 Tone: <b>{ $mood ->
        [neutral] Neutral
       *[playful] Playful
    }</b>
    🔔 Reminders: <b>{ $reminders }</b>
    🔥 Alerts: <b>{ $level ->
        [0] off
        [1] scoreboard only
        [2] + system tests
        [3] + upsolves
       *[4] everything
    }</b>
    📊 Table columns: <b>{ $cols }</b>
    📈 Table style: <b>{ $style ->
       *[classic] classic
        [emoji] emoji
    }</b>
    🏁 Summary: <b>{ $summary ->
        [off] off
       *[on] on
    }</b>
    👥 Following: <b>{ $count ->
        [one] { $count } handle
       *[other] { $count } handles
    }</b>
settings-timezone-unset = not set yet
button-language = Language
button-timezone = Time zone
button-tone = { $mood ->
        [neutral] Tone: neutral
       *[playful] Tone: playful
    }
button-help-settings = Settings
button-help-track = Handles

track-usage =
    👥 <b>Handles to follow</b>

    <code>/track add handle1, handle2</code> — add
    <code>/track remove handle</code> — remove
    <code>/track list</code> — show the list
    <code>/track add kep:handle</code> — a kep.uz user
track-list-empty = 👥 The list is empty. Add handles: <code>/track add tourist, jiangly</code>
track-list-header = { $count ->
        [one] 👥 <b>Following { $count } handle</b>
       *[other] 👥 <b>Following { $count } handles</b>
    }
track-added = ✅ Added: <b>{ $handles }</b>
track-added-neutral = Added: { $handles }
track-already = ➖ Already in the list: { $handles }
track-unknown = ❌ Not found on Codeforces: { $handles }
track-invalid = ❌ Not a valid handle: { $handles }
track-limit = 🔒 The list is limited to { $limit } handles. Not added: { $handles }
track-truncated = ⚠️ Too many items in one message; only the first { $limit } were read.
track-removed = ✅ Removed: <b>{ $handles }</b>
track-not-found = ➖ Not in the list: { $handles }
track-nothing = Nothing to do. Example: <code>/track add tourist, jiangly</code>
track-source-error = ⚠️ Codeforces does not answer right now. Nothing was changed; try again in a minute.

not-admin = 🔒 Only the chat admins can do this.
button-expired = This button has expired. Please send the command again.
rate-limited = ⏰ Easy there, speedster! Give me a moment.
rate-limited-neutral = Too many requests. Please wait a moment.
error-generic = 😵 Something broke on my side. Please try again in a moment.
error-generic-neutral = Something went wrong. Please try again later.
help-text =
    💬 <b>cpstands</b> — contests for you and your friends

    <b>Setup</b>
    /start — language and time zone
    /timezone — change the time zone
    /settings — current settings

    <b>Friends</b>
    /track — handles to follow
    /friends — the same, in a private chat
    /rank — ratings of the followed handles (/rank kep — kep.uz)
    /rating — one user's rating card
    /summary — how the followed handles did in the last contest
    /import — copy your Codeforces friends (private chat)
    /donate — support the bot with Telegram Stars
    /app — open the Mini App

    <b>Contests</b> <i>(coming soon)</i>
    /standings · /upcoming · /rank

standings-usage =
    🏆 <b>Contest standings</b>

    <code>/standings 1970</code> — by contest id
    <code>/standings https://codeforces.com/contest/1970</code> — by link
    <code>/standings kep:504</code> — a kep.uz contest
standings-status = { $phase ->
        [running] 🔥 <b>Running</b>
        [before] ⏰ <b>Not started</b>
       *[finished] 🏁 <b>Finished</b>
    } · 👥 { $count ->
        [one] { $count } participant
       *[other] { $count } participants
    }{ $view ->
        [friends]  (friends)
       *[all] {""}
    } · 🕐 { $time }
standings-footer = Rows { $first }–{ $last } of { $total } · problems { $from_problem }–{ $to_problem }
standings-empty = No rows yet.
standings-not-found = ❌ Contest <b>{ $id }</b> was not found on Codeforces.
standings-not-started = ⏰ <b>{ $name }</b> has not started yet. The table appears when it does.
standings-source-error = ⚠️ Codeforces does not answer right now. Try again in a minute.
button-refresh = Refresh

reminder =
    ⏰ <b>{ $name }</b>
    { $left ->
        [d3] starts in 3 days
        [day] starts in 24 hours
        [h2] starts in 2 hours
        [hour] starts in 1 hour
       *[minutes] starts in { $minutes } minutes
    }
    🕐 { $start }
reminder-neutral =
    <b>{ $name }</b>
    { $left ->
        [d3] starts in 3 days
        [day] starts in 24 hours
        [h2] starts in 2 hours
        [hour] starts in 1 hour
       *[minutes] starts in { $minutes } minutes
    }
    { $start }
reminder-moved =
    🔄 <b>{ $name }</b> has been rescheduled.
    🕐 { $start }
reminder-moved-neutral =
    <b>{ $name }</b> has been rescheduled.
    { $start }
reminder-cancelled = ❌ <b>{ $name }</b> has been cancelled.
reminder-cancelled-neutral = <b>{ $name }</b> has been cancelled.
button-register = Register
button-contest = Contest page
upcoming-header = 🏆 <b>Upcoming contests</b>
upcoming-line =
    { $name }
    🕐 { $start } · ⏱ { $duration }
upcoming-empty = No contests are scheduled for the next two weeks.
upcoming-source-error = ⚠️ Codeforces does not answer right now. Try again in a minute.

alert-contest = 🏆 <b>{ $contest }</b>
alert-solve = { $v ->
        [0] 🔥 { $handle } solved { $problem } · { $title } · ⏱ { $time }
        [1] ⚡ { $handle } cracked { $problem } · { $title } · ⏱ { $time }
       *[2] 🎯 { $handle } got { $problem } · { $title } · ⏱ { $time }
    }
alert-solve-neutral = { $v ->
       *[other] { $handle } solved { $problem } ({ $title }) at { $time }.
    }
alert-upsolve = { $v ->
        [0] 📚 { $handle } upsolved { $problem } · { $title }
        [1] 🛠 { $handle } went back and solved { $problem } · { $title }
       *[2] 🌱 { $handle } finished { $problem } after the round · { $title }
    }
alert-upsolve-neutral = { $v ->
       *[other] { $handle } solved { $problem } ({ $title }) after the contest.
    }
alert-systest-fail = { $v ->
        [0] 💥 { $handle }'s { $problem } did not survive the system tests. It happens to the best! { $title } { $time }
        [1] 🧪 System tests had other plans for { $handle }'s { $problem }. Better luck next time! { $title } { $time }
       *[2] 😬 { $handle }'s { $problem } fell at the final hurdle: the system tests. Chin up! { $title } { $time }
    }
alert-systest-fail-neutral = { $v ->
       *[other] System tests failed: { $handle }, problem { $problem } ({ $title }, { $time }).
    }

privacy-text =
    🔒 <b>Privacy</b>

    I store only what the bot needs to work:
    • this chat's id, language, time zone, tone and switches
    • the public Codeforces handles you follow
    • contest results of those handles, for 30 days

    I never keep message text and never ask for passwords or tokens. The only exception is the optional /import: you send an API key once in a private chat, I delete the message, use the key for one request and never store or log it.
    Send /delete to erase everything stored about this chat.
button-privacy-policy = Privacy policy
button-delete-data = Delete data
button-delete-yes = Yes, delete everything
button-delete-no = Cancel
delete-confirm =
    🗑 <b>Delete all data of this chat?</b>

    The followed handles, settings, reminders and live tables will be erased. This cannot be undone.
delete-done =
    ✅ Done. Everything stored about this chat is deleted ({ $handles ->
        [one] { $handles } followed handle
       *[other] { $handles } followed handles
    }). Messages already in the chat stay; delete them yourself. Send /start to set up again.
delete-cancelled = Cancelled. Nothing was deleted.
delete-nothing = Nothing is stored about this chat.
delete-expired = ⏰ This confirmation has expired. Send /delete again.
owner-only = 🔒 Owner only.
owner-status =
    📟 <b>Status</b> v{ $version } · up { $uptime }

    <b>Sources</b>
    { $sources }

    <b>Queues</b>
    alerts pending { $alerts } · reminders overdue { $overdue }, scheduled { $scheduled }
    live messages { $live } · running contests { $contests }

    <b>Chats</b> { $chats }
    <b>Open operator alerts</b> { $open }
owner-stats =
    📊 <b>Stats</b>

    Active chats: { $chats }
    Followed handles: { $handles }
    Solve events (24 h): { $events }
    Reminders sent (24 h): { $reminders }
    Alerts pending: { $pending } · failed (24 h): { $failed }
owner-pause-usage = Use /pause or /resume alone for the source, or with a chat id.
owner-paused-source = ⏸ Source <code>{ $source }</code> is paused.
owner-resumed-source = ▶️ Source <code>{ $source }</code> is running.
owner-paused-chat = ⏸ Chat <code>{ $id }</code> is paused.
owner-resumed-chat = ▶️ Chat <code>{ $id }</code> is running.
owner-chat-unknown = Chat <code>{ $id }</code> was not found in the needed state.
ops-alert-stale = ⚠️ Standings of contest { $contest } are { $age } s old.
ops-alert-late = ⚠️ { $count } reminders are more than a minute late.
ops-alert-sends = ⚠️ { $percent }% of the last { $count } sends failed.
ops-alert-source = ⚠️ Source <code>{ $source }</code> failed { $count } times in a row.
ops-alert-resolved = ✅ Resolved: { $rule }

rank-title = 🏆 Friends' ratings
rank-status = { $count ->
        [one] 👥 { $count } handle
       *[other] 👥 { $count } handles
    } · 🕐 { $time }
rank-footer = Rows { $first }–{ $last } of { $total }
rank-unknown = ❌ Not found on Codeforces: { $handles }
rank-empty = 👥 The list is empty. Add handles first: <code>/track add tourist, jiangly</code>
rank-source-error = ⚠️ Codeforces does not answer right now. Try again in a minute.

word-off = off
button-back = Back
button-columns = Columns: { $n }
button-table-style = Style: { $style ->
       *[classic] classic
        [emoji] emoji
    }
button-summary = { $state ->
        [off] Summary: off
       *[on] Summary: on
    }
button-reminders-menu = Reminders
button-alerts-menu = Alerts
button-friends = Friends
button-level = { $level ->
        [0] Off
        [1] Scoreboard
        [2] + System tests
        [3] + Upsolves
       *[4] Everything
    }
reminders-menu =
    🔔 <b>Reminders</b>

    Choose when I remind you before a contest starts. Tap a time to switch it on or off.
alerts-menu =
    🔥 <b>Alerts</b>

    How much should I tell you about the handles you follow?
    <b>Off</b> — nothing
    <b>Scoreboard</b> — they only show in the standings
    <b>+ System tests</b> — also when a solution fails the system tests
    <b>+ Upsolves</b> — also problems solved after the contest
    <b>Everything</b> — and every solve during a contest
friends-menu =
    { $count ->
        [one] 👥 <b>Friends</b> · { $count } handle
       *[other] 👥 <b>Friends</b> · { $count } handles
    }

    Tap a handle to choose what I tell you about it.
friends-empty = 👥 No handles yet. Add some: <code>/track add tourist, jiangly</code>
friend-detail =
    👤 <b>{ $handle }</b>

    Choose what I tell you about this handle.
button-toggle-show = Show on scoreboard
button-toggle-solve = Solves during contests
button-toggle-systest = System test failures
button-toggle-upsolve = Upsolves
standings-no-friends = 👥 None of the followed handles took part in this contest.
button-view-friends = Friends
button-view-all = Everyone

rating-usage =
    👤 <b>Rating card</b>

    <code>/rating tourist</code> — a user's rating, rank and last contest
    <code>/rating kep:handle</code> — a kep.uz rating
rating-not-found = ❌ There is no user called <b>{ $handle }</b>.
rating-source-error = ⚠️ Codeforces does not answer right now. Try again in a minute.
rating-card =
    👤 <b>{ $handle }</b>

    { $body }
rating-unrated = 🏆 Unrated
rating-line = 🏆 <b>{ $rating }</b> · max { $max } · { $rank }
rating-contests = { $count ->
        [one] 📊 { $count } rated contest
       *[other] 📊 { $count } rated contests
    }
rating-no-contests = 📊 No rated contests yet
rating-last = 🕐 Last: <b>{ $contest }</b> · { $delta } ({ $old } → { $new })
rating-follow-done = ✅ Added to the list
rating-follow-limit = 🔒 The list is full ({ $limit } handles).
button-follow = Follow
button-profile = Profile

summary-header = 🏁 <b>{ $contest }</b> is over · { $count } participants
summary-line = { $medal } { $handle } · place { $rank } · { $solved ->
        [one] { $solved } problem
       *[other] { $solved } problems
    }
summary-rating = {" "}· { $delta } → { $new }
summary-best = 📈 Biggest rating gain: { $handle } ({ $delta })
summary-more = … and { $count } more followed handles
summary-unrated = ℹ️ Rating changes are not published for this contest (yet).
summary-usage =
    🏁 <b>Contest summary</b>

    <code>/summary</code> — the latest finished contest
    <code>/summary 2287</code> — a contest by its number
    <code>/summary kep</code> — the latest kep.uz contest
summary-no-friends = 👥 Follow some handles first: <code>/track add tourist</code>.
summary-none = 🤷 None of the followed handles took part in it.
summary-source-error = ⚠️ Codeforces does not answer right now. Try again in a minute.
button-results = Results

import-private-only = 🔒 Importing needs your API key, so it works only in a private chat with me. Open the bot and send /import there.
import-intro =
    📥 <b>Import friends from Codeforces</b>

    1. Open <a href="https://codeforces.com/settings/api">codeforces.com/settings/api</a> and press "Add API key".
    2. Send me the <b>key and the secret</b> in one message, for example:
    <code>KEY SECRET</code> (two 40-character codes).

    I delete your message at once, use the key for one request and forget it: it is never saved or logged. Afterwards delete the key on Codeforces. /cancel to stop; I wait 5 minutes.
import-cancelled = ✋ Import cancelled.
import-bad-format = ⚠️ I could not find two 40-character codes (key and secret) in your message. It was deleted. Send them again, or /cancel.
import-not-deleted = ⚠️ I could not delete your message with the key. Please delete it yourself and remove the key on Codeforces.
import-bad-credentials = ❌ Codeforces rejected this key or secret. Check both codes and start again with /import.
import-source-error = ⚠️ Codeforces does not answer right now. Start again with /import in a minute.
import-none = 🤷 Your friends list on Codeforces is empty.
import-done = ✅ Imported: { $count } new, { $already } were already in the list.
import-over-limit = 🔒 { $count } did not fit into the list limit.
import-revoke = 🧹 Now delete the API key at codeforces.com/settings/api: I no longer need it.
button-app = Open in app
donate-text =
    ⭐ <b>Support cpstands</b>

    The bot is free and stays free. If it helps you, you can thank it with Telegram Stars. Pick an amount:
donate-title = Support cpstands
donate-description = A voluntary donation. Every feature stays free.
donate-label = Donation
donate-thanks = 🎉 Thank you for { $stars } ⭐! It keeps the bot running.
app-text = 📱 cpstands in an app: contests, live standings, your friends and statistics.
app-text-group = 📱 This group in the app: its followed handles, standings and leaderboard.
