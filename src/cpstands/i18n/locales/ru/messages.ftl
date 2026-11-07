# Русский каталог. Идентификаторы и переменные должны совпадать с каталогами uz и en (проверяется тестами).

pick-language = Tilni tanlang · Выберите язык · Choose your language
onboarding-intro = Привет! Я cpstands: показываю живые результаты контестов, напоминаю о них и сообщаю, когда друзья решают задачи.
onboarding-pick-timezone = Выберите часовой пояс. Если его нет в списке, напишите город по-английски: /timezone Tashkent
setup-done = Готово! Язык: { $language }, часовой пояс: { $zone }. Теперь добавьте хендлы для отслеживания: /track add tourist, jiangly
setup-admin-needed = Настройку могут завершить только админы чата. Попросите админа отправить /start.
group-added = Спасибо, что добавили меня! Админу нужно отправить /start, чтобы выбрать язык и часовой пояс.

timezone-set = Часовой пояс установлен: { $zone } (там сейчас { $time })
timezone-choose = Для «{ $query }» найдено несколько вариантов. Выберите:
timezone-not-found = Часовой пояс для «{ $query }» не найден. Напишите город по-английски, например: /timezone Tashkent
timezone-invalid-button = Этот часовой пояс недопустим. Отправьте /timezone и попробуйте снова.

settings-summary =
    Настройки
    Язык: { $language }
    Часовой пояс: { $zone }
    Отслеживается: { $count ->
        [one] { $count } хендл
        [few] { $count } хендла
        [many] { $count } хендлов
       *[other] { $count } хендла
    }
settings-timezone-unset = пока не задан
button-language = Язык
button-timezone = Часовой пояс

track-usage =
    Хендлы для отслеживания:
    /track add handle1, handle2 - добавить
    /track remove handle - убрать
    /track list - показать список
track-list-empty = Список пуст. Добавьте хендлы: /track add tourist, jiangly
track-list-header = { $count ->
        [one] Отслеживается: { $count } хендл
        [few] Отслеживается: { $count } хендла
        [many] Отслеживается: { $count } хендлов
       *[other] Отслеживается: { $count } хендла
    }
track-added = Добавлено: { $handles }
track-already = Уже в списке: { $handles }
track-unknown = Не найдено на Codeforces: { $handles }
track-invalid = Недопустимый хендл: { $handles }
track-limit = Список ограничен { $limit } хендлами. Не добавлено: { $handles }
track-truncated = В одном сообщении слишком много элементов; прочитаны только первые { $limit }.
track-removed = Удалено: { $handles }
track-not-found = Нет в списке: { $handles }
track-nothing = Нечего делать. Пример: /track add tourist, jiangly
track-source-error = Codeforces сейчас не отвечает. Ничего не изменено, попробуйте через минуту.

not-admin = Это могут делать только админы чата.
button-expired = Кнопка устарела. Отправьте команду ещё раз.
rate-limited = Слишком много запросов. Подождите немного.
error-generic = Что-то пошло не так на моей стороне. Попробуйте позже.
coming-soon = Эта команда пока недоступна. Она скоро появится.
help-text =
    Я слежу за контестами для вас и ваших друзей.
    /start - настроить язык и часовой пояс
    /track - хендлы для отслеживания
    /timezone - сменить часовой пояс
    /settings - текущие настройки
    /help - это сообщение
