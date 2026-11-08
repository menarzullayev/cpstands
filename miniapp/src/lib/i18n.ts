import { tgUser } from './tg'

const en = {
  'tab.home': 'Home',
  'tab.contests': 'Contests',
  'tab.standings': 'Standings',
  'tab.friends': 'Friends',
  'tab.me': 'Me',

  'onb.title': 'Welcome to cpstands',
  'onb.lead': 'Contests, live standings and your friends on Codeforces, in one place.',
  'onb.ask': 'What is your Codeforces handle?',
  'onb.placeholder': 'e.g. tourist',
  'onb.go': 'Continue',
  'onb.skip': 'I don’t have one yet',
  'onb.checking': 'Checking…',

  'home.next': 'Next contest',
  'home.startsIn': 'Starts in',
  'home.live': 'Live now',
  'home.endsIn': 'Ends in',
  'home.noContest': 'No contests announced yet',
  'home.myRating': 'My rating',
  'home.toNext': '{0} to {1}',
  'home.top': 'Top of the ladder',
  'home.lastChange': 'Last contest',
  'home.setHandle': 'Add your handle to see your rating',
  'home.activity': 'Friends’ activity',
  'home.noActivity': 'No activity in the last two weeks',
  'home.addFriends': 'Add friends to see what they solve',
  'home.pending': 'Loading {0} more…',
  'home.solved': 'solved',
  'home.inContest': 'in contest',

  'contests.live': 'Live now',
  'contests.upcoming': 'Upcoming',
  'contests.finished': 'Recently finished',
  'contests.none': 'Nothing here yet',
  'contests.in': 'in {0}',
  'contests.left': '{0} left',
  'contests.standings': 'Standings',

  'st.title': 'Standings',
  'st.noFriends': 'Add friends to compare places in contests',
  'st.nobody': 'None of your friends took part in this contest',
  'st.pick': 'Contest',
  'st.rank': '#',
  'st.who': 'Handle',
  'st.score': 'Score',
  'st.unofficial': 'out of competition',
  'st.refresh': 'Refresh',

  'fr.title': 'Friends',
  'fr.add': 'Add',
  'fr.placeholder': 'Handles, separated by spaces',
  'fr.empty': 'No friends yet. Add handles of people you follow.',
  'fr.count': '{0} of {1}',
  'fr.added': 'Added: {0}',
  'fr.already': 'Already there: {0}',
  'fr.over': 'Over the limit: {0}',
  'fr.remove': 'Remove',
  'fr.compare': 'Compare',
  'fr.online': 'online {0} ago',

  'me.title': 'Me',
  'me.handle': 'My handle',
  'me.change': 'Change',
  'me.profile': 'Open my profile',
  'me.settings': 'Settings',
  'me.language': 'Language',
  'me.theme': 'Theme',
  'me.theme.dark': 'Dark',
  'me.theme.light': 'Light',
  'me.theme.auto': 'Telegram',
  'me.effects': 'Effects and animations',
  'me.effectsHint': 'Turn off on slow phones',
  'me.home': 'Add to home screen',
  'me.homeHint': 'Open cpstands like an app',
  'me.bot': 'Open the bot',
  'me.donate': 'Support cpstands',
  'me.donateHint': 'A voluntary gift in Telegram Stars',
  'me.about': 'cpstands · Codeforces in Telegram',

  'pr.rating': 'Rating',
  'pr.max': 'Max',
  'pr.solved': 'Solved',
  'pr.contests': 'Contests',
  'pr.best': 'Best place',
  'pr.streak': 'Day streak',
  'pr.history': 'Rating history',
  'pr.activity': 'Activity',
  'pr.subsYear': '{0} submissions in a year',
  'pr.tags': 'Strongest topics',
  'pr.difficulty': 'Solved by difficulty',
  'pr.verdicts': 'Verdicts',
  'pr.languages': 'Languages',
  'pr.recent': 'Recent submissions',
  'pr.follow': 'Add to friends',
  'pr.following': 'In friends',
  'pr.compare': 'Compare',

  'cmp.title': 'Compare',
  'cmp.placeholder': 'Add a handle',
  'cmp.empty': 'Add two or more handles to compare',
  'cmp.h2h': 'Head to head',
  'cmp.noCommon': 'No contests in common',
  'cmp.max': 'Up to 6 handles',
  'cmp.wins': 'best place',

  'share': 'Share',
  'share.story': 'Story',
  'share.profile': '{0} on Codeforces: {1}',
  'share.compare': 'Codeforces: {0}',
  'more': 'Show more',
  'less': 'Show less',
  'cmp.contest': 'Contest',
  'unit.d': 'days',
  'unit.h': 'hours',
  'unit.m': 'min',
  'unit.s': 'sec',
  'retry': 'Try again',
  'unrated': 'unrated',
  'back': 'Back',

  'error.NOT_FOUND': 'No such handle on Codeforces',
  'error.BAD_HANDLE': 'This is not a valid handle',
  'error.CF_DOWN': 'Codeforces does not answer right now. Try again in a minute.',
  'error.CF_BUSY': 'Codeforces is busy. Try again in a few seconds.',
  'error.NO_TELEGRAM': 'Open this app from @cpstandsbot in Telegram.',
  'error.UNAUTHORIZED': 'Telegram could not confirm who you are. Reopen the app.',
  'error.NO_FRIENDS': 'Add friends first',
  'error.generic': 'Something went wrong. Try again.',
}

