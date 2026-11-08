# Русский каталог (Telegram HTML). Идентификаторы и переменные совпадают с uz и en.
# "<id>-neutral" — серьёзный вариант "<id>" для чатов с нейтральным тоном.

pick-language =
    🌍 <b>1/3 · Til · Язык · Language</b>

    Tilni tanlang · Выберите язык · Choose your language
onboarding-intro =
    👋 <b>Привет, я cpstands!</b>
    Живые результаты контестов, напоминания и сигналы, когда друзья решают задачи. Три быстрых шага, и всё готово.
onboarding-intro-neutral =
    <b>cpstands</b>
    Результаты контестов, напоминания и уведомления о решённых задачах. Настройка в три шага.
onboarding-pick-timezone =
    🧭 <b>2/3 · Часовой пояс</b>

    Выберите часовой пояс ниже. Нет в списке? Напишите город: <code>/timezone Tashkent</code>
setup-done =
    ✅ <b>3/3 · Всё готово!</b>

    🌍 { $language}
    🧭 { $zone }

    Последний шаг: скажите, за кем следить.
    <code>/track add tourist, jiangly</code>
setup-done-neutral =
    ✅ <b>3/3 · Настройка завершена</b>

    🌍 { $language}
    🧭 { $zone }

    Добавьте хендлы для отслеживания:
    <code>/track add tourist, jiangly</code>
setup-celebrate = 🎉 Добро пожаловать! Результаты ваших друзей появятся здесь.
setup-admin-needed = 🔒 Настройку могут завершить только админы чата. Попросите админа отправить /start.
group-added =
    👋 <b>Спасибо, что добавили меня!</b>
    Админу нужно отправить /start, чтобы выбрать язык и часовой пояс. Это займёт десять секунд.
group-added-neutral =
    <b>cpstands в чате.</b>
    Админу нужно отправить /start, чтобы выбрать язык и часовой пояс.

timezone-set =
    🧭 Часовой пояс установлен: <b>{ $zone }</b>
    🕐 Там сейчас <b>{ $time }</b>
timezone-choose = 🧭 Для «<b>{ $query }</b>» найдено несколько вариантов. Выберите:
timezone-not-found =
    ❌ Часовой пояс для «<b>{ $query }</b>» не найден.
    Напишите город по-английски, например: <code>/timezone Tashkent</code>
timezone-invalid-button = ❌ Этот часовой пояс недопустим. Отправьте /timezone и попробуйте снова.

settings-summary =
    ⚙️ <b>Настройки</b>

    🌍 Язык: <b>{ $language }</b>
    🧭 Часовой пояс: <b>{ $zone }</b>
    🎭 Тон: <b>{ $mood ->
        [neutral] нейтральный
       *[playful] игривый
    }</b>
    🔔 Напоминания: <b>{ $reminders }</b>
    🔥 Оповещения: <b>{ $level ->
        [0] выключены
        [1] только таблица
        [2] + системные тесты
        [3] + дорешивание
       *[4] всё
    }</b>
    📊 Колонок в таблице: <b>{ $cols }</b>
    🏁 Итоги контеста: <b>{ $summary ->
        [off] выкл
       *[on] вкл
    }</b>
    👥 Отслеживается: <b>{ $count ->
        [one] { $count } хендл
        [few] { $count } хендла
        [many] { $count } хендлов
       *[other] { $count } хендла
    }</b>
settings-timezone-unset = пока не задан
button-language = Язык
button-timezone = Часовой пояс
button-tone = { $mood ->
        [neutral] Тон: нейтральный
       *[playful] Тон: игривый
    }
button-help-settings = Настройки
button-help-track = Хендлы

track-usage =
    👥 <b>Хендлы для отслеживания</b>

    <code>/track add handle1, handle2</code> — добавить
    <code>/track remove handle</code> — убрать
    <code>/track list</code> — показать список
