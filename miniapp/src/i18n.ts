import { tg } from './tg'

const en = {
  'tab.contests': 'Contests',
  'tab.profile': 'Profile',
  'tab.compare': 'Compare',
  'contests.live': 'Live now',
  'contests.upcoming': 'Upcoming',
  'contests.finished': 'Recently finished',
  'contests.none': 'No contests here',
  'contests.in': 'in {0}',
  'contests.left': '{0} left',
  'contests.open': 'Open',
  'profile.placeholder': 'Codeforces handle',
  'profile.search': 'Show',
  'profile.rating': 'Rating',
  'profile.max': 'Max',
  'profile.contests': 'Contests',
  'profile.solved': 'Solved',
  'profile.streak': 'Day streak',
  'profile.friends': 'Friend of',
  'profile.best': 'Best place',
  'profile.history': 'Rating history',
  'profile.activity': 'Activity, last year',
  'profile.submissionsYear': '{0} submissions in a year',
  'profile.tags': 'Strongest topics',
  'profile.difficulty': 'Solved by difficulty',
  'profile.verdicts': 'Verdicts',
  'profile.languages': 'Languages',
  'profile.recent': 'Recent submissions',
  'profile.empty': 'Type a handle to see a profile',
  'compare.placeholder': 'Add a handle',
  'compare.add': 'Add',
  'compare.empty': 'Add two or more handles to compare their ratings',
  'compare.common': 'Head to head',
  'compare.noCommon': 'These handles have no contests in common',
  'compare.max': 'Up to 6 handles',
  'error.NOT_FOUND': 'No such handle on Codeforces',
  'error.BAD_HANDLE': 'This is not a valid handle',
  'error.CF_DOWN': 'Codeforces does not answer right now. Try again in a minute.',
  'error.CF_BUSY': 'Codeforces is busy. Try again in a few seconds.',
  'error.NO_TELEGRAM': 'Open this app from the @cpstandsbot menu in Telegram.',
  'error.UNAUTHORIZED': 'Telegram could not confirm who you are. Reopen the app.',
  'error.generic': 'Something went wrong. Try again.',
  'retry': 'Try again',
  'unrated': 'unrated',
}

type Key = keyof typeof en
type Dict = Record<Key, string>

const uz: Dict = {
  'tab.contests': 'Contestlar',
  'tab.profile': 'Profil',
  'tab.compare': 'Solishtirish',
  'contests.live': 'Hozir ketmoqda',
  'contests.upcoming': 'Yaqinlashayotgan',
  'contests.finished': 'Yaqinda tugagan',
  'contests.none': 'Bu yerda contest yo\'q',
  'contests.in': '{0} dan keyin',
  'contests.left': '{0} qoldi',
  'contests.open': 'Ochish',
  'profile.placeholder': 'Codeforces handle',
  'profile.search': 'Ko\'rsatish',
  'profile.rating': 'Rating',
  'profile.max': 'Maks',
  'profile.contests': 'Contestlar',
  'profile.solved': 'Yechilgan',
  'profile.streak': 'Kunlik seriya',
  'profile.friends': 'Do\'st sifatida',
  'profile.best': 'Eng yaxshi o\'rin',
  'profile.history': 'Rating tarixi',
  'profile.activity': 'Faollik, oxirgi yil',
  'profile.submissionsYear': 'Bir yilda {0} ta yuborish',
  'profile.tags': 'Kuchli mavzular',
  'profile.difficulty': 'Qiyinlik bo\'yicha yechilgan',
  'profile.verdicts': 'Verdiktlar',
  'profile.languages': 'Tillar',
  'profile.recent': 'Oxirgi yuborishlar',
  'profile.empty': 'Profilni ko\'rish uchun handle yozing',
  'compare.placeholder': 'Handle qo\'shing',
  'compare.add': 'Qo\'shish',
  'compare.empty': 'Ratinglarni solishtirish uchun ikki yoki undan ko\'p handle qo\'shing',
  'compare.common': 'Yuzma-yuz',
  'compare.noCommon': 'Bu handle\'larning umumiy contesti yo\'q',
  'compare.max': 'Ko\'pi bilan 6 ta handle',
  'error.NOT_FOUND': 'Codeforces\'da bunday handle yo\'q',
  'error.BAD_HANDLE': 'Bu to\'g\'ri handle emas',
  'error.CF_DOWN': 'Codeforces hozir javob bermayapti. Bir daqiqadan keyin urinib ko\'ring.',
  'error.CF_BUSY': 'Codeforces band. Bir necha soniyadan keyin urinib ko\'ring.',
  'error.NO_TELEGRAM': 'Ilovani Telegram\'da @cpstandsbot menyusidan oching.',
  'error.UNAUTHORIZED': 'Telegram sizni tasdiqlay olmadi. Ilovani qayta oching.',
  'error.generic': 'Nimadir xato ketdi. Qayta urinib ko\'ring.',
  'retry': 'Qayta urinish',
  'unrated': 'reytingsiz',
}