export type Key = keyof typeof en
type Dict = Record<Key, string>

const uz: Dict = {
  'tab.home': 'Bosh',
  'tab.contests': 'Contestlar',
  'tab.standings': 'Natijalar',
  'tab.friends': 'Do‘stlar',
  'tab.me': 'Men',

  'onb.title': 'cpstands’ga xush kelibsiz',
  'onb.lead': 'Codeforces contestlari, jonli natijalar va do‘stlaringiz bir joyda.',
  'onb.ask': 'Codeforces handle’ingiz qanday?',
  'onb.placeholder': 'masalan, tourist',
  'onb.go': 'Davom etish',
  'onb.skip': 'Hali handle’im yo‘q',
  'onb.checking': 'Tekshirilmoqda…',

  'home.next': 'Keyingi contest',
  'home.startsIn': 'Boshlanishiga',
  'home.live': 'Hozir ketmoqda',
  'home.endsIn': 'Tugashiga',
  'home.noContest': 'Hali contest e’lon qilinmagan',
  'home.myRating': 'Mening ratingim',
  'home.toNext': '{1} gacha {0}',
  'home.top': 'Eng yuqori pog‘ona',
  'home.lastChange': 'Oxirgi contest',
  'home.setHandle': 'Ratingni ko‘rish uchun handle’ingizni qo‘shing',
  'home.activity': 'Do‘stlar faolligi',
  'home.noActivity': 'Oxirgi ikki haftada faollik yo‘q',
  'home.addFriends': 'Nimalar yechayotganini ko‘rish uchun do‘st qo‘shing',
  'home.pending': 'Yana {0} ta yuklanmoqda…',
  'home.solved': 'yechdi',
  'home.inContest': 'contestda',

  'contests.live': 'Hozir ketmoqda',
  'contests.upcoming': 'Yaqinlashayotgan',
  'contests.finished': 'Yaqinda tugagan',
  'contests.none': 'Hozircha bo‘sh',
  'contests.in': '{0} dan keyin',
  'contests.left': '{0} qoldi',
  'contests.standings': 'Natijalar',

  'st.title': 'Natijalar',
  'st.noFriends': 'Contestdagi o‘rinlarni solishtirish uchun do‘st qo‘shing',
  'st.nobody': 'Bu contestda do‘stlaringizdan hech kim qatnashmagan',
  'st.pick': 'Contest',
  'st.rank': '#',
  'st.who': 'Handle',
  'st.score': 'Ball',
  'st.unofficial': 'tanlovdan tashqari',
  'st.refresh': 'Yangilash',

  'fr.title': 'Do‘stlar',
  'fr.add': 'Qo‘shish',
  'fr.placeholder': 'Handle’lar, bo‘sh joy bilan',
  'fr.empty': 'Hali do‘st yo‘q. Kuzatadigan odamlaringiz handle’ini qo‘shing.',
  'fr.count': '{0} / {1}',
  'fr.added': 'Qo‘shildi: {0}',
  'fr.already': 'Allaqachon bor: {0}',
  'fr.over': 'Limitdan oshdi: {0}',
  'fr.remove': 'O‘chirish',
  'fr.compare': 'Solishtirish',
  'fr.online': '{0} oldin onlayn',

  'me.title': 'Men',
  'me.handle': 'Mening handle’im',
  'me.change': 'O‘zgartirish',
  'me.profile': 'Profilimni ochish',
  'me.settings': 'Sozlamalar',
  'me.language': 'Til',
  'me.theme': 'Mavzu',
  'me.theme.dark': 'Qorong‘i',
  'me.theme.light': 'Yorug‘',
  'me.theme.auto': 'Telegram',
  'me.effects': 'Effektlar va animatsiya',
  'me.effectsHint': 'Sekin telefonlarda o‘chiring',
  'me.home': 'Bosh ekranga qo‘shish',
  'me.homeHint': 'cpstands’ni ilova kabi oching',
  'me.bot': 'Botni ochish',
  'me.donate': 'cpstands’ni qo‘llab-quvvatlash',
  'me.donateHint': 'Telegram Stars bilan ixtiyoriy sovg‘a',
  'me.about': 'cpstands · Telegram’da Codeforces',

  'pr.rating': 'Rating',
  'pr.max': 'Maks',
  'pr.solved': 'Yechilgan',
  'pr.contests': 'Contestlar',
  'pr.best': 'Eng yaxshi o‘rin',
  'pr.streak': 'Kunlik seriya',
  'pr.history': 'Rating tarixi',
  'pr.activity': 'Faollik',
  'pr.subsYear': 'Bir yilda {0} ta yuborish',
  'pr.tags': 'Kuchli mavzular',
  'pr.difficulty': 'Qiyinlik bo‘yicha',
  'pr.verdicts': 'Verdiktlar',
  'pr.languages': 'Tillar',
  'pr.recent': 'Oxirgi yuborishlar',
  'pr.follow': 'Do‘stlarga qo‘shish',
  'pr.following': 'Do‘stlarda',
  'pr.compare': 'Solishtirish',

  'cmp.title': 'Solishtirish',
  'cmp.placeholder': 'Handle qo‘shing',
  'cmp.empty': 'Solishtirish uchun ikki yoki undan ko‘p handle qo‘shing',
  'cmp.h2h': 'Yuzma-yuz',
  'cmp.noCommon': 'Umumiy contest yo‘q',
  'cmp.max': 'Ko‘pi bilan 6 ta',
  'cmp.wins': 'eng yaxshi o‘rin',

  'share': 'Ulashish',
  'share.story': 'Story',
  'share.profile': '{0} Codeforces’da: {1}',
  'share.compare': 'Codeforces: {0}',
  'more': 'Yana ko‘rsatish',
  'less': 'Kamroq',
  'cmp.contest': 'Contest',
  'unit.d': 'kun',
  'unit.h': 'soat',
  'unit.m': 'daq',
  'unit.s': 'son',
  'retry': 'Qayta urinish',
  'unrated': 'reytingsiz',
  'back': 'Orqaga',

  'error.NOT_FOUND': 'Codeforces’da bunday handle yo‘q',
  'error.BAD_HANDLE': 'Bu to‘g‘ri handle emas',
  'error.CF_DOWN': 'Codeforces hozir javob bermayapti. Bir daqiqadan keyin urinib ko‘ring.',
  'error.CF_BUSY': 'Codeforces band. Bir necha soniyadan keyin urinib ko‘ring.',
  'error.NO_TELEGRAM': 'Ilovani Telegram’da @cpstandsbot orqali oching.',
  'error.UNAUTHORIZED': 'Telegram sizni tasdiqlay olmadi. Ilovani qayta oching.',
  'error.NO_FRIENDS': 'Avval do‘st qo‘shing',
  'error.generic': 'Nimadir xato ketdi. Qayta urinib ko‘ring.',
}