track-list-empty = 👥 Список пуст. Добавьте хендлы: <code>/track add tourist, jiangly</code>
track-list-header = { $count ->
        [one] 👥 <b>Отслеживается { $count } хендл</b>
        [few] 👥 <b>Отслеживается { $count } хендла</b>
        [many] 👥 <b>Отслеживается { $count } хендлов</b>
       *[other] 👥 <b>Отслеживается { $count } хендла</b>
    }
track-added = ✅ Добавлено: <b>{ $handles }</b>
track-added-neutral = Добавлено: { $handles }
track-already = ➖ Уже в списке: { $handles }
track-unknown = ❌ Не найдено на Codeforces: { $handles }
track-invalid = ❌ Недопустимый хендл: { $handles }
track-limit = 🔒 Список ограничен { $limit } хендлами. Не добавлено: { $handles }
track-truncated = ⚠️ В одном сообщении слишком много элементов; прочитаны только первые { $limit }.
track-removed = ✅ Удалено: <b>{ $handles }</b>
track-not-found = ➖ Нет в списке: { $handles }
track-nothing = Нечего делать. Пример: <code>/track add tourist, jiangly</code>
track-source-error = ⚠️ Codeforces сейчас не отвечает. Ничего не изменено, попробуйте через минуту.

not-admin = 🔒 Это могут делать только админы чата.
button-expired = Кнопка устарела. Отправьте команду ещё раз.
rate-limited = ⏰ Полегче, торопыга! Дайте мне секунду.
rate-limited-neutral = Слишком много запросов. Подождите немного.
error-generic = 😵 У меня что-то сломалось. Попробуйте ещё раз чуть позже.
error-generic-neutral = Произошла ошибка. Попробуйте позже.
help-text =
    💬 <b>cpstands</b> — контесты для вас и ваших друзей

    <b>Настройка</b>
    /start — язык и часовой пояс
    /timezone — сменить часовой пояс
    /settings — текущие настройки

    <b>Друзья</b>
    /track — хендлы для отслеживания
    /friends — то же самое, в личном чате

    <b>Контесты</b> <i>(скоро)</i>
    /standings · /upcoming · /rank

standings-usage =
    🏆 <b>Результаты контеста</b>

    <code>/standings 1970</code> — по номеру контеста
    <code>/standings https://codeforces.com/contest/1970</code> — по ссылке
standings-status = { $phase ->
        [running] 🔥 <b>Идёт</b>
        [before] ⏰ <b>Ещё не начался</b>
       *[finished] 🏁 <b>Завершён</b>
    } · 👥 { $count ->
        [one] { $count } участник
        [few] { $count } участника
        [many] { $count } участников
       *[other] { $count } участника
    }{ $view ->
        [friends]  (друзья)
       *[all] {""}
    } · 🕐 { $time }
standings-footer = Строки { $first }–{ $last } из { $total } · задачи { $from_problem }–{ $to_problem }
standings-empty = Строк пока нет.
standings-not-found = ❌ Контест <b>{ $id }</b> не найден на Codeforces.
standings-not-started = ⏰ <b>{ $name }</b> ещё не начался. Таблица появится, когда он начнётся.
standings-source-error = ⚠️ Codeforces сейчас не отвечает. Попробуйте через минуту.
button-refresh = Обновить

reminder =
    ⏰ <b>{ $name }</b>
    { $left ->
        [d3] начнётся через 3 дня
        [day] начнётся через 24 часа
        [h2] начнётся через 2 часа
        [hour] начнётся через 1 час
       *[minutes] начнётся через { $minutes } мин
    }
    🕐 { $start }
reminder-neutral =
    <b>{ $name }</b>
    { $left ->
        [d3] начнётся через 3 дня
        [day] начнётся через 24 часа
        [h2] начнётся через 2 часа
        [hour] начнётся через 1 час
       *[minutes] начнётся через { $minutes } мин
    }
    { $start }
