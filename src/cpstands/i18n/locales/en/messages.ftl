# English catalog. Message ids and variables must match the uz and ru catalogs (checked by tests).

pick-language = Tilni tanlang · Выберите язык · Choose your language
onboarding-intro = Hi! I'm cpstands: live contest standings, reminders, and alerts when your friends solve problems.
onboarding-pick-timezone = Pick your time zone. If it is not listed, send your city in English: /timezone Tashkent
setup-done = All set! Language: { $language }, time zone: { $zone }. Now add the handles to follow: /track add tourist, jiangly
setup-admin-needed = Only the chat admins can finish the setup. Ask an admin to send /start.
group-added = Thanks for adding me! An admin should send /start to choose the language and time zone.

timezone-set = Time zone set: { $zone } (it is { $time } there now)
timezone-choose = Several matches for “{ $query }”. Choose one:
timezone-not-found = No time zone found for “{ $query }”. Send your city in English, for example: /timezone Tashkent
timezone-invalid-button = That time zone is not valid. Send /timezone and try again.

settings-summary =
    Settings
    Language: { $language }
    Time zone: { $zone }
    Followed: { $count ->
        [one] { $count } handle
       *[other] { $count } handles
    }
settings-timezone-unset = not set yet
button-language = Language
button-timezone = Time zone

track-usage =
    Handles to follow:
    /track add handle1, handle2 - add
    /track remove handle - remove
    /track list - show the list
track-list-empty = The list is empty. Add handles: /track add tourist, jiangly
track-list-header = { $count ->
        [one] Followed: { $count } handle
       *[other] Followed: { $count } handles
    }
track-added = Added: { $handles }
track-already = Already in the list: { $handles }
track-unknown = Not found on Codeforces: { $handles }
track-invalid = Not a valid handle: { $handles }
track-limit = The list is limited to { $limit } handles. Not added: { $handles }
track-truncated = Too many items in one message; only the first { $limit } were read.
track-removed = Removed: { $handles }
track-not-found = Not in the list: { $handles }
track-nothing = Nothing to do. Example: /track add tourist, jiangly
track-source-error = Codeforces does not answer right now. Nothing was changed; please try again in a minute.

not-admin = Only the chat admins can do this.
button-expired = This button has expired. Please send the command again.
rate-limited = Too many requests. Please wait a moment.
error-generic = Something went wrong on my side. Please try again later.
coming-soon = This command is not available yet. It is on the way.
help-text =
    I follow contests for you and your friends.
    /start - set up language and time zone
    /track - handles to follow
    /timezone - change the time zone
    /settings - current settings
    /help - this message