const ru: Dict = {
  'tab.home': 'Главная',
  'tab.contests': 'Контесты',
  'tab.standings': 'Таблица',
  'tab.friends': 'Друзья',
  'tab.me': 'Я',

  'onb.title': 'Добро пожаловать в cpstands',
  'onb.lead': 'Контесты, живые таблицы и ваши друзья на Codeforces в одном месте.',
  'onb.ask': 'Какой у вас хендл на Codeforces?',
  'onb.placeholder': 'например, tourist',
  'onb.go': 'Продолжить',
  'onb.skip': 'Пока нет хендла',
  'onb.checking': 'Проверяю…',

  'home.next': 'Следующий контест',
  'home.startsIn': 'До начала',
  'home.live': 'Идёт сейчас',
  'home.endsIn': 'До конца',
  'home.noContest': 'Контесты пока не объявлены',
  'home.myRating': 'Мой рейтинг',
  'home.toNext': '{0} до {1}',
  'home.top': 'Вершина рейтинга',
  'home.lastChange': 'Последний контест',
  'home.setHandle': 'Добавьте хендл, чтобы видеть рейтинг',
  'home.activity': 'Активность друзей',
  'home.noActivity': 'За две недели активности нет',
  'home.addFriends': 'Добавьте друзей, чтобы видеть их решения',
  'home.pending': 'Загружаю ещё {0}…',
  'home.solved': 'решил',
  'home.inContest': 'на контесте',

  'contests.live': 'Идут сейчас',
  'contests.upcoming': 'Скоро',
  'contests.finished': 'Недавно завершились',
  'contests.none': 'Пока пусто',
  'contests.in': 'через {0}',
  'contests.left': 'осталось {0}',
  'contests.standings': 'Таблица',

  'st.title': 'Таблица',
  'st.noFriends': 'Добавьте друзей, чтобы сравнивать места',
  'st.nobody': 'Никто из друзей не участвовал в этом контесте',
  'st.pick': 'Контест',
  'st.rank': '#',
  'st.who': 'Хендл',
  'st.score': 'Баллы',
  'st.unofficial': 'вне конкурса',
  'st.refresh': 'Обновить',

  'fr.title': 'Друзья',
  'fr.add': 'Добавить',
  'fr.placeholder': 'Хендлы через пробел',
  'fr.empty': 'Друзей пока нет. Добавьте хендлы тех, за кем следите.',
  'fr.count': '{0} из {1}',
  'fr.added': 'Добавлено: {0}',
  'fr.already': 'Уже есть: {0}',
  'fr.over': 'Сверх лимита: {0}',
  'fr.remove': 'Удалить',
  'fr.compare': 'Сравнить',
  'fr.online': 'в сети {0} назад',

  'me.title': 'Я',
  'me.handle': 'Мой хендл',
  'me.change': 'Изменить',
  'me.profile': 'Открыть мой профиль',
  'me.settings': 'Настройки',
  'me.language': 'Язык',
  'me.theme': 'Тема',
  'me.theme.dark': 'Тёмная',
  'me.theme.light': 'Светлая',
  'me.theme.auto': 'Telegram',
  'me.effects': 'Эффекты и анимация',
  'me.effectsHint': 'Выключите на медленных телефонах',
  'me.home': 'На главный экран',
  'me.homeHint': 'Открывать cpstands как приложение',
  'me.bot': 'Открыть бота',
  'me.donate': 'Поддержать cpstands',
  'me.donateHint': 'Добровольный подарок звёздами Telegram',
  'me.about': 'cpstands · Codeforces в Telegram',

  'pr.rating': 'Рейтинг',
  'pr.max': 'Макс',
  'pr.solved': 'Решено',
  'pr.contests': 'Контесты',
  'pr.best': 'Лучшее место',
  'pr.streak': 'Дней подряд',
  'pr.history': 'История рейтинга',
  'pr.activity': 'Активность',
  'pr.subsYear': '{0} посылок за год',
  'pr.tags': 'Сильные темы',
  'pr.difficulty': 'По сложности',
  'pr.verdicts': 'Вердикты',
  'pr.languages': 'Языки',
  'pr.recent': 'Последние посылки',
  'pr.follow': 'В друзья',
  'pr.following': 'В друзьях',
  'pr.compare': 'Сравнить',

  'cmp.title': 'Сравнение',
  'cmp.placeholder': 'Добавьте хендл',
  'cmp.empty': 'Добавьте два или больше хендла',
  'cmp.h2h': 'Очные встречи',
  'cmp.noCommon': 'Общих контестов нет',
  'cmp.max': 'Не больше 6',
  'cmp.wins': 'лучшее место',

  'share': 'Поделиться',
  'share.story': 'История',
  'share.profile': '{0} на Codeforces: {1}',
  'share.compare': 'Codeforces: {0}',
  'more': 'Показать ещё',
  'less': 'Свернуть',
  'cmp.contest': 'Контест',
  'unit.d': 'дн',
  'unit.h': 'ч',
  'unit.m': 'мин',
  'unit.s': 'сек',
  'retry': 'Повторить',
  'unrated': 'без рейтинга',
  'back': 'Назад',

  'error.NOT_FOUND': 'Такого хендла нет на Codeforces',
  'error.BAD_HANDLE': 'Это не похоже на хендл',
  'error.CF_DOWN': 'Codeforces сейчас не отвечает. Попробуйте через минуту.',
  'error.CF_BUSY': 'Codeforces занят. Попробуйте через несколько секунд.',
  'error.NO_TELEGRAM': 'Откройте приложение через @cpstandsbot в Telegram.',
  'error.UNAUTHORIZED': 'Telegram не подтвердил вход. Откройте приложение заново.',
  'error.NO_FRIENDS': 'Сначала добавьте друзей',
  'error.generic': 'Что-то пошло не так. Попробуйте ещё раз.',
}