reminder-moved =
    🔄 Время контеста <b>{ $name }</b> изменилось.
    🕐 { $start }
reminder-moved-neutral =
    Время контеста <b>{ $name }</b> изменилось.
    { $start }
reminder-cancelled = ❌ Контест <b>{ $name }</b> отменён.
reminder-cancelled-neutral = Контест <b>{ $name }</b> отменён.
button-register = Регистрация
button-contest = Страница контеста
upcoming-header = 🏆 <b>Ближайшие контесты</b>
upcoming-line =
    { $name }
    🕐 { $start } · ⏱ { $duration }
upcoming-empty = На ближайшие две недели контестов не запланировано.
upcoming-source-error = ⚠️ Codeforces сейчас не отвечает. Попробуйте через минуту.

alert-contest = 🏆 <b>{ $contest }</b>
alert-solve = { $v ->
        [0] 🔥 { $handle }: { $problem } решена! · { $title } · ⏱ { $time }
        [1] ⚡ Есть! { $handle } закрывает { $problem } · { $title } · ⏱ { $time }
       *[2] 🎯 { $handle } забирает { $problem } · { $title } · ⏱ { $time }
    }
alert-solve-neutral = { $v ->
       *[other] { $handle }: задача { $problem } решена ({ $title }), { $time }.
    }
alert-systest-fail = { $v ->
        [0] 💥 { $problem } у { $handle } не прошла системные тесты. Бывает и у лучших! { $title } { $time }
        [1] 🧪 Системные тесты оказались строже: { $problem } у { $handle } не засчитана. В следующий раз повезёт! { $title } { $time }
       *[2] 😬 { $problem } у { $handle } споткнулась о системные тесты. Держимся! { $title } { $time }
    }
alert-systest-fail-neutral = { $v ->
       *[other] Системные тесты не пройдены: { $handle }, задача { $problem } ({ $title }, { $time }).
    }

privacy-text =
    🔒 <b>Конфиденциальность</b>

    Я храню только то, что нужно для работы:
    • id этого чата, язык, часовой пояс, тон и переключатели
    • публичные хендлы Codeforces, за которыми вы следите
    • результаты контестов этих хендлов, 30 дней

    Я не храню текст сообщений и никогда не прошу пароли, API-ключи или токены.
    Отправьте /delete, чтобы стереть всё, что хранится об этом чате.
button-privacy-policy = Политика
button-delete-data = Удалить данные
button-delete-yes = Да, удалить всё
button-delete-no = Отмена
delete-confirm =
    🗑 <b>Удалить все данные этого чата?</b>

    Отслеживаемые хендлы, настройки, напоминания и живые таблицы будут стёрты. Это нельзя отменить.
delete-done =
    ✅ Готово. Всё, что хранилось об этом чате, удалено ({ $handles ->
        [one] { $handles } отслеживаемый хендл
        [few] { $handles } отслеживаемых хендла
        [many] { $handles } отслеживаемых хендлов
       *[other] { $handles } отслеживаемого хендла
    }). Сообщения в чате остаются, удалите их сами. Отправьте /start, чтобы настроить заново.
delete-cancelled = Отменено. Ничего не удалено.
delete-nothing = Об этом чате ничего не хранится.
delete-expired = ⏰ Подтверждение устарело. Отправьте /delete ещё раз.
owner-only = 🔒 Только для владельца.
owner-status =
    📟 <b>Статус</b> v{ $version } · работает { $uptime }

    <b>Источники</b>
    { $sources }

    <b>Очереди</b>
    алерты в ожидании { $alerts } · напоминания просрочены { $overdue }, запланированы { $scheduled }
    живых сообщений { $live } · идущих контестов { $contests }

    <b>Чаты</b> { $chats }
    <b>Открытые оповещения оператору</b> { $open }
