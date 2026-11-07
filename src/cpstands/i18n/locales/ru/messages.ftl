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
coming-soon = 🚧 Эта команда ещё в мастерской. Скоро будет!
coming-soon-neutral = Эта команда пока недоступна.
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