const ru: Dict = {
  'tab.contests': 'Контесты',
  'tab.profile': 'Профиль',
  'tab.compare': 'Сравнение',
  'contests.live': 'Идут сейчас',
  'contests.upcoming': 'Скоро',
  'contests.finished': 'Недавно завершились',
  'contests.none': 'Здесь пока пусто',
  'contests.in': 'через {0}',
  'contests.left': 'осталось {0}',
  'contests.open': 'Открыть',
  'profile.placeholder': 'Хендл Codeforces',
  'profile.search': 'Показать',
  'profile.rating': 'Рейтинг',
  'profile.max': 'Макс',
  'profile.contests': 'Контесты',
  'profile.solved': 'Решено',
  'profile.streak': 'Дней подряд',
  'profile.friends': 'В друзьях у',
  'profile.best': 'Лучшее место',
  'profile.history': 'История рейтинга',
  'profile.activity': 'Активность за год',
  'profile.submissionsYear': '{0} посылок за год',
  'profile.tags': 'Сильные темы',
  'profile.difficulty': 'Решено по сложности',
  'profile.verdicts': 'Вердикты',
  'profile.languages': 'Языки',
  'profile.recent': 'Последние посылки',
  'profile.empty': 'Введите хендл, чтобы увидеть профиль',
  'compare.placeholder': 'Добавьте хендл',
  'compare.add': 'Добавить',
  'compare.empty': 'Добавьте два или больше хендла, чтобы сравнить рейтинг',
  'compare.common': 'Очные встречи',
  'compare.noCommon': 'У этих хендлов нет общих контестов',
  'compare.max': 'Не больше 6 хендлов',
  'error.NOT_FOUND': 'Такого хендла нет на Codeforces',
  'error.BAD_HANDLE': 'Это не похоже на хендл',
  'error.CF_DOWN': 'Codeforces сейчас не отвечает. Попробуйте через минуту.',
  'error.CF_BUSY': 'Codeforces занят. Попробуйте через несколько секунд.',
  'error.NO_TELEGRAM': 'Откройте приложение из меню @cpstandsbot в Telegram.',
  'error.UNAUTHORIZED': 'Telegram не подтвердил вход. Откройте приложение заново.',
  'error.generic': 'Что-то пошло не так. Попробуйте ещё раз.',
  'retry': 'Повторить',
  'unrated': 'без рейтинга',
}

const dicts: Record<string, Dict> = { en, uz, ru }

export type Lang = 'en' | 'uz' | 'ru'

export const lang: Lang = (() => {
  const code = (tg?.initDataUnsafe.user?.language_code || navigator.language || 'en').slice(0, 2)
  return (code in dicts ? code : code === 'kk' || code === 'ky' ? 'ru' : 'en') as Lang
})()

export function t(key: Key, ...args: (string | number)[]): string {
  const text = dicts[lang][key] ?? en[key]
  return args.reduce<string>((s, a, i) => s.replace(`{${i}}`, String(a)), text)
}

export function errorText(code: string): string {
  const key = `error.${code}` as Key
  return key in en ? t(key) : t('error.generic')
}

const locale = lang === 'uz' ? 'uz-Latn-UZ' : lang === 'ru' ? 'ru-RU' : 'en-GB'

export function fmtDate(unix: number, withTime = true): string {
  return new Intl.DateTimeFormat(locale, {
    day: 'numeric',
    month: 'short',
    ...(withTime ? { hour: '2-digit', minute: '2-digit' } : { year: 'numeric' }),
  }).format(new Date(unix * 1000))
}

export function fmtNumber(n: number): string {
  return new Intl.NumberFormat(locale).format(n)
}

/** "2d 4h", "3h 10m", "12m" — compact and language-neutral. */
export function fmtSpan(seconds: number): string {
  const s = Math.max(0, Math.round(seconds))
  const d = Math.floor(s / 86400)
  const h = Math.floor((s % 86400) / 3600)
  const m = Math.floor((s % 3600) / 60)
  const unit = lang === 'ru' ? { d: 'д', h: 'ч', m: 'м' } : lang === 'uz' ? { d: 'k', h: 's', m: 'd' } : { d: 'd', h: 'h', m: 'm' }
  if (d > 0) return `${d}${unit.d} ${h}${unit.h}`
  if (h > 0) return `${h}${unit.h} ${m}${unit.m}`
  return `${m}${unit.m}`
}