owner-stats =
    📊 <b>Статистика</b>

    Активные чаты: { $chats }
    Отслеживаемые хендлы: { $handles }
    События решений (24 ч): { $events }
    Отправлено напоминаний (24 ч): { $reminders }
    Алерты в очереди: { $pending } · неудачные (24 ч): { $failed }
owner-pause-usage = Используйте /pause или /resume без аргументов для источника или с id чата.
owner-paused-source = ⏸ Источник <code>{ $source }</code> приостановлен.
owner-resumed-source = ▶️ Источник <code>{ $source }</code> работает.
owner-paused-chat = ⏸ Чат <code>{ $id }</code> приостановлен.
owner-resumed-chat = ▶️ Чат <code>{ $id }</code> работает.
owner-chat-unknown = Чат <code>{ $id }</code> не найден в нужном состоянии.
ops-alert-stale = ⚠️ Таблица контеста { $contest } устарела на { $age } с.
ops-alert-late = ⚠️ { $count } напоминаний опаздывают больше чем на минуту.
ops-alert-sends = ⚠️ { $percent }% из последних { $count } отправок не удались.
ops-alert-source = ⚠️ Источник <code>{ $source }</code> дал сбой { $count } раз подряд.
ops-alert-resolved = ✅ Устранено: { $rule }

rank-title = 🏆 Рейтинг друзей
rank-status = { $count ->
        [one] 👥 { $count } хендл
        [few] 👥 { $count } хендла
        [many] 👥 { $count } хендлов
       *[other] 👥 { $count } хендла
    } · 🕐 { $time }
rank-footer = Строки { $first }–{ $last } из { $total }
rank-unknown = ❌ Не найдено на Codeforces: { $handles }
rank-empty = 👥 Список пуст. Сначала добавьте хендлы: <code>/track add tourist, jiangly</code>
rank-source-error = ⚠️ Codeforces сейчас не отвечает. Попробуйте через минуту.

word-off = выкл
button-back = Назад
button-columns = Колонок: { $n }
button-summary = { $state ->
        [off] Итоги: выкл
       *[on] Итоги: вкл
    }
button-reminders-menu = Напоминания
button-alerts-menu = Оповещения
button-friends = Друзья
button-level = { $level ->
        [0] Выкл
        [1] Таблица
        [2] + Сист. тесты
        [3] + Дорешивание
       *[4] Всё
    }
reminders-menu =
    🔔 <b>Напоминания</b>

    Выберите, когда напоминать перед началом контеста. Нажмите на время, чтобы включить или выключить его.
alerts-menu =
    🔥 <b>Оповещения</b>

    О чём сообщать по отслеживаемым хендлам?
    <b>Выкл</b> — ни о чём
    <b>Таблица</b> — они только в таблице результатов
    <b>+ Сист. тесты</b> — ещё и когда решение не прошло системные тесты
    <b>+ Дорешивание</b> — ещё и задачи, решённые после контеста
    <b>Всё</b> — и каждое решение во время контеста
friends-menu =
    { $count ->
        [one] 👥 <b>Друзья</b> · { $count } хендл
        [few] 👥 <b>Друзья</b> · { $count } хендла
        [many] 👥 <b>Друзья</b> · { $count } хендлов
       *[other] 👥 <b>Друзья</b> · { $count } хендла
    }

    Нажмите на хендл, чтобы выбрать, о чём сообщать.
friends-empty = 👥 Хендлов пока нет. Добавьте: <code>/track add tourist, jiangly</code>
friend-detail =
    👤 <b>{ $handle }</b>

    Выберите, о чём сообщать по этому хендлу.
button-toggle-show = Показывать в таблице
button-toggle-solve = Решения во время контеста
button-toggle-systest = Провал системных тестов
button-toggle-upsolve = Дорешивание
standings-no-friends = 👥 Никто из отслеживаемых хендлов не участвовал в этом контесте.
button-view-friends = Друзья
button-view-all = Все
