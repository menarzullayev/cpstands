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
    🔔 Reminders: <b>{ $reminders ->
        [off] off
       *[on] on
    }</b>
    🔥 Alerts: <b>{ $alerts ->
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
coming-soon = 🚧 This one is still in the workshop. Coming soon!
coming-soon-neutral = This command is not available yet.
help-text =
    💬 <b>cpstands</b> — contests for you and your friends

    <b>Setup</b>
    /start — language and time zone
    /timezone — change the time zone
    /settings — current settings

    <b>Friends</b>
    /track — handles to follow
    /friends — the same, in a private chat

    <b>Contests</b> <i>(coming soon)</i>
    /standings · /upcoming · /rank

standings-usage =
    🏆 <b>Contest standings</b>

    <code>/standings 1970</code> — by contest id
    <code>/standings https://codeforces.com/contest/1970</code> — by link
standings-status = { $phase ->
        [running] 🔥 <b>Running</b>
        [before] ⏰ <b>Not started</b>
       *[finished] 🏁 <b>Finished</b>
    } · 👥 { $count ->
        [one] { $count } participant
       *[other] { $count } participants
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
        [day] starts in 24 hours
        [hour] starts in 1 hour
       *[minutes] starts in { $minutes } minutes
    }
    🕐 { $start }
reminder-neutral =
    <b>{ $name }</b>
    { $left ->
        [day] starts in 24 hours
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
button-reminders = { $state ->
        [off] Reminders: off
       *[on] Reminders: on
    }
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
alert-systest-fail = { $v ->
        [0] 💥 { $handle }'s { $problem } did not survive the system tests. It happens to the best! { $title } { $time }
        [1] 🧪 System tests had other plans for { $handle }'s { $problem }. Better luck next time! { $title } { $time }
       *[2] 😬 { $handle }'s { $problem } fell at the final hurdle: the system tests. Chin up! { $title } { $time }
    }
alert-systest-fail-neutral = { $v ->
       *[other] System tests failed: { $handle }, problem { $problem } ({ $title }, { $time }).
    }
button-alerts = { $state ->
        [off] Alerts: off
       *[on] Alerts: on
    }