export type Lang = 'en' | 'uz' | 'ru'
export const LANGS: { code: Lang; label: string }[] = [
  { code: 'uz', label: 'O‘zbekcha' },
  { code: 'ru', label: 'Русский' },
  { code: 'en', label: 'English' },
]
const dicts: Record<Lang, Dict> = { en, uz, ru }

export function detectLang(): Lang {
  const code = (tgUser?.language_code || navigator.language || 'en').slice(0, 2)
  if (code === 'uz' || code === 'ru' || code === 'en') return code
  return code === 'kk' || code === 'ky' || code === 'tg' || code === 'be' || code === 'uk' ? 'ru' : 'en'
}

export type T = (key: Key, ...args: (string | number)[]) => string

export function translator(lang: Lang): T {
  return (key, ...args) =>
    args.reduce<string>((s, a, i) => s.replace(`{${i}}`, String(a)), dicts[lang][key] ?? en[key])
}

export function errorKey(code: string): Key {
  const key = `error.${code}` as Key
  return key in en ? key : 'error.generic'
}

const locales: Record<Lang, string> = { uz: 'uz-Latn-UZ', ru: 'ru-RU', en: 'en-GB' }

export function formatters(lang: Lang) {
  const locale = locales[lang]
  const unit = lang === 'ru' ? { d: 'д', h: 'ч', m: 'м' } : lang === 'uz' ? { d: 'k', h: 's', m: 'd' } : { d: 'd', h: 'h', m: 'm' }
  return {
    date: (unix: number, withTime = true) =>
      new Intl.DateTimeFormat(locale, {
        day: 'numeric',
        month: 'short',
        ...(withTime ? { hour: '2-digit', minute: '2-digit' } : { year: 'numeric' }),
      }).format(new Date(unix * 1000)),
    weekday: (unix: number) =>
      new Intl.DateTimeFormat(locale, { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(
        new Date(unix * 1000),
      ),
    time: (unix: number) => new Intl.DateTimeFormat(locale, { hour: '2-digit', minute: '2-digit' }).format(new Date(unix * 1000)),
    month: (unix: number) => new Intl.DateTimeFormat(locale, { month: 'short' }).format(new Date(unix * 1000)).replace('.', ''),
    number: (n: number) => new Intl.NumberFormat(locale).format(n),
    span: (seconds: number) => {
      const s = Math.max(0, Math.round(seconds))
      const d = Math.floor(s / 86400)
      const h = Math.floor((s % 86400) / 3600)
      const m = Math.floor((s % 3600) / 60)
      if (d > 0) return `${d}${unit.d} ${h}${unit.h}`
      if (h > 0) return `${h}${unit.h} ${m}${unit.m}`
      return `${m}${unit.m}`
    },
    ago: (unix: number) => {
      const s = Date.now() / 1000 - unix
      const rtf = new Intl.RelativeTimeFormat(locale, { numeric: 'auto', style: 'short' })
      if (s < 3600) return rtf.format(-Math.max(1, Math.round(s / 60)), 'minute')
      if (s < 86400) return rtf.format(-Math.round(s / 3600), 'hour')
      return rtf.format(-Math.round(s / 86400), 'day')
    },
  }
}
export type Fmt = ReturnType<typeof formatters>
